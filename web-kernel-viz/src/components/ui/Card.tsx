
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
                background: 'var(--bg-card)',
                border: `1px solid ${hovered && isClickable ? '#3b82f6' : 'var(--border)'}`,
                borderLeft: borderLeftColor ? `4px solid ${borderLeftColor}` : undefined,
                borderRadius: 8,
                cursor: isClickable ? 'pointer' : 'default',
                boxShadow: hovered && isClickable ? '0 2px 8px rgba(59,130,246,0.10)' : 'none',
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
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
            {sub && <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>{sub}</div>}
        </Card>
    );
}
