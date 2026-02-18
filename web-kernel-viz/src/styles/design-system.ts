
import { LAYER_COLORS } from '@/lib/layer-colors';

export const DESIGN_SYSTEM = {
    node: {
        width: 220,
        height: 100,
        headerHeight: 32, // approx
        borderRadius: 8,
    },
    colors: {
        layers: {
            // Legacy numeric keys (L1–L4) for backward compat
            L1: { color: '#3b82f6', bg: '#eff6ff' },      // Blue
            L2: { color: '#a855f7', bg: '#faf5ff' },   // Purple
            L3: { color: '#22c55e', bg: '#f0fdf4' },     // Green
            L4: { color: '#f97316', bg: '#fff7ed' },       // Orange
            // Domain layers — delegated to single source of truth
            ...LAYER_COLORS,
            default: { color: '#64748b', bg: '#f8fafc' }, // Slate
        }
    },
    layout: {
        nodesep: 80,
        ranksep: 100,
    }
} as const;
