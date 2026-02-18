
import { useGovernanceDashboard } from '@/api/hooks';
import { ErrorBanner, LoadingSpinner } from '@/components/ui';
import { PageHeader } from '@/components/layout';

export default function FrameworksView() {
    const { data: dash, isLoading, isError, refetch } = useGovernanceDashboard();

    if (isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <ErrorBanner
                    message="Unable to load frameworks — API server may be unavailable."
                    onRetry={() => refetch()}
                />
            </div>
        );
    }

    if (isLoading || !dash) {
        return <LoadingSpinner message="Loading frameworks..." />;
    }

    const frameworks = dash.frameworks;

    if (frameworks.length === 0) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: 'var(--muted-foreground)' }}>
                No frameworks registered.
            </div>
        );
    }

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <PageHeader metaKey="status.frameworks" subtitle={`${frameworks.length} frameworks registered`} />

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
                {frameworks.map((fw) => (
                    <div key={fw.name} style={{
                        padding: '16px 18px', border: '1px solid var(--border)', borderRadius: 8,
                        background: 'var(--card)',
                    }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--foreground)', marginBottom: 2 }}>{fw.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 12 }}>v{fw.version}</div>
                        <div style={{ display: 'flex', gap: 12 }}>
                            <StatChip label="Entities" value={fw.element_count} />
                            <StatChip label="Relations" value={fw.relation_count} />
                            <StatChip label="Rules" value={fw.rule_count} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function StatChip({ label, value }: { label: string; value: number }) {
    return (
        <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--foreground)' }}>{value}</div>
            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
        </div>
    );
}
