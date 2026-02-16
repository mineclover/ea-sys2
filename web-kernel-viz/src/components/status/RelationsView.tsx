
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchProfileTopology } from '@/api/client';
import { useProfiles } from '@/api/hooks';
import type { TopologyEdge } from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';
import { ErrorBanner, LoadingSpinner } from '@/components/ui';

interface ProfileEdgeData {
    name: string;
    version: string;
    edges: TopologyEdge[];
    distribution: Record<string, number>;
}

export default function RelationsView() {
    const { lang } = useAppState();
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});

    const profilesQuery = useProfiles();

    const topologyQuery = useQuery({
        queryKey: ['profiles-topology-edges', profilesQuery.data?.map((p) => p.name), lang],
        queryFn: async () => {
            const profiles = profilesQuery.data!;
            const results = await Promise.all(
                profiles.map((p) =>
                    fetchProfileTopology(p.name, { lang })
                        .then((topo) => ({
                            name: p.name,
                            version: p.version,
                            edges: topo.edges,
                            distribution: topo.relation_distribution,
                        }))
                        .catch(() => null),
                ),
            );
            const valid = results.filter((r): r is ProfileEdgeData => r !== null);
            if (valid.length === 0) throw new Error('No profile topology data available');
            return valid;
        },
        enabled: !!profilesQuery.data && profilesQuery.data.length > 0,
    });

    const toggle = (key: string) =>
        setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

    if (profilesQuery.isError || topologyQuery.isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <ErrorBanner
                    message="Unable to load profile relations — API server may be unavailable."
                    onRetry={() => { profilesQuery.refetch(); topologyQuery.refetch(); }}
                />
            </div>
        );
    }

    if (profilesQuery.isLoading || topologyQuery.isLoading || !topologyQuery.data) {
        return <LoadingSpinner message="Loading relations from all profiles..." />;
    }

    const data = topologyQuery.data;
    const totalEdges = data.reduce((s, p) => s + p.edges.length, 0);

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Relations — All Profiles</h2>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
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
                                border: '1px solid var(--border)', borderRadius: 6,
                                background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer',
                                textAlign: 'left',
                            }}
                        >
                            <span style={{ fontSize: 10 }}>{open ? '\u25BC' : '\u25B6'}</span>
                            {profile.name}
                            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4 }}>
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
                                                background: 'var(--bg-hover)', borderRadius: 3, color: 'var(--text-secondary)',
                                            }}>
                                                {rel}: {count}
                                            </span>
                                        ))}
                                </div>

                                {relations.map(([relName, edges]) => (
                                    <div key={relName} style={{ marginBottom: 8 }}>
                                        <div style={{
                                            fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
                                            padding: '4px 8px', background: 'var(--bg-hover)', borderRadius: 4,
                                            display: 'inline-block', marginBottom: 4,
                                        }}>
                                            {relName} ({edges.length})
                                        </div>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                            <thead>
                                                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                    <th style={thStyle}>Source</th>
                                                    <th style={{ ...thStyle, width: 30, textAlign: 'center' }}></th>
                                                    <th style={thStyle}>Target</th>
                                                    <th style={thStyle}>Rule ID</th>
                                                    <th style={thNumStyle}>Priority</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {edges.map((e, i) => (
                                                    <tr key={i} style={{ borderBottom: '1px solid var(--bg-hover)' }}>
                                                        <td style={tdStyle}>{e.source}</td>
                                                        <td style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-muted)' }}>{'\u2192'}</td>
                                                        <td style={tdStyle}>{e.target}</td>
                                                        <td style={{ ...tdStyle, fontSize: 10, color: 'var(--text-muted)' }}>{e.rule_id}</td>
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
    color: 'var(--text-muted)', textTransform: 'uppercase',
};

const thNumStyle: React.CSSProperties = { ...thStyle, textAlign: 'right' };

const tdStyle: React.CSSProperties = {
    padding: '6px 8px', fontSize: 12, color: 'var(--text-primary)',
};

const tdNumStyle: React.CSSProperties = { ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
