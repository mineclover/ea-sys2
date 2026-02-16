
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

import { CustomEdge } from './edges';
import { CustomMarkers } from './markers';
import { getLayoutedElements } from '@/utils/layout';
import { DynamicNode } from './nodes';
import { routeEdges } from '@/utils/routing';
import { useKernelEntities, useKernelRelations } from '@/api/hooks';
import type {
    KernelEntitiesResponse,
    KernelRelationsResponse,
    KernelEntityItem,
    KernelRelationItem,
    I18nString,
} from '@/api/types';
import type { MarkerType } from '@/types/diagram';

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

            if (entity.parent) {
                const eid = `e-extends-${entity.parent}-${entity.name}`;
                edges.push({
                    id: eid,
                    source: entity.parent,
                    target: entity.name,
                    type: 'custom',
                    data: {
                        style: {
                            connector: 'solid',
                            endMarker: 'directed',
                            strokeColor: 'var(--border)',
                            strokeWidth: 1,
                        },
                    },
                    markerEnd: 'url(#directed)',
                    label: 'extends',
                });
            }
        }
    }

    for (const layer of relations.layers) {
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
                        style: { ...style, strokeColor: 'var(--text-secondary)' },
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

// --- Inline info panel ---

const labelStyle = { fontSize: 10, fontWeight: 700 as const, color: 'var(--text-muted)', textTransform: 'uppercase' as const };

function InfoPanel({ info, lang, onClose }: { info: InfoData; lang: string; onClose: () => void }) {
    const isEntity = info.kind === 'entity';
    const item = isEntity ? info.entity : info.relation;
    const name = item.name;
    const layer = item.layerName;
    const parent = item.parent;
    const displayName = i18nText(item.display_name, lang);
    const desc = i18nText(item.description, lang);

    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '12px 16px',
                boxShadow: `0 4px 6px -1px var(--shadow-lg)`,
                minWidth: 220,
                maxWidth: 320,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={labelStyle}>{isEntity ? 'Entity' : 'Relation'}</div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-muted)', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                    {displayName || name}
                    {displayName && displayName !== name && (
                        <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6, fontSize: 11 }}>{name}</span>
                    )}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 2 }}>
                    {layer}{parent ? ` · extends ${parent}` : ''}
                    {isEntity && info.entity.is_abstract ? ' · abstract' : ''}
                </div>
                {desc && (
                    <div style={{ fontSize: 11, color: 'var(--text-primary)', marginTop: 6, lineHeight: 1.5 }}>
                        {desc}
                    </div>
                )}
                {!isEntity && info.relation.roles && info.relation.roles.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                        {info.relation.roles.map((r, i) => (
                            <div key={i} style={{ fontSize: 11, color: 'var(--text-primary)' }}>
                                <strong>{r.name}</strong>
                                <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>{r.player}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </Panel>
    );
}

// --- Main component ---

interface LayoutFlowProps {
    lang: string;
}

const LayoutFlow = ({ lang }: LayoutFlowProps) => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [info, setInfo] = useState<InfoData | null>(null);

    const { data: entData, isError: entError } = useKernelEntities({ lang });
    const { data: relData, isError: relError } = useKernelRelations({ lang });

    const lookup = useMemo(() => {
        if (!entData || !relData) return null;
        return buildLookup(entData, relData);
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

    const onPaneClick = useCallback(() => setInfo(null), []);

    if (entError || relError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--bg-secondary)', fontSize: 12, color: 'var(--text-secondary)',
                }}>
                    Unable to load kernel schema — API server may be unavailable.
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
                    <button onClick={() => onLayout('TB')} style={{ marginRight: 10 }}>Vertical Layout</button>
                    <button onClick={() => onLayout('LR')}>Horizontal Layout</button>
                </Panel>
                {info && <InfoPanel info={info} lang={lang} onClose={() => setInfo(null)} />}
            </ReactFlow>
        </div>
    );
};

export default function FlowGraph({ lang = 'en' }: { lang?: string }) {
    return (
        <ReactFlowProvider>
            <LayoutFlow lang={lang} />
        </ReactFlowProvider>
    );
}
