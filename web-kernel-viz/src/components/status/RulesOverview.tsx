
import { useState } from 'react';
import { useKernelRules } from '@/api/hooks';
import { ErrorBanner, LoadingSpinner } from '@/components/ui';

export default function RulesOverview() {
    const [expandedGroup, setExpandedGroup] = useState<string | null>(null);

    const rulesQuery = useKernelRules();
    const groupRulesQuery = useKernelRules(
        expandedGroup ? { group: expandedGroup } : undefined,
    );

    const toggleGroup = (groupName: string) => {
        setExpandedGroup((prev) => (prev === groupName ? null : groupName));
    };

    if (rulesQuery.isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <ErrorBanner
                    message="Unable to load kernel rules — API server may be unavailable."
                    onRetry={() => rulesQuery.refetch()}
                />
            </div>
        );
    }

    if (rulesQuery.isLoading || !rulesQuery.data) {
        return <LoadingSpinner message="Loading rules..." />;
    }

    const data = rulesQuery.data;
    const groups = data.groups || [];
    const explicitCount = groups.filter((g) => !g.name.startsWith('fallback')).reduce((s, g) => s + g.count, 0);
    const fallbackCount = groups.filter((g) => g.name.startsWith('fallback')).reduce((s, g) => s + g.count, 0);

    const groupRules = expandedGroup ? (groupRulesQuery.data?.rules || null) : null;
    const groupLoading = expandedGroup ? groupRulesQuery.isLoading : false;

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Kernel Rules</h2>
                <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                    <Stat label="Total" value={data.total} />
                    <Stat label="Explicit" value={explicitCount} />
                    <Stat label="Fallback" value={fallbackCount} />
                    <Stat label="Groups" value={groups.length} />
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
                {groups.map((g) => (
                    <div key={g.name}>
                        <button
                            onClick={() => toggleGroup(g.name)}
                            style={{
                                width: '100%', textAlign: 'left',
                                padding: '12px 14px', border: '1px solid var(--border)', borderRadius: 8,
                                background: expandedGroup === g.name ? 'var(--accent-bg)' : 'var(--bg-card)',
                                cursor: 'pointer',
                            }}
                        >
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{g.name}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{g.count} rules</div>
                        </button>
                        {expandedGroup === g.name && (
                            <div style={{ marginTop: 4, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
                                {groupLoading ? (
                                    <div style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>Loading...</div>
                                ) : groupRules && groupRules.length > 0 ? (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                <th style={thStyle}>Source</th>
                                                <th style={thStyle}>Target</th>
                                                <th style={thStyle}>Relation</th>
                                                <th style={thStyle}>Valid</th>
                                                <th style={thStyle}>Pri</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {groupRules.map((r) => (
                                                <tr key={r.id} style={{ borderBottom: '1px solid var(--bg-hover)' }}>
                                                    <td style={tdStyle}>{r.source}</td>
                                                    <td style={tdStyle}>{r.target}</td>
                                                    <td style={tdStyle}>{r.relation}</td>
                                                    <td style={tdStyle}>
                                                        <span style={{
                                                            padding: '1px 5px', fontSize: 10, fontWeight: 600, borderRadius: 3,
                                                            background: r.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                                                            color: r.valid ? 'var(--success-text)' : 'var(--error-text)',
                                                        }}>{r.valid ? 'ALLOW' : 'DENY'}</span>
                                                    </td>
                                                    <td style={{ ...tdStyle, color: 'var(--text-muted)' }}>{r.priority}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div style={{ padding: 12, fontSize: 12, color: 'var(--text-muted)' }}>No rules</div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

function Stat({ label, value }: { label: string; value: number }) {
    return (
        <div style={{
            padding: '8px 14px', border: '1px solid var(--border)', borderRadius: 6,
            background: 'var(--bg-secondary)', minWidth: 80,
        }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
        </div>
    );
}

const thStyle: React.CSSProperties = {
    textAlign: 'left', padding: '5px 6px', fontSize: 10, fontWeight: 600,
    color: 'var(--text-muted)', textTransform: 'uppercase',
};

const tdStyle: React.CSSProperties = {
    padding: '5px 6px', fontSize: 11, color: 'var(--text-primary)',
};
