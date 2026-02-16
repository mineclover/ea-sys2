
import { useCallback, useEffect, useMemo, useState } from 'react';
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
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { CustomEdge } from '../edges';
import { CustomMarkers } from '../markers';
import { DynamicNode } from '../nodes';
import { getLayoutedElements } from '@/utils/layout';
import { routeEdges } from '@/utils/routing';
import { useLayerSchema } from '@/api/hooks';
import type {
    LayerSchemaResponse,
    LayerSchemaElement,
    LayerSchemaRule,
    I18nString,
} from '@/api/types';
import type { MarkerType } from '@/types/diagram';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

const nodeTypes = { dynamic: DynamicNode };
const edgeTypes = { custom: CustomEdge };

// --- Relation style mapping (kernel_relation based) ---

interface RelationStyle {
    connector?: string;
    endMarker?: MarkerType;
    startMarker?: MarkerType;
}

const RELATION_STYLES: Record<string, RelationStyle> = {
    ownership:      { endMarker: 'composition' },
    membership:     { endMarker: 'composition' },
    specialization: { connector: 'solid', endMarker: 'directed' },
    feature_typing: { connector: 'dashed', endMarker: 'none' },
    association:    { connector: 'solid' },
    connector:      { connector: 'solid' },
    redefinition:   { connector: 'dashed', startMarker: 'none', endMarker: 'none' },
    subsetting:     { connector: 'dashed' },
    flow:           { connector: 'solid', endMarker: 'directed' },
    succession:     { connector: 'dashed', endMarker: 'directed' },
    triggering:     { connector: 'dashed', endMarker: 'directed' },
    guarding:       { connector: 'dashed', startMarker: 'none' },
    transition:     { connector: 'solid', endMarker: 'directed' },
};

const getMarkerUrl = (m?: MarkerType) => {
    if (!m || m === 'none') return undefined;
    return `url(#${m})`;
};

// --- Resolve kernel_relation for a profile relation name ---

function resolveKernelRelation(
    schema: LayerSchemaResponse,
    relationName: string,
): string | undefined {
    const rel = schema.relations.find((r) => r.name === relationName);
    return rel?.kernel_relation;
}

// --- Build ReactFlow elements from M2 schema data ---

interface NodeLookup {
    byName: Map<string, LayerSchemaElement & { layer: string }>;
    ruleByIdx: Map<string, LayerSchemaRule>;
}

interface BuildOptions {
    edgeMode: 'summary' | 'rules';
    relationFilter: string;
    crossLayerOnly: boolean;
    showEdgeLabels: boolean;
    compactNodes: boolean;
}

function buildElements(
    schema: LayerSchemaResponse,
    lang: string,
    options: BuildOptions,
): { nodes: Node[]; edges: Edge[]; lookup: NodeLookup } {
    const byName = new Map<string, LayerSchemaElement & { layer: string }>();
    const ruleByIdx = new Map<string, LayerSchemaRule>();
    const layerOf = new Map<string, string>();

    // Build element name set for filtering rules to concrete elements
    const elementNames = new Set<string>();
    const rfNodes: Node[] = [];

    for (const group of schema.elements_by_layer) {
        for (const elem of group.elements) {
            elementNames.add(elem.name);
            byName.set(elem.name, { ...elem, layer: group.layer });
            layerOf.set(elem.name, group.layer);
            const label = i18n(elem.display_name, lang) || elem.name;
            rfNodes.push({
                id: elem.name,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: {
                    label,
                    description: options.compactNodes ? undefined : i18n(elem.description, lang),
                    layer: group.layer,
                },
            });
        }
    }

    // Build edges from rules — only rules that reference concrete element names
    const rfEdges: Edge[] = [];
    let edgeIdx = 0;
    const summaryRules = new Map<string, LayerSchemaRule>();

    const considerSummaryRule = (rule: LayerSchemaRule) => {
        const current = summaryRules.get(rule.relation);
        if (!current) {
            summaryRules.set(rule.relation, rule);
            return;
        }
        if (rule.priority > current.priority) {
            summaryRules.set(rule.relation, rule);
            return;
        }
        if (rule.priority === current.priority) {
            const currentKey = `${current.source}->${current.target}`;
            const nextKey = `${rule.source}->${rule.target}`;
            if (nextKey < currentKey) {
                summaryRules.set(rule.relation, rule);
            }
        }
    };

    for (const rule of schema.rules) {
        if (!rule.valid) continue;
        if (options.relationFilter !== 'all' && rule.relation !== options.relationFilter) continue;
        // Skip pattern-based rules (starting with @ or #)
        if (rule.source.startsWith('@') || rule.source.startsWith('#')) continue;
        if (rule.target.startsWith('@') || rule.target.startsWith('#')) continue;
        // Both source and target must be known elements
        if (!elementNames.has(rule.source) || !elementNames.has(rule.target)) continue;
        if (options.crossLayerOnly && layerOf.get(rule.source) === layerOf.get(rule.target)) continue;
        considerSummaryRule(rule);
        if (options.edgeMode === 'summary') continue;

        const eid = `e-${edgeIdx++}-${rule.source}-${rule.target}`;
        ruleByIdx.set(eid, rule);

        const kernelRel = resolveKernelRelation(schema, rule.relation);
        const style = RELATION_STYLES[kernelRel || rule.relation] || { connector: 'solid', endMarker: 'directed' };

        rfEdges.push({
            id: eid,
            source: rule.source,
            target: rule.target,
            type: 'custom',
            data: { style: { ...style, strokeColor: '#555' } },
            markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
            markerStart: getMarkerUrl(style.startMarker),
            label: options.showEdgeLabels ? rule.relation : undefined,
        });
    }

    if (options.edgeMode === 'summary') {
        for (const rule of summaryRules.values()) {
            const eid = `e-summary-${rule.relation}`;
            ruleByIdx.set(eid, rule);
            const kernelRel = resolveKernelRelation(schema, rule.relation);
            const style = RELATION_STYLES[kernelRel || rule.relation] || { connector: 'solid', endMarker: 'directed' };

            rfEdges.push({
                id: eid,
                source: rule.source,
                target: rule.target,
                type: 'custom',
                data: { style: { ...style, strokeColor: '#555' } },
                markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
                markerStart: getMarkerUrl(style.startMarker),
                label: options.showEdgeLabels ? rule.relation : undefined,
            });
        }
    }

    const layouted = getLayoutedElements(rfNodes, rfEdges, 'TB');
    const routed = routeEdges(layouted.nodes, layouted.edges);
    return { nodes: routed.nodes, edges: routed.edges, lookup: { byName, ruleByIdx } };
}

// --- Info panel ---

type InfoData =
    | { kind: 'node'; elem: LayerSchemaElement & { layer: string } }
    | { kind: 'edge'; rule: LayerSchemaRule };

const lbl = { fontSize: 10, fontWeight: 700 as const, color: 'var(--text-muted)', textTransform: 'uppercase' as const };

function InfoPanel({ info, lang, onClose }: { info: InfoData; lang: string; onClose: () => void }) {
    const isNode = info.kind === 'node';
    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
                padding: '12px 16px', boxShadow: '0 4px 6px -1px var(--shadow-lg)',
                minWidth: 220, maxWidth: 340, fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={lbl}>{isNode ? 'Element' : 'Rule'}</div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-muted)', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                {isNode ? (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                            {i18n(info.elem.display_name, lang) || info.elem.name}
                            {info.elem.display_name && (
                                <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6, fontSize: 11 }}>{info.elem.name}</span>
                            )}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>
                            {info.elem.layer}
                            {info.elem.category ? ` \u00b7 ${info.elem.category}` : ''}
                        </div>
                        <div style={{ marginTop: 4 }}>
                            <span style={{
                                padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                background: '#ede9fe', color: '#6d28d9', borderRadius: 3,
                            }}>{info.elem.kernel_type}</span>
                        </div>
                        {i18n(info.elem.description, lang) && (
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6, lineHeight: 1.5 }}>
                                {i18n(info.elem.description, lang)}
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                            {info.rule.source} <span style={{ color: 'var(--text-muted)' }}>{'\u2192'}</span> {info.rule.target}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>
                            Relation: <strong>{info.rule.relation}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            Priority {info.rule.priority}
                        </div>
                        {info.rule.notes && (
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 6, lineHeight: 1.5 }}>
                                {info.rule.notes}
                            </div>
                        )}
                    </>
                )}
            </div>
        </Panel>
    );
}

// --- Inner graph component (needs ReactFlow context) ---

interface InnerProps {
    layerKey: string;
    lang: string;
}

function InnerGraph({ layerKey, lang }: InnerProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [info, setInfo] = useState<InfoData | null>(null);
    const [edgeMode, setEdgeMode] = useState<'summary' | 'rules'>('summary');
    const [relationFilter, setRelationFilter] = useState('all');
    const [crossLayerOnly, setCrossLayerOnly] = useState(false);
    const [showEdgeLabels, setShowEdgeLabels] = useState(false);
    const [compactNodes, setCompactNodes] = useState(true);

    const { data: rawSchema, isError, refetch } = useLayerSchema(layerKey, { lang });
    const relationOptions = useMemo(
        () => rawSchema ? [...rawSchema.relations.map((r) => r.name)].sort() : [],
        [rawSchema],
    );
    const buildOptions = useMemo(
        () => ({
            edgeMode,
            relationFilter,
            crossLayerOnly,
            showEdgeLabels,
            compactNodes,
        }),
        [edgeMode, relationFilter, crossLayerOnly, showEdgeLabels, compactNodes],
    );

    const { lookup, stats } = useMemo(() => {
        if (!rawSchema) return { lookup: null, stats: null };
        const { lookup: lk, edges: e } = buildElements(rawSchema, lang, buildOptions);
        return {
            lookup: lk,
            stats: { nodes: rawSchema.element_count, edges: e.length, rules: rawSchema.rule_count },
        };
    }, [rawSchema, lang, buildOptions]);

    // Build ReactFlow elements when API data or lang changes
    useEffect(() => {
        if (!rawSchema) return;
        const { nodes: n, edges: e } = buildElements(rawSchema, lang, buildOptions);
        setNodes(n);
        setEdges(e);
        window.requestAnimationFrame(() => fitView());
    }, [rawSchema, lang, buildOptions, setNodes, setEdges, fitView]);

    useEffect(() => {
        if (nodes.length > 0) window.requestAnimationFrame(() => fitView());
    }, [nodes.length, fitView]);

    const onLayout = useCallback((dir: string) => {
        const layouted = getLayoutedElements(nodes, edges, dir);
        const routed = routeEdges(layouted.nodes, layouted.edges);
        setNodes([...routed.nodes]);
        setEdges([...routed.edges]);
        window.requestAnimationFrame(() => fitView());
    }, [nodes, edges, setNodes, setEdges, fitView]);

    const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
        if (!lookup) return;
        const elem = lookup.byName.get(node.id);
        if (elem) setInfo({ kind: 'node', elem });
    }, [lookup]);

    const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
        if (!lookup) return;
        const rule = lookup.ruleByIdx.get(edge.id);
        if (rule) setInfo({ kind: 'edge', rule });
    }, [lookup]);

    const onPaneClick = useCallback(() => setInfo(null), []);

    if (isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--bg-secondary)', fontSize: 12, color: 'var(--text-secondary)',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load layer schema — API server may be unavailable.
                    <button onClick={() => refetch()} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid var(--border-strong)', borderRadius: 4,
                        background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer',
                    }}>Retry</button>
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
                onEdgeClick={onEdgeClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                <Panel position="top-right">
                    <div style={{
                        display: 'grid', gap: 8, alignItems: 'center',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            {rawSchema && (
                                <span style={{
                                    fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
                                    padding: '4px 8px', background: 'var(--bg-hover)', borderRadius: 4,
                                }}>
                                    {rawSchema.profile_name} v{rawSchema.version}
                                    {stats && ` · ${stats.nodes}E / ${stats.edges}R`}
                                </span>
                            )}
                            <button onClick={() => onLayout('TB')} style={layoutBtnStyle}>Vertical</button>
                            <button onClick={() => onLayout('LR')} style={layoutBtnStyle}>Horizontal</button>
                        </div>

                        <div style={{
                            display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
                            padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 6,
                            background: 'var(--bg-card)', boxShadow: '0 1px 2px var(--shadow)',
                        }}>
                            <label style={filterLabelStyle}>
                                Edge mode
                                <select
                                    value={edgeMode}
                                    onChange={(e) => setEdgeMode(e.target.value as 'summary' | 'rules')}
                                    style={filterSelectStyle}
                                >
                                    <option value="summary">summary</option>
                                    <option value="rules">rules</option>
                                </select>
                            </label>

                            <label style={filterLabelStyle}>
                                Relation
                                <select
                                    value={relationFilter}
                                    onChange={(e) => setRelationFilter(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="all">all</option>
                                    {relationOptions.map((rel) => (
                                        <option key={rel} value={rel}>{rel}</option>
                                    ))}
                                </select>
                            </label>

                            <label style={toggleLabelStyle}>
                                <input
                                    type="checkbox"
                                    checked={crossLayerOnly}
                                    onChange={(e) => setCrossLayerOnly(e.target.checked)}
                                />
                                Cross-layer
                            </label>
                            <label style={toggleLabelStyle}>
                                <input
                                    type="checkbox"
                                    checked={showEdgeLabels}
                                    onChange={(e) => setShowEdgeLabels(e.target.checked)}
                                />
                                Labels
                            </label>
                            <label style={toggleLabelStyle}>
                                <input
                                    type="checkbox"
                                    checked={compactNodes}
                                    onChange={(e) => setCompactNodes(e.target.checked)}
                                />
                                Compact nodes
                            </label>
                        </div>
                    </div>
                </Panel>
                {info && <InfoPanel info={info} lang={lang} onClose={() => setInfo(null)} />}
            </ReactFlow>
        </div>
    );
}

const layoutBtnStyle: React.CSSProperties = {
    padding: '4px 10px', fontSize: 11, fontWeight: 500,
    border: '1px solid var(--border-strong)', borderRadius: 4,
    background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer',
};

const filterLabelStyle: React.CSSProperties = {
    fontSize: 11,
    color: 'var(--text-muted)',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
};

const filterSelectStyle: React.CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 4,
    background: 'var(--bg-card)',
    color: 'var(--text-secondary)',
    fontSize: 11,
    padding: '2px 6px',
};

const toggleLabelStyle: React.CSSProperties = {
    fontSize: 11,
    color: 'var(--text-secondary)',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
};

// --- Exported wrapper ---

interface LayerSchemaViewProps {
    layerKey: string;
    lang: string;
}

export default function LayerSchemaView({ layerKey, lang }: LayerSchemaViewProps) {
    return (
        <ReactFlowProvider>
            <InnerGraph layerKey={layerKey} lang={lang} />
        </ReactFlowProvider>
    );
}
