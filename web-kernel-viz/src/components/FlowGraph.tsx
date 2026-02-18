
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
    type EdgeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { CustomEdge } from './edges';
import { CustomMarkers } from './markers';
import { getLayoutedElements } from '@/utils/layout';
import { DynamicNode } from './nodes';
import { routeEdges } from '@/utils/routing';
import { useKernelEntities, useKernelRelations, useKernelRules } from '@/api/hooks';
import type {
    KernelEntitiesResponse,
    KernelRelationsResponse,
    KernelEntityItem,
    KernelRelationItem,
    I18nString,
} from '@/api/types';
import type { MarkerType } from '@/types/diagram';
import { DESIGN_SYSTEM } from '@/styles/design-system';

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

// --- Relation style mapping (presentation layer) ---

interface RelationStyle {
    connector?: string;
    endMarker?: MarkerType;
    startMarker?: MarkerType;
}

const RELATION_STYLES: Record<string, RelationStyle> = {
    ownership:      { endMarker: 'composition' },
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

const getMarkerUrl = (markerType?: MarkerType) => {
    if (!markerType || markerType === 'none') return undefined;
    return `url(#${markerType})`;
};

function shortLayer(apiLayerName: string): string {
    const match = apiLayerName.match(/^(L\d)/);
    return match ? match[1] : apiLayerName;
}

function getLayerColor(layerKey: string): string {
    const colors = DESIGN_SYSTEM.colors.layers[layerKey as keyof typeof DESIGN_SYSTEM.colors.layers];
    return colors?.color ?? 'var(--muted-foreground)';
}

// Lookup helpers built from raw API data
interface SchemaLookup {
    entityByName: Map<string, KernelEntityItem & { layerName: string }>;
    relationByName: Map<string, KernelRelationItem & { layerName: string }>;
    // edge id → relation name
    edgeRelation: Map<string, string>;
}

function buildLookup(
    entities: KernelEntitiesResponse,
    relations: KernelRelationsResponse,
): SchemaLookup {
    const entityByName = new Map<string, KernelEntityItem & { layerName: string }>();
    for (const layer of entities.layers) {
        for (const e of layer.entities) {
            entityByName.set(e.name, { ...e, layerName: layer.name });
        }
    }
    const relationByName = new Map<string, KernelRelationItem & { layerName: string }>();
    for (const layer of relations.layers) {
        for (const r of layer.relations) {
            relationByName.set(r.name, { ...r, layerName: layer.name });
        }
    }
    return { entityByName, relationByName, edgeRelation: new Map() };
}

function buildElements(
    entities: KernelEntitiesResponse,
    relations: KernelRelationsResponse,
    lookup: SchemaLookup,
    lang: string,
) {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    for (const layer of entities.layers) {
        const layerKey = shortLayer(layer.name);
        for (const entity of layer.entities) {
            const title = (lang === 'ko' ? i18nText(entity.display_name, 'ko') : undefined) || entity.name;
            const desc = i18nText(entity.description, lang);
            nodes.push({
                id: entity.name,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: { label: title, description: desc, layer: layerKey },
            });
        }
    }

    for (const layer of relations.layers) {
        const layerKey = shortLayer(layer.name);
        const strokeColor = getLayerColor(layerKey);

        for (const relation of layer.relations) {
            let roles = relation.roles;
            let current: KernelRelationItem | undefined = relation;

            while ((!roles || roles.length === 0) && current?.parent) {
                const parentName: string = current.parent;
                current = undefined;
                for (const rl of relations.layers) {
                    current = rl.relations.find((r) => r.name === parentName);
                    if (current) break;
                }
                if (current) roles = current.roles;
            }

            if (roles && roles.length >= 2) {
                const source = roles[0].player;
                const target = roles[1].player;
                const style = RELATION_STYLES[relation.name] || {};
                const eid = `e-rel-${relation.name}`;

                lookup.edgeRelation.set(eid, relation.name);

                edges.push({
                    id: eid,
                    source,
                    target,
                    type: 'custom',
                    data: {
                        style: { ...style, strokeColor, strokeWidth: 1.5 },
                        relation: relation.name,
                        kernelLayer: layerKey,
                        edgeType: layerKey === 'L3' ? 'behavioral' : 'structural',
                    },
                    markerEnd: getMarkerUrl(style.endMarker),
                    markerStart: getMarkerUrl(style.startMarker),
                    label: relation.name,
                });
            }
        }
    }

    const layouted = getLayoutedElements(nodes, edges, 'TB');
    return routeEdges(layouted.nodes, layouted.edges);
}

// --- Inline info panel types ---

type InfoData =
    | { kind: 'entity'; entity: KernelEntityItem & { layerName: string } }
    | { kind: 'relation'; relation: KernelRelationItem & { layerName: string } };

// --- Hover tooltip types ---

interface HoverInfo {
    relation: KernelRelationItem & { layerName: string };
    x: number;
    y: number;
}

// --- Style description helper ---

function describeStyle(styleDef: RelationStyle): string {
    const parts: string[] = [];
    parts.push(styleDef.connector === 'dashed' ? 'dashed line' : 'solid line');
    if (styleDef.endMarker === 'composition') parts.push('composition end');
    else if (styleDef.endMarker === 'directed') parts.push('directed end');
    if (styleDef.startMarker && styleDef.startMarker !== 'none') parts.push(`${styleDef.startMarker} start`);
    return parts.join(' / ');
}

// --- Inline info panel ---

const sectionLabelStyle = { fontSize: 10, fontWeight: 700 as const, color: 'var(--muted-foreground)', textTransform: 'uppercase' as const };

function InfoPanel({ info, lang, onClose }: { info: InfoData; lang: string; onClose: () => void }) {
    const isEntity = info.kind === 'entity';
    const item = isEntity ? info.entity : info.relation;
    const name = item.name;
    const layer = item.layerName;
    const layerKey = shortLayer(layer);
    const layerColor = getLayerColor(layerKey);
    const parent = item.parent;
    const displayName = i18nText(item.display_name, lang);
    const desc = i18nText(item.description, lang);

    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--card)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '12px 16px',
                boxShadow: `0 4px 6px -1px var(--shadow-lg)`,
                minWidth: 220,
                maxWidth: 320,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={sectionLabelStyle}>{isEntity ? 'Entity' : 'Relation'}</div>
                        <span style={{
                            fontSize: 9, fontWeight: 600,
                            padding: '1px 5px', borderRadius: 3,
                            background: layerColor + '1a',
                            color: layerColor,
                            border: `1px solid ${layerColor}40`,
                        }}>{layerKey}</span>
                    </div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--muted-foreground)', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', marginBottom: 2 }}>
                    {displayName || name}
                    {displayName && displayName !== name && (
                        <span style={{ fontWeight: 400, color: 'var(--muted-foreground)', marginLeft: 6, fontSize: 11 }}>{name}</span>
                    )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                    {layer}{parent ? ` · extends ${parent}` : ''}
                    {isEntity && info.entity.is_abstract ? ' · abstract' : ''}
                </div>
                {desc && (
                    <div style={{ fontSize: 11, color: 'var(--foreground)', marginTop: 6, lineHeight: 1.5 }}>
                        {desc}
                    </div>
                )}
                {!isEntity && info.relation.roles && info.relation.roles.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                        <div style={{ ...sectionLabelStyle, marginBottom: 2 }}>Roles</div>
                        {info.relation.roles.map((r, i) => (
                            <div key={i} style={{ fontSize: 11, color: 'var(--foreground)' }}>
                                <strong>{r.name}</strong>
                                <span style={{ color: 'var(--muted-foreground)', marginLeft: 6 }}>{r.player}</span>
                            </div>
                        ))}
                    </div>
                )}
                {!isEntity && info.relation.owns && info.relation.owns.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                        <div style={{ ...sectionLabelStyle, marginBottom: 2 }}>Owned Attributes</div>
                        <div style={{ fontSize: 11, color: 'var(--foreground)' }}>
                            {info.relation.owns.join(', ')}
                        </div>
                    </div>
                )}
                {!isEntity && (() => {
                    const styleDef = RELATION_STYLES[info.relation.name];
                    if (!styleDef) return null;
                    return (
                        <div style={{ marginTop: 6 }}>
                            <div style={{ ...sectionLabelStyle, marginBottom: 2 }}>Visual Style</div>
                            <div style={{ fontSize: 11, color: 'var(--foreground)' }}>
                                {describeStyle(styleDef)}
                            </div>
                        </div>
                    );
                })()}
            </div>
        </Panel>
    );
}

// --- Edge Legend ---

function LegendItem({ color, dash, label }: { color: string; dash?: boolean; label: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <svg width={28} height={8}>
                <line x1={0} y1={4} x2={28} y2={4}
                    stroke={color} strokeWidth={2}
                    strokeDasharray={dash ? '3 3' : undefined} />
            </svg>
            <span style={{ fontSize: 10, color: 'var(--foreground)' }}>{label}</span>
        </div>
    );
}

function MarkerLegendItem({ symbol, label }: { symbol: string; label: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{ fontSize: 12, width: 28, textAlign: 'center', lineHeight: 1 }}>{symbol}</span>
            <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>{label}</span>
        </div>
    );
}

// --- Hover Tooltip ---

function EdgeTooltip({ info, lang }: { info: HoverInfo; lang: string }) {
    const { relation, x, y } = info;
    const layerKey = shortLayer(relation.layerName);
    const layerColor = getLayerColor(layerKey);
    const displayName = i18nText(relation.display_name, lang);
    const desc = i18nText(relation.description, lang);
    const descTruncated = desc && desc.length > 120 ? desc.slice(0, 120) + '...' : desc;

    return (
        <div style={{
            position: 'fixed',
            left: x + 12,
            top: y - 8,
            zIndex: 1000,
            pointerEvents: 'none',
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '8px 10px',
            boxShadow: '0 4px 12px var(--shadow-lg)',
            maxWidth: 280,
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>
                    {displayName || relation.name}
                </span>
                <span style={{
                    fontSize: 9, fontWeight: 600,
                    padding: '1px 5px', borderRadius: 3,
                    background: layerColor + '1a',
                    color: layerColor,
                    border: `1px solid ${layerColor}40`,
                }}>{layerKey}</span>
            </div>
            {relation.parent && (
                <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                    extends {relation.parent}
                </div>
            )}
            {descTruncated && (
                <div style={{ fontSize: 10, color: 'var(--foreground)', lineHeight: 1.4, marginBottom: 2 }}>
                    {descTruncated}
                </div>
            )}
            {relation.roles && relation.roles.length > 0 && (
                <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                    {relation.roles.map(r => r.name).join(', ')}
                </div>
            )}
        </div>
    );
}

// --- Layout button style ---

const layoutBtnStyle: React.CSSProperties = {
    padding: '4px 10px', fontSize: 11, fontWeight: 500,
    border: '1px solid var(--input)', borderRadius: 4,
    background: 'var(--card)', color: 'var(--muted-foreground)', cursor: 'pointer',
};

// --- Main component ---

interface LayoutFlowProps {
    lang: string;
}

const LayoutFlow = ({ lang }: LayoutFlowProps) => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [info, setInfo] = useState<InfoData | null>(null);
    const [hoverInfo, setHoverInfo] = useState<HoverInfo | null>(null);
    const wrapperRef = useRef<HTMLDivElement>(null);

    const { data: entData, isError: entError } = useKernelEntities({ lang });
    const { data: relData, isError: relError } = useKernelRelations({ lang });
    const { data: rulesData } = useKernelRules();

    const lookup = useMemo(() => {
        if (!entData || !relData) return null;
        return buildLookup(entData, relData);
    }, [entData, relData]);

    const layerSummary = useMemo(() => {
        if (!entData || !relData) return null;
        const findEntityLayer = (prefix: string) => entData.layers.find((l) => shortLayer(l.name) === prefix);
        const findRelationLayer = (prefix: string) => relData.layers.find((l) => shortLayer(l.name) === prefix);

        const l1 = findEntityLayer('L1');
        const l4 = findEntityLayer('L4');
        const l2 = findRelationLayer('L2');
        const l3 = findRelationLayer('L3');

        return {
            l1Entities: l1?.entities.map((e) => e.name) ?? [],
            l4Entities: l4?.entities.map((e) => e.name) ?? [],
            l2Relations: l2?.relations.map((r) => r.name) ?? [],
            l3Relations: l3?.relations.map((r) => r.name) ?? [],
            l1Count: l1?.count ?? 0,
            l2Count: l2?.count ?? 0,
            l3Count: l3?.count ?? 0,
            l4Count: l4?.count ?? 0,
        };
    }, [entData, relData]);

    const onLayout = useCallback(
        (direction: string) => {
            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                nodes, edges, direction,
            );
            const routed = routeEdges(layoutedNodes, layoutedEdges);
            setNodes([...routed.nodes]);
            setEdges([...routed.edges]);
            window.requestAnimationFrame(() => fitView());
        },
        [nodes, edges, setNodes, setEdges, fitView],
    );

    // Build ReactFlow elements when API data or lang changes
    useEffect(() => {
        if (!entData || !relData || !lookup) return;
        const { nodes: n, edges: e } = buildElements(entData, relData, lookup, lang);
        setNodes(n);
        setEdges(e);
        window.requestAnimationFrame(() => fitView());
    }, [entData, relData, lookup, lang, setNodes, setEdges, fitView]);

    useEffect(() => {
        if (nodes.length > 0) {
            window.requestAnimationFrame(() => fitView());
        }
    }, [nodes.length, fitView]);

    const onNodeClick = useCallback(
        (_: React.MouseEvent, node: Node) => {
            if (!lookup) return;
            const entity = lookup.entityByName.get(node.id);
            if (entity) setInfo({ kind: 'entity', entity });
        },
        [lookup],
    );

    const onEdgeClick = useCallback(
        (_: React.MouseEvent, edge: Edge) => {
            if (!lookup) return;
            const relName = lookup.edgeRelation.get(edge.id);
            if (relName) {
                const relation = lookup.relationByName.get(relName);
                if (relation) setInfo({ kind: 'relation', relation });
            }
        },
        [lookup],
    );

    const onEdgeMouseEnter: EdgeMouseHandler = useCallback(
        (event: React.MouseEvent, edge: Edge) => {
            if (!lookup) return;
            const relName = lookup.edgeRelation.get(edge.id);
            if (relName) {
                const relation = lookup.relationByName.get(relName);
                if (relation) {
                    setHoverInfo({ relation, x: event.clientX, y: event.clientY });
                }
            }
        },
        [lookup],
    );

    const onEdgeMouseLeave: EdgeMouseHandler = useCallback(() => {
        setHoverInfo(null);
    }, []);

    const onPaneClick = useCallback(() => setInfo(null), []);

    if (entError || relError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--secondary)', fontSize: 12, color: 'var(--muted-foreground)',
                }}>
                    Unable to load kernel schema — API server may be unavailable.
                </div>
            </div>
        );
    }

    const l2Color = DESIGN_SYSTEM.colors.layers.L2.color;
    const l3Color = DESIGN_SYSTEM.colors.layers.L3.color;

    return (
        <div ref={wrapperRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
            <CustomMarkers />
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onEdgeClick={onEdgeClick}
                onEdgeMouseEnter={onEdgeMouseEnter}
                onEdgeMouseLeave={onEdgeMouseLeave}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                <Panel position="top-right">
                    <div style={{ display: 'flex', gap: 6 }}>
                        <button onClick={() => onLayout('TB')} style={layoutBtnStyle}>Vertical Layout</button>
                        <button onClick={() => onLayout('LR')} style={layoutBtnStyle}>Horizontal Layout</button>
                    </div>
                </Panel>
                {layerSummary && (
                    <Panel position="top-left">
                        <div style={{
                            width: 380,
                            maxWidth: '48vw',
                            maxHeight: '42vh',
                            overflow: 'auto',
                            background: 'var(--card)',
                            border: '1px solid var(--border)',
                            borderRadius: 8,
                            padding: '10px 12px',
                            boxShadow: `0 2px 8px var(--shadow)`,
                            fontFamily: 'system-ui, -apple-system, sans-serif',
                        }}>
                            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>
                                {lang === 'ko' ? '레이어 책임 (Kernel)' : 'Layer Responsibility (Kernel)'}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--foreground)', marginTop: 6, marginBottom: 8 }}>
                                {lang === 'ko'
                                    ? 'L1/L4는 엔티티 노드 레이어, L2/L3는 관계 엣지 레이어로 동작합니다.'
                                    : 'L1/L4 are entity node layers; L2/L3 are relation edge layers.'}
                            </div>
                            <LayerSpecLine
                                title="L1 Structure"
                                role={lang === 'ko' ? '메타 구조 엔티티' : 'meta structure entities'}
                                count={layerSummary.l1Count}
                                items={layerSummary.l1Entities}
                            />
                            <LayerSpecLine
                                title="L2 Relationship"
                                role={lang === 'ko' ? '정적 관계 정의 (edge)' : 'static relation definitions (edges)'}
                                count={layerSummary.l2Count}
                                items={layerSummary.l2Relations}
                            />
                            <LayerSpecLine
                                title="L3 Behavioral"
                                role={lang === 'ko' ? '동작/전이 관계 (edge)' : 'behavioral/transition relations (edges)'}
                                count={layerSummary.l3Count}
                                items={layerSummary.l3Relations}
                            />
                            <LayerSpecLine
                                title="L4 Concrete"
                                role={lang === 'ko' ? '실행/구체 엔티티' : 'runtime concrete entities'}
                                count={layerSummary.l4Count}
                                items={layerSummary.l4Entities}
                            />
                            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted-foreground)' }}>
                                {lang === 'ko' ? '룰 총량' : 'Rules total'}: <strong style={{ color: 'var(--foreground)' }}>{rulesData?.total ?? '-'}</strong>
                            </div>
                            <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>
                                    {lang === 'ko' ? '식별 체계 (Kernel Native)' : 'Identifier System (Kernel Native)'}
                                </div>
                                <div style={{ marginTop: 4, fontSize: 10, color: 'var(--foreground)', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}>
                                    entity_id = entity.name
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--foreground)', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}>
                                    relation_id = relation.name
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--foreground)', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}>
                                    rule_id = rule.id
                                </div>
                            </div>
                            {/* Edge Legend */}
                            <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 4 }}>
                                    {lang === 'ko' ? '엣지 범례' : 'Edge Legend'}
                                </div>
                                <LegendItem color={l2Color} label="L2 Structural" />
                                <LegendItem color={l3Color} label="L3 Behavioral (solid)" />
                                <LegendItem color={l3Color} dash label="L3 Behavioral (dashed)" />
                                <div style={{ marginTop: 4 }}>
                                    <MarkerLegendItem symbol="&#9670;" label="composition" />
                                    <MarkerLegendItem symbol="&#9654;" label="directed" />
                                </div>
                            </div>
                        </div>
                    </Panel>
                )}
                {info && <InfoPanel info={info} lang={lang} onClose={() => setInfo(null)} />}
            </ReactFlow>
            {hoverInfo && <EdgeTooltip info={hoverInfo} lang={lang} />}
        </div>
    );
};

function LayerSpecLine({
    title,
    role,
    count,
    items,
}: {
    title: string;
    role: string;
    count: number;
    items: string[];
}) {
    return (
        <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>
                {title} <span style={{ color: 'var(--muted-foreground)', fontWeight: 500 }}>({count})</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{role}</div>
            <div style={{ fontSize: 11, color: 'var(--foreground)' }}>{items.join(', ') || '-'}</div>
        </div>
    );
}

export default function FlowGraph({ lang = 'en' }: { lang?: string }) {
    return (
        <ReactFlowProvider>
            <LayoutFlow lang={lang} />
        </ReactFlowProvider>
    );
}
