
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
                        background: rule.valid ? '#dcfce7' : '#fee2e2',
                        color: rule.valid ? '#166534' : '#991b1b',
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
                    <div style={{ ...valueStyle, fontSize: 12, color: '#64748b' }}>{rule.notes}</div>
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
                            <span key={t} style={{ ...badgeStyle, background: '#f1f5f9', color: '#475569', marginRight: 4 }}>{t}</span>
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
                                <span style={{ color: '#94a3b8' }}> ({JSON.stringify(c.parameters)})</span>
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
                    background: result.verdict === 'allow' ? '#dcfce7' : result.verdict === 'deny' ? '#fee2e2' : '#fef9c3',
                    color: result.verdict === 'allow' ? '#166534' : result.verdict === 'deny' ? '#991b1b' : '#854d0e',
                }}>
                    {result.verdict.toUpperCase()}
                </span>
                <span style={{ marginLeft: 8, fontSize: 12, color: '#64748b' }}>
                    confidence: {result.confidence}
                </span>
            </div>
            {result.evidence.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                    <div style={labelStyle}>Evidence ({result.evidence.length})</div>
                    {result.evidence.map((ev) => (
                        <div key={ev.rule_id} style={{
                            padding: '6px 10px', marginBottom: 4, borderRadius: 4, fontSize: 12,
                            background: ev.winner ? '#eff6ff' : '#f8fafc',
                            border: ev.winner ? '1px solid #93c5fd' : '1px solid #e2e8f0',
                        }}>
                            <strong>{ev.rule_id}</strong>
                            {ev.winner && <span style={{ color: '#3b82f6', marginLeft: 6 }}>★ winner</span>}
                            <div style={{ color: '#64748b', marginTop: 2 }}>
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
                        <div key={i} style={{ fontSize: 12, color: '#ef4444' }}>{c}</div>
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

    useEffect(() => {
        setLoading(true);
        fetchKernelRules()
            .then((res) => {
                setGroups(res.groups || []);
                setRules([]);
                setLoading(false);
            })
            .catch((err) => { setError(String(err)); setLoading(false); });
    }, []);

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
                onShowDetail('Judge Error', <div style={{ color: '#ef4444' }}>{String(err)}</div>);
            });
    }, [judgeSource, judgeTarget, judgeRelation, onShowDetail]);

    if (error) {
        return <div style={{ padding: 40, color: '#ef4444', fontFamily: 'system-ui' }}>{error}</div>;
    }

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            {/* Judge bar */}
            <div style={{
                padding: '10px 16px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                gap: 8,
                alignItems: 'center',
                background: '#fafbfc',
            }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Judge</span>
                <input placeholder="Source entity" value={judgeSource} onChange={(e) => setJudgeSource(e.target.value)}
                    style={inputStyle} />
                <span style={{ color: '#94a3b8' }}>→</span>
                <input placeholder="Target entity" value={judgeTarget} onChange={(e) => setJudgeTarget(e.target.value)}
                    style={inputStyle} />
                <span style={{ color: '#94a3b8' }}>via</span>
                <input placeholder="Relation" value={judgeRelation} onChange={(e) => setJudgeRelation(e.target.value)}
                    style={inputStyle} />
                <button onClick={onJudge} style={{
                    padding: '5px 14px', fontSize: 12, fontWeight: 600, border: '1px solid #3b82f6',
                    borderRadius: 4, background: '#3b82f6', color: '#fff', cursor: 'pointer',
                }}>
                    Execute
                </button>
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
                {loading && <div style={{ color: '#94a3b8' }}>Loading...</div>}

                {!loading && !activeGroup && groups.length > 0 && (
                    <div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: '#64748b', marginBottom: 12, textTransform: 'uppercase' }}>
                            Rule Groups
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
                            {groups.map((g) => (
                                <button
                                    key={g.name}
                                    onClick={() => onSelectGroup(g.name)}
                                    style={{
                                        padding: '14px 16px', textAlign: 'left',
                                        border: '1px solid #e2e8f0', borderRadius: 8, background: '#fff',
                                        cursor: 'pointer', transition: 'border-color 0.15s',
                                    }}
                                    onMouseOver={(e) => (e.currentTarget.style.borderColor = '#93c5fd')}
                                    onMouseOut={(e) => (e.currentTarget.style.borderColor = '#e2e8f0')}
                                >
                                    <div style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>{g.name}</div>
                                    <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>{g.count} rules</div>
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
                                marginBottom: 12, fontSize: 12, color: '#3b82f6', background: 'none',
                                border: 'none', cursor: 'pointer', padding: 0,
                            }}
                        >
                            ← Back to groups
                        </button>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 12 }}>
                            {activeGroup} ({rules.length} rules)
                        </div>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
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
                                        style={{ borderBottom: '1px solid #f1f5f9', cursor: 'pointer' }}
                                        onMouseOver={(e) => (e.currentTarget.style.background = '#f8fafc')}
                                        onMouseOut={(e) => (e.currentTarget.style.background = '')}
                                    >
                                        <td style={tdStyle}><span style={{ color: '#3b82f6' }}>{r.id}</span></td>
                                        <td style={tdStyle}>{r.source}</td>
                                        <td style={tdStyle}>{r.target}</td>
                                        <td style={tdStyle}>{r.relation}</td>
                                        <td style={tdStyle}>
                                            <span style={{
                                                ...badgeStyle,
                                                background: r.valid ? '#dcfce7' : '#fee2e2',
                                                color: r.valid ? '#166534' : '#991b1b',
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

const labelStyle = { fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' as const, marginBottom: 2 };
const valueStyle = { fontSize: 13, color: '#1e293b' };
const badgeStyle = { fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, display: 'inline-block' };
const inputStyle = { padding: '5px 8px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4, width: 130 };
const thStyle = { textAlign: 'left' as const, padding: '8px 10px', color: '#64748b', fontWeight: 600 };
const tdStyle = { padding: '8px 10px' };
