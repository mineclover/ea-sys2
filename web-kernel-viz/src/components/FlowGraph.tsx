
import { useCallback, useEffect, useState } from 'react';
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
import { fetchKernelEntities, fetchKernelRelations } from '@/api/client';
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
) {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    for (const layer of entities.layers) {
        const layerKey = shortLayer(layer.name);
        for (const entity of layer.entities) {
            const koName = i18nText(entity.display_name, 'ko');
            nodes.push({
                id: entity.name,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: { label: entity.name, subLabel: koName, layer: layerKey },
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
                            strokeColor: '#ccc',
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
                const parentName = current.parent;
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
                        style: { ...style, strokeColor: '#555' },
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

const labelStyle = { fontSize: 10, fontWeight: 700 as const, color: '#94a3b8', textTransform: 'uppercase' as const };

function InfoPanel({ info, onClose }: { info: InfoData; onClose: () => void }) {
    const isEntity = info.kind === 'entity';
    const item = isEntity ? info.entity : info.relation;
    const name = item.name;
    const layer = item.layerName;
    const parent = item.parent;
    const koName = i18nText(item.display_name, 'ko');
    const enDesc = i18nText(item.description, 'en');
    const koDesc = i18nText(item.description, 'ko');

    return (
        <Panel position="bottom-right">
            <div style={{
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '12px 16px',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                minWidth: 220,
                maxWidth: 320,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={labelStyle}>{isEntity ? 'Entity' : 'Relation'}</div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: '#94a3b8', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 2 }}>
                    {name}
                    {koName && <span style={{ fontWeight: 400, color: '#64748b', marginLeft: 6 }}>{koName}</span>}
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginBottom: 2 }}>
                    {layer}{parent ? ` · extends ${parent}` : ''}
                    {isEntity && info.entity.is_abstract ? ' · abstract' : ''}
                </div>
                {enDesc && (
                    <div style={{ fontSize: 11, color: '#475569', marginTop: 6, lineHeight: 1.5 }}>
                        {enDesc}
                    </div>
                )}
                {koDesc && koDesc !== enDesc && (
                    <div style={{ fontSize: 11, color: '#64748b', marginTop: 2, lineHeight: 1.5 }}>
                        {koDesc}
                    </div>
                )}
                {!isEntity && info.relation.roles && info.relation.roles.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                        {info.relation.roles.map((r, i) => (
                            <div key={i} style={{ fontSize: 11, color: '#475569' }}>
                                <strong>{r.name}</strong>
                                <span style={{ color: '#94a3b8', marginLeft: 6 }}>{r.player}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </Panel>
    );
}

// --- Main component ---

const LayoutFlow = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [error, setError] = useState<string | null>(null);
    const [lookup, setLookup] = useState<SchemaLookup | null>(null);
    const [info, setInfo] = useState<InfoData | null>(null);

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

    useEffect(() => {
        Promise.all([fetchKernelEntities({ lang: 'ko' }), fetchKernelRelations({ lang: 'ko' })])
            .then(([ent, rel]) => {
                const lk = buildLookup(ent, rel);
                setLookup(lk);
                const { nodes: n, edges: e } = buildElements(ent, rel, lk);
                setNodes(n);
                setEdges(e);
            })
            .catch((err) => setError(String(err)));
    }, [setNodes, setEdges]);

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

    if (error) {
        return (
            <div style={{ padding: 40, color: '#ef4444', fontFamily: 'system-ui' }}>
                Failed to load kernel schema: {error}
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
                {info && <InfoPanel info={info} onClose={() => setInfo(null)} />}
            </ReactFlow>
        </div>
    );
};

export default function FlowGraph() {
    return (
        <ReactFlowProvider>
            <LayoutFlow />
        </ReactFlowProvider>
    );
}
