
import { useState, type ReactNode, type CSSProperties } from 'react';

interface CardProps {
    children: ReactNode;
    onClick?: () => void;
    borderLeftColor?: string;
    padding?: string;
    style?: CSSProperties;
}

export default function Card({ children, onClick, borderLeftColor, padding = '16px 20px', style }: CardProps) {
    const [hovered, setHovered] = useState(false);
    const isClickable = !!onClick;

    return (
        <div
            onClick={onClick}
            onKeyDown={isClickable ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(); } } : undefined}
            role={isClickable ? 'button' : undefined}
            tabIndex={isClickable ? 0 : undefined}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                padding,
                background: 'var(--card)',
                border: `1px solid ${hovered && isClickable ? 'var(--primary)' : 'var(--border)'}`,
                borderLeft: borderLeftColor ? `4px solid ${borderLeftColor}` : undefined,
                borderRadius: 'var(--radius)',
                cursor: isClickable ? 'pointer' : 'default',
                boxShadow: hovered && isClickable ? '0 2px 8px var(--shadow-sm)' : 'none',
                transition: 'border-color 0.15s, box-shadow 0.15s',
                ...style,
            }}
        >
            {children}
        </div>
    );
}

interface StatCardProps {
    label: string;
    value: string | number;
    sub?: string;
    onClick?: () => void;
}

export function StatCard({ label, value, sub, onClick }: StatCardProps) {
    return (
        <Card onClick={onClick} style={{ flex: 1, minWidth: 180 }}>
            <div style={{ fontSize: 12, color: 'var(--muted-foreground)', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--foreground)' }}>{value}</div>
            {sub && <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 2 }}>{sub}</div>}
        </Card>
    );
}
