import {
    type EdgeProps,
    getBezierPath,
    BaseEdge,
    EdgeLabelRenderer,
} from '@xyflow/react';
import { type DiagramStyle } from '../../types/diagram';

export const CustomEdge = ({
    id,
    source,
    target,
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    style = {},
    markerEnd,
    markerStart,
    data,
    label,
    labelStyle,
}: EdgeProps) => {
    let edgePath = '';
    let labelX = 0;
    let labelY = 0;

    if (source === target) {
        // Self-loop logic (simplified center point for label)
        const dist = 60;
        let cp1x, cp1y, cp2x, cp2y;

        switch (sourcePosition) {
            case 'top':
                cp1x = sourceX - 10; cp1y = sourceY - dist;
                cp2x = targetX + 10; cp2y = targetY - dist;
                labelX = sourceX; labelY = sourceY - dist - 10;
                break;
            case 'right':
                cp1x = sourceX + dist; cp1y = sourceY - 10;
                cp2x = targetX + dist; cp2y = targetY + 10;
                labelX = sourceX + dist + 10; labelY = sourceY;
                break;
            case 'bottom':
                cp1x = sourceX - 10; cp1y = sourceY + dist;
                cp2x = targetX + 10; cp2y = targetY + dist;
                labelX = sourceX; labelY = sourceY + dist + 10;
                break;
            case 'left':
                cp1x = sourceX - dist; cp1y = sourceY - 10;
                cp2x = targetX - dist; cp2y = targetY + 10;
                labelX = sourceX - dist - 10; labelY = sourceY;
                break;
            default:
                cp1x = sourceX; cp1y = sourceY - dist;
                cp2x = targetX; cp2y = targetY - dist;
                labelX = sourceX; labelY = sourceY - dist;
        }
        edgePath = `M ${sourceX} ${sourceY} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${targetX} ${targetY}`;
    } else {
        [edgePath, labelX, labelY] = getBezierPath({
            sourceX,
            sourceY,
            sourcePosition,
            targetX,
            targetY,
            targetPosition,
        });
    }

    const diagramStyle = (data?.style as DiagramStyle) || {};
    const connectorType = diagramStyle.connector || 'solid';
    const strokeColor = diagramStyle.strokeColor || '#555';
    const strokeWidth = diagramStyle.strokeWidth || 1.5;

    let strokeDasharray: string | undefined = undefined;

    switch (connectorType) {
        case 'spaced':
            strokeDasharray = '8 8';
            break;
        case 'dashed':
            strokeDasharray = '3 3';
            break;
        default:
            strokeDasharray = undefined;
    }

    const renderLabel = () => {
        if (!label) return null;
        return (
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                        background: '#ffffff',
                        padding: '2px 6px',
                        borderRadius: 4,
                        fontSize: 10,
                        fontWeight: 500,
                        border: '1px solid #ddd',
                        pointerEvents: 'all',
                        zIndex: 10,
                        color: '#333',
                        ...labelStyle,
                        ...(diagramStyle.labelStyle || {}),
                    }}
                    className="nodrag nopan"
                >
                    {label}
                </div>
            </EdgeLabelRenderer>
        );
    }

    // Double Line Implementation
    if (connectorType === 'double') {
        return (
            <>
                <BaseEdge
                    id={id + '_outer'}
                    path={edgePath}
                    style={{
                        ...style,
                        stroke: strokeColor,
                        strokeWidth: strokeWidth * 3,
                        fill: 'none',
                    }}
                />
                <BaseEdge
                    id={id + '_inner'}
                    path={edgePath}
                    style={{
                        ...style,
                        stroke: '#fff',
                        strokeWidth: strokeWidth,
                        fill: 'none',
                    }}
                    markerEnd={markerEnd}
                    markerStart={markerStart}
                />
                {renderLabel()}
            </>
        );
    }

    return (
        <>
            <BaseEdge
                id={id}
                path={edgePath}
                style={{
                    ...style,
                    stroke: strokeColor,
                    strokeWidth: strokeWidth,
                    strokeDasharray,
                    fill: 'none',
                    opacity: diagramStyle.opacity || 1,
                    animation: diagramStyle.animated ? 'dashdraw 1s linear infinite' : undefined,
                }}
                markerEnd={markerEnd}
                markerStart={markerStart}
            />
            {renderLabel()}
        </>
    );
};
