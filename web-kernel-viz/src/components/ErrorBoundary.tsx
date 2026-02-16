
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
    state: State = { hasError: false, error: null };

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error('ErrorBoundary caught:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div role="alert" style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 40,
                    fontFamily: 'system-ui, -apple-system, sans-serif',
                }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
                        Something went wrong
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, maxWidth: 480, textAlign: 'center' }}>
                        {this.state.error?.message || 'An unexpected error occurred.'}
                    </div>
                    <button
                        onClick={() => this.setState({ hasError: false, error: null })}
                        style={{
                            padding: '8px 20px',
                            fontSize: 13,
                            fontWeight: 600,
                            border: '1px solid var(--accent)',
                            borderRadius: 6,
                            background: 'var(--accent)',
                            color: 'var(--bg-card)',
                            cursor: 'pointer',
                        }}
                    >
                        Try Again
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
