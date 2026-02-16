
interface LoadingSpinnerProps {
    message?: string;
    fullHeight?: boolean;
}

export default function LoadingSpinner({ message = 'Loading...', fullHeight = true }: LoadingSpinnerProps) {
    return (
        <div role="status" aria-live="polite" style={{
            ...(fullHeight ? { flex: 1, height: '100%' } : {}),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            fontSize: 14,
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            {message}
        </div>
    );
}
