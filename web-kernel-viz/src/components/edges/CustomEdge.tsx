import {
    type EdgeProps,
    getBezierPath,
    BaseEdge,
    EdgeLabelRenderer,
} from '@xyflow/react';
import { type DiagramStyle } from '../../types/diagram';

type EdgeTypeTag =
    | 'intra_layer'
    | 'runtime_chain'
    | 'model_port_bridge'
    | 'governance_oversight'
    | 'cross_layer'
    | 'structural'
    | 'behavioral'
    | 'inheritance'
    | 'm2_rule'
    | 'm2_rule_summary'
    | 'm2_blueprint'
    | 'm2_blueprint_summary';

interface CustomEdgeData {
    style?: DiagramStyle;
    highlighted?: boolean;
    relation?: string;
    priority?: number;
    kernelLayer?: string;
    edgeType?: EdgeTypeTag;
    labelDetail?: string;
}

function defaultEdgeColor(edgeData: CustomEdgeData, fallback: string): string {
    if (edgeData.edgeType === 'runtime_chain') return 'var(--color-layer-kernel)';
    if (edgeData.edgeType === 'model_port_bridge') return 'var(--status-warning-text)';
    if (edgeData.edgeType === 'governance_oversight') return 'var(--destructive)';
    if (edgeData.edgeType === 'cross_layer') return 'var(--status-indigo-text)';
    return fallback;
}

function edgeTypeChip(edgeType: EdgeTypeTag | undefined): string | null {
    if (!edgeType) return null;
    switch (edgeType) {
        case 'runtime_chain':
            return 'chain';
        case 'model_port_bridge':
            return 'bridge';
        case 'governance_oversight':
            return 'oversight';
        case 'cross_layer':
            return 'x-layer';
        case 'behavioral':
            return 'behavior';
        case 'structural':
            return 'struct';
        case 'inheritance':
            return 'extends';
        case 'm2_blueprint':
            return 'M2';
        case 'm2_blueprint_summary':
            return 'M2 sum';
        case 'm2_rule_summary':
            return 'rule sum';
        case 'm2_rule':
            return 'M2 rule';
        default:
            return null;
    }
}

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
    selected,
}: EdgeProps) => {
    const edgeData = (data || {}) as CustomEdgeData;
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

    const diagramStyle = edgeData.style || {};
    const highlighted = !!edgeData.highlighted || !!selected;
    const inferredConnector =
        diagramStyle.connector
        || (edgeData.kernelLayer === 'L3' ? 'dashed' : undefined)
        || (edgeData.edgeType === 'runtime_chain' ? 'dashed' : undefined)
        || 'solid';
    const priority = typeof edgeData.priority === 'number' ? Math.max(0, Math.min(100, edgeData.priority)) : null;
    const priorityBoost = priority == null ? 0 : (priority / 100) * 0.9;
    const baseStroke = diagramStyle.strokeColor || 'var(--muted-foreground)';
    const strokeColor = highlighted ? 'var(--primary)' : defaultEdgeColor(edgeData, baseStroke);
    const strokeWidth = highlighted ? 2.8 : (diagramStyle.strokeWidth || 1.5) + priorityBoost;
    const shouldAnimate =
        !!diagramStyle.animated
        || edgeData.edgeType === 'runtime_chain'
        || edgeData.edgeType === 'behavioral'
        || edgeData.kernelLayer === 'L3';

    let strokeDasharray: string | undefined = undefined;
    let strokeLinecap: 'round' | 'butt' = 'butt';

    switch (inferredConnector) {
        case 'spaced':
            strokeDasharray = '9 8';
            break;
        case 'dashed':
            strokeDasharray = '6 5';
            break;
        case 'wave':
            strokeDasharray = '1 9';
            strokeLinecap = 'round';
            break;
        default:
            strokeDasharray = undefined;
    }

    const edgeTokens: string[] = [];
    if (edgeData.kernelLayer) edgeTokens.push(edgeData.kernelLayer);
    if (priority != null) edgeTokens.push(`P${priority}`);
    const typeChip = edgeTypeChip(edgeData.edgeType);
    if (typeChip) edgeTokens.push(typeChip);
    if (edgeData.labelDetail) edgeTokens.push(edgeData.labelDetail);
    const fallbackLabel = (!label && (highlighted || (priority != null && priority >= 85))) ? edgeData.relation : undefined;
    const renderedLabel = label || fallbackLabel;

    const renderLabel = () => {
        if (!renderedLabel) return null;
        return (
            <EdgeLabelRenderer>
                <div
                    style={{
                        position: 'absolute',
                        transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
                        background: 'var(--card)',
                        padding: edgeTokens.length ? '3px 7px' : '2px 6px',
                        borderRadius: 4,
                        fontSize: 10,
                        fontWeight: 600,
                        border: `1px solid ${strokeColor}`,
                        pointerEvents: 'all',
                        zIndex: 10,
                        color: 'var(--foreground)',
                        boxShadow: '0 1px 2px var(--shadow-sm)',
                        ...labelStyle,
                        ...(diagramStyle.labelStyle || {}),
                    }}
                    className="nodrag nopan"
                >
                    <div style={{ display: 'grid', gap: edgeTokens.length ? 2 : 0 }}>
                        <span>{renderedLabel}</span>
                        {edgeTokens.length > 0 && (
                            <span style={{ fontSize: 9, color: 'var(--muted-foreground)', fontWeight: 600 }}>
                                {edgeTokens.join(' · ')}
                            </span>
                        )}
                    </div>
                </div>
            </EdgeLabelRenderer>
        );
    }

    // Double Line Implementation
    if (inferredConnector === 'double') {
        return (
            <>
                <BaseEdge
                    id={id + '_outer'}
                    path={edgePath}
                    style={{
                        ...style,
                        stroke: strokeColor,
                        strokeWidth: strokeWidth * 3,
                        color: strokeColor,
                        fill: 'none',
                        opacity: diagramStyle.opacity || 1,
                    }}
                />
                <BaseEdge
                    id={id + '_inner'}
                    path={edgePath}
                    style={{
                        ...style,
                        stroke: 'var(--card)',
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

    const showHalo =
        highlighted
        || edgeData.edgeType === 'runtime_chain'
        || (priority != null && priority >= 80);

    return (
        <>
            {showHalo && (
                <BaseEdge
                    id={id + '_halo'}
                    path={edgePath}
                    style={{
                        stroke: strokeColor,
                        strokeWidth: strokeWidth + 5,
                        fill: 'none',
                        opacity: highlighted ? 0.22 : 0.14,
                    }}
                />
            )}
            <BaseEdge
                id={id}
                path={edgePath}
                style={{
                    ...style,
                    stroke: strokeColor,
                    strokeWidth: strokeWidth,
                    strokeDasharray,
                    strokeLinecap,
                    fill: 'none',
                    color: strokeColor,
                    opacity: diagramStyle.opacity || 1,
                    animation: shouldAnimate ? 'edge-dash-flow 1.25s linear infinite' : undefined,
                }}
                markerEnd={markerEnd}
                markerStart={markerStart}
            />
            {renderLabel()}
        </>
    );
};
