
import { useEffect, useState, useCallback } from 'react';
import { fetchProfiles, fetchProfileTopology } from '@/api/client';
import type { ProfileListItem, ProfileTopologyResponse, TopologyEdge } from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';

interface ProfileEdgeData {
    name: string;
    version: string;
    edges: TopologyEdge[];
    distribution: Record<string, number>;
}

export default function RelationsView() {
    const { lang } = useAppState();
    const [data, setData] = useState<ProfileEdgeData[] | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});

    const load = useCallback(() => {
        setError(null);
        setData(null);
        fetchProfiles()
            .then((profiles: ProfileListItem[]) =>
                Promise.all(
                    profiles.map((p) =>
                        fetchProfileTopology(p.name, { lang })
                            .then((topo: ProfileTopologyResponse) => ({
                                name: p.name,
                                version: p.version,
                                edges: topo.edges,
                                distribution: topo.relation_distribution,
                            }))
                            .catch(() => null),
                    ),
                ),
            )
            .then((results) => {
                const valid = results.filter((r): r is ProfileEdgeData => r !== null);
                if (valid.length === 0) {
                    setError('unavailable');
                } else {
                    setData(valid);
                }
            })
            .catch(() => setError('unavailable'));
    }, [lang]);

    useEffect(() => { load(); }, [load]);

    const toggle = (key: string) =>
        setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                    background: '#f8fafc', fontSize: 12, color: '#64748b',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load profile relations — API server may be unavailable.
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
        return <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>Loading relations from all profiles…</div>;
    }

    const totalEdges = data.reduce((s, p) => s + p.edges.length, 0);

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' }}>Relations — All Profiles</h2>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>
                    Total: {totalEdges} edges across {data.length} profiles
                </span>
            </div>

            {data.map((profile) => {
                const open = expanded[profile.name] !== false;
                // Group edges by relation type
                const byRelation = new Map<string, TopologyEdge[]>();
                for (const e of profile.edges) {
                    const list = byRelation.get(e.relation) || [];
                    list.push(e);
                    byRelation.set(e.relation, list);
                }
                const relations = Array.from(byRelation.entries()).sort(([a], [b]) => a.localeCompare(b));

                return (
                    <div key={profile.name} style={{ marginBottom: 16 }}>
                        <button
                            onClick={() => toggle(profile.name)}
                            style={{
                                display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                                padding: '10px 14px', fontSize: 13, fontWeight: 600,
                                border: '1px solid #e2e8f0', borderRadius: 6,
                                background: '#f8fafc', color: '#334155', cursor: 'pointer',
                                textAlign: 'left',
                            }}
                        >
                            <span style={{ fontSize: 10 }}>{open ? '\u25BC' : '\u25B6'}</span>
                            {profile.name}
                            <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8', marginLeft: 4 }}>
                                v{profile.version} — {profile.edges.length} edges
                            </span>
                        </button>
                        {open && (
                            <div style={{ paddingLeft: 12, marginTop: 4 }}>
                                {/* Distribution summary */}
                                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                                    {Object.entries(profile.distribution)
                                        .sort(([, a], [, b]) => b - a)
                                        .map(([rel, count]) => (
                                            <span key={rel} style={{
                                                padding: '2px 8px', fontSize: 10, fontWeight: 600,
                                                background: '#f1f5f9', borderRadius: 3, color: '#475569',
                                            }}>
                                                {rel}: {count}
                                            </span>
                                        ))}
                                </div>

                                {relations.map(([relName, edges]) => (
                                    <div key={relName} style={{ marginBottom: 8 }}>
                                        <div style={{
                                            fontSize: 11, fontWeight: 600, color: '#64748b',
                                            padding: '4px 8px', background: '#f1f5f9', borderRadius: 4,
                                            display: 'inline-block', marginBottom: 4,
                                        }}>
                                            {relName} ({edges.length})
                                        </div>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                            <thead>
                                                <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                    <th style={thStyle}>Source</th>
                                                    <th style={{ ...thStyle, width: 30, textAlign: 'center' }}></th>
                                                    <th style={thStyle}>Target</th>
                                                    <th style={thStyle}>Rule ID</th>
                                                    <th style={thNumStyle}>Priority</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {edges.map((e, i) => (
                                                    <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                                        <td style={tdStyle}>{e.source}</td>
                                                        <td style={{ ...tdStyle, textAlign: 'center', color: '#94a3b8' }}>{'\u2192'}</td>
                                                        <td style={tdStyle}>{e.target}</td>
                                                        <td style={{ ...tdStyle, fontSize: 10, color: '#94a3b8' }}>{e.rule_id}</td>
                                                        <td style={tdNumStyle}>{e.priority}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}

const thStyle: React.CSSProperties = {
    textAlign: 'left', padding: '6px 8px', fontSize: 11, fontWeight: 600,
    color: '#94a3b8', textTransform: 'uppercase',
};

const thNumStyle: React.CSSProperties = { ...thStyle, textAlign: 'right' };

const tdStyle: React.CSSProperties = {
    padding: '6px 8px', fontSize: 12, color: '#1e293b',
};

const tdNumStyle: React.CSSProperties = { ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
