
interface EmptyStateProps {
    message?: string;
    icon?: string;
}

export default function EmptyState({ message = 'No data found.', icon = '\u2205' }: EmptyStateProps) {
    return (
        <div role="status" style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 40,
            color: 'var(--text-muted)',
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>{icon}</div>
            <div style={{ fontSize: 13 }}>{message}</div>
        </div>
    );
}
