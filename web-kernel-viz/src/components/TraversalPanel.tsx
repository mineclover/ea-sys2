
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
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: 8,
                padding: '12px 16px',
                boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                minWidth: 200,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
                    Traversal
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 4 }}>
                    {selectedNode}
                </div>
                <div style={{ fontSize: 12, color: '#475569', marginBottom: 8 }}>
                    {reachableCount} reachable element{reachableCount !== 1 ? 's' : ''}
                </div>
                <button
                    onClick={onClear}
                    style={{
                        fontSize: 12,
                        padding: '4px 12px',
                        border: '1px solid #cbd5e1',
                        borderRadius: 4,
                        background: '#f8fafc',
                        color: '#475569',
                        cursor: 'pointer',
                    }}
                >
                    Clear
                </button>
            </div>
        </Panel>
    );
}
