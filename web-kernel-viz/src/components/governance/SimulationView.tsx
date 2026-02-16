
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { fetchKernelRuleDetail, fetchKernelRules, simulatePromotion } from '@/api/client';
import type { KernelRuleDetail, KernelRuleSummary, SimulationResult } from '@/api/types';

interface SimulationViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

const IMPACT_COLORS: Record<string, { bg: string; color: string }> = {
    LOW: { bg: 'var(--success-bg)', color: 'var(--success-text)' },
    MEDIUM: { bg: 'var(--warning-bg)', color: 'var(--warning-text)' },
    HIGH: { bg: 'var(--error-bg)', color: 'var(--error-text)' },
    CRITICAL: { bg: 'var(--pink-bg)', color: 'var(--pink-text)' },
};

function SimulationResultContent({ result }: { result: SimulationResult }) {
    const ic = IMPACT_COLORS[result.impact_level] || IMPACT_COLORS.MEDIUM;
    return (
        <div style={{ fontSize: 12 }}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>IMPACT</div>
                    <span style={{ fontSize: 13, fontWeight: 600, padding: '4px 12px', borderRadius: 4, background: ic.bg, color: ic.color }}>
                        {result.impact_level}
                    </span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>SAFE</div>
                    <span style={{
                        fontSize: 13, fontWeight: 600, padding: '4px 12px', borderRadius: 4,
                        background: result.safe_to_apply ? 'var(--success-bg)' : 'var(--error-bg)',
                        color: result.safe_to_apply ? 'var(--success-text)' : 'var(--error-text)',
                    }}>
                        {result.safe_to_apply ? 'Yes' : 'No'}
                    </span>
                </div>
            </div>
            <div style={{ marginBottom: 12 }}>
                Analyzed <strong>{result.total_decisions_analyzed}</strong> decisions,
                <strong> {result.affected_decisions}</strong> affected.
            </div>
            {result.risk_factors.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>RISK FACTORS</div>
                    {result.risk_factors.map((f, i) => (
                        <div key={i} style={{ padding: '4px 8px', marginBottom: 2, background: '#fef2f2', borderRadius: 4, color: 'var(--error-text)' }}>{f}</div>
                    ))}
                </div>
            )}
            {result.verdict_changes.length > 0 && (
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>VERDICT CHANGES</div>
                    {result.verdict_changes.map((c, i) => (
                        <div key={i} style={{ padding: '8px 10px', marginBottom: 4, border: '1px solid var(--border)', borderRadius: 6 }}>
                            <div>{c.triple.join(' → ')}</div>
                            <div style={{ color: 'var(--text-secondary)', marginTop: 2 }}>
                                {c.original} → <strong>{c.simulated}</strong>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function RuleDetailContent({ detail }: { detail: KernelRuleDetail }) {
    return (
        <div style={{ fontSize: 12 }}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>SOURCE</div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{detail.source}</span>
                </div>
                <div style={{ color: 'var(--text-muted)', alignSelf: 'end', paddingBottom: 1 }}>&rarr;</div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>TARGET</div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{detail.target}</span>
                </div>
            </div>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>RELATION</div>
                    <span style={{ padding: '2px 8px', borderRadius: 4, background: 'var(--bg-hover)', fontSize: 12, fontWeight: 600 }}>{detail.relation}</span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>VERDICT</div>
                    <span style={{
                        padding: '2px 8px', borderRadius: 4, fontSize: 12, fontWeight: 600,
                        background: detail.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                        color: detail.valid ? 'var(--success-text)' : 'var(--error-text)',
                    }}>{detail.valid ? 'ALLOW' : 'DENY'}</span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>PRIORITY</div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{detail.priority}</span>
                </div>
            </div>
            {detail.notes && (
                <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>NOTES</div>
                    <div style={{ padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 6, color: 'var(--text-primary)', lineHeight: 1.5 }}>{detail.notes}</div>
                </div>
            )}
            {detail.conditions.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>CONDITIONS</div>
                    {detail.conditions.map((c, i) => (
                        <div key={i} style={{ padding: '6px 10px', marginBottom: 4, border: '1px solid var(--border)', borderRadius: 6 }}>
                            <span style={{ fontWeight: 600 }}>{c.type}</span>
                            {Object.entries(c.parameters).map(([k, v]) => (
                                <span key={k} style={{ marginLeft: 8, color: 'var(--text-secondary)' }}>{k}=<strong>{v}</strong></span>
                            ))}
                        </div>
                    ))}
                </div>
            )}
            <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>METADATA</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', fontSize: 11, padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 6 }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Group</span><span style={{ fontWeight: 600 }}>{detail.metadata.group}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>Category</span><span style={{ fontWeight: 600 }}>{detail.metadata.category}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>Confidence</span><span style={{ fontWeight: 600 }}>{detail.metadata.confidence}</span>
                    <span style={{ color: 'var(--text-secondary)' }}>Source</span><span style={{ fontWeight: 600 }}>{detail.metadata.source}</span>
                    {detail.metadata.rationale && (
                        <><span style={{ color: 'var(--text-secondary)' }}>Rationale</span><span style={{ fontWeight: 600 }}>{detail.metadata.rationale}</span></>
                    )}
                    {detail.metadata.tags.length > 0 && (
                        <><span style={{ color: 'var(--text-secondary)' }}>Tags</span><span style={{ fontWeight: 600 }}>{detail.metadata.tags.join(', ')}</span></>
                    )}
                    {detail.metadata.established_version && (
                        <><span style={{ color: 'var(--text-secondary)' }}>Version</span><span style={{ fontWeight: 600 }}>{detail.metadata.established_version}</span></>
                    )}
                </div>
            </div>
        </div>
    );
}

type RuleWithGroup = KernelRuleSummary & { group: string };

function RuleBrowserPanel({ selectedRuleId, onSelectRule, onShowDetail }: {
    selectedRuleId: string;
    onSelectRule: (ruleId: string) => void;
    onShowDetail: (title: string, content: ReactNode) => void;
}) {
    const [rules, setRules] = useState<RuleWithGroup[]>([]);
    const [loadingRules, setLoadingRules] = useState(true);
    const [expanded, setExpanded] = useState(true);
    const [search, setSearch] = useState('');
    const [filterGroup, setFilterGroup] = useState('');
    const [filterRelation, setFilterRelation] = useState('');
    const [filterValid, setFilterValid] = useState('');

    useEffect(() => {
        let cancelled = false;
        setLoadingRules(true);
        fetchKernelRules()
            .then((res) => {
                const groups = res.groups ?? [];
                return Promise.all(
                    groups.map((g) =>
                        fetchKernelRules({ group: g.name }).then((gr) =>
                            (gr.rules ?? []).map((r) => ({ ...r, group: g.name }))
                        )
                    )
                );
            })
            .then((results) => {
                if (!cancelled) {
                    setRules(results.flat());
                    setLoadingRules(false);
                }
            })
            .catch(() => {
                if (!cancelled) setLoadingRules(false);
            });
        return () => { cancelled = true; };
    }, []);

    const groupNames = useMemo(() => [...new Set(rules.map((r) => r.group))].sort(), [rules]);
    const relationNames = useMemo(() => [...new Set(rules.map((r) => r.relation))].sort(), [rules]);

    const filtered = useMemo(() => {
        const q = search.toLowerCase();
        return rules.filter((r) => {
            if (q && !r.id.toLowerCase().includes(q) && !r.source.toLowerCase().includes(q) && !r.target.toLowerCase().includes(q))
                return false;
            if (filterGroup && r.group !== filterGroup) return false;
            if (filterRelation && r.relation !== filterRelation) return false;
            if (filterValid === 'allow' && !r.valid) return false;
            if (filterValid === 'deny' && r.valid) return false;
            return true;
        });
    }, [rules, search, filterGroup, filterRelation, filterValid]);

    return (
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16 }}>
            <button
                onClick={() => setExpanded((v) => !v)}
                style={{
                    width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '8px 12px', background: 'var(--bg-secondary)', border: 'none', borderRadius: expanded ? '8px 8px 0 0' : 8,
                    cursor: 'pointer', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)',
                }}
            >
                <span>Rule Browser</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {loadingRules ? 'Loading...' : `${filtered.length} / ${rules.length} rules`}
                    {' '}{expanded ? '▲' : '▼'}
                </span>
            </button>
            {expanded && (
                <div style={{ padding: 12 }}>
                    <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                        <input
                            placeholder="Search rule ID, source, target..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            style={{ padding: '4px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4, flex: 1, minWidth: 140 }}
                        />
                        <select value={filterGroup} onChange={(e) => setFilterGroup(e.target.value)}
                            style={{ padding: '4px 6px', fontSize: 11, border: '1px solid var(--border-strong)', borderRadius: 4 }}>
                            <option value="">All Groups</option>
                            {groupNames.map((g) => <option key={g} value={g}>{g}</option>)}
                        </select>
                        <select value={filterRelation} onChange={(e) => setFilterRelation(e.target.value)}
                            style={{ padding: '4px 6px', fontSize: 11, border: '1px solid var(--border-strong)', borderRadius: 4 }}>
                            <option value="">All Relations</option>
                            {relationNames.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                        <select value={filterValid} onChange={(e) => setFilterValid(e.target.value)}
                            style={{ padding: '4px 6px', fontSize: 11, border: '1px solid var(--border-strong)', borderRadius: 4 }}>
                            <option value="">Allow/Deny</option>
                            <option value="allow">Allow</option>
                            <option value="deny">Deny</option>
                        </select>
                    </div>
                    <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid var(--bg-hover)', borderRadius: 4 }}>
                        {loadingRules ? (
                            <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>Loading rules...</div>
                        ) : filtered.length === 0 ? (
                            <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>No rules match filters</div>
                        ) : (
                            filtered.map((r) => {
                                const selected = r.id === selectedRuleId;
                                return (
                                    <div
                                        key={r.id}
                                        onClick={() => onSelectRule(r.id)}
                                        style={{
                                            display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                                            cursor: 'pointer', fontSize: 11, borderBottom: '1px solid var(--bg-hover)',
                                            background: selected ? 'var(--accent-bg)' : 'transparent',
                                            border: selected ? '1px solid var(--accent)' : '1px solid transparent',
                                            borderRadius: 4,
                                        }}
                                    >
                                        <span style={{ fontWeight: 600, color: 'var(--text-primary)', minWidth: 0, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {r.id}
                                        </span>
                                        <span style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                            {r.source} → {r.target}
                                        </span>
                                        <span style={{
                                            padding: '1px 6px', borderRadius: 3, fontSize: 10, fontWeight: 600,
                                            background: 'var(--bg-hover)', color: 'var(--text-secondary)',
                                        }}>
                                            {r.relation}
                                        </span>
                                        <span style={{
                                            padding: '1px 6px', borderRadius: 3, fontSize: 10, fontWeight: 600,
                                            background: r.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                                            color: r.valid ? 'var(--success-text)' : 'var(--error-text)',
                                        }}>
                                            {r.valid ? 'ALLOW' : 'DENY'}
                                        </span>
                                        <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                                            P{r.priority}
                                        </span>
                                        <button
                                            title="View rule detail"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                fetchKernelRuleDetail(r.id).then((detail) => {
                                                    onShowDetail(`Rule: ${r.id}`, <RuleDetailContent detail={detail} />);
                                                });
                                            }}
                                            style={{
                                                padding: '1px 5px', border: '1px solid var(--border-strong)', borderRadius: 3,
                                                background: 'var(--bg-card)', cursor: 'pointer', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1,
                                            }}
                                        >
                                            i
                                        </button>
                                    </div>
                                );
                            })
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default function SimulationView({ onShowDetail }: SimulationViewProps) {
    const [ruleId, setRuleId] = useState('');
    const [confidence, setConfidence] = useState('high');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const onSimulate = useCallback(() => {
        if (!ruleId.trim()) return;
        setError(null);
        setLoading(true);
        simulatePromotion(ruleId.trim(), confidence)
            .then((result) => {
                onShowDetail(`Simulation: ${ruleId}`, <SimulationResultContent result={result} />);
                setLoading(false);
            })
            .catch((err) => { setError(String(err)); setLoading(false); });
    }, [ruleId, confidence, onShowDetail]);

    const handleSelectRule = useCallback((id: string) => {
        setRuleId(id);
        setError(null);
        setLoading(true);
        simulatePromotion(id, confidence)
            .then((result) => {
                onShowDetail(`Simulation: ${id}`, <SimulationResultContent result={result} />);
                setLoading(false);
            })
            .catch((err) => { setError(String(err)); setLoading(false); });
    }, [confidence, onShowDetail]);

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    What-If Simulation
                </span>
            </div>

            <div style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
                    <input
                        placeholder="Rule ID"
                        value={ruleId}
                        onChange={(e) => setRuleId(e.target.value)}
                        style={{ padding: '6px 10px', fontSize: 13, border: '1px solid var(--border-strong)', borderRadius: 4, flex: 1 }}
                    />
                    <select value={confidence} onChange={(e) => setConfidence(e.target.value)}
                        style={{ padding: '6px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4 }}>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                    </select>
                    <button onClick={onSimulate} disabled={loading} style={{
                        padding: '6px 16px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #a855f7', borderRadius: 4,
                        background: loading ? 'var(--border)' : '#a855f7', color: 'var(--bg-card)', cursor: loading ? 'default' : 'pointer',
                    }}>
                        {loading ? 'Running...' : 'Simulate'}
                    </button>
                </div>

                <RuleBrowserPanel selectedRuleId={ruleId} onSelectRule={handleSelectRule} onShowDetail={onShowDetail} />

                {error && (
                    <div style={{
                        padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                        background: 'var(--bg-secondary)', fontSize: 12, color: 'var(--text-secondary)',
                    }}>
                        Unable to run simulation — API server may be unavailable.
                    </div>
                )}
                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 16 }}>
                    Simulate the impact of promoting a rule to a new confidence level.
                    Shows affected decisions, verdict changes, and risk assessment.
                </div>
            </div>
        </div>
    );
}
