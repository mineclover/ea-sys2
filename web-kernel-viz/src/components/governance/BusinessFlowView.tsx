
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

import { CustomEdge } from '../edges';
import { CustomMarkers } from '../markers';
import { DynamicNode } from '../nodes';
import { getLayoutedElements } from '@/utils/layout';
import { routeEdges } from '@/utils/routing';
import { fetchBusinessFlowTopology } from '@/api/client';
import type {
    BusinessFlowTopologyResponse,
    BusinessFlowElement,
    BusinessFlowEdge,
    I18nString,
} from '@/api/types';
import { DESIGN_SYSTEM } from '@/styles/design-system';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

const nodeTypes = { dynamic: DynamicNode };
const edgeTypes = { custom: CustomEdge };

// Layer key → display label for the legend
const LAYER_LABELS: Record<string, string> = {
    infra: 'Infra',
    governance: 'Governance',
    decision: 'Decision',
    needs: 'Needs',
    kernel: 'Kernel',
    flow: 'Flow',
};

// Map layer_key to the DESIGN_SYSTEM key (capitalised)
const LAYER_DS_KEY: Record<string, string> = {
    infra: 'Infra',
    governance: 'Governance',
    decision: 'Decision',
    needs: 'Needs',
    kernel: 'Kernel',
    flow: 'Flow',
};

// --- Build ReactFlow elements from business flow topology ---

interface NodeLookup {
    byNodeId: Map<string, BusinessFlowElement & { layer_key: string }>;
    edgeByIdx: Map<string, BusinessFlowEdge>;
}

function buildElements(
    data: BusinessFlowTopologyResponse,
    lang: string,
): { nodes: Node[]; edges: Edge[]; lookup: NodeLookup } {
    const byNodeId = new Map<string, BusinessFlowElement & { layer_key: string }>();
    const edgeByIdx = new Map<string, BusinessFlowEdge>();
    const nodeIdSet = new Set<string>();

    const rfNodes: Node[] = [];

    for (const layerGroup of data.layers) {
        if (!layerGroup.loaded) continue;
        const dsKey = LAYER_DS_KEY[layerGroup.layer_key] || 'default';
        for (const elem of layerGroup.elements) {
            const nodeId = elem.node_id;
            nodeIdSet.add(nodeId);
            byNodeId.set(nodeId, { ...elem, layer_key: layerGroup.layer_key });
            const displayName = i18n(elem.display_name, lang) || elem.name;
            rfNodes.push({
                id: nodeId,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: {
                    label: displayName,
                    description: i18n(elem.description, lang),
                    layer: dsKey,
                    style: elem.is_model_port
                        ? { shape: 'rounded' as const, width: 180 }
                        : undefined,
                },
            });
        }
    }

    const rfEdges: Edge[] = [];
    let edgeIdx = 0;
    for (const be of data.edges) {
        if (!nodeIdSet.has(be.source) || !nodeIdSet.has(be.target)) continue;

        const eid = `bf-${edgeIdx++}`;
        edgeByIdx.set(eid, be);

        const edgeStyle = getEdgeStyle(be.edge_type);
        const edgePriority = getEdgePriority(be.edge_type);
        const edgeLabel = be.edge_type === 'intra_layer'
            ? be.relation
            : be.edge_type.replace(/_/g, ' ');

        rfEdges.push({
            id: eid,
            source: be.source,
            target: be.target,
            type: 'custom',
            data: {
                style: edgeStyle,
                relation: be.relation,
                edgeType: be.edge_type,
                priority: edgePriority,
            },
            markerEnd: 'url(#directed)',
            label: edgeLabel,
        });
    }

    const layouted = getLayoutedElements(rfNodes, rfEdges, 'TB');
    const routed = routeEdges(layouted.nodes, layouted.edges);
    return { nodes: routed.nodes, edges: routed.edges, lookup: { byNodeId, edgeByIdx } };
}

function getEdgeStyle(edgeType: string) {
    switch (edgeType) {
        case 'model_port_bridge':
            return { connector: 'solid', strokeColor: 'var(--status-warning-text)', strokeWidth: 2 };
        case 'runtime_chain':
            return { connector: 'dashed', strokeColor: 'var(--color-layer-kernel)', strokeWidth: 2, animated: true };
        case 'governance_oversight':
            return { connector: 'spaced', strokeColor: 'var(--destructive)', strokeWidth: 1.5 };
        default: // intra_layer
            return { connector: 'solid', strokeColor: 'var(--muted-foreground)' };
    }
}

function getEdgePriority(edgeType: string): number {
    switch (edgeType) {
        case 'runtime_chain':
            return 90;
        case 'model_port_bridge':
            return 78;
        case 'governance_oversight':
            return 72;
        default:
            return 60;
    }
}

// --- Info panel ---

type InfoData =
    | { kind: 'node'; elem: BusinessFlowElement & { layer_key: string } }
    | { kind: 'edge'; edge: BusinessFlowEdge };

const lbl = { fontSize: 10, fontWeight: 700 as const, color: 'var(--muted-foreground)', textTransform: 'uppercase' as const };

function InfoPanel({ info, lang, onClose }: { info: InfoData; lang: string; onClose: () => void }) {
    const isNode = info.kind === 'node';
    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
                padding: '12px 16px', boxShadow: '0 4px 6px -1px var(--shadow-lg)',
                minWidth: 220, maxWidth: 340, fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={lbl}>{isNode ? 'Element' : 'Edge'}</div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--muted-foreground)', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                {isNode ? (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', marginBottom: 2 }}>
                            {i18n(info.elem.display_name, lang) || info.elem.name}
                            {info.elem.display_name && (
                                <span style={{ fontWeight: 400, color: 'var(--muted-foreground)', marginLeft: 6, fontSize: 11 }}>{info.elem.name}</span>
                            )}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                            {LAYER_LABELS[info.elem.layer_key] || info.elem.layer_key}
                            {` · ${info.elem.category}`}
                            {info.elem.is_model_port && ' · ModelPort'}
                        </div>
                        <div style={{ marginTop: 4 }}>
                            <span style={{
                                padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                background: 'var(--status-indigo-bg)', color: 'var(--status-indigo-text)', borderRadius: 3,
                            }}>{info.elem.kernel_type}</span>
                        </div>
                        {i18n(info.elem.description, lang) && (
                            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 6, lineHeight: 1.5 }}>
                                {i18n(info.elem.description, lang)}
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', marginBottom: 4 }}>
                            {info.edge.source} <span style={{ color: 'var(--muted-foreground)' }}>{'\u2192'}</span> {info.edge.target}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                            Relation: <strong>{info.edge.relation}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                            Type: {info.edge.edge_type.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 2 }}>
                            {LAYER_LABELS[info.edge.source_layer] || info.edge.source_layer}
                            {' \u2192 '}
                            {LAYER_LABELS[info.edge.target_layer] || info.edge.target_layer}
                        </div>
                    </>
                )}
            </div>
        </Panel>
    );
}

// --- Inner graph component (needs ReactFlow context) ---

interface InnerProps {
    lang: string;
}

function InnerGraph({ lang }: InnerProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [error, setError] = useState<string | null>(null);
    const [rawData, setRawData] = useState<BusinessFlowTopologyResponse | null>(null);
    const [lookup, setLookup] = useState<NodeLookup | null>(null);
    const [info, setInfo] = useState<InfoData | null>(null);
    const [stats, setStats] = useState<{ elements: number; edges: number } | null>(null);

    const load = useCallback(() => {
        setError(null);
        setNodes([]);
        setEdges([]);
        setInfo(null);
        setStats(null);
        setRawData(null);

        fetchBusinessFlowTopology({ lang })
            .then((data) => {
                setRawData(data);
                const { nodes: n, edges: e, lookup: lk } = buildElements(data, lang);
                setLookup(lk);
                setNodes(n);
                setEdges(e);
                setStats({ elements: data.total_elements, edges: data.total_edges });
            })
            .catch(() => {
                setError('unavailable');
            });
    }, [lang, setNodes, setEdges]);

    useEffect(() => { load(); }, [load]);

    // Rebuild when lang changes and we have raw data
    useEffect(() => {
        if (!rawData) return;
        const { nodes: n, edges: e, lookup: lk } = buildElements(rawData, lang);
        setLookup(lk);
        setNodes(n);
        setEdges(e);
        window.requestAnimationFrame(() => fitView());
    }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

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
        const elem = lookup.byNodeId.get(node.id);
        if (elem) setInfo({ kind: 'node', elem });
    }, [lookup]);

    const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
        if (!lookup) return;
        const be = lookup.edgeByIdx.get(edge.id);
        if (be) setInfo({ kind: 'edge', edge: be });
    }, [lookup]);

    const onPaneClick = useCallback(() => setInfo(null), []);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--secondary)', fontSize: 12, color: 'var(--muted-foreground)',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load business flow — API server may be unavailable.
                    <button onClick={load} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid var(--input)', borderRadius: 4,
                        background: 'var(--card)', color: 'var(--muted-foreground)', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    // Layer legend colors
    const layerColors = DESIGN_SYSTEM.colors.layers;

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
                        display: 'flex', gap: 8, alignItems: 'center',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}>
                        {stats && (
                            <span style={{
                                fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)',
                                padding: '4px 8px', background: 'var(--accent)', borderRadius: 4,
                            }}>
                                {stats.elements} elements · {stats.edges} edges
                            </span>
                        )}
                        <button onClick={() => onLayout('TB')} style={layoutBtnStyle}>Vertical</button>
                        <button onClick={() => onLayout('LR')} style={layoutBtnStyle}>Horizontal</button>
                    </div>
                </Panel>
                <Panel position="top-left">
                    <div style={{
                        background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
                        padding: '8px 12px', boxShadow: '0 1px 3px var(--shadow-md)',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 6 }}>
                            Layers
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                            {Object.entries(LAYER_LABELS).map(([key, label]) => {
                                const dsKey = LAYER_DS_KEY[key] as keyof typeof layerColors;
                                const c = layerColors[dsKey] || layerColors.default;
                                return (
                                    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <div style={{ width: 10, height: 10, borderRadius: 2, background: c.color }} />
                                        <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{label}</span>
                                    </div>
                                );
                            })}
                        </div>
                        <div style={{ borderTop: '1px solid var(--accent)', marginTop: 8, paddingTop: 6 }}>
                            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 4 }}>
                                Edge Types
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="#555" strokeWidth="1.5" /></svg>
                                    <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>Intra-layer</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="var(--color-layer-infra)" strokeWidth="2" /></svg>
                                    <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>ModelPort bridge</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="var(--color-layer-kernel)" strokeWidth="2" strokeDasharray="3 3" /></svg>
                                    <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>Runtime chain</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="var(--destructive)" strokeWidth="1.5" strokeDasharray="8 8" /></svg>
                                    <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>Governance oversight</span>
                                </div>
                            </div>
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
    border: '1px solid var(--input)', borderRadius: 4,
    background: 'var(--card)', color: 'var(--muted-foreground)', cursor: 'pointer',
};

// --- Exported wrapper ---

interface BusinessFlowViewProps {
    lang: string;
}

export default function BusinessFlowView({ lang }: BusinessFlowViewProps) {
    return (
        <ReactFlowProvider>
            <InnerGraph lang={lang} />
        </ReactFlowProvider>
    );
}
