
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { memo } from 'react';
import { DESIGN_SYSTEM } from '@/styles/design-system';
import type { NodeStyle } from '@/types/diagram';

export interface HandleConfig {
    id: string;
    offset: number;
}

export type DynamicNodeData = {
    label: string;
    description?: string;
    handles?: {
        top?: HandleConfig[];
        right?: HandleConfig[];
        bottom?: HandleConfig[];
        left?: HandleConfig[];
    }
    layer?: string;
    style?: NodeStyle;
    [key: string]: unknown;
};

export type DynamicNodeType = Node<DynamicNodeData, 'dynamic'>;

const HandleGroup = ({
    configs,
    position,
    accentColor
}: {
    configs?: HandleConfig[],
    position: Position,
    accentColor?: string
}) => {
    if (!configs || configs.length === 0) return null;

    return (
        <>
            {configs.map((handle) => (
                <Handle
                    key={handle.id}
                    id={handle.id}
                    type={handle.id.startsWith('t-') ? 'target' : 'source'}
                    position={position}
                    style={{
                        left: (position === Position.Top || position === Position.Bottom) ? `${handle.offset}%` : undefined,
                        top: (position === Position.Left || position === Position.Right) ? `${handle.offset}%` : undefined,
                        background: 'var(--bg-card)',
                        border: `2px solid ${accentColor}`,
                        width: 8,
                        height: 8,
                        zIndex: 50,
                    }}
                />
            ))}
        </>
    );
};

const defaultLayer = DESIGN_SYSTEM.colors.layers.default;

export const DynamicNode = memo(({ data, selected }: NodeProps<DynamicNodeType>) => {
    // Type-safe generic lookup or fallback
    const layerKey = (data.layer as keyof typeof DESIGN_SYSTEM.colors.layers) || 'default';
    const config = DESIGN_SYSTEM.colors.layers[layerKey] || defaultLayer;

    // Applying custom styles if present
    const customStyle = data.style || {};
    const highlighted = !!(data as Record<string, unknown>).highlighted;
    const borderColor = selected ? config.color : highlighted ? config.color : (customStyle.borderColor || 'var(--border)');
    const borderRadius = customStyle.shape === 'circle' ? '50%' :
        customStyle.shape === 'rounded' ? 20 :
            DESIGN_SYSTEM.node.borderRadius;

    const glowShadow = highlighted
        ? `0 0 12px 4px ${config.color}60, 0 0 0 2px ${config.color}`
        : undefined;

    return (
        <div style={{
            minWidth: customStyle.width || (DESIGN_SYSTEM.node.width - 20),
            minHeight: customStyle.height,
            borderRadius: borderRadius,
            background: customStyle.backgroundColor || 'var(--bg-card)',
            boxShadow: glowShadow || (selected ? `0 0 0 2px ${config.color}, 0 4px 6px -1px var(--shadow-lg)` : `0 1px 3px 0 var(--shadow-lg), 0 1px 2px -1px var(--shadow-lg)`),
            border: `1px solid ${borderColor}`,
            borderWidth: customStyle.borderWidth || 1,
            transition: 'all 0.2s ease',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            overflow: 'hidden',
        }}>
            {/* Header */}
            <div style={{
                padding: '6px 12px',
                background: config.bg,
                borderBottom: `1px solid ${config.color}30`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}>
                <span style={{
                    fontSize: 10,
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: config.color,
                }}>
                    {data.layer || 'ENTITY'}
                </span>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: config.color }} />
            </div>

            {/* Body */}
            <div style={{
                padding: '8px 12px',
                minHeight: 40,
                display: 'flex',
                flexDirection: 'column',
                gap: data.description ? 4 : 0,
            }}>
                <span style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                    lineHeight: 1.3,
                }}>
                    {data.label}
                </span>
                {data.description && (
                    <span style={{
                        fontSize: 10,
                        color: 'var(--text-secondary)',
                        lineHeight: 1.4,
                        maxWidth: 200,
                        overflow: 'hidden',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                    }}>
                        {data.description}
                    </span>
                )}
            </div>

            <HandleGroup configs={data.handles?.top} position={Position.Top} accentColor={config.color} />
            <HandleGroup configs={data.handles?.right} position={Position.Right} accentColor={config.color} />
            <HandleGroup configs={data.handles?.bottom} position={Position.Bottom} accentColor={config.color} />
            <HandleGroup configs={data.handles?.left} position={Position.Left} accentColor={config.color} />
        </div>
    );
});
