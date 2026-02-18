
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchProfileTopology } from '@/api/client';
import { useProfiles } from '@/api/hooks';
import type { TopologyEdge } from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';
import { Badge, ErrorBanner, LoadingSpinner } from '@/components/ui';
import { PageHeader } from '@/components/layout';

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
                    fetchProfileTopology(p.name, {
                        lang,
                        view_mode: 'summary',
                        surface_only: true,
                        max_edges: 900,
                    })
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
            <PageHeader
                metaKey="status.relations"
                subtitle={`${totalEdges} edges across ${data.length} profiles`}
                rightContent={
                    <>
                        <Badge
                            label={lang === 'ko' ? 'M1 요약' : 'M1 summary'}
                            bg="var(--status-indigo-bg)"
                            color="var(--status-indigo-text)"
                        />
                        <Badge
                            label={lang === 'ko' ? '표층만' : 'surface-only'}
                            bg="var(--status-success-bg)"
                            color="var(--status-success-text)"
                        />
                        <Badge label="max:900" />
                    </>
                }
            />

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
                                background: 'var(--secondary)', color: 'var(--foreground)', cursor: 'pointer',
                                textAlign: 'left',
                            }}
                        >
                            <span style={{ fontSize: 10 }}>{open ? '\u25BC' : '\u25B6'}</span>
                            {profile.name}
                            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--muted-foreground)', marginLeft: 4 }}>
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
                                                background: 'var(--accent)', borderRadius: 3, color: 'var(--muted-foreground)',
                                            }}>
                                                {rel}: {count}
                                            </span>
                                        ))}
                                </div>

                                {relations.map(([relName, edges]) => (
                                    <div key={relName} style={{ marginBottom: 8 }}>
                                        <div style={{
                                            fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)',
                                            padding: '4px 8px', background: 'var(--accent)', borderRadius: 4,
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
                                                    <th style={thStyle}>Semantic</th>
                                                    <th style={thNumStyle}>Edges</th>
                                                    <th style={thNumStyle}>Priority</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {edges.map((e, i) => (
                                                    <tr key={i} style={{ borderBottom: '1px solid var(--accent)' }}>
                                                        <td style={tdStyle}>{e.source}</td>
                                                        <td style={{ ...tdStyle, textAlign: 'center', color: 'var(--muted-foreground)' }}>{'\u2192'}</td>
                                                        <td style={tdStyle}>{e.target}</td>
                                                        <td style={{ ...tdStyle, fontSize: 10, color: 'var(--muted-foreground)' }}>
                                                            {e.semantic_axis ?? 'other'}
                                                            {e.semantic_intent ? `/${e.semantic_intent}` : ''}
                                                        </td>
                                                        <td style={tdNumStyle}>{e.rule_count ?? 1}</td>
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
    color: 'var(--muted-foreground)', textTransform: 'uppercase',
};

const thNumStyle: React.CSSProperties = { ...thStyle, textAlign: 'right' };

const tdStyle: React.CSSProperties = {
    padding: '6px 8px', fontSize: 12, color: 'var(--foreground)',
};

const tdNumStyle: React.CSSProperties = { ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
