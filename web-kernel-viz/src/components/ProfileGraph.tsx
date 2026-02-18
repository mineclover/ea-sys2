
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    BackgroundVariant,
    type Node,
    type Edge,
    useReactFlow,
    Panel,
    ReactFlowProvider,
    Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { CustomEdge } from './edges';
import { CustomMarkers } from './markers';
import { getLayoutedElements } from '@/utils/layout';
import { DynamicNode } from './nodes';
import { routeEdges } from '@/utils/routing';
import TraversalPanel from './TraversalPanel';
import { useProfileTopology } from '@/api/hooks';
import type { ProfileTopologyResponse, TopologyNode, TopologyEdge, I18nString } from '@/api/types';
import {
    evaluateM1Quality,
    inferM1LayerKey,
    type M1LayerKey,
    type M1QualityIssue,
    type M1QualityReport,
} from '@/config/m1Quality';
import { isM1DebugEnabled, m1DebugCountRender, m1DebugLog } from '@/lib/m1Debug';

/** Extract a specific language from an I18nString, falling back to the raw value. */
function i18nText(value: I18nString | null | undefined, lang: string): string | undefined {
    if (value == null) return undefined;
    if (typeof value === 'string') return value;
    return value[lang] ?? value['en'];
}

const nodeTypes = {
    dynamic: DynamicNode,
};
const edgeTypes = {
    custom: CustomEdge,
};

export type ProfileViewMode = 'raw' | 'summary' | 'focus';
export type ProfileFocusMode = 'core' | 'relation' | 'layer' | 'actor' | 'topic';
export type ProfileDomainScope = 'all' | 'owned' | 'bridge';
type TraversalDirection = 'outgoing' | 'incoming' | 'both';

const PROFILE_EDGE_RENDER_LIMIT_BY_MODE: Record<ProfileViewMode, number> = {
    raw: 1200,
    summary: 2200,
    focus: 1800,
};
const PROFILE_EDGE_RENDER_LIMIT_BY_LAYER: Record<M1LayerKey, Record<ProfileViewMode, number>> = {
    infra: { raw: 700, summary: 1000, focus: 850 },
    governance: { raw: 900, summary: 1400, focus: 1100 },
    decision: { raw: 850, summary: 1300, focus: 1000 },
    needs: { raw: 750, summary: 1100, focus: 900 },
    kernel: { raw: 850, summary: 1300, focus: 1000 },
    flow: { raw: 900, summary: 1400, focus: 1100 },
    unknown: PROFILE_EDGE_RENDER_LIMIT_BY_MODE,
};
const PROFILE_DAGRE_EDGE_LIMIT = 900;

interface ProfileRenderMeta {
    viewMode: ProfileViewMode;
    totalEdges: number;
    renderedEdges: number;
    truncated: boolean;
    fallbackLayout: boolean;
    relationKinds: number;
    dominantRelation: string | null;
    dominantRelationShare: number;
    crossLayerEdges: number;
    intraLayerEdges: number;
    sourceEdgeTotal: number;
    sourceEdgeRaw: number;
    sourceTruncated: boolean;
}

function focusSignalSignature(focus: ProfileTopologyResponse['focus'] | undefined) {
    if (!focus) return null;
    return {
        mode: focus.mode,
        relation: focus.relation,
        layer: focus.layer,
        actor: focus.actor,
        actor_depth: focus.actor_depth,
        topic: focus.topic,
        topic_depth: focus.topic_depth,
        selected_relations: focus.selected_relations || [],
        visible_relations: focus.visible_relations || [],
        hidden_relations: focus.hidden_relations || [],
        visibility_profile: focus.visibility_profile || {},
        topic_seeds: focus.topic_seeds || [],
        topic_matches: (focus.topic_matches || []).map((item) => ({
            name: item.name,
            score: item.score,
            coverage: item.coverage,
        })),
        topic_policy: focus.topic_policy || null,
        topic_filter_stats: focus.topic_filter_stats || null,
        relation_candidate_count: (focus.relation_candidates || []).length,
        layer_candidate_count: (focus.layer_candidates || []).length,
        actor_candidate_count: (focus.actor_candidates || []).length,
    };
}

function areStringSetsEqual(a: Set<string>, b: Set<string>): boolean {
    if (a === b) return true;
    if (a.size !== b.size) return false;
    for (const item of a) {
        if (!b.has(item)) return false;
    }
    return true;
}

function areRenderMetaEqual(a: ProfileRenderMeta | null, b: ProfileRenderMeta | null): boolean {
    if (a === b) return true;
    if (!a || !b) return false;
    return (
        a.viewMode === b.viewMode
        && a.totalEdges === b.totalEdges
        && a.renderedEdges === b.renderedEdges
        && a.truncated === b.truncated
        && a.fallbackLayout === b.fallbackLayout
        && a.relationKinds === b.relationKinds
        && a.dominantRelation === b.dominantRelation
        && a.dominantRelationShare === b.dominantRelationShare
        && a.crossLayerEdges === b.crossLayerEdges
        && a.intraLayerEdges === b.intraLayerEdges
        && a.sourceEdgeTotal === b.sourceEdgeTotal
        && a.sourceEdgeRaw === b.sourceEdgeRaw
        && a.sourceTruncated === b.sourceTruncated
    );
}

function areNodeSnapshotsEqual(a: Node[], b: Node[]): boolean {
    if (a === b) return true;
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i += 1) {
        const x = a[i];
        const y = b[i];
        if (x.id !== y.id) return false;
        if (x.type !== y.type) return false;
        if (x.position.x !== y.position.x || x.position.y !== y.position.y) return false;
        const xd = x.data as Record<string, unknown>;
        const yd = y.data as Record<string, unknown>;
        if (xd?.label !== yd?.label) return false;
        if (xd?.subLabel !== yd?.subLabel) return false;
        if (xd?.layer !== yd?.layer) return false;
    }
    return true;
}

function areEdgeSnapshotsEqual(a: Edge[], b: Edge[]): boolean {
    if (a === b) return true;
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i += 1) {
        const x = a[i];
        const y = b[i];
        if (x.id !== y.id) return false;
        if (x.source !== y.source || x.target !== y.target) return false;
        if (x.type !== y.type) return false;
        if (x.label !== y.label) return false;
        const xd = x.data as Record<string, unknown>;
        const yd = y.data as Record<string, unknown>;
        if (xd?.relation !== yd?.relation) return false;
        if (xd?.labelDetail !== yd?.labelDetail) return false;
        if (xd?.edgeType !== yd?.edgeType) return false;
    }
    return true;
}

export interface ProfileGraphQualitySignal {
    report: M1QualityReport;
    focus?: ProfileTopologyResponse['focus'];
    metrics: {
        viewMode: ProfileViewMode;
        renderedEdges: number;
        totalEdges: number;
        sourceEdges: number;
        sourceEdgesRaw: number;
        relationKinds: number;
        crossLayerEdges: number;
        intraLayerEdges: number;
        dominantRelation: string | null;
        dominantRelationShare: number;
        apiTruncated: boolean;
        uiTruncated: boolean;
        fallbackLayout: boolean;
    };
}

const DEFAULT_VISIBLE_LAYERS = ['Infra', 'Governance', 'Decision', 'Needs', 'Kernel', 'Flow'] as const;

function capProfileEdges(edges: TopologyEdge[], maxEdges: number): { edges: TopologyEdge[]; truncated: boolean } {
    if (edges.length <= maxEdges) {
        return { edges, truncated: false };
    }

    const sortKey = (a: TopologyEdge, b: TopologyEdge): number => {
        if (b.priority !== a.priority) return b.priority - a.priority;
        if (a.relation !== b.relation) return a.relation.localeCompare(b.relation);
        if (a.source !== b.source) return a.source.localeCompare(b.source);
        return a.target.localeCompare(b.target);
    };

    const byRelation = new Map<string, TopologyEdge[]>();
    for (const edge of edges) {
        const bucket = byRelation.get(edge.relation);
        if (bucket) {
            bucket.push(edge);
        } else {
            byRelation.set(edge.relation, [edge]);
        }
    }
    for (const [relation, bucket] of byRelation.entries()) {
        byRelation.set(relation, [...bucket].sort(sortKey));
    }

    const total = edges.length;
    const relations = [...byRelation.keys()].sort();
    const quota = new Map<string, number>();
    const fractions: { relation: string; fraction: number; size: number }[] = [];
    let allocated = 0;

    for (const relation of relations) {
        const size = byRelation.get(relation)?.length ?? 0;
        const exact = (size * maxEdges) / total;
        const base = Math.min(size, Math.floor(exact));
        quota.set(relation, base);
        allocated += base;
        fractions.push({ relation, fraction: exact - base, size });
    }

    if (relations.length <= maxEdges) {
        for (const relation of relations) {
            const current = quota.get(relation) ?? 0;
            if (current === 0) {
                quota.set(relation, 1);
                allocated += 1;
            }
        }
    }

    if (allocated < maxEdges) {
        let remaining = maxEdges - allocated;
        const expandable = [...fractions].sort((a, b) => {
            if (b.fraction !== a.fraction) return b.fraction - a.fraction;
            if (b.size !== a.size) return b.size - a.size;
            return a.relation.localeCompare(b.relation);
        });
        while (remaining > 0) {
            let progressed = false;
            for (const item of expandable) {
                const bucketSize = byRelation.get(item.relation)?.length ?? 0;
                const current = quota.get(item.relation) ?? 0;
                if (current >= bucketSize) continue;
                quota.set(item.relation, current + 1);
                remaining -= 1;
                progressed = true;
                if (remaining === 0) break;
            }
            if (!progressed) break;
        }
    } else if (allocated > maxEdges) {
        let over = allocated - maxEdges;
        const reducible = [...relations].sort((a, b) => {
            const qa = quota.get(a) ?? 0;
            const qb = quota.get(b) ?? 0;
            if (qb !== qa) return qb - qa;
            return a.localeCompare(b);
        });
        let idx = 0;
        while (over > 0 && reducible.length > 0) {
            const relation = reducible[idx % reducible.length];
            const current = quota.get(relation) ?? 0;
            if (current > 0) {
                quota.set(relation, current - 1);
                over -= 1;
            }
            idx += 1;
        }
    }

    const selected: TopologyEdge[] = [];
    const edgeKey = (edge: TopologyEdge): string => (
        `${edge.source}|${edge.target}|${edge.relation}|${edge.priority}|${edge.edge_origin || 'expanded'}|${edge.rule_count || 1}`
    );
    const selectedIds = new Set<string>();
    for (const relation of relations) {
        const take = quota.get(relation) ?? 0;
        const bucket = byRelation.get(relation) ?? [];
        for (const edge of bucket.slice(0, take)) {
            selected.push(edge);
            selectedIds.add(edgeKey(edge));
        }
    }

    if (selected.length < maxEdges) {
        const remainderPool = [...edges]
            .filter((edge) => !selectedIds.has(edgeKey(edge)))
            .sort(sortKey);
        selected.push(...remainderPool.slice(0, maxEdges - selected.length));
    }

    return { edges: selected.slice(0, maxEdges).sort(sortKey), truncated: true };
}

function applyLayerGridLayout(nodes: Node[]): Node[] {
    const byLayer = new Map<string, Node[]>();
    nodes.forEach((node) => {
        const layer = String((node.data as Record<string, unknown>)?.layer || 'Layer');
        const arr = byLayer.get(layer) || [];
        arr.push(node);
        byLayer.set(layer, arr);
    });
    const layers = [...byLayer.keys()].sort();
    const rowHeight = 170;
    const rowsPerColumn = 18;
    const layerGap = 360;
    const columnGap = 220;

    const laidOut: Node[] = [];
    layers.forEach((layer, layerIdx) => {
        const layerNodes = byLayer.get(layer) || [];
        layerNodes.forEach((node, nodeIdx) => {
            const col = Math.floor(nodeIdx / rowsPerColumn);
            const row = nodeIdx % rowsPerColumn;
            laidOut.push({
                ...node,
                targetPosition: Position.Top,
                sourcePosition: Position.Bottom,
                position: {
                    x: layerIdx * layerGap + col * columnGap,
                    y: row * rowHeight,
                },
            });
        });
    });
    return laidOut;
}

function edgeSemanticAxisLabel(axis: TopologyEdge['semantic_axis'], lang: string): string {
    const value = axis || 'other';
    if (lang === 'ko') {
        if (value === 'structure') return '구조';
        if (value === 'flow') return '흐름';
        if (value === 'causality') return '인과';
        if (value === 'dataflow') return '데이터흐름';
        if (value === 'orchestration') return '조율';
        if (value === 'registry') return '등록';
        if (value === 'availability') return '가용성';
        if (value === 'type_meta') return '타입메타';
        if (value === 'contract') return '계약';
        if (value === 'projection') return '투영';
        if (value === 'invariant') return '불변성';
        if (value === 'integration') return '통합';
        if (value === 'runtime') return '런타임';
        if (value === 'persistence') return '저장';
        if (value === 'policy') return '정책';
        if (value === 'intent') return '의도';
        if (value === 'motivation') return '동기';
        if (value === 'journey') return '여정';
        if (value === 'touchpoint') return '접점';
        return '기타';
    }
    return value;
}

function buildElements(
    topo: ProfileTopologyResponse,
    visibleLayers: Set<string>,
    crossLayerOnly: boolean,
    lang: string,
    viewMode: ProfileViewMode,
    scopeElements?: Set<string>,
    maxEdges = PROFILE_EDGE_RENDER_LIMIT_BY_MODE.raw,
) {
    // Build layer lookup
    const layerOf = new Map(topo.nodes.map((n) => [n.name, n.layer]));

    // Filter edges: visible layers + optional scope filter
    let filteredNodes = topo.nodes.filter((n) => visibleLayers.has(n.layer));
    if (scopeElements) {
        filteredNodes = filteredNodes.filter((n) => scopeElements.has(n.name));
    }
    const visibleNodeNames = new Set(filteredNodes.map((n) => n.name));

    let filteredEdges = topo.edges.filter(
        (e) => visibleNodeNames.has(e.source) && visibleNodeNames.has(e.target),
    );

    if (crossLayerOnly) {
        filteredEdges = filteredEdges.filter(
            (e) => layerOf.get(e.source) !== layerOf.get(e.target),
        );
    }

    const relationCounts = new Map<string, number>();
    let crossLayerEdges = 0;
    for (const edge of filteredEdges) {
        relationCounts.set(edge.relation, (relationCounts.get(edge.relation) ?? 0) + 1);
        if (layerOf.get(edge.source) !== layerOf.get(edge.target)) {
            crossLayerEdges += 1;
        }
    }
    let dominantRelation: string | null = null;
    let dominantRelationCount = 0;
    for (const [relation, count] of relationCounts.entries()) {
        if (count > dominantRelationCount) {
            dominantRelation = relation;
            dominantRelationCount = count;
        }
    }
    const totalEdges = filteredEdges.length;
    const intraLayerEdges = Math.max(0, totalEdges - crossLayerEdges);
    const capped = capProfileEdges(filteredEdges, maxEdges);
    filteredEdges = capped.edges;

    if (crossLayerOnly) {
        // Prune nodes to only those connected by cross-layer edges
        const connected = new Set<string>();
        for (const e of filteredEdges) {
            connected.add(e.source);
            connected.add(e.target);
        }
        const nodes: Node[] = topo.nodes
            .filter((n) => connected.has(n.name))
            .map((n) => ({
                id: n.name,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: {
                    label: (lang === 'ko' ? i18nText(n.display_name, 'ko') : undefined) || n.name,
                    description: i18nText(n.description, lang),
                    layer: n.layer,
                },
            }));

        const edges: Edge[] = filteredEdges.map((e, i) => {
            const ruleCount = e.rule_count ?? 1;
            return {
                id: `e-${e.source}-${e.target}-${e.relation}-${i}`,
                source: e.source,
                target: e.target,
                type: 'custom',
            label: viewMode !== 'raw' ? e.relation : undefined,
            data: {
                style: { connector: 'solid', strokeColor: 'var(--muted-foreground)', strokeWidth: 1.5 },
                relation: e.relation,
                priority: e.priority,
                labelDetail: viewMode !== 'raw'
                    ? `${ruleCount} edges · ${edgeSemanticAxisLabel(e.semantic_axis, lang)}`
                    : undefined,
                edgeType: 'cross_layer',
            },
            markerEnd: 'url(#directed)',
            };
        });

        const fallbackLayout = edges.length > PROFILE_DAGRE_EDGE_LIMIT;
        const baseNodes = fallbackLayout ? applyLayerGridLayout(nodes) : getLayoutedElements(nodes, edges, 'TB').nodes;
        const routed = routeEdges(baseNodes, edges);
        return {
            nodes: routed.nodes,
            edges: routed.edges,
            meta: {
                viewMode,
                totalEdges,
                renderedEdges: edges.length,
                truncated: capped.truncated,
                fallbackLayout,
                relationKinds: relationCounts.size,
                dominantRelation,
                dominantRelationShare: totalEdges > 0 ? dominantRelationCount / totalEdges : 0,
                crossLayerEdges,
                intraLayerEdges,
                sourceEdgeTotal: topo.edge_total_before_cap ?? topo.edge_count,
                sourceEdgeRaw: topo.edge_total_raw ?? topo.edge_total_before_cap ?? topo.edge_count,
                sourceTruncated: Boolean(topo.edge_truncated),
            },
        };
    }

    const nodes: Node[] = topo.nodes
        .filter((n) => visibleNodeNames.has(n.name))
        .map((n) => ({
            id: n.name,
            type: 'dynamic',
            position: { x: 0, y: 0 },
            data: { label: n.name, subLabel: i18nText(n.display_name, 'ko'), layer: n.layer },
        }));

    const edges: Edge[] = filteredEdges.map((e, i) => {
        const ruleCount = e.rule_count ?? 1;
        return {
            id: `e-${e.source}-${e.target}-${e.relation}-${i}`,
            source: e.source,
            target: e.target,
            type: 'custom',
            label: viewMode !== 'raw' ? e.relation : undefined,
            data: {
                style: { connector: 'solid', strokeColor: 'var(--muted-foreground)', strokeWidth: 1.5 },
                relation: e.relation,
                priority: e.priority,
                labelDetail: viewMode !== 'raw'
                    ? `${ruleCount} edges · ${edgeSemanticAxisLabel(e.semantic_axis, lang)}`
                    : undefined,
                edgeType: layerOf.get(e.source) !== layerOf.get(e.target) ? 'cross_layer' : 'intra_layer',
            },
            markerEnd: 'url(#directed)',
        };
    });

    const fallbackLayout = edges.length > PROFILE_DAGRE_EDGE_LIMIT;
    const baseNodes = fallbackLayout ? applyLayerGridLayout(nodes) : getLayoutedElements(nodes, edges, 'TB').nodes;
    const routed = routeEdges(baseNodes, edges);
    return {
        nodes: routed.nodes,
        edges: routed.edges,
        meta: {
            viewMode,
            totalEdges,
            renderedEdges: edges.length,
            truncated: capped.truncated,
            fallbackLayout,
            relationKinds: relationCounts.size,
            dominantRelation,
            dominantRelationShare: totalEdges > 0 ? dominantRelationCount / totalEdges : 0,
            crossLayerEdges,
            intraLayerEdges,
            sourceEdgeTotal: topo.edge_total_before_cap ?? topo.edge_count,
            sourceEdgeRaw: topo.edge_total_raw ?? topo.edge_total_before_cap ?? topo.edge_count,
            sourceTruncated: Boolean(topo.edge_truncated),
        },
    };
}

interface LayoutProfileFlowProps {
    profileName: string;
    visibleLayers: Set<string>;
    crossLayerOnly: boolean;
    lang: string;
    viewMode: ProfileViewMode;
    surfaceOnly: boolean;
    domainScope?: ProfileDomainScope;
    focusMode?: ProfileFocusMode;
    focusRelation?: string;
    focusLayer?: string;
    focusActor?: string;
    focusTopic?: string;
    focusDepth?: number;
    edgeRenderLimit?: number;
    topologyData?: ProfileTopologyResponse;
    scopeElements?: Set<string>;
    onShowDetail?: (title: string, content: ReactNode) => void;
    onNodeSelect?: (nodeName: string | null) => void;
    onQualitySignal?: (signal: ProfileGraphQualitySignal | null) => void;
}

interface NodeDesignSignals {
    inbound: number;
    outbound: number;
    neighbors: number;
    crossLayerLinks: number;
    intraLayerLinks: number;
    relationMix: Array<{ relation: string; count: number }>;
    semanticMix: Array<{ semantic: string; count: number }>;
}

function buildNodeDesignSignals(
    nodeName: string,
    nodes: TopologyNode[],
    edges: TopologyEdge[],
): NodeDesignSignals {
    const nodeLayer = new Map(nodes.map((item) => [item.name, item.layer]));
    const relationCount = new Map<string, number>();
    const semanticCount = new Map<string, number>();
    const neighbors = new Set<string>();
    let inbound = 0;
    let outbound = 0;
    let crossLayerLinks = 0;
    let intraLayerLinks = 0;

    for (const edge of edges) {
        if (edge.source !== nodeName && edge.target !== nodeName) continue;

        if (edge.source === nodeName) {
            outbound += 1;
            neighbors.add(edge.target);
        }
        if (edge.target === nodeName) {
            inbound += 1;
            neighbors.add(edge.source);
        }

        const sourceLayer = nodeLayer.get(edge.source);
        const targetLayer = nodeLayer.get(edge.target);
        if (sourceLayer && targetLayer && sourceLayer !== targetLayer) {
            crossLayerLinks += 1;
        } else {
            intraLayerLinks += 1;
        }

        relationCount.set(edge.relation, (relationCount.get(edge.relation) ?? 0) + 1);
        const semantic = edge.semantic_axis || 'other';
        semanticCount.set(semantic, (semanticCount.get(semantic) ?? 0) + 1);
    }

    const sortByCount = <T extends { count: number }>(items: T[]): T[] => {
        return items.sort((a, b) => {
            if (b.count !== a.count) return b.count - a.count;
            return JSON.stringify(a).localeCompare(JSON.stringify(b));
        });
    };

    return {
        inbound,
        outbound,
        neighbors: neighbors.size,
        crossLayerLinks,
        intraLayerLinks,
        relationMix: sortByCount(
            [...relationCount.entries()].map(([relation, count]) => ({ relation, count })),
        ),
        semanticMix: sortByCount(
            [...semanticCount.entries()].map(([semantic, count]) => ({ semantic, count })),
        ),
    };
}

function NodeDetailContent({
    node,
    lang,
    signals,
}: {
    node: TopologyNode;
    lang: string;
    signals: NodeDesignSignals;
}) {
    const tr = lang === 'ko';
    const displayName = i18nText(node.display_name, lang);
    const desc = i18nText(node.description, lang);
    return (
        <div style={{ fontSize: 12, lineHeight: 1.8 }}>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '이름' : 'Name'}</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--foreground)' }}>
                    {displayName || node.name}
                    {displayName && displayName !== node.name && (
                        <span style={{ fontWeight: 400, color: 'var(--muted-foreground)', marginLeft: 6, fontSize: 12 }}>{node.name}</span>
                    )}
                </div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '레이어' : 'Layer'}</div>
                <div>{node.layer}</div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '카테고리' : 'Category'}</div>
                <div>{node.category}</div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '커널 타입' : 'Kernel Type'}</div>
                <div>{node.kernel_type}</div>
            </div>
            {node.ownership && (
                <div style={{ marginBottom: 10 }}>
                    <div style={detailLabelStyle}>{tr ? '소유 구분' : 'Ownership'}</div>
                    <div>
                        {node.ownership}
                        {node.home_layer ? ` · home=${node.home_layer}` : ''}
                    </div>
                </div>
            )}
            {Array.isArray(node.profile_owners) && node.profile_owners.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                    <div style={detailLabelStyle}>{tr ? '프로파일 소유자' : 'Profile Owners'}</div>
                    <div style={{ color: 'var(--muted-foreground)' }}>
                        {node.profile_owners.join(', ')}
                    </div>
                </div>
            )}
            {desc && (
                <div style={{ marginBottom: 10 }}>
                    <div style={detailLabelStyle}>{tr ? '설명' : 'Description'}</div>
                    <div style={{ color: 'var(--muted-foreground)' }}>{desc}</div>
                </div>
            )}
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '구조 신호' : 'Design Signals'}</div>
                <div>
                    {tr
                        ? `입력 ${signals.inbound} · 출력 ${signals.outbound} · 이웃 ${signals.neighbors}`
                        : `in ${signals.inbound} · out ${signals.outbound} · neighbors ${signals.neighbors}`}
                </div>
                <div style={{ color: 'var(--muted-foreground)' }}>
                    {tr
                        ? `교차 ${signals.crossLayerLinks} · 내부 ${signals.intraLayerLinks}`
                        : `cross ${signals.crossLayerLinks} · intra ${signals.intraLayerLinks}`}
                </div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '관계 분포' : 'Relation Mix'}</div>
                {signals.relationMix.length === 0 && (
                    <div style={{ color: 'var(--muted-foreground)' }}>{tr ? '엣지 없음' : 'no edges'}</div>
                )}
                {signals.relationMix.slice(0, 6).map((item) => (
                    <div key={item.relation} style={{ color: 'var(--muted-foreground)' }}>
                        {`${item.relation} · ${item.count}`}
                    </div>
                ))}
                {signals.relationMix.length > 6 && (
                    <div style={{ color: 'var(--muted-foreground)' }}>
                        {tr
                            ? `...외 ${signals.relationMix.length - 6}개`
                            : `...and ${signals.relationMix.length - 6} more`}
                    </div>
                )}
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>{tr ? '의미 축' : 'Semantic Axes'}</div>
                {signals.semanticMix.length === 0 && (
                    <div style={{ color: 'var(--muted-foreground)' }}>{tr ? '엣지 없음' : 'no edges'}</div>
                )}
                {signals.semanticMix.slice(0, 6).map((item) => (
                    <div key={item.semantic} style={{ color: 'var(--muted-foreground)' }}>
                        {`${edgeSemanticAxisLabel(item.semantic, lang)} · ${item.count}`}
                    </div>
                ))}
                {signals.semanticMix.length > 6 && (
                    <div style={{ color: 'var(--muted-foreground)' }}>
                        {tr
                            ? `...외 ${signals.semanticMix.length - 6}개`
                            : `...and ${signals.semanticMix.length - 6} more`}
                    </div>
                )}
            </div>
        </div>
    );
}

const detailLabelStyle = {
    fontSize: 10, fontWeight: 700 as const, color: 'var(--muted-foreground)',
    textTransform: 'uppercase' as const, marginBottom: 2,
};

function qualityStatusLabel(status: M1QualityReport['status'], lang: string): string {
    if (lang !== 'ko') return status;
    if (status === 'critical') return 'critical(즉시 보강)';
    if (status === 'attention') return 'attention(점검 필요)';
    return 'healthy';
}

function qualityIssueMessage(issue: M1QualityIssue, lang: string): string {
    if (lang !== 'ko') return issue.message;
    if (issue.code === 'api_edge_cap') {
        return 'API 엣지 상한이 적용되어 토폴로지 복잡도가 축소되어 보일 수 있습니다.';
    }
    if (issue.code === 'ui_edge_cap') {
        return 'UI 엣지 상한이 적용되었습니다. summary/focus 또는 범위 축소로 상세 점검하세요.';
    }
    if (issue.code === 'relation_variety_low') {
        return '관계 유형 다양성이 낮습니다. 핵심 의미 축 관계를 추가해 표현력을 보강하세요.';
    }
    if (issue.code === 'dominant_relation_high') {
        return '단일 관계 집중도가 높습니다. 관계 타입을 분해해 균형을 맞추세요.';
    }
    if (issue.code === 'cross_layer_density_high') {
        return '교차 레이어 결합 비율이 높습니다. 포트/브리지 경계를 분리하세요.';
    }
    if (issue.code === 'layout_fallback') {
        return '엣지 밀도가 높아 그리드 폴백 레이아웃이 적용되었습니다.';
    }
    return issue.message;
}

const LayoutProfileFlow = ({
    profileName,
    visibleLayers,
    crossLayerOnly,
    lang,
    viewMode,
    surfaceOnly,
    domainScope = 'all',
    focusMode,
    focusRelation,
    focusLayer,
    focusActor,
    focusTopic,
    focusDepth,
    edgeRenderLimit: edgeRenderLimitProp,
    topologyData,
    scopeElements,
    onShowDetail,
    onNodeSelect,
    onQualitySignal,
}: LayoutProfileFlowProps) => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [selectedNode, setSelectedNode] = useState<string | null>(null);
    const [reachableSet, setReachableSet] = useState<Set<string>>(new Set());
    const [traversalDepth, setTraversalDepth] = useState<number>(3);
    const [traversalMaxNodes, setTraversalMaxNodes] = useState<number>(120);
    const [traversalDirection, setTraversalDirection] = useState<TraversalDirection>('outgoing');
    const [traversalRelationFilter, setTraversalRelationFilter] = useState<string>('all');
    const [blockedRelations, setBlockedRelations] = useState<string[]>([]);
    const [autoTraverse, setAutoTraverse] = useState<boolean>(true);
    const [traversalMeta, setTraversalMeta] = useState<{ traversedEdges: number; capped: boolean } | null>(null);
    const [renderMeta, setRenderMeta] = useState<ProfileRenderMeta | null>(null);
    const qualitySignalKeyRef = useRef<string>('');
    const nodesRef = useRef<Node[]>([]);
    const edgesRef = useRef<Edge[]>([]);
    const renderMetaRef = useRef<ProfileRenderMeta | null>(null);
    const m1DebugEnabled = useMemo(() => isM1DebugEnabled(), []);

    useEffect(() => {
        nodesRef.current = nodes;
    }, [nodes]);
    useEffect(() => {
        edgesRef.current = edges;
    }, [edges]);
    useEffect(() => {
        renderMetaRef.current = renderMeta;
    }, [renderMeta]);
    const layerKey = inferM1LayerKey(profileName);
    const edgeRenderLimit = edgeRenderLimitProp ?? PROFILE_EDGE_RENDER_LIMIT_BY_LAYER[layerKey][viewMode];
    const focusQueryParams = viewMode === 'focus'
        ? {
            focus: focusMode || 'core',
            focus_relation: focusMode === 'relation' ? focusRelation : undefined,
            focus_layer: focusMode === 'layer' ? focusLayer : undefined,
            focus_actor: focusMode === 'actor' ? focusActor : undefined,
            focus_topic: focusMode === 'topic' ? focusTopic : undefined,
            focus_depth: focusMode === 'actor' || focusMode === 'topic' ? focusDepth : undefined,
        }
        : {};
    const topologyQuery = useProfileTopology(profileName, {
        lang,
        view_mode: viewMode,
        surface_only: surfaceOnly,
        domain_scope: domainScope,
        max_edges: edgeRenderLimit,
        ...focusQueryParams,
        enabled: !topologyData,
    });
    const rawTopo = topologyData || topologyQuery.data;
    const isError = !topologyData && topologyQuery.isError;
    const traversalRelationOptions = useMemo(() => {
        if (!rawTopo) return [];
        const relationNames = Object.keys(rawTopo.relation_distribution || {});
        return relationNames.sort((a, b) => a.localeCompare(b));
    }, [rawTopo]);
    const traversalAdjacency = useMemo(() => {
        const outgoing = new Map<string, TopologyEdge[]>();
        const incoming = new Map<string, TopologyEdge[]>();
        if (!rawTopo) {
            return { outgoing, incoming };
        }
        for (const edge of rawTopo.edges) {
            const source = String(edge.source);
            const target = String(edge.target);
            const outBucket = outgoing.get(source);
            if (outBucket) {
                outBucket.push(edge);
            } else {
                outgoing.set(source, [edge]);
            }
            const inBucket = incoming.get(target);
            if (inBucket) {
                inBucket.push(edge);
            } else {
                incoming.set(target, [edge]);
            }
        }
        return { outgoing, incoming };
    }, [rawTopo]);
    const quality = useMemo(() => {
        if (!renderMeta) return null;
        return evaluateM1Quality({
            profileName,
            viewMode: renderMeta.viewMode,
            totalEdges: renderMeta.totalEdges,
            renderedEdges: renderMeta.renderedEdges,
            relationKinds: renderMeta.relationKinds,
            dominantRelation: renderMeta.dominantRelation,
            dominantRelationShare: renderMeta.dominantRelationShare,
            crossLayerEdges: renderMeta.crossLayerEdges,
            intraLayerEdges: renderMeta.intraLayerEdges,
            sourceTruncated: renderMeta.sourceTruncated,
            uiTruncated: renderMeta.truncated,
            fallbackLayout: renderMeta.fallbackLayout,
        });
    }, [renderMeta, profileName]);

    useEffect(() => {
        if (!onQualitySignal) return;
        if (!quality || !renderMeta) {
            if (qualitySignalKeyRef.current !== 'none') {
                qualitySignalKeyRef.current = 'none';
                onQualitySignal(null);
            }
            return;
        }
        const nextSignal: ProfileGraphQualitySignal = {
            report: quality,
            focus: rawTopo?.focus,
            metrics: {
                viewMode: renderMeta.viewMode,
                renderedEdges: renderMeta.renderedEdges,
                totalEdges: renderMeta.totalEdges,
                sourceEdges: renderMeta.sourceEdgeTotal,
                sourceEdgesRaw: renderMeta.sourceEdgeRaw,
                relationKinds: renderMeta.relationKinds,
                crossLayerEdges: renderMeta.crossLayerEdges,
                intraLayerEdges: renderMeta.intraLayerEdges,
                dominantRelation: renderMeta.dominantRelation,
                dominantRelationShare: renderMeta.dominantRelationShare,
                apiTruncated: renderMeta.sourceTruncated,
                uiTruncated: renderMeta.truncated,
                fallbackLayout: renderMeta.fallbackLayout,
            },
        };
        const nextKey = JSON.stringify({
            report: {
                layerKey: nextSignal.report.layerKey,
                status: nextSignal.report.status,
                issues: nextSignal.report.issues,
                thresholds: nextSignal.report.thresholds,
            },
            focus: focusSignalSignature(nextSignal.focus),
            metrics: nextSignal.metrics,
        });
        if (qualitySignalKeyRef.current === nextKey) return;
        qualitySignalKeyRef.current = nextKey;
        onQualitySignal(nextSignal);
    }, [onQualitySignal, quality, rawTopo, renderMeta]);

    useEffect(() => {
        if (traversalRelationFilter !== 'all' && !traversalRelationOptions.includes(traversalRelationFilter)) {
            setTraversalRelationFilter('all');
        }
        setBlockedRelations((prev) => {
            const next = prev.filter((name) => traversalRelationOptions.includes(name));
            if (next.length === prev.length && next.every((name, index) => name === prev[index])) {
                return prev;
            }
            return next;
        });
    }, [traversalRelationFilter, traversalRelationOptions]);

    // Reset selection when profile changes
    useEffect(() => {
        setSelectedNode((prev) => (prev === null ? prev : null));
        setReachableSet((prev) => (prev.size === 0 ? prev : new Set()));
        setTraversalMeta((prev) => (prev === null ? prev : null));
    }, [profileName]);

    // Build ReactFlow elements when raw data or view options change
    useEffect(() => {
        if (!rawTopo) return;
        const result = buildElements(
            rawTopo,
            visibleLayers,
            crossLayerOnly,
            lang,
            viewMode,
            scopeElements,
            edgeRenderLimit,
        );
        const { nodes: n, edges: e } = result;
        const nodesChanged = !areNodeSnapshotsEqual(nodesRef.current, n);
        const edgesChanged = !areEdgeSnapshotsEqual(edgesRef.current, e);
        const metaChanged = !areRenderMetaEqual(renderMetaRef.current, result.meta);
        if (!nodesChanged && !edgesChanged && !metaChanged) {
            if (m1DebugEnabled) {
                m1DebugLog('profile-graph.build.skip', {
                    profileName,
                    viewMode,
                    source: rawTopo.profile,
                    nodeCount: n.length,
                    edgeCount: e.length,
                });
            }
            return;
        }
        if (nodesChanged) setNodes(n);
        if (edgesChanged) setEdges(e);
        if (metaChanged) setRenderMeta(result.meta);
        if (m1DebugEnabled) {
            m1DebugCountRender('ProfileGraph.build.apply');
            m1DebugLog('profile-graph.build.apply', {
                profileName,
                viewMode,
                nodesChanged,
                edgesChanged,
                metaChanged,
                nodeCount: n.length,
                edgeCount: e.length,
                renderedEdges: result.meta.renderedEdges,
                totalEdges: result.meta.totalEdges,
            });
        }
        if (nodesChanged || edgesChanged) {
            window.requestAnimationFrame(() => fitView());
        }
    }, [rawTopo, visibleLayers, crossLayerOnly, lang, viewMode, scopeElements, edgeRenderLimit, setNodes, setEdges, fitView, m1DebugEnabled, profileName]);

    // Fit view on initial load
    useEffect(() => {
        if (nodes.length > 0) {
            window.requestAnimationFrame(() => fitView());
        }
    }, [nodes.length, fitView]);

    // Apply highlight when reachableSet changes
    useEffect(() => {
        if (!rawTopo) return;

        setNodes((prev) =>
            {
                let changed = false;
                const next = prev.map((n) => {
                    const highlighted = reachableSet.has(n.id);
                    const prevHighlighted = !!(n.data as Record<string, unknown> | undefined)?.highlighted;
                    if (highlighted === prevHighlighted) return n;
                    changed = true;
                    return {
                        ...n,
                        data: { ...n.data, highlighted },
                    };
                });
                return changed ? next : prev;
            },
        );

        setEdges((prev) =>
            {
                let changed = false;
                const next = prev.map((e) => {
                    const highlighted = reachableSet.has(e.source) && reachableSet.has(e.target);
                    const prevHighlighted = !!(e.data as Record<string, unknown> | undefined)?.highlighted;
                    if (highlighted === prevHighlighted) return e;
                    changed = true;
                    return {
                        ...e,
                        data: {
                            ...e.data,
                            highlighted,
                        },
                    };
                });
                return changed ? next : prev;
            },
        );
    }, [reachableSet, rawTopo, setNodes, setEdges]);

    const runTraversal = useCallback((seedNode?: string) => {
        const root = seedNode || selectedNode;
        if (!rawTopo || !root) {
            setReachableSet((prev) => (prev.size === 0 ? prev : new Set()));
            setTraversalMeta((prev) => (prev === null ? prev : null));
            return;
        }

        const blocked = new Set(blockedRelations);
        const relationFilter = traversalRelationFilter !== 'all'
            ? traversalRelationFilter
            : null;

        const visited = new Set<string>([root]);
        const queue: Array<{ node: string; depth: number }> = [{ node: root, depth: 0 }];
        let traversedEdges = 0;
        let capped = false;

        while (queue.length > 0 && !capped) {
            const current = queue.shift();
            if (!current) break;
            if (current.depth >= traversalDepth) continue;

            const candidates: TopologyEdge[] = [];
            if (traversalDirection === 'outgoing' || traversalDirection === 'both') {
                candidates.push(...(traversalAdjacency.outgoing.get(current.node) || []));
            }
            if (traversalDirection === 'incoming' || traversalDirection === 'both') {
                candidates.push(...(traversalAdjacency.incoming.get(current.node) || []));
            }

            for (const edge of candidates) {
                const relation = String(edge.relation);
                if (relationFilter && relation !== relationFilter) continue;
                if (blocked.has(relation)) continue;

                let nextNode: string | null = null;
                if (edge.source === current.node && (traversalDirection === 'outgoing' || traversalDirection === 'both')) {
                    nextNode = String(edge.target);
                } else if (edge.target === current.node && (traversalDirection === 'incoming' || traversalDirection === 'both')) {
                    nextNode = String(edge.source);
                }
                if (!nextNode) continue;

                traversedEdges += 1;
                if (visited.has(nextNode)) continue;
                if (visited.size >= traversalMaxNodes) {
                    capped = true;
                    break;
                }
                visited.add(nextNode);
                queue.push({ node: nextNode, depth: current.depth + 1 });
            }
        }

        setReachableSet((prev) => (areStringSetsEqual(prev, visited) ? prev : visited));
        setTraversalMeta((prev) => {
            if (prev && prev.traversedEdges === traversedEdges && prev.capped === capped) {
                return prev;
            }
            return { traversedEdges, capped };
        });
    }, [
        blockedRelations,
        rawTopo,
        selectedNode,
        traversalAdjacency.incoming,
        traversalAdjacency.outgoing,
        traversalDepth,
        traversalDirection,
        traversalMaxNodes,
        traversalRelationFilter,
    ]);

    useEffect(() => {
        if (!selectedNode || !autoTraverse) return;
        runTraversal(selectedNode);
    }, [
        autoTraverse,
        selectedNode,
        runTraversal,
    ]);

    const onNodeClick = useCallback(
        (_: React.MouseEvent, node: Node) => {
            setSelectedNode(node.id);
            onNodeSelect?.(node.id);

            // Show detail in slide-over
            if (onShowDetail && rawTopo) {
                const topoNode = rawTopo.nodes.find((n) => n.name === node.id);
                if (topoNode) {
                    const designSignals = buildNodeDesignSignals(node.id, rawTopo.nodes, rawTopo.edges);
                    const reachEdges = rawTopo.edges.filter(
                        (e) => e.source === node.id || e.target === node.id,
                    );
                            onShowDetail(
                                node.id,
                                <div>
                                    <NodeDetailContent node={topoNode} lang={lang} signals={designSignals} />
                                    <div style={{ marginTop: 16 }}>
                                        <div style={detailLabelStyle}>
                                            {lang === 'ko'
                                                ? `연결 (${reachEdges.length})`
                                                : `Connections (${reachEdges.length})`}
                                        </div>
                                {reachEdges.slice(0, 20).map((e, i) => (
                                    <div key={i} style={{
                                        fontSize: 11, padding: '3px 0',
                                        color: 'var(--foreground)', borderBottom: '1px solid var(--accent)',
                                    }}>
                                        {e.source === node.id
                                            ? <span>→ <strong>{e.target}</strong> <span style={{ color: 'var(--muted-foreground)' }}>({e.relation}{e.rule_count && e.rule_count > 1 ? ` · edges=${e.rule_count}` : ''} · {edgeSemanticAxisLabel(e.semantic_axis, lang)}{e.semantic_intent ? `/${e.semantic_intent}` : ''})</span></span>
                                            : <span>← <strong>{e.source}</strong> <span style={{ color: 'var(--muted-foreground)' }}>({e.relation}{e.rule_count && e.rule_count > 1 ? ` · edges=${e.rule_count}` : ''} · {edgeSemanticAxisLabel(e.semantic_axis, lang)}{e.semantic_intent ? `/${e.semantic_intent}` : ''})</span></span>
                                        }
                                    </div>
                                ))}
                                {reachEdges.length > 20 && (
                                    <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 4 }}>
                                        ...and {reachEdges.length - 20} more
                                    </div>
                                )}
                            </div>
                        </div>,
                    );
                }
            }

            if (autoTraverse) {
                runTraversal(node.id);
            } else {
                setReachableSet((prev) => {
                    const next = new Set([node.id]);
                    return areStringSetsEqual(prev, next) ? prev : next;
                });
                setTraversalMeta((prev) => (prev === null ? prev : null));
            }
        },
        [autoTraverse, lang, onNodeSelect, onShowDetail, rawTopo, runTraversal],
    );

    const onClear = useCallback(() => {
        setSelectedNode((prev) => (prev === null ? prev : null));
        setReachableSet((prev) => (prev.size === 0 ? prev : new Set()));
        setTraversalMeta((prev) => (prev === null ? prev : null));
        onNodeSelect?.(null);
    }, [onNodeSelect]);

    const onLayout = useCallback(
        (direction: string) => {
            const layouted = getLayoutedElements(nodes, edges, direction);
            const routed = routeEdges(layouted.nodes, layouted.edges);
            setNodes([...routed.nodes]);
            setEdges([...routed.edges]);
            window.requestAnimationFrame(() => fitView());
        },
        [nodes, edges, setNodes, setEdges, fitView],
    );

    if (isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--secondary)', fontSize: 12, color: 'var(--muted-foreground)',
                }}>
                    {lang === 'ko'
                        ? '프로파일 토폴로지를 불러올 수 없습니다. API 서버 상태를 확인해주세요.'
                        : 'Unable to load profile topology — API server may be unavailable.'}
                </div>
            </div>
        );
    }

    return (
        <div style={{ width: '100%', height: '100%' }}>
            <CustomMarkers />
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                <Panel position="top-right">
                    <button onClick={() => onLayout('TB')} style={{ marginRight: 10 }}>
                        {lang === 'ko' ? '세로 레이아웃' : 'Vertical Layout'}
                    </button>
                    <button onClick={() => onLayout('LR')}>{lang === 'ko' ? '가로 레이아웃' : 'Horizontal Layout'}</button>
                </Panel>
                {renderMeta && (
                    <Panel position="top-left">
                        <div style={{
                            padding: '8px 10px',
                            border: '1px solid var(--border)',
                            borderRadius: 6,
                            background: 'var(--card)',
                            color: 'var(--muted-foreground)',
                            fontSize: 11,
                            lineHeight: 1.5,
                            display: 'grid',
                            gap: 3,
                        }}>
                            {quality && (
                                <div style={{
                                    fontWeight: 700,
                                    color: quality.status === 'critical'
                                        ? 'var(--status-error-text)'
                                        : quality.status === 'attention'
                                            ? 'var(--status-warning-text)'
                                            : 'var(--status-success-text)',
                                }}>
                                    {`${lang === 'ko' ? '품질' : 'quality'} ${qualityStatusLabel(quality.status, lang)} · ${lang === 'ko' ? '레이어' : 'layer'} ${quality.layerKey}`}
                                </div>
                            )}
                            <div>
                                {`M1 ${renderMeta.viewMode} · ${lang === 'ko' ? '렌더' : 'render'} ${renderMeta.renderedEdges}/${renderMeta.totalEdges} ${lang === 'ko' ? '엣지' : 'edges'}`}
                                {renderMeta.truncated ? (lang === 'ko' ? ' (UI 상한)' : ' (ui cap)') : ''}
                                {renderMeta.fallbackLayout ? (lang === 'ko' ? ' (그리드 레이아웃)' : ' (grid layout)') : ''}
                            </div>
                            <div>
                                {`${lang === 'ko' ? '소스' : 'source'} ${renderMeta.sourceEdgeTotal}`}
                                {renderMeta.sourceTruncated ? `/${renderMeta.sourceEdgeRaw} ${lang === 'ko' ? '(API 상한)' : '(api cap)'}` : ''}
                            </div>
                            <div>
                                {`${lang === 'ko' ? '관계' : 'relations'} ${renderMeta.relationKinds} · cross ${renderMeta.crossLayerEdges} · intra ${renderMeta.intraLayerEdges}`}
                            </div>
                            {rawTopo?.domain_view && (
                                <div>
                                    {`${lang === 'ko' ? '도메인' : 'domain'} ${rawTopo.domain_view.scope} · owned ${rawTopo.domain_view.stats.owned_edges} · bridge ${rawTopo.domain_view.stats.bridge_edges}`}
                                </div>
                            )}
                            {rawTopo?.surface_filter && (
                                <div>
                                    {`${lang === 'ko' ? '표층 필터' : 'surface filter'} ${rawTopo.surface_filter.applied ? (lang === 'ko' ? '적용' : 'on') : (lang === 'ko' ? '해제' : 'off')} · ${lang === 'ko' ? '노출' : 'visible'} ${rawTopo.surface_filter.visible_relations.length}`}
                                </div>
                            )}
                            {rawTopo?.composition && (
                                <div>
                                    {`${lang === 'ko' ? '합성' : 'composition'} ${rawTopo.composition.source_profile_count} ${lang === 'ko' ? '프로파일' : 'profiles'}`}
                                    {rawTopo.composition.missing_profiles.length > 0
                                        ? ` · ${lang === 'ko' ? '누락' : 'missing'} ${rawTopo.composition.missing_profiles.length}`
                                        : ''}
                                </div>
                            )}
                            {renderMeta.dominantRelation && (
                                <div>
                                    {`${lang === 'ko' ? '집중' : 'dominant'} ${renderMeta.dominantRelation} ${(renderMeta.dominantRelationShare * 100).toFixed(1)}%`}
                                </div>
                            )}
                            {quality && (
                                <div>
                                    {`${lang === 'ko' ? '가드레일' : 'guardrail'} dominant<=${(quality.thresholds.maxDominantRelationShare * 100).toFixed(1)}% · rel>=${quality.thresholds.minRelationKinds} · cross<=${(quality.thresholds.maxCrossLayerShare * 100).toFixed(1)}%`}
                                </div>
                            )}
                            {quality && quality.issues.length > 0 && quality.issues.slice(0, 3).map((issue) => (
                                <div
                                    key={issue.code}
                                    style={{
                                        color: issue.severity === 'critical'
                                            ? 'var(--status-error-text)'
                                            : 'var(--status-warning-text)',
                                    }}
                                >
                                    {`${issue.severity}: ${qualityIssueMessage(issue, lang)}`}
                                </div>
                            ))}
                        </div>
                    </Panel>
                )}
                <TraversalPanel
                    lang={lang}
                    selectedNode={selectedNode}
                    reachableCount={reachableSet.size}
                    relationOptions={traversalRelationOptions}
                    relationFilter={traversalRelationFilter}
                    blockedRelations={blockedRelations}
                    direction={traversalDirection}
                    depth={traversalDepth}
                    maxNodes={traversalMaxNodes}
                    autoTraverse={autoTraverse}
                    traversalMeta={traversalMeta}
                    onRelationFilterChange={setTraversalRelationFilter}
                    onBlockedRelationsChange={setBlockedRelations}
                    onDirectionChange={setTraversalDirection}
                    onDepthChange={setTraversalDepth}
                    onMaxNodesChange={setTraversalMaxNodes}
                    onAutoTraverseChange={setAutoTraverse}
                    onRunTraversal={() => runTraversal()}
                    onClear={onClear}
                />
            </ReactFlow>
        </div>
    );
};

interface ProfileGraphProps {
    profileName: string;
    visibleLayers?: Set<string>;
    crossLayerOnly?: boolean;
    viewMode?: ProfileViewMode;
    surfaceOnly?: boolean;
    domainScope?: ProfileDomainScope;
    edgeRenderLimit?: number;
    focusMode?: ProfileFocusMode;
    focusRelation?: string;
    focusLayer?: string;
    focusActor?: string;
    focusTopic?: string;
    focusDepth?: number;
    lang?: string;
    topologyData?: ProfileTopologyResponse;
    scopeElements?: Set<string>;
    onShowDetail?: (title: string, content: ReactNode) => void;
    onNodeSelect?: (nodeName: string | null) => void;
    onQualitySignal?: (signal: ProfileGraphQualitySignal | null) => void;
}

export default function ProfileGraph({
    profileName,
    visibleLayers,
    crossLayerOnly,
    viewMode = 'raw',
    surfaceOnly = false,
    domainScope = 'all',
    edgeRenderLimit,
    focusMode = 'core',
    focusRelation,
    focusLayer,
    focusActor,
    focusTopic,
    focusDepth,
    lang = 'en',
    topologyData,
    scopeElements,
    onShowDetail,
    onNodeSelect,
    onQualitySignal,
}: ProfileGraphProps) {
    // Avoid recreating the default layer set on every render.
    const defaultLayers = useMemo(() => new Set<string>(DEFAULT_VISIBLE_LAYERS), []);
    const layers = visibleLayers || defaultLayers;
    return (
        <ReactFlowProvider>
            <LayoutProfileFlow
                profileName={profileName}
                visibleLayers={layers}
                crossLayerOnly={crossLayerOnly ?? false}
                lang={lang}
                viewMode={viewMode}
                surfaceOnly={surfaceOnly}
                domainScope={domainScope}
                edgeRenderLimit={edgeRenderLimit}
                focusMode={focusMode}
                focusRelation={focusRelation}
                focusLayer={focusLayer}
                focusActor={focusActor}
                focusTopic={focusTopic}
                focusDepth={focusDepth}
                topologyData={topologyData}
                scopeElements={scopeElements}
                onShowDetail={onShowDetail}
                onNodeSelect={onNodeSelect}
                onQualitySignal={onQualitySignal}
            />
        </ReactFlowProvider>
    );
}
