import { useCallback, useEffect } from 'react';
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    type Connection,
    BackgroundVariant,
    type Node,
    type Edge,
    useReactFlow,
    Panel,
    ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { KERNEL_ENTITIES, KERNEL_RELATIONS, type KernelRelation } from '@/data/kernel';
import type { MarkerType } from '@/types/diagram';

import { CustomEdge } from './edges';
import { CustomMarkers } from './markers';
import { getLayoutedElements } from '@/utils/layout';
import { DynamicNode } from './nodes';
import { routeEdges } from '@/utils/routing';

const nodeTypes = {
    dynamic: DynamicNode,
};
const edgeTypes = {
    custom: CustomEdge,
};

const getMarkerUrl = (markerType?: MarkerType) => {
    if (!markerType || markerType === 'none') return undefined;
    return `url(#${markerType})`;
};

const generateElements = () => {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    KERNEL_ENTITIES.forEach((entity) => {
        nodes.push({
            id: entity.name,
            type: 'dynamic',
            position: { x: 0, y: 0 },
            data: { label: entity.name, layer: entity.layer },
            // Styles handled by DynamicNode
        });

        // Inheritance Edges (Parent -> Child)
        if (entity.parent) {
            edges.push({
                id: `e-extends-${entity.parent}-${entity.name}`,
                source: entity.parent,
                target: entity.name,
                type: 'custom',
                data: {
                    style: {
                        connector: 'solid',
                        endMarker: 'directed',
                        strokeColor: '#ccc', // Lighter for inheritance
                        strokeWidth: 1,
                    }
                },
                markerEnd: 'url(#directed)',
                label: 'extends',
            });
        }
    });

    // Relation Edges
    KERNEL_RELATIONS.forEach((relation) => {
        let roles = relation.roles;
        let current: KernelRelation | undefined = relation;

        // Resolve inherited roles if missing
        while (!roles && current?.parent) {
            const parentName: string | undefined = current.parent;
            if (parentName) {
                current = KERNEL_RELATIONS.find(r => r.name === parentName);
                if (current) {
                    roles = current.roles;
                } else {
                    break;
                }
            } else {
                break;
            }
        }

        if (roles && roles.length >= 2) {
            const source = roles[0].player;
            const target = roles[1].player;

            edges.push({
                id: `e-rel-${relation.name}`,
                source: source,
                target: target,
                type: 'custom',
                data: {
                    relation: relation,
                    style: {
                        ...relation.style,
                        strokeColor: '#555',
                    }
                },
                markerEnd: getMarkerUrl(relation.style?.endMarker),
                markerStart: getMarkerUrl(relation.style?.startMarker),
                label: relation.name,
            });
        }
    });

    // 1. Calculate Dagre Layout first (positions)
    const layouted = getLayoutedElements(nodes, edges, 'TB');

    // 2. Calculate dynamic routing (handles)
    return routeEdges(layouted.nodes, layouted.edges);
};

const LayoutFlow = () => {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const onLayout = useCallback(
        (direction: string) => {
            // 1. Re-run Dagre
            const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
                nodes,
                edges,
                direction,
            );

            // 2. Re-run Routing
            const routed = routeEdges(layoutedNodes, layoutedEdges);

            setNodes([...routed.nodes]);
            setEdges([...routed.edges]); // Edges likely modified with handle IDs

            window.requestAnimationFrame(() => fitView());
        },
        [nodes, edges, setNodes, setEdges, fitView],
    );

    useEffect(() => {
        const { nodes: initialNodes, edges: initialEdges } = generateElements();
        setNodes(initialNodes);
        setEdges(initialEdges);
    }, [setNodes, setEdges]); // generateElements is stable (defined outside component or should be memoized/static) -> defined outside component

    // Trigger fit view after initial render
    useEffect(() => {
        if (nodes.length > 0) {
            window.requestAnimationFrame(() => fitView());
        }
    }, [nodes.length, fitView]);

    return (
        <div style={{ width: '100vw', height: '100vh' }}>
            <CustomMarkers />
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
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
