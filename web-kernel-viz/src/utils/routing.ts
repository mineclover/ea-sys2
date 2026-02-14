
import { type Node, type Edge } from '@xyflow/react';
import { DESIGN_SYSTEM } from '@/styles/design-system';

interface HandleInfo {
    edgeId: string;
    isSource: boolean;
    otherX: number;
    otherY: number;
    angle: number;
}

interface NodeHandleConfig {
    top: HandleInfo[];
    right: HandleInfo[];
    bottom: HandleInfo[];
    left: HandleInfo[];
}

export const routeEdges = (nodes: Node[], edges: Edge[]) => {
    const nodeHandles: Record<string, NodeHandleConfig> = {};

    nodes.forEach(node => {
        nodeHandles[node.id] = { top: [], right: [], bottom: [], left: [] };
    });

    edges.forEach((edge) => {
        const sourceNode = nodes.find(n => n.id === edge.source);
        const targetNode = nodes.find(n => n.id === edge.target);

        if (!sourceNode || !targetNode || !nodeHandles[sourceNode.id] || !nodeHandles[targetNode.id]) return;

        // Use DS dimensions for center calculation
        const w = DESIGN_SYSTEM.node.width;
        const h = DESIGN_SYSTEM.node.height;

        const sx = sourceNode.position.x + w / 2;
        const sy = sourceNode.position.y + h / 2;
        const tx = targetNode.position.x + w / 2;
        const ty = targetNode.position.y + h / 2;

        const dx = tx - sx;
        const dy = ty - sy;
        const angle = Math.atan2(dy, dx);

        let sSide: 'top' | 'right' | 'bottom' | 'left';
        let tSide: 'top' | 'right' | 'bottom' | 'left';
        let sOtherX = tx;
        let sOtherY = ty;
        let tOtherX = sx;
        let tOtherY = sy;

        if (sourceNode.id === targetNode.id) {
            sSide = 'top';
            tSide = 'top';
            // Sort Self-loops: Source Left, Target Right on Top edge
            // Large offset ensures they sort to the outsides if other edges exist on Top?
            // Or insides?
            // -1000 puts Source at far Left. +1000 puts Target at far Right.
            // If other edges attach to Top, they will have otherX between Sx and Tx.
            // So self-loop will embrace the other edges. This is cleaner.
            sOtherX = sx - 1000;
            tOtherX = sx + 1000;
        } else {
            const deg = angle * (180 / Math.PI);

            // Simple 45 deg quadrant logic works well for general routing
            if (deg >= -45 && deg < 45) {
                sSide = 'right';
                tSide = 'left';
            } else if (deg >= 45 && deg < 135) {
                sSide = 'bottom';
                tSide = 'top';
            } else if (deg >= -135 && deg < -45) {
                sSide = 'top';
                tSide = 'bottom';
            } else {
                sSide = 'left';
                tSide = 'right';
            }
        }

        nodeHandles[sourceNode.id][sSide].push({
            edgeId: edge.id, isSource: true, otherX: sOtherX, otherY: sOtherY, angle
        });
        nodeHandles[targetNode.id][tSide].push({
            edgeId: edge.id, isSource: false, otherX: tOtherX, otherY: tOtherY, angle: angle + Math.PI
        });
    });

    const newEdges = edges.map(e => ({ ...e }));
    const newNodes = nodes.map(n => {
        const config = nodeHandles[n.id];
        if (!config) return n;

        config.top.sort((a, b) => a.otherX - b.otherX);
        config.bottom.sort((a, b) => a.otherX - b.otherX);
        config.left.sort((a, b) => a.otherY - b.otherY);
        config.right.sort((a, b) => a.otherY - b.otherY);

        const handlesData: Record<string, any[]> = { top: [], right: [], bottom: [], left: [] };

        (['top', 'right', 'bottom', 'left'] as const).forEach(side => {
            const list = config[side];
            if (list.length === 0) return;

            const step = 100 / (list.length + 1);

            list.forEach((h, idx) => {
                const offset = step * (idx + 1);
                const handleId = `${h.isSource ? 's' : 't'}-${side}-${idx}`;

                handlesData[side].push({
                    id: handleId,
                    offset
                });

                const edgeIndex = newEdges.findIndex(e => e.id === h.edgeId);
                if (edgeIndex >= 0) {
                    if (h.isSource) {
                        newEdges[edgeIndex].sourceHandle = handleId;
                    } else {
                        newEdges[edgeIndex].targetHandle = handleId;
                    }
                }
            });
        });

        return {
            ...n,
            type: 'dynamic',
            data: {
                ...n.data,
                handles: handlesData
            }
        };
    });

    return { nodes: newNodes, edges: newEdges };
};
