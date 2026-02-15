
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { fetchGovernanceRules, approveRule } from '@/api/client';
import type { GovernanceRuleItem } from '@/api/types';

interface RuleLifecycleViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

const STATE_COLORS: Record<string, { bg: string; color: string }> = {
    DRAFT: { bg: '#fef9c3', color: '#854d0e' },
    SUBMITTED: { bg: '#e0e7ff', color: '#3730a3' },
    APPROVED: { bg: '#dcfce7', color: '#166534' },
    ACTIVE: { bg: '#dbeafe', color: '#1e40af' },
    DEPRECATED: { bg: '#f1f5f9', color: '#64748b' },
};

export default function RuleLifecycleView({ onShowDetail }: RuleLifecycleViewProps) {
    const [rules, setRules] = useState<GovernanceRuleItem[]>([]);
    const [stateFilter, setStateFilter] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(() => {
        setLoading(true);
        setError(null);
        fetchGovernanceRules(stateFilter || undefined)
            .then((data) => { setRules(data); setLoading(false); })
            .catch(() => { setError('unavailable'); setLoading(false); });
    }, [stateFilter]);

    useEffect(() => { load(); }, [load]);

    const onApprove = useCallback((ruleId: string) => {
        approveRule(ruleId)
            .then((res) => {
                onShowDetail(ruleId, <div>Rule <strong>{res.rule_id}</strong> approved.</div>);
                load();
            })
            .catch((err) => {
                onShowDetail('Approve Error', <div style={{ color: '#ef4444' }}>{String(err)}</div>);
            });
    }, [onShowDetail, load]);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                    background: '#f8fafc', fontSize: 12, color: '#64748b',
                    display: 'flex', alignItems: 'center', gap: 10,
                }}>
                    <span>Unable to load governance rules — API server may be unavailable.</span>
                    <button onClick={load} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid #cbd5e1', borderRadius: 4,
                        background: '#fff', color: '#475569', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif', overflow: 'auto' }}>
            {/* Filter bar */}
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #e2e8f0', display: 'flex', gap: 8, alignItems: 'center', background: '#fafbfc' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>State</span>
                <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}
                    style={{ padding: '4px 8px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4 }}>
                    <option value="">All</option>
                    <option value="DRAFT">Draft</option>
                    <option value="SUBMITTED">Submitted</option>
                    <option value="APPROVED">Approved</option>
                    <option value="ACTIVE">Active</option>
                    <option value="DEPRECATED">Deprecated</option>
                </select>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>{rules.length} rules</span>
            </div>

            {/* Rules list */}
            <div style={{ padding: 16 }}>
                {loading && <div style={{ color: '#94a3b8' }}>Loading...</div>}
                {!loading && rules.length === 0 && (
                    <div style={{ color: '#94a3b8', fontSize: 13 }}>No rules found.</div>
                )}
                {!loading && rules.map((r) => {
                    const sc = STATE_COLORS[r.state] || STATE_COLORS.DRAFT;
                    return (
                        <div key={r.id} style={{
                            padding: '12px 14px', marginBottom: 8, border: '1px solid #e2e8f0',
                            borderRadius: 8, background: '#fff', display: 'flex', alignItems: 'center', gap: 12,
                        }}>
                            <span style={{
                                fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                                background: sc.bg, color: sc.color,
                            }}>
                                {r.state}
                            </span>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{r.id}</div>
                                <div style={{ fontSize: 11, color: '#94a3b8' }}>domain: {r.domain} | v{r.version}</div>
                            </div>
                            {r.state === 'SUBMITTED' && (
                                <button
                                    onClick={() => onApprove(r.id)}
                                    style={{
                                        fontSize: 11, padding: '4px 10px', border: '1px solid #22c55e',
                                        borderRadius: 4, background: '#f0fdf4', color: '#166534', cursor: 'pointer',
                                    }}
                                >
                                    Approve
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
