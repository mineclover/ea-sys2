
export const DESIGN_SYSTEM = {
    node: {
        width: 220,
        height: 100,
        headerHeight: 32, // approx
        borderRadius: 8,
    },
    colors: {
        layers: {
            L1: { color: '#3b82f6', bg: '#eff6ff' },      // Blue
            L2: { color: '#a855f7', bg: '#faf5ff' },   // Purple
            L3: { color: '#22c55e', bg: '#f0fdf4' },     // Green
            L4: { color: '#f97316', bg: '#fff7ed' },       // Orange
            // Domain layers (6-layer EA architecture)
            Infra: { color: '#64748b', bg: '#f8fafc' },       // Slate
            Governance: { color: '#ef4444', bg: '#fef2f2' },  // Red
            Decision: { color: '#a855f7', bg: '#faf5ff' },    // Purple
            Needs: { color: '#06b6d4', bg: '#ecfeff' },       // Cyan
            Kernel: { color: '#3b82f6', bg: '#eff6ff' },      // Blue
            Flow: { color: '#22c55e', bg: '#f0fdf4' },        // Green
            default: { color: '#64748b', bg: '#f8fafc' }, // Slate
        }
    },
    layout: {
        nodesep: 80,
        ranksep: 100,
    }
} as const;
