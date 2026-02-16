
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { fetchKernelRules, fetchKernelRuleDetail, fetchJudge } from '@/api/client';
import type { KernelRuleSummary, KernelRuleDetail, JudgeResponse } from '@/api/types';

interface RulesViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
    sidePanel: ReactNode;
}

function RuleDetailContent({ rule }: { rule: KernelRuleDetail }) {
    return (
        <div>
            <div style={{ marginBottom: 12 }}>
                <div style={labelStyle}>ID</div>
                <div style={valueStyle}>{rule.id}</div>
            </div>
            <div style={{ marginBottom: 12 }}>
                <div style={labelStyle}>Pattern</div>
                <div style={valueStyle}>{rule.source} → {rule.target}</div>
            </div>
            <div style={{ marginBottom: 12 }}>
                <div style={labelStyle}>Relation</div>
                <div style={valueStyle}>{rule.relation}</div>
            </div>
            <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
                <div>
                    <div style={labelStyle}>Valid</div>
                    <span style={{
                        ...badgeStyle,
                        background: rule.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                        color: rule.valid ? 'var(--success-text)' : 'var(--error-text)',
                    }}>
                        {rule.valid ? 'ALLOW' : 'DENY'}
                    </span>
                </div>
                <div>
                    <div style={labelStyle}>Priority</div>
                    <div style={valueStyle}>{rule.priority}</div>
                </div>
            </div>
            {rule.notes && (
                <div style={{ marginBottom: 12 }}>
                    <div style={labelStyle}>Notes</div>
                    <div style={{ ...valueStyle, fontSize: 12, color: 'var(--text-secondary)' }}>{rule.notes}</div>
                </div>
            )}
            <div style={{ marginBottom: 12 }}>
                <div style={labelStyle}>Metadata</div>
                <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                    <div>Group: <strong>{rule.metadata.group}</strong></div>
                    <div>Category: <strong>{rule.metadata.category}</strong></div>
                    <div>Confidence: <strong>{rule.metadata.confidence}</strong></div>
                    {rule.metadata.rationale && <div>Rationale: {rule.metadata.rationale}</div>}
                    {rule.metadata.tags.length > 0 && (
                        <div>Tags: {rule.metadata.tags.map((t) => (
                            <span key={t} style={{ ...badgeStyle, background: 'var(--bg-hover)', color: 'var(--text-secondary)', marginRight: 4 }}>{t}</span>
                        ))}</div>
                    )}
                </div>
            </div>
            {rule.conditions.length > 0 && (
                <div>
                    <div style={labelStyle}>Conditions</div>
                    {rule.conditions.map((c, i) => (
                        <div key={i} style={{ fontSize: 12, marginBottom: 4 }}>
                            <strong>{c.type}</strong>
                            {Object.keys(c.parameters).length > 0 && (
                                <span style={{ color: 'var(--text-muted)' }}> ({JSON.stringify(c.parameters)})</span>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function JudgeResultContent({ result }: { result: JudgeResponse }) {
    return (
        <div>
            <div style={{ marginBottom: 16 }}>
                <span style={{
                    ...badgeStyle,
                    fontSize: 14,
                    padding: '6px 16px',
                    background: result.verdict === 'allow' ? 'var(--success-bg)' : result.verdict === 'deny' ? 'var(--error-bg)' : 'var(--warning-bg)',
                    color: result.verdict === 'allow' ? 'var(--success-text)' : result.verdict === 'deny' ? 'var(--error-text)' : 'var(--warning-text)',
                }}>
                    {result.verdict.toUpperCase()}
                </span>
                <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
                    confidence: {result.confidence}
                </span>
            </div>
            {result.evidence.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    <div style={labelStyle}>Evidence ({result.evidence.length})</div>
                    {result.evidence.map((ev) => (
                        <div key={ev.rule_id} style={{
                            padding: '6px 10px', marginBottom: 4, borderRadius: 4, fontSize: 12,
                            background: ev.winner ? 'var(--accent-bg)' : 'var(--bg-secondary)',
                            border: ev.winner ? '1px solid #93c5fd' : '1px solid var(--border)',
                        }}>
                            <strong>{ev.rule_id}</strong>
                            {ev.winner && <span style={{ color: 'var(--accent)', marginLeft: 6 }}>★ winner</span>}
                            <div style={{ color: 'var(--text-secondary)', marginTop: 2 }}>
                                {ev.source} → {ev.target} | {ev.valid ? 'allow' : 'deny'} | p{ev.priority}
                            </div>
                        </div>
                    ))}
                </div>
            )}
            {result.conflicts.length > 0 && (
                <div>
                    <div style={labelStyle}>Conflicts</div>
                    {result.conflicts.map((c, i) => (
                        <div key={i} style={{ fontSize: 12, color: 'var(--error-text)' }}>{c}</div>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function RulesView({ onShowDetail }: RulesViewProps) {
    const [groups, setGroups] = useState<{ name: string; count: number }[]>([]);
    const [rules, setRules] = useState<KernelRuleSummary[]>([]);
    const [activeGroup, setActiveGroup] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Judge form state
    const [judgeSource, setJudgeSource] = useState('');
    const [judgeTarget, setJudgeTarget] = useState('');
    const [judgeRelation, setJudgeRelation] = useState('');

    const loadGroups = useCallback(() => {
        setLoading(true);
        setError(null);
        fetchKernelRules()
            .then((res) => {
                setGroups(res.groups || []);
                setRules([]);
                setLoading(false);
            })
            .catch(() => { setError('unavailable'); setLoading(false); });
    }, []);

    useEffect(() => { loadGroups(); }, [loadGroups]);

    const onSelectGroup = useCallback((group: string) => {
        setActiveGroup(group);
        setLoading(true);
        fetchKernelRules({ group })
            .then((res) => { setRules(res.rules || []); setLoading(false); })
            .catch((err) => { setError(String(err)); setLoading(false); });
    }, []);

    const onClickRule = useCallback((ruleId: string) => {
        fetchKernelRuleDetail(ruleId)
            .then((detail) => {
                onShowDetail(ruleId, <RuleDetailContent rule={detail} />);
            })
            .catch(() => {});
    }, [onShowDetail]);

    const onJudge = useCallback(() => {
        if (!judgeSource || !judgeTarget || !judgeRelation) return;
        fetchJudge(judgeSource, judgeTarget, judgeRelation)
            .then((result) => {
                onShowDetail(
                    `Judge: ${judgeSource} → ${judgeTarget}`,
                    <JudgeResultContent result={result} />,
                );
            })
            .catch((err) => {
                onShowDetail('Judge Error', <div style={{ color: 'var(--error-text)' }}>{String(err)}</div>);
            });
    }, [judgeSource, judgeTarget, judgeRelation, onShowDetail]);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--bg-secondary)', fontSize: 12, color: 'var(--text-secondary)',
                    display: 'flex', alignItems: 'center', gap: 10,
                }}>
                    <span>Unable to load kernel rules — API server may be unavailable.</span>
                    <button onClick={loadGroups} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid var(--border-strong)', borderRadius: 4,
                        background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            {/* Judge bar */}
            <div style={{
                padding: '10px 16px',
                borderBottom: '1px solid var(--border)',
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                background: 'var(--bg-secondary)',
            }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Judge</span>
                <input placeholder="Source entity" value={judgeSource} onChange={(e) => setJudgeSource(e.target.value)}
                    style={inputStyle} />
                <span style={{ color: 'var(--text-muted)' }}>→</span>
                <input placeholder="Target entity" value={judgeTarget} onChange={(e) => setJudgeTarget(e.target.value)}
                    style={inputStyle} />
                <span style={{ color: 'var(--text-muted)' }}>via</span>
                <input placeholder="Relation" value={judgeRelation} onChange={(e) => setJudgeRelation(e.target.value)}
                    style={inputStyle} />
                <button onClick={onJudge} style={{
                    padding: '5px 14px', fontSize: 12, fontWeight: 600, border: '1px solid var(--accent)',
                    borderRadius: 4, background: 'var(--accent)', color: 'var(--bg-card)', cursor: 'pointer',
                }}>
                    Execute
                </button>
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
                {loading && <div style={{ color: 'var(--text-muted)' }}>Loading...</div>}

                {!loading && !activeGroup && groups.length > 0 && (
                    <div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'uppercase' }}>
                            Rule Groups
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
                            {groups.map((g) => (
                                <button
                                    key={g.name}
                                    onClick={() => onSelectGroup(g.name)}
                                    style={{
                                        padding: '14px 16px', textAlign: 'left',
                                        border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-card)',
                                        cursor: 'pointer', transition: 'border-color 0.15s',
                                    }}
                                    onMouseOver={(e) => (e.currentTarget.style.borderColor = '#93c5fd')}
                                    onMouseOut={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
                                >
                                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{g.name}</div>
                                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{g.count} rules</div>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {!loading && activeGroup && (
                    <div>
                        <button
                            onClick={() => { setActiveGroup(null); setRules([]); }}
                            style={{
                                marginBottom: 12, fontSize: 12, color: 'var(--accent)', background: 'none',
                                border: 'none', cursor: 'pointer', padding: 0,
                            }}
                        >
                            ← Back to groups
                        </button>
                        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
                            {activeGroup} ({rules.length} rules)
                        </div>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                                    <th style={thStyle}>ID</th>
                                    <th style={thStyle}>Source</th>
                                    <th style={thStyle}>Target</th>
                                    <th style={thStyle}>Relation</th>
                                    <th style={thStyle}>Valid</th>
                                    <th style={thStyle}>Priority</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rules.map((r) => (
                                    <tr
                                        key={r.id}
                                        onClick={() => onClickRule(r.id)}
                                        style={{ borderBottom: '1px solid var(--bg-hover)', cursor: 'pointer' }}
                                        onMouseOver={(e) => (e.currentTarget.style.background = 'var(--bg-secondary)')}
                                        onMouseOut={(e) => (e.currentTarget.style.background = '')}
                                    >
                                        <td style={tdStyle}><span style={{ color: 'var(--accent)' }}>{r.id}</span></td>
                                        <td style={tdStyle}>{r.source}</td>
                                        <td style={tdStyle}>{r.target}</td>
                                        <td style={tdStyle}>{r.relation}</td>
                                        <td style={tdStyle}>
                                            <span style={{
                                                ...badgeStyle,
                                                background: r.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                                                color: r.valid ? 'var(--success-text)' : 'var(--error-text)',
                                            }}>
                                                {r.valid ? 'ALLOW' : 'DENY'}
                                            </span>
                                        </td>
                                        <td style={tdStyle}>{r.priority}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}

// --- Styles ---

const labelStyle = { fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' as const, marginBottom: 2 };
const valueStyle = { fontSize: 13, color: 'var(--text-primary)' };
const badgeStyle = { fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, display: 'inline-block' };
const inputStyle = { padding: '5px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4, width: 130 };
const thStyle = { textAlign: 'left' as const, padding: '8px 10px', color: 'var(--text-secondary)', fontWeight: 600 };
const tdStyle = { padding: '8px 10px' };
