
interface ErrorBannerProps {
    message?: string;
    onRetry?: () => void;
}

export default function ErrorBanner({
    message = 'Unable to load data — API server may be unavailable.',
    onRetry,
}: ErrorBannerProps) {
    return (
        <div role="alert" style={{
            padding: '14px 16px',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            background: 'var(--secondary)',
            fontSize: 12,
            color: 'var(--muted-foreground)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
        }}>
            <span>{message}</span>
            {onRetry && (
                <button onClick={onRetry} style={{
                    padding: '4px 12px',
                    fontSize: 11,
                    fontWeight: 600,
                    border: '1px solid var(--border)',
                    borderRadius: 4,
                    background: 'var(--card)',
                    color: 'var(--muted-foreground)',
                    cursor: 'pointer',
                    flexShrink: 0,
                }}>
                    Retry
                </button>
            )}
        </div>
    );
}
