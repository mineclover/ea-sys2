
import { useCallback, useState, type ReactNode } from 'react';
import { useGovernanceRules, useApproveRule } from '@/api/hooks';
import type { GovernanceRuleItem } from '@/api/types';
import { ErrorBanner } from '@/components/ui';
import { PageHeader } from '@/components/layout';

interface RuleLifecycleViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

const STATE_COLORS: Record<string, { bg: string; color: string }> = {
    DRAFT: { bg: 'var(--status-warning-bg)', color: 'var(--status-warning-text)' },
    SUBMITTED: { bg: 'var(--status-indigo-bg)', color: 'var(--status-indigo-text)' },
    APPROVED: { bg: 'var(--status-success-bg)', color: 'var(--status-success-text)' },
    ACTIVE: { bg: 'var(--status-info-bg)', color: 'var(--status-info-text)' },
    DEPRECATED: { bg: 'var(--accent)', color: 'var(--muted-foreground)' },
};

export default function RuleLifecycleView({ onShowDetail }: RuleLifecycleViewProps) {
    const [stateFilter, setStateFilter] = useState<string>('');

    const { data: rules = [], isLoading, isError, refetch } = useGovernanceRules(stateFilter || undefined);
    const approveMutation = useApproveRule();

    const onApprove = useCallback((ruleId: string) => {
        approveMutation.mutateAsync(ruleId)
            .then((res) => {
                onShowDetail(ruleId, <div>Rule <strong>{res.rule_id}</strong> approved.</div>);
            })
            .catch((err) => {
                onShowDetail('Approve Error', <div style={{ color: 'var(--status-error-text)' }}>{String(err)}</div>);
            });
    }, [onShowDetail, approveMutation]);

    if (isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <ErrorBanner
                    message="Unable to load governance rules — API server may be unavailable."
                    onRetry={() => refetch()}
                />
            </div>
        );
    }

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif', overflow: 'auto' }}>
            <PageHeader
                metaKey="governance.rule-lifecycle"
                compact
                subtitle={`${rules.length} rules`}
                rightContent={
                    <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}
                        style={{ padding: '4px 8px', fontSize: 12, border: '1px solid var(--input)', borderRadius: 4 }}>
                        <option value="">All</option>
                        <option value="DRAFT">Draft</option>
                        <option value="SUBMITTED">Submitted</option>
                        <option value="APPROVED">Approved</option>
                        <option value="ACTIVE">Active</option>
                        <option value="DEPRECATED">Deprecated</option>
                    </select>
                }
            />

            {/* Rules list */}
            <div style={{ padding: 16 }}>
                {isLoading && <div style={{ color: 'var(--muted-foreground)' }}>Loading...</div>}
                {!isLoading && rules.length === 0 && (
                    <div style={{ color: 'var(--muted-foreground)', fontSize: 13 }}>No rules found.</div>
                )}
                {!isLoading && rules.map((r: GovernanceRuleItem) => {
                    const sc = STATE_COLORS[r.state] || STATE_COLORS.DRAFT;
                    return (
                        <div key={r.id} style={{
                            padding: '12px 14px', marginBottom: 8, border: '1px solid var(--border)',
                            borderRadius: 8, background: 'var(--card)', display: 'flex', alignItems: 'center', gap: 12,
                        }}>
                            <span style={{
                                fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                                background: sc.bg, color: sc.color,
                            }}>
                                {r.state}
                            </span>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)' }}>{r.id}</div>
                                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>domain: {r.domain} | v{r.version}</div>
                            </div>
                            {r.state === 'SUBMITTED' && (
                                <button
                                    onClick={() => onApprove(r.id)}
                                    style={{
                                        fontSize: 11, padding: '4px 10px', border: '1px solid var(--color-layer-flow)',
                                        borderRadius: 4, background: 'var(--status-success-bg)', color: 'var(--status-success-text)', cursor: 'pointer',
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
