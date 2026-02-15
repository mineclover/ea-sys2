
import type { ReactNode } from 'react';

interface SidePanelProps {
    open: boolean;
    children: ReactNode;
}

export default function SidePanel({ open, children }: SidePanelProps) {
    return (
        <div style={{
            width: open ? 280 : 0,
            minWidth: open ? 280 : 0,
            overflow: 'hidden',
            transition: 'width 0.2s ease, min-width 0.2s ease',
            borderRight: open ? '1px solid #e2e8f0' : 'none',
            background: '#fafbfc',
            height: '100%',
        }}>
            <div style={{
                width: 280,
                padding: open ? '12px 14px' : 0,
                fontFamily: 'system-ui, -apple-system, sans-serif',
                fontSize: 13,
                color: '#475569',
                height: '100%',
                overflowY: 'auto',
            }}>
                {children}
            </div>
        </div>
    );
}
