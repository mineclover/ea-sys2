/**
 * Single source of truth for EA layer colors.
 * All layer-specific color references should use this module.
 */

export const LAYER_COLORS = {
    Infra:      { color: '#64748b', bg: '#f8fafc' },
    Governance: { color: '#ef4444', bg: '#fef2f2' },
    Decision:   { color: '#a855f7', bg: '#faf5ff' },
    Needs:      { color: '#06b6d4', bg: '#ecfeff' },
    Kernel:     { color: '#3b82f6', bg: '#eff6ff' },
    Flow:       { color: '#22c55e', bg: '#f0fdf4' },
} as const;

export type LayerName = keyof typeof LAYER_COLORS;

const LAYER_LOOKUP = new Map<string, { color: string; bg: string }>(
    Object.entries(LAYER_COLORS).map(([k, v]) => [k.toLowerCase(), v]),
);

const DEFAULT_LAYER = { color: '#64748b', bg: '#f8fafc' } as const;

/** Case-insensitive layer color lookup. */
export function getLayerColor(key: string): { color: string; bg: string } {
    return LAYER_LOOKUP.get(key.toLowerCase()) ?? DEFAULT_LAYER;
}
