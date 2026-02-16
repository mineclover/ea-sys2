
import { Panel } from '@xyflow/react';

interface TraversalPanelProps {
    selectedNode: string | null;
    reachableCount: number;
    onClear: () => void;
}

export default function TraversalPanel({ selectedNode, reachableCount, onClear }: TraversalPanelProps) {
    if (!selectedNode) return null;

    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '12px 16px',
                boxShadow: `0 4px 6px -1px var(--shadow-lg)`,
                minWidth: 200,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
                    Traversal
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {selectedNode}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', marginBottom: 8 }}>
                    {reachableCount} reachable element{reachableCount !== 1 ? 's' : ''}
                </div>
                <button
                    onClick={onClear}
                    style={{
                        fontSize: 12,
                        padding: '4px 12px',
                        border: '1px solid var(--border-strong)',
                        borderRadius: 4,
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-primary)',
                        cursor: 'pointer',
                    }}
                >
                    Clear
                </button>
            </div>
        </Panel>
    );
}
