
import { useFlowLogic } from '@/api/hooks';

interface FlowLogicViewerProps {
    anchorId: string;
    onClose: () => void;
}

export default function FlowLogicViewer({ anchorId, onClose }: FlowLogicViewerProps) {
    const { data, isLoading, error } = useFlowLogic(anchorId);

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            right: 0,
            width: 480,
            height: '100vh',
            background: 'var(--bg-card)',
            boxShadow: '-4px 0 12px var(--shadow-lg)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
            }}>
                <h2 style={{
                    margin: 0,
                    fontSize: 16,
                    fontWeight: 600,
                    color: 'var(--text-primary)',
                }}>
                    Flow Logic: {anchorId}
                </h2>
                <button
                    onClick={onClose}
                    style={{
                        border: 'none',
                        background: 'transparent',
                        cursor: 'pointer',
                        fontSize: 20,
                        color: 'var(--text-secondary)',
                        padding: 4,
                    }}
                >
                    ×
                </button>
            </div>

            <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: 20,
            }}>
                {isLoading && (
                    <div style={{
                        color: 'var(--text-secondary)',
                        fontSize: 14,
                        textAlign: 'center',
                        marginTop: 40,
                    }}>
                        Loading flow logic...
                    </div>
                )}

                {error && (
                    <div style={{
                        padding: 12,
                        background: '#fef2f2',
                        border: '1px solid #fecaca',
                        borderRadius: 6,
                        color: 'var(--error-text)',
                        fontSize: 13,
                    }}>
                        Error loading flow logic: {error instanceof Error ? error.message : 'Unknown error'}
                    </div>
                )}

                {data && (
                    <div>
                        {Object.entries(data).map(([key, value]) => (
                            <div key={key} style={{
                                marginBottom: 16,
                                padding: 12,
                                background: 'var(--bg-secondary)',
                                borderRadius: 6,
                                border: '1px solid var(--border)',
                            }}>
                                <div style={{
                                    fontSize: 11,
                                    fontWeight: 700,
                                    color: 'var(--text-muted)',
                                    textTransform: 'uppercase',
                                    marginBottom: 6,
                                }}>
                                    {key}
                                </div>
                                <div style={{
                                    fontSize: 13,
                                    color: 'var(--text-primary)',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word',
                                }}>
                                    {typeof value === 'object' && value !== null
                                        ? JSON.stringify(value, null, 2)
                                        : String(value)}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
