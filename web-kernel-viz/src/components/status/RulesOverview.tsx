
import { useEffect, useState, useCallback } from 'react';
import { fetchKernelRules } from '@/api/client';
import type { KernelRulesResponse, KernelRuleSummary } from '@/api/types';

export default function RulesOverview() {
    const [data, setData] = useState<KernelRulesResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
    const [groupRules, setGroupRules] = useState<KernelRuleSummary[] | null>(null);
    const [groupLoading, setGroupLoading] = useState(false);

    const load = useCallback(() => {
        setError(null);
        fetchKernelRules()
            .then(setData)
            .catch(() => setError('unavailable'));
    }, []);

    useEffect(() => { load(); }, [load]);

    const toggleGroup = useCallback((groupName: string) => {
        if (expandedGroup === groupName) {
            setExpandedGroup(null);
            setGroupRules(null);
            return;
        }
        setExpandedGroup(groupName);
        setGroupRules(null);
        setGroupLoading(true);
        fetchKernelRules({ group: groupName })
            .then((res) => setGroupRules(res.rules || []))
            .catch(() => setGroupRules([]))
            .finally(() => setGroupLoading(false));
    }, [expandedGroup]);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                    background: '#f8fafc', fontSize: 12, color: '#64748b',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load kernel rules — API server may be unavailable.
                    <button onClick={load} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid #cbd5e1', borderRadius: 4,
                        background: '#fff', color: '#475569', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    if (!data) {
        return <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>Loading rules…</div>;
    }

    const groups = data.groups || [];
    const explicitCount = groups.filter((g) => !g.name.startsWith('fallback')).reduce((s, g) => s + g.count, 0);
    const fallbackCount = groups.filter((g) => g.name.startsWith('fallback')).reduce((s, g) => s + g.count, 0);

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' }}>Kernel Rules</h2>
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
                                padding: '12px 14px', border: '1px solid #e2e8f0', borderRadius: 8,
                                background: expandedGroup === g.name ? '#eff6ff' : '#fff',
                                cursor: 'pointer',
                            }}
                        >
                            <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{g.name}</div>
                            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{g.count} rules</div>
                        </button>
                        {expandedGroup === g.name && (
                            <div style={{ marginTop: 4, border: '1px solid #e2e8f0', borderRadius: 6, overflow: 'hidden' }}>
                                {groupLoading ? (
                                    <div style={{ padding: 12, fontSize: 12, color: '#94a3b8' }}>Loading…</div>
                                ) : groupRules && groupRules.length > 0 ? (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                <th style={thStyle}>Source</th>
                                                <th style={thStyle}>Target</th>
                                                <th style={thStyle}>Relation</th>
                                                <th style={thStyle}>Valid</th>
                                                <th style={thStyle}>Pri</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {groupRules.map((r) => (
                                                <tr key={r.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                                    <td style={tdStyle}>{r.source}</td>
                                                    <td style={tdStyle}>{r.target}</td>
                                                    <td style={tdStyle}>{r.relation}</td>
                                                    <td style={tdStyle}>
                                                        <span style={{
                                                            padding: '1px 5px', fontSize: 10, fontWeight: 600, borderRadius: 3,
                                                            background: r.valid ? '#dcfce7' : '#fee2e2',
                                                            color: r.valid ? '#166534' : '#991b1b',
                                                        }}>{r.valid ? 'ALLOW' : 'DENY'}</span>
                                                    </td>
                                                    <td style={{ ...tdStyle, color: '#94a3b8' }}>{r.priority}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div style={{ padding: 12, fontSize: 12, color: '#94a3b8' }}>No rules</div>
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
            padding: '8px 14px', border: '1px solid #e2e8f0', borderRadius: 6,
            background: '#f8fafc', minWidth: 80,
        }}>
            <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b' }}>{value}</div>
        </div>
    );
}

const thStyle: React.CSSProperties = {
    textAlign: 'left', padding: '5px 6px', fontSize: 10, fontWeight: 600,
    color: '#94a3b8', textTransform: 'uppercase',
};

const tdStyle: React.CSSProperties = {
    padding: '5px 6px', fontSize: 11, color: '#1e293b',
};
