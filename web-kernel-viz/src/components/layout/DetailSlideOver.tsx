
import type { ReactNode } from 'react';

interface DetailSlideOverProps {
    open: boolean;
    onClose: () => void;
    title?: string;
    children: ReactNode;
}

export default function DetailSlideOver({ open, onClose, title, children }: DetailSlideOverProps) {
    return (
        <div style={{
            position: 'fixed',
            top: 0,
            right: 0,
            bottom: 0,
            width: open ? 380 : 0,
            overflow: 'hidden',
            transition: 'width 0.25s ease',
            zIndex: 200,
            pointerEvents: open ? 'auto' : 'none',
        }}>
            {/* Backdrop */}
            {open && (
                <div
                    onClick={onClose}
                    style={{
                        position: 'fixed',
                        top: 0, left: 0, right: 380, bottom: 0,
                        background: 'rgba(0,0,0,0.05)',
                        zIndex: -1,
                    }}
                />
            )}

            {/* Panel */}
            <div style={{
                width: 380,
                height: '100%',
                background: '#fff',
                borderLeft: '1px solid #e2e8f0',
                boxShadow: open ? '-4px 0 12px rgba(0,0,0,0.08)' : 'none',
                display: 'flex',
                flexDirection: 'column',
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                {/* Header */}
                <div style={{
                    padding: '14px 16px',
                    borderBottom: '1px solid #e2e8f0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: '#1e293b' }}>
                        {title || 'Detail'}
                    </span>
                    <button
                        onClick={onClose}
                        style={{
                            width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '1px solid #e2e8f0', borderRadius: 4, background: '#fff',
                            cursor: 'pointer', fontSize: 14, color: '#94a3b8',
                        }}
                    >
                        ✕
                    </button>
                </div>

                {/* Content */}
                <div style={{
                    flex: 1,
                    overflowY: 'auto',
                    padding: '16px',
                    fontSize: 13,
                    color: '#475569',
                }}>
                    {children}
                </div>
            </div>
        </div>
    );
}
