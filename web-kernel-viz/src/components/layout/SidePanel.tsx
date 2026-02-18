
import type { ReactNode } from 'react';

interface SidePanelProps {
    open: boolean;
    children: ReactNode;
}

export default function SidePanel({ open, children }: SidePanelProps) {
    return (
        <aside aria-label="Side panel" aria-hidden={!open} style={{
            width: open ? 320 : 0,
            minWidth: open ? 320 : 0,
            overflow: open ? 'visible' : 'hidden',
            transition: 'width 0.2s ease, min-width 0.2s ease',
            borderRight: open ? '1px solid var(--border)' : 'none',
            background: 'var(--secondary)',
            height: '100%',
        }}>
            <div style={{
                width: 320,
                padding: open ? '12px 14px' : 0,
                fontFamily: 'system-ui, -apple-system, sans-serif',
                fontSize: 13,
                color: 'var(--muted-foreground)',
                height: '100%',
                overflowY: 'auto',
            }}>
                {children}
            </div>
        </aside>
    );
}
