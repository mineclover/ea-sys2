
import { useCallback, useState, type ReactNode } from 'react';
import { simulatePromotion } from '@/api/client';
import type { SimulationResult } from '@/api/types';

interface SimulationViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

const IMPACT_COLORS: Record<string, { bg: string; color: string }> = {
    LOW: { bg: '#dcfce7', color: '#166534' },
    MEDIUM: { bg: '#fef9c3', color: '#854d0e' },
    HIGH: { bg: '#fee2e2', color: '#991b1b' },
    CRITICAL: { bg: '#fce7f3', color: '#9d174d' },
};

function SimulationResultContent({ result }: { result: SimulationResult }) {
    const ic = IMPACT_COLORS[result.impact_level] || IMPACT_COLORS.MEDIUM;
    return (
        <div style={{ fontSize: 12 }}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', marginBottom: 2 }}>IMPACT</div>
                    <span style={{ fontSize: 13, fontWeight: 600, padding: '4px 12px', borderRadius: 4, background: ic.bg, color: ic.color }}>
                        {result.impact_level}
                    </span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', marginBottom: 2 }}>SAFE</div>
                    <span style={{
                        fontSize: 13, fontWeight: 600, padding: '4px 12px', borderRadius: 4,
                        background: result.safe_to_apply ? '#dcfce7' : '#fee2e2',
                        color: result.safe_to_apply ? '#166534' : '#991b1b',
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
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', marginBottom: 4 }}>RISK FACTORS</div>
                    {result.risk_factors.map((f, i) => (
                        <div key={i} style={{ padding: '4px 8px', marginBottom: 2, background: '#fef2f2', borderRadius: 4, color: '#991b1b' }}>{f}</div>
                    ))}
                </div>
            )}
            {result.verdict_changes.length > 0 && (
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', marginBottom: 4 }}>VERDICT CHANGES</div>
                    {result.verdict_changes.map((c, i) => (
                        <div key={i} style={{ padding: '8px 10px', marginBottom: 4, border: '1px solid #e2e8f0', borderRadius: 6 }}>
                            <div>{c.triple.join(' → ')}</div>
                            <div style={{ color: '#64748b', marginTop: 2 }}>
                                {c.original} → <strong>{c.simulated}</strong>
                            </div>
                        </div>
                    ))}
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

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #e2e8f0', background: '#fafbfc' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                    What-If Simulation
                </span>
            </div>

            <div style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
                    <input
                        placeholder="Rule ID"
                        value={ruleId}
                        onChange={(e) => setRuleId(e.target.value)}
                        style={{ padding: '6px 10px', fontSize: 13, border: '1px solid #cbd5e1', borderRadius: 4, flex: 1 }}
                    />
                    <select value={confidence} onChange={(e) => setConfidence(e.target.value)}
                        style={{ padding: '6px 8px', fontSize: 12, border: '1px solid #cbd5e1', borderRadius: 4 }}>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                    </select>
                    <button onClick={onSimulate} disabled={loading} style={{
                        padding: '6px 16px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #a855f7', borderRadius: 4,
                        background: loading ? '#e2e8f0' : '#a855f7', color: '#fff', cursor: loading ? 'default' : 'pointer',
                    }}>
                        {loading ? 'Running...' : 'Simulate'}
                    </button>
                </div>
                {error && (
                    <div style={{ padding: '12px 14px', border: '1px solid #fecaca', borderRadius: 8, background: '#fef2f2', fontSize: 12, color: '#991b1b' }}>
                        {error}
                    </div>
                )}
                <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 16 }}>
                    Simulate the impact of promoting a rule to a new confidence level.
                    Shows affected decisions, verdict changes, and risk assessment.
                </div>
            </div>
        </div>
    );
}
