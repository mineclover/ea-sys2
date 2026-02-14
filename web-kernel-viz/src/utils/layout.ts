
import { type Node, type Edge, Position } from '@xyflow/react';
import dagre from 'dagre';
import { DESIGN_SYSTEM } from '@/styles/design-system';

export const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
    const dagreGraph = new dagre.graphlib.Graph();
    dagreGraph.setDefaultEdgeLabel(() => ({}));

    const isHorizontal = direction === 'LR';
    dagreGraph.setGraph({
        rankdir: direction,
        nodesep: DESIGN_SYSTEM.layout.nodesep,
        ranksep: DESIGN_SYSTEM.layout.ranksep,
    });

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, {
            width: DESIGN_SYSTEM.node.width,
            height: DESIGN_SYSTEM.node.height
        });
    });

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target);
    });

    dagre.layout(dagreGraph);

    const layoutedNodes = nodes.map((node) => {
        const nodeWithPosition = dagreGraph.node(node.id);
        return {
            ...node,
            targetPosition: isHorizontal ? Position.Left : Position.Top,
            sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
            position: {
                x: nodeWithPosition.x - (DESIGN_SYSTEM.node.width / 2),
                y: nodeWithPosition.y - (DESIGN_SYSTEM.node.height / 2),
            },
        };
    });

    return { nodes: layoutedNodes, edges };
};
