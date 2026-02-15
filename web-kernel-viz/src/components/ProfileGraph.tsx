
import { useCallback, useEffect, useState, type ReactNode } from 'react';
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
import TraversalPanel from './TraversalPanel';
import { fetchProfileTopology, fetchReachable } from '@/api/client';
import type { ProfileTopologyResponse, TopologyNode } from '@/api/types';

const nodeTypes = {
    dynamic: DynamicNode,
};
const edgeTypes = {
    custom: CustomEdge,
};

function buildElements(
    topo: ProfileTopologyResponse,
    visibleLayers: Set<string>,
    crossLayerOnly: boolean,
) {
    // Build layer lookup
    const layerOf = new Map(topo.nodes.map((n) => [n.name, n.layer]));

    // Filter edges: visible layers + optional cross-layer filter
    const visibleNodeNames = new Set(
        topo.nodes.filter((n) => visibleLayers.has(n.layer)).map((n) => n.name),
    );

    let filteredEdges = topo.edges.filter(
        (e) => visibleNodeNames.has(e.source) && visibleNodeNames.has(e.target),
    );

    if (crossLayerOnly) {
        filteredEdges = filteredEdges.filter(
            (e) => layerOf.get(e.source) !== layerOf.get(e.target),
        );
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
                data: { label: n.name, layer: n.layer },
            }));

        const edges: Edge[] = filteredEdges.map((e, i) => ({
            id: `e-${e.source}-${e.target}-${e.relation}-${i}`,
            source: e.source,
            target: e.target,
            type: 'custom',
            data: {
                style: { connector: 'solid', strokeColor: '#555', strokeWidth: 1.5 },
            },
            markerEnd: 'url(#directed)',
            label: e.relation,
        }));

        const layouted = getLayoutedElements(nodes, edges, 'TB');
        return routeEdges(layouted.nodes, layouted.edges);
    }

    const nodes: Node[] = topo.nodes
        .filter((n) => visibleNodeNames.has(n.name))
        .map((n) => ({
            id: n.name,
            type: 'dynamic',
            position: { x: 0, y: 0 },
            data: { label: n.name, layer: n.layer },
        }));

    const edges: Edge[] = filteredEdges.map((e, i) => ({
        id: `e-${e.source}-${e.target}-${e.relation}-${i}`,
        source: e.source,
        target: e.target,
        type: 'custom',
        data: {
            style: { connector: 'solid', strokeColor: '#555', strokeWidth: 1.5 },
        },
        markerEnd: 'url(#directed)',
        label: e.relation,
    }));

    const layouted = getLayoutedElements(nodes, edges, 'TB');
    return routeEdges(layouted.nodes, layouted.edges);
}

interface LayoutProfileFlowProps {
    profileName: string;
    visibleLayers: Set<string>;
    crossLayerOnly: boolean;
    onShowDetail?: (title: string, content: ReactNode) => void;
}

function NodeDetailContent({ node }: { node: TopologyNode }) {
    return (
        <div style={{ fontSize: 12, lineHeight: 1.8 }}>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>Name</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{node.name}</div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>Layer</div>
                <div>{node.layer}</div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>Category</div>
                <div>{node.category}</div>
            </div>
            <div style={{ marginBottom: 10 }}>
                <div style={detailLabelStyle}>Kernel Type</div>
                <div>{node.kernel_type}</div>
            </div>
            {node.description && (
                <div style={{ marginBottom: 10 }}>
                    <div style={detailLabelStyle}>Description</div>
                    <div style={{ color: '#64748b' }}>{node.description}</div>
                </div>
            )}
        </div>
    );
}

const detailLabelStyle = {
    fontSize: 10, fontWeight: 700 as const, color: '#94a3b8',
    textTransform: 'uppercase' as const, marginBottom: 2,
};

const LayoutProfileFlow = ({ profileName, visibleLayers, crossLayerOnly, onShowDetail }: LayoutProfileFlowProps) => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [selectedNode, setSelectedNode] = useState<string | null>(null);
    const [reachableSet, setReachableSet] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [rawTopo, setRawTopo] = useState<ProfileTopologyResponse | null>(null);

    // Load topology on profile change
    useEffect(() => {
        setError(null);
        setSelectedNode(null);
        setReachableSet(new Set());

        fetchProfileTopology(profileName)
            .then((topo) => {
                setRawTopo(topo);
                const { nodes: n, edges: e } = buildElements(topo, visibleLayers, crossLayerOnly);
                setNodes(n);
                setEdges(e);
            })
            .catch((err) => setError(String(err)));
    }, [profileName, setNodes, setEdges]); // visibleLayers/crossLayerOnly handled separately

    // Re-layout when visibleLayers or crossLayerOnly changes
    useEffect(() => {
        if (!rawTopo) return;
        const { nodes: n, edges: e } = buildElements(rawTopo, visibleLayers, crossLayerOnly);
        setNodes(n);
        setEdges(e);
        window.requestAnimationFrame(() => fitView());
    }, [visibleLayers, crossLayerOnly, rawTopo, setNodes, setEdges, fitView]);

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
            prev.map((n) => ({
                ...n,
                data: { ...n.data, highlighted: reachableSet.has(n.id) },
            })),
        );

        setEdges((prev) =>
            prev.map((e) => ({
                ...e,
                data: {
                    ...e.data,
                    highlighted: reachableSet.has(e.source) && reachableSet.has(e.target),
                },
            })),
        );
    }, [reachableSet, rawTopo, setNodes, setEdges]);

    const onNodeClick = useCallback(
        (_: React.MouseEvent, node: Node) => {
            setSelectedNode(node.id);

            // Show detail in slide-over
            if (onShowDetail && rawTopo) {
                const topoNode = rawTopo.nodes.find((n) => n.name === node.id);
                if (topoNode) {
                    const reachEdges = rawTopo.edges.filter(
                        (e) => e.source === node.id || e.target === node.id,
                    );
                    onShowDetail(
                        node.id,
                        <div>
                            <NodeDetailContent node={topoNode} />
                            <div style={{ marginTop: 16 }}>
                                <div style={detailLabelStyle}>
                                    Connections ({reachEdges.length})
                                </div>
                                {reachEdges.slice(0, 20).map((e, i) => (
                                    <div key={i} style={{
                                        fontSize: 11, padding: '3px 0',
                                        color: '#475569', borderBottom: '1px solid #f1f5f9',
                                    }}>
                                        {e.source === node.id
                                            ? <span>→ <strong>{e.target}</strong> <span style={{ color: '#94a3b8' }}>({e.relation})</span></span>
                                            : <span>← <strong>{e.source}</strong> <span style={{ color: '#94a3b8' }}>({e.relation})</span></span>
                                        }
                                    </div>
                                ))}
                                {reachEdges.length > 20 && (
                                    <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                                        ...and {reachEdges.length - 20} more
                                    </div>
                                )}
                            </div>
                        </div>,
                    );
                }
            }

            // Fetch reachable set for highlighting
            fetchReachable(profileName, node.id, { max_depth: 3 })
                .then((res) => {
                    setReachableSet(new Set([node.id, ...res.reachable]));
                })
                .catch(() => setReachableSet(new Set([node.id])));
        },
        [profileName, onShowDetail, rawTopo],
    );

    const onClear = useCallback(() => {
        setSelectedNode(null);
        setReachableSet(new Set());
    }, []);

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

    if (error) {
        return (
            <div style={{ padding: 40, color: '#ef4444', fontFamily: 'system-ui' }}>
                Failed to load profile: {error}
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
                        Vertical Layout
                    </button>
                    <button onClick={() => onLayout('LR')}>Horizontal Layout</button>
                </Panel>
                <TraversalPanel
                    selectedNode={selectedNode}
                    reachableCount={reachableSet.size}
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
    onShowDetail?: (title: string, content: ReactNode) => void;
}

export default function ProfileGraph({ profileName, visibleLayers, crossLayerOnly, onShowDetail }: ProfileGraphProps) {
    // Default: all layers visible
    const layers = visibleLayers || new Set(['Infra', 'Governance', 'Decision', 'Needs', 'Kernel', 'Flow']);
    return (
        <ReactFlowProvider>
            <LayoutProfileFlow
                profileName={profileName}
                visibleLayers={layers}
                crossLayerOnly={crossLayerOnly ?? false}
                onShowDetail={onShowDetail}
            />
        </ReactFlowProvider>
    );
}
