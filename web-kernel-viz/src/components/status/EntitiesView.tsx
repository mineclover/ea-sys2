
import { useEffect, useState, useCallback } from 'react';
import { fetchProfiles, fetchProfileTopology } from '@/api/client';
import type { ProfileListItem, ProfileTopologyResponse, TopologyNode, I18nString } from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';

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
    const [data, setData] = useState<ProfileData[] | null>(null);
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
                                nodes: topo.nodes,
                            }))
                            .catch(() => null),
                    ),
                ),
            )
            .then((results) => {
                const valid = results.filter((r): r is ProfileData => r !== null);
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
                    Unable to load profile elements — API server may be unavailable.
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
        return <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>Loading elements from all profiles…</div>;
    }

    const totalNodes = data.reduce((s, p) => s + p.nodes.length, 0);

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' }}>Elements — All Profiles</h2>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>
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
                                border: '1px solid #e2e8f0', borderRadius: 6,
                                background: '#f8fafc', color: '#334155', cursor: 'pointer',
                                textAlign: 'left',
                            }}
                        >
                            <span style={{ fontSize: 10 }}>{open ? '\u25BC' : '\u25B6'}</span>
                            {profile.name}
                            <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8', marginLeft: 4 }}>
                                v{profile.version} — {profile.nodes.length} elements
                            </span>
                        </button>
                        {open && (
                            <div style={{ paddingLeft: 12, marginTop: 4 }}>
                                {layers.map(([layerName, nodes]) => (
                                    <div key={layerName} style={{ marginBottom: 8 }}>
                                        <div style={{
                                            fontSize: 11, fontWeight: 600, color: '#64748b',
                                            padding: '4px 8px', background: '#f1f5f9', borderRadius: 4,
                                            display: 'inline-block', marginBottom: 4,
                                        }}>
                                            {layerName} ({nodes.length})
                                        </div>
                                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                                            <thead>
                                                <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                    <th style={thStyle}>Name</th>
                                                    <th style={thStyle}>Kernel Type</th>
                                                    <th style={thStyle}>Category</th>
                                                    <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {nodes.map((n) => (
                                                    <tr key={n.name} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                                        <td style={tdStyle}>
                                                            {i18n(n.display_name, lang) || n.name}
                                                            {n.display_name && (
                                                                <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 4 }}>({n.name})</span>
                                                            )}
                                                        </td>
                                                        <td style={tdStyle}>
                                                            <span style={{
                                                                padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                                                background: '#ede9fe', color: '#6d28d9', borderRadius: 3,
                                                            }}>{n.kernel_type}</span>
                                                        </td>
                                                        <td style={{ ...tdStyle, color: '#64748b' }}>{n.category || '—'}</td>
                                                        <td style={{ ...tdStyle, color: '#64748b' }}>{i18n(n.description, lang)}</td>
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

const tdStyle: React.CSSProperties = {
    padding: '6px 8px', fontSize: 12, color: '#1e293b',
};
