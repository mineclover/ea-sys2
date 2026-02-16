
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchProfileTopology } from '@/api/client';
import { useProfiles } from '@/api/hooks';
import type { TopologyNode, I18nString } from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';
import { ErrorBanner, LoadingSpinner } from '@/components/ui';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

interface ProfileData {
    name: string;
    version: string;
    nodes: TopologyNode[];
}

export default function EntitiesView() {
    const { lang } = useAppState();
    const [expanded, setExpanded] = useState<Record<string, boolean>>({});

    const profilesQuery = useProfiles();

    const topologyQuery = useQuery({
        queryKey: ['profiles-topology-nodes', profilesQuery.data?.map((p) => p.name), lang],
        queryFn: async () => {
            const profiles = profilesQuery.data!;
            const results = await Promise.all(
                profiles.map((p) =>
                    fetchProfileTopology(p.name, { lang })
                        .then((topo) => ({
                            name: p.name,
                            version: p.version,
                            nodes: topo.nodes,
                        }))
                        .catch(() => null),
                ),
            );
            const valid = results.filter((r): r is ProfileData => r !== null);
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
                    message="Unable to load profile elements — API server may be unavailable."
                    onRetry={() => { profilesQuery.refetch(); topologyQuery.refetch(); }}
                />
            </div>
        );
    }

    if (profilesQuery.isLoading || topologyQuery.isLoading || !topologyQuery.data) {
        return <LoadingSpinner message="Loading elements from all profiles..." />;
    }

    const data = topologyQuery.data;
    const totalNodes = data.reduce((s, p) => s + p.nodes.length, 0);

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Elements — All Profiles</h2>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Total: {totalNodes} elements across {data.length} profiles
                </span>
            </div>

            {data.map((profile) => {
                const open = expanded[profile.name] !== false;
                // Group nodes by layer within this profile
                const byLayer = new Map<string, TopologyNode[]>();
                for (const n of profile.nodes) {
                    const list = byLayer.get(n.layer) || [];
                    list.push(n);
                    byLayer.set(n.layer, list);
                }
                const layers = Array.from(byLayer.entries()).sort(([a], [b]) => a.localeCompare(b));

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
                                v{profile.version} — {profile.nodes.length} elements
                            </span>
                        </button>
                        {open && (
                            <div style={{ paddingLeft: 12, marginTop: 4 }}>
                                {layers.map(([layerName, nodes]) => (
                                    <div key={layerName} style={{ marginBottom: 8 }}>
                                        <div style={{
                                            fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
                                            padding: '4px 8px', background: 'var(--bg-hover)', borderRadius: 4,
                                            display: 'inline-block', marginBottom: 4,
                                        }}>
                                            {layerName} ({nodes.length})
                                        </div>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                            <thead>
                                                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                    <th style={thStyle}>Name</th>
                                                    <th style={thStyle}>Kernel Type</th>
                                                    <th style={thStyle}>Category</th>
                                                    <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {nodes.map((n) => (
                                                    <tr key={n.name} style={{ borderBottom: '1px solid var(--bg-hover)' }}>
                                                        <td style={tdStyle}>
                                                            {i18n(n.display_name, lang) || n.name}
                                                            {n.display_name && (
                                                                <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>({n.name})</span>
                                                            )}
                                                        </td>
                                                        <td style={tdStyle}>
                                                            <span style={{
                                                                padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                                                background: '#ede9fe', color: '#6d28d9', borderRadius: 3,
                                                            }}>{n.kernel_type}</span>
                                                        </td>
                                                        <td style={{ ...tdStyle, color: 'var(--text-secondary)' }}>{n.category || '—'}</td>
                                                        <td style={{ ...tdStyle, color: 'var(--text-secondary)' }}>{i18n(n.description, lang)}</td>
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

const tdStyle: React.CSSProperties = {
    padding: '6px 8px', fontSize: 12, color: 'var(--text-primary)',
};
