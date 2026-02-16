
import { useEffect, useRef, type ReactNode } from 'react';

interface DetailSlideOverProps {
    open: boolean;
    onClose: () => void;
    title?: string;
    children: ReactNode;
}

export default function DetailSlideOver({ open, onClose, title, children }: DetailSlideOverProps) {
    const panelRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handler);
        return () => document.removeEventListener('keydown', handler);
    }, [open, onClose]);

    useEffect(() => {
        if (open && panelRef.current) {
            panelRef.current.focus();
        }
    }, [open]);

    return (
        <div
            ref={panelRef}
            role="dialog"
            aria-modal={open}
            aria-label={title || 'Detail panel'}
            tabIndex={-1}
            style={{
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
                background: 'var(--bg-primary)',
                borderLeft: '1px solid var(--border)',
                boxShadow: open ? '-4px 0 12px rgba(0,0,0,0.08)' : 'none',
                display: 'flex',
                flexDirection: 'column',
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                {/* Header */}
                <div style={{
                    padding: '14px 16px',
                    borderBottom: '1px solid var(--border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                        {title || 'Detail'}
                    </span>
                    <button
                        onClick={onClose}
                        aria-label="Close detail panel"
                        style={{
                            width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-card)',
                            cursor: 'pointer', fontSize: 14, color: 'var(--text-muted)',
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
                    color: 'var(--text-secondary)',
                }}>
                    {children}
                </div>
            </div>
        </div>
    );
}
