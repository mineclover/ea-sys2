
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { fetchImpact, fetchProfiles, fetchProfileTopology } from '@/api/client';
import type { ImpactResponse, ProfileListItem } from '@/api/types';

interface ImpactAnalysisViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

function ImpactDetailContent({ result }: { result: ImpactResponse }) {
    const entries = useMemo(() =>
        Object.entries(result.impact)
            .map(([element, paths]) => ({ element, paths }))
            .sort((a, b) => {
                const aMin = Math.min(...a.paths.map(p => p.length));
                const bMin = Math.min(...b.paths.map(p => p.length));
                return aMin - bMin;
            }),
        [result.impact],
    );

    return (
        <div style={{ fontSize: 12 }}>
            <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>ELEMENT</div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{result.element}</span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>DIRECTION</div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{result.direction}</span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>MAX DEPTH</div>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{result.max_depth}</span>
                </div>
                <div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 2 }}>AFFECTED</div>
                    <span style={{
                        fontSize: 13, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                        background: result.affected_count > 10 ? 'var(--error-bg)' : result.affected_count > 5 ? 'var(--warning-bg)' : 'var(--success-bg)',
                        color: result.affected_count > 10 ? 'var(--error-text)' : result.affected_count > 5 ? 'var(--warning-text)' : 'var(--success-text)',
                    }}>
                        {result.affected_count}
                    </span>
                </div>
            </div>

            {entries.length === 0 ? (
                <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-muted)' }}>No impacted elements found.</div>
            ) : (
                entries.map(({ element, paths }) => (
                    <div key={element} style={{ marginBottom: 8, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
                        <div style={{
                            padding: '6px 10px', background: 'var(--bg-secondary)', fontWeight: 600,
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        }}>
                            <span>{element}</span>
                            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                                {paths.length} path{paths.length > 1 ? 's' : ''}, min length {Math.min(...paths.map(p => p.length))}
                            </span>
                        </div>
                        {paths.map((path, pi) => (
                            <div key={pi} style={{ padding: '4px 10px', borderTop: '1px solid var(--bg-hover)', fontSize: 11, color: 'var(--text-secondary)' }}>
                                {path.edges.map((e, ei) => (
                                    <span key={ei}>
                                        {ei === 0 && <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{e.source}</span>}
                                        <span style={{ padding: '0 4px', color: 'var(--text-muted)' }}>
                                            &mdash;<span style={{ fontSize: 10 }}>{e.relation}</span>&rarr;
                                        </span>
                                        <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{e.target}</span>
                                    </span>
                                ))}
                            </div>
                        ))}
                    </div>
                ))
            )}
        </div>
    );
}

export default function ImpactAnalysisView({ onShowDetail }: ImpactAnalysisViewProps) {
    const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
    const [selectedProfile, setSelectedProfile] = useState('');
    const [elements, setElements] = useState<{ name: string; layer: string; kernel_type: string }[]>([]);
    const [selectedElement, setSelectedElement] = useState('');
    const [elementSearch, setElementSearch] = useState('');
    const [direction, setDirection] = useState('both');
    const [maxDepth, setMaxDepth] = useState(3);
    const [loading, setLoading] = useState(false);
    const [loadingElements, setLoadingElements] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<ImpactResponse | null>(null);

    // Load profiles on mount
    useEffect(() => {
        fetchProfiles()
            .then((ps) => {
                setProfiles(ps);
                if (ps.length > 0) setSelectedProfile(ps[0].name);
            })
            .catch(() => {});
    }, []);

    // Load elements when profile changes
    useEffect(() => {
        if (!selectedProfile) { setElements([]); return; }
        setLoadingElements(true);
        setSelectedElement('');
        setResult(null);
        fetchProfileTopology(selectedProfile)
            .then((topo) => {
                setElements(topo.nodes.map((n) => ({ name: n.name, layer: n.layer, kernel_type: n.kernel_type })));
                setLoadingElements(false);
            })
            .catch(() => { setElements([]); setLoadingElements(false); });
    }, [selectedProfile]);

    const filteredElements = useMemo(() => {
        const q = elementSearch.toLowerCase();
        if (!q) return elements;
        return elements.filter((n) =>
            n.name.toLowerCase().includes(q) || n.layer.toLowerCase().includes(q) || n.kernel_type.toLowerCase().includes(q)
        );
    }, [elements, elementSearch]);

    const onAnalyze = useCallback(() => {
        if (!selectedProfile || !selectedElement) return;
        setError(null);
        setLoading(true);
        setResult(null);
        fetchImpact(selectedProfile, selectedElement, { direction, max_depth: maxDepth })
            .then((res) => {
                setResult(res);
                setLoading(false);
                onShowDetail(
                    `Impact: ${selectedElement}`,
                    <ImpactDetailContent result={res} />,
                );
            })
            .catch((err) => { setError(String(err)); setLoading(false); });
    }, [selectedProfile, selectedElement, direction, maxDepth, onShowDetail]);

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                    Impact Analysis
                </span>
            </div>

            <div style={{ padding: 16 }}>
                {/* Controls row */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <select
                        value={selectedProfile}
                        onChange={(e) => setSelectedProfile(e.target.value)}
                        style={{ padding: '6px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4 }}
                    >
                        <option value="">Select Profile</option>
                        {profiles.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
                    </select>
                    <select
                        value={direction}
                        onChange={(e) => setDirection(e.target.value)}
                        style={{ padding: '6px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4 }}
                    >
                        <option value="both">Both</option>
                        <option value="downstream">Downstream</option>
                        <option value="upstream">Upstream</option>
                    </select>
                    <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        Depth
                        <input
                            type="number"
                            min={1}
                            max={10}
                            value={maxDepth}
                            onChange={(e) => setMaxDepth(Number(e.target.value))}
                            style={{ width: 48, padding: '4px 6px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4 }}
                        />
                    </label>
                    <button
                        onClick={onAnalyze}
                        disabled={loading || !selectedElement || !selectedProfile}
                        style={{
                            padding: '6px 16px', fontSize: 12, fontWeight: 600,
                            border: '1px solid var(--accent)', borderRadius: 4,
                            background: loading || !selectedElement ? 'var(--border)' : 'var(--accent)',
                            color: 'var(--bg-card)', cursor: loading || !selectedElement ? 'default' : 'pointer',
                        }}
                    >
                        {loading ? 'Analyzing...' : 'Analyze Impact'}
                    </button>
                </div>

                {/* Element browser */}
                <div style={{ border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16 }}>
                    <div style={{
                        padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: '8px 8px 0 0',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>Element Browser</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                            {loadingElements ? 'Loading...' : `${filteredElements.length} / ${elements.length} elements`}
                        </span>
                    </div>
                    <div style={{ padding: '8px 12px' }}>
                        <input
                            placeholder="Search elements..."
                            value={elementSearch}
                            onChange={(e) => setElementSearch(e.target.value)}
                            style={{ width: '100%', padding: '4px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4, boxSizing: 'border-box' }}
                        />
                    </div>
                    <div style={{ maxHeight: 240, overflowY: 'auto', borderTop: '1px solid var(--bg-hover)' }}>
                        {loadingElements ? (
                            <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>Loading elements...</div>
                        ) : filteredElements.length === 0 ? (
                            <div style={{ padding: 16, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
                                {elements.length === 0 ? 'Select a profile to load elements' : 'No elements match search'}
                            </div>
                        ) : (
                            filteredElements.map((node) => {
                                const selected = node.name === selectedElement;
                                return (
                                    <div
                                        key={node.name}
                                        onClick={() => setSelectedElement(node.name)}
                                        style={{
                                            display: 'flex', alignItems: 'center', gap: 8, padding: '5px 12px',
                                            cursor: 'pointer', fontSize: 11, borderBottom: '1px solid var(--bg-hover)',
                                            background: selected ? 'var(--accent-bg)' : 'transparent',
                                            border: selected ? '1px solid var(--accent)' : '1px solid transparent',
                                            borderRadius: 4,
                                        }}
                                    >
                                        <span style={{ fontWeight: 600, color: 'var(--text-primary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {node.name}
                                        </span>
                                        {node.layer && (
                                            <span style={{ padding: '1px 6px', borderRadius: 3, fontSize: 10, fontWeight: 600, background: 'var(--bg-hover)', color: 'var(--text-secondary)' }}>
                                                {node.layer}
                                            </span>
                                        )}
                                        {node.kernel_type && (
                                            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{node.kernel_type}</span>
                                        )}
                                    </div>
                                );
                            })
                        )}
                    </div>
                </div>

                {/* Error */}
                {error && (
                    <div style={{
                        padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                        background: 'var(--bg-secondary)', fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16,
                    }}>
                        Unable to run impact analysis — API server may be unavailable.
                    </div>
                )}

                {/* Inline result summary */}
                {result && (
                    <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 12, marginBottom: 16 }}>
                        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8 }}>RESULT SUMMARY</div>
                        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
                            <div>
                                <span style={{ color: 'var(--text-secondary)' }}>Affected: </span>
                                <strong>{result.affected_count}</strong> elements
                            </div>
                            <div>
                                <span style={{ color: 'var(--text-secondary)' }}>Direction: </span>
                                <strong>{result.direction}</strong>
                            </div>
                            <div>
                                <span style={{ color: 'var(--text-secondary)' }}>Depth: </span>
                                <strong>{result.max_depth}</strong>
                            </div>
                        </div>
                        {result.affected_count > 0 && (
                            <div style={{ marginTop: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                {Object.keys(result.impact).slice(0, 20).map((el) => (
                                    <span key={el} style={{
                                        padding: '2px 6px', borderRadius: 3, fontSize: 10, fontWeight: 600,
                                        background: 'var(--accent-bg)', color: 'var(--accent-text)', border: '1px solid #bfdbfe',
                                    }}>
                                        {el}
                                    </span>
                                ))}
                                {Object.keys(result.impact).length > 20 && (
                                    <span style={{ fontSize: 10, color: 'var(--text-muted)', alignSelf: 'center' }}>
                                        +{Object.keys(result.impact).length - 20} more
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                )}

                <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 16 }}>
                    Analyze the impact of changing a profile element.
                    Shows upstream and downstream affected elements with propagation paths.
                </div>
            </div>
        </div>
    );
}
