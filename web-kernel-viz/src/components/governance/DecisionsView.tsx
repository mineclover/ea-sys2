
import { useEffect, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { fetchDecisionTrace, exploreDecision } from '@/api/client';
import Badge from '@/components/ui/Badge';
import ErrorBanner from '@/components/ui/ErrorBanner';
import { PageHeader } from '@/components/layout';

interface DecisionsViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

interface Evidence {
    rule_id: string;
    matched: boolean;
    winner: boolean;
    valid: boolean;
    source: string;
    target: string;
    priority: number;
    confidence?: string;
}

interface DecisionTrace {
    decision_id: string;
    source: string;
    type: string;
    timestamp: string;
    verdict: string;
    confidence: string;
    evidence: Evidence[];
    conflicts: string[];
    context?: Record<string, unknown>;
}

interface ExploreNode {
    id: string;
    label: string;
    type: string;
}

interface ExploreEdge {
    source: string;
    target: string;
    relation: string;
}

interface ExploreResult {
    nodes: ExploreNode[];
    edges: ExploreEdge[];
    summary?: string;
}

export default function DecisionsView({ onShowDetail }: DecisionsViewProps) {
    const [searchParams, setSearchParams] = useSearchParams();
    const [decisionId, setDecisionId] = useState('');
    const [trace, setTrace] = useState<DecisionTrace | null>(null);
    const [exploreData, setExploreData] = useState<ExploreResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [exploring, setExploring] = useState(false);
    const queryDecisionId = (searchParams.get('decision_id') || '').trim();

    const runLookup = async (targetDecisionId: string) => {
        setLoading(true);
        setError(null);
        setTrace(null);
        setExploreData(null);

        try {
            const result = await fetchDecisionTrace(targetDecisionId);
            setTrace(result as unknown as DecisionTrace);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch decision trace.');
        } finally {
            setLoading(false);
        }
    };

    const handleLookup = async () => {
        const normalizedDecisionId = decisionId.trim();
        if (!normalizedDecisionId) {
            setError('Please enter a decision ID.');
            return;
        }
        if (queryDecisionId !== normalizedDecisionId) {
            const next = new URLSearchParams(searchParams);
            next.set('decision_id', normalizedDecisionId);
            setSearchParams(next, { replace: true });
            return;
        }
        await runLookup(normalizedDecisionId);
    };

    useEffect(() => {
        if (!queryDecisionId) return;
        setDecisionId((prev) => (prev === queryDecisionId ? prev : queryDecisionId));
        void runLookup(queryDecisionId);
    }, [queryDecisionId]);

    const handleExplore = async () => {
        if (!trace?.decision_id) return;

        setExploring(true);
        setError(null);

        try {
            const result = await exploreDecision(trace.decision_id);
            setExploreData(result as unknown as ExploreResult);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to explore decision.');
        } finally {
            setExploring(false);
        }
    };

    const handleShowExploreDetail = () => {
        if (!exploreData) return;

        const content = (
            <div style={{ fontSize: 12, lineHeight: 1.7 }}>
                {exploreData.summary && (
                    <div style={{ marginBottom: 16, padding: 12, background: 'var(--secondary)', borderRadius: 6 }}>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 4 }}>
                            Summary
                        </div>
                        <div style={{ color: 'var(--muted-foreground)' }}>{exploreData.summary}</div>
                    </div>
                )}

                <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 6 }}>
                        Nodes ({exploreData.nodes.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {exploreData.nodes.map((node) => (
                            <div key={node.id} style={{
                                padding: '8px 10px',
                                border: '1px solid var(--border)',
                                borderRadius: 6,
                                background: 'var(--card)',
                            }}>
                                <div style={{ fontWeight: 600, color: 'var(--foreground)', marginBottom: 2 }}>
                                    {node.label}
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                                    {node.type} · {node.id}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 6 }}>
                        Edges ({exploreData.edges.length})
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {exploreData.edges.map((edge, idx) => (
                            <div key={idx} style={{
                                padding: '6px 8px',
                                border: '1px solid var(--border)',
                                borderRadius: 4,
                                background: 'var(--secondary)',
                                fontSize: 11,
                                color: 'var(--muted-foreground)',
                            }}>
                                <span style={{ fontWeight: 600 }}>{edge.source}</span>
                                {' → '}
                                <Badge label={edge.relation} size="sm" />
                                {' → '}
                                <span style={{ fontWeight: 600 }}>{edge.target}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        );

        onShowDetail('Decision Exploration', content);
    };

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif', overflow: 'auto' }}>
            <PageHeader metaKey="governance.decisions" compact />

            <div style={{ padding: 16 }}>
                {/* Input Section */}
                <div style={{ marginBottom: 16 }}>
                    <div style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: 'var(--muted-foreground)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                        marginBottom: 6,
                    }}>
                        Decision ID
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <input
                            type="text"
                            value={decisionId}
                            onChange={(e) => setDecisionId(e.target.value)}
                            placeholder="Enter decision ID"
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') handleLookup();
                            }}
                            style={{
                                flex: 1,
                                padding: '8px 10px',
                                fontSize: 12,
                                border: '1px solid var(--border)',
                                borderRadius: 6,
                                background: 'var(--card)',
                                color: 'var(--foreground)',
                                outline: 'none',
                            }}
                        />
                        <button
                            onClick={handleLookup}
                            disabled={loading}
                            style={{
                                padding: '8px 16px',
                                fontSize: 12,
                                fontWeight: 600,
                                border: '1px solid var(--primary)',
                                borderRadius: 6,
                                background: loading ? 'var(--input)' : 'var(--primary)',
                                color: 'var(--card)',
                                cursor: loading ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {loading ? 'Loading...' : 'Lookup'}
                        </button>
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div style={{ marginBottom: 16 }}>
                        <ErrorBanner message={error} onRetry={() => setError(null)} />
                    </div>
                )}

                {/* Trace View */}
                {trace && (
                    <div>
                        {/* Context Section */}
                        <div style={{
                            marginBottom: 16,
                            padding: 14,
                            border: '1px solid var(--border)',
                            borderRadius: 8,
                            background: 'var(--secondary)',
                        }}>
                            <div style={{
                                fontSize: 10,
                                fontWeight: 700,
                                color: 'var(--muted-foreground)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em',
                                marginBottom: 8,
                            }}>
                                Context
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 12px', fontSize: 12 }}>
                                <div style={{ color: 'var(--muted-foreground)', fontWeight: 600 }}>Decision ID:</div>
                                <div style={{ color: 'var(--foreground)', fontFamily: 'monospace' }}>{trace.decision_id}</div>

                                <div style={{ color: 'var(--muted-foreground)', fontWeight: 600 }}>Source:</div>
                                <div style={{ color: 'var(--foreground)' }}>{trace.source}</div>

                                <div style={{ color: 'var(--muted-foreground)', fontWeight: 600 }}>Type:</div>
                                <div style={{ color: 'var(--foreground)' }}>{trace.type}</div>

                                <div style={{ color: 'var(--muted-foreground)', fontWeight: 600 }}>Timestamp:</div>
                                <div style={{ color: 'var(--foreground)', fontSize: 11 }}>{trace.timestamp}</div>
                            </div>
                        </div>

                        {/* Evidence Section */}
                        <div style={{ marginBottom: 16 }}>
                            <div style={{
                                fontSize: 10,
                                fontWeight: 700,
                                color: 'var(--muted-foreground)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em',
                                marginBottom: 8,
                            }}>
                                Evidence ({trace.evidence.length})
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                {trace.evidence.map((ev, idx) => (
                                    <div key={idx} style={{
                                        padding: '10px 12px',
                                        border: '1px solid var(--border)',
                                        borderRadius: 6,
                                        background: 'var(--card)',
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                                            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)', fontFamily: 'monospace' }}>
                                                {ev.rule_id}
                                            </span>
                                            {ev.matched && <Badge label="matched" />}
                                            {ev.winner && <Badge label="winner" bg="var(--status-success-bg)" color="var(--status-success-text)" />}
                                            {!ev.valid && <Badge label="invalid" bg="var(--status-error-bg)" color="var(--status-error-text)" />}
                                        </div>
                                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 4 }}>
                                            <span style={{ fontWeight: 600 }}>{ev.source}</span>
                                            {' → '}
                                            <span style={{ fontWeight: 600 }}>{ev.target}</span>
                                        </div>
                                        <div style={{ display: 'flex', gap: 8, fontSize: 10, color: 'var(--muted-foreground)' }}>
                                            <span>Priority: {ev.priority}</span>
                                            {ev.confidence && <span>Confidence: {ev.confidence}</span>}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Outcome Section */}
                        <div style={{
                            marginBottom: 16,
                            padding: 14,
                            border: '1px solid var(--border)',
                            borderRadius: 8,
                            background: 'var(--card)',
                        }}>
                            <div style={{
                                fontSize: 10,
                                fontWeight: 700,
                                color: 'var(--muted-foreground)',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em',
                                marginBottom: 8,
                            }}>
                                Outcome
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                                <Badge label={trace.verdict} size="md" />
                                <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                                    Confidence: <strong>{trace.confidence}</strong>
                                </span>
                            </div>
                            {trace.conflicts.length > 0 && (
                                <div style={{ marginTop: 8 }}>
                                    <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--status-error-text)', marginBottom: 4 }}>
                                        Conflicts:
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                        {trace.conflicts.map((conflict, idx) => (
                                            <div key={idx} style={{
                                                padding: '6px 8px',
                                                border: '1px solid var(--status-error-bg)',
                                                borderRadius: 4,
                                                background: 'var(--status-error-bg)',
                                                fontSize: 11,
                                                color: 'var(--status-error-text)',
                                            }}>
                                                {conflict}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Explore Button */}
                        <div style={{ display: 'flex', gap: 8 }}>
                            <button
                                onClick={handleExplore}
                                disabled={exploring}
                                style={{
                                    padding: '8px 16px',
                                    fontSize: 12,
                                    fontWeight: 600,
                                    border: '1px solid var(--status-success-text)',
                                    borderRadius: 6,
                                    background: exploring ? 'var(--input)' : 'var(--status-success-text)',
                                    color: 'var(--card)',
                                    cursor: exploring ? 'not-allowed' : 'pointer',
                                }}
                            >
                                {exploring ? 'Exploring...' : 'Explore'}
                            </button>
                            {exploreData && (
                                <button
                                    onClick={handleShowExploreDetail}
                                    style={{
                                        padding: '8px 16px',
                                        fontSize: 12,
                                        fontWeight: 600,
                                        border: '1px solid var(--primary)',
                                        borderRadius: 6,
                                        background: 'var(--card)',
                                        color: 'var(--primary)',
                                        cursor: 'pointer',
                                    }}
                                >
                                    View Graph Details
                                </button>
                            )}
                        </div>

                        {/* Explore Graph Preview */}
                        {exploreData && (
                            <div style={{
                                marginTop: 16,
                                padding: 14,
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                background: 'var(--secondary)',
                            }}>
                                <div style={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    color: 'var(--muted-foreground)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    marginBottom: 8,
                                }}>
                                    Exploration Result
                                </div>
                                <div style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>
                                    {exploreData.nodes.length} nodes, {exploreData.edges.length} edges
                                </div>
                                {exploreData.summary && (
                                    <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted-foreground)', fontStyle: 'italic' }}>
                                        {exploreData.summary}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Empty State */}
                {!trace && !loading && !error && (
                    <div style={{
                        padding: 40,
                        textAlign: 'center',
                        color: 'var(--muted-foreground)',
                        fontSize: 13,
                    }}>
                        Enter a decision ID above to view its trace and explore its graph.
                    </div>
                )}
            </div>
        </div>
    );
}
