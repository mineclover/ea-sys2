
import { useCallback, useState, type ReactNode } from 'react';
import { fetchDecisionTrace } from '@/api/client';

interface DecisionsViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

function TraceDetail({ data }: { data: Record<string, unknown> }) {
    return (
        <pre style={{
            fontSize: 11, lineHeight: 1.5, color: '#1e293b',
            background: '#f8fafc', padding: 12, borderRadius: 6,
            overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        }}>
            {JSON.stringify(data, null, 2)}
        </pre>
    );
}

export default function DecisionsView({ onShowDetail }: DecisionsViewProps) {
    const [decisionId, setDecisionId] = useState('');
    const [error, setError] = useState<string | null>(null);

    const onLookup = useCallback(() => {
        if (!decisionId.trim()) return;
        setError(null);
        fetchDecisionTrace(decisionId.trim())
            .then((trace) => {
                onShowDetail(`Decision ${decisionId}`, <TraceDetail data={trace} />);
            })
            .catch((err) => setError(String(err)));
    }, [decisionId, onShowDetail]);

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #e2e8f0', background: '#fafbfc' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                    Decision Trace Lookup
                </span>
            </div>

            <div style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                    <input
                        placeholder="Decision ID"
                        value={decisionId}
                        onChange={(e) => setDecisionId(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && onLookup()}
                        style={{ padding: '6px 10px', fontSize: 13, border: '1px solid #cbd5e1', borderRadius: 4, flex: 1 }}
                    />
                    <button onClick={onLookup} style={{
                        padding: '6px 16px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #3b82f6', borderRadius: 4, background: '#3b82f6', color: '#fff', cursor: 'pointer',
                    }}>
                        Lookup
                    </button>
                </div>
                {error && (
                    <div style={{ padding: '12px 14px', border: '1px solid #fecaca', borderRadius: 8, background: '#fef2f2', fontSize: 12, color: '#991b1b' }}>
                        {error}
                    </div>
                )}
                <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 16 }}>
                    Enter a decision ID to inspect the full trace including context, evidence, and outcome.
                </div>
            </div>
        </div>
    );
}
