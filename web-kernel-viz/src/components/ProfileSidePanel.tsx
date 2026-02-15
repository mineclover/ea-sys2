
import { useEffect, useState } from 'react';
import { fetchProfileDescription, fetchProfileTopology } from '@/api/client';
import type { ProfileDescription, ProfileTopologyResponse } from '@/api/types';

interface ProfileSidePanelProps {
    profileName: string;
    profiles: { name: string; version: string }[];
    onSelectProfile: (name: string) => void;
    visibleLayers: Set<string>;
    onToggleLayer: (layer: string) => void;
}

const LAYER_COLORS: Record<string, string> = {
    Infra: '#64748b',
    Governance: '#ef4444',
    Decision: '#a855f7',
    Needs: '#06b6d4',
    Kernel: '#3b82f6',
    Flow: '#22c55e',
};

export default function ProfileSidePanel({
    profileName,
    profiles,
    onSelectProfile,
    visibleLayers,
    onToggleLayer,
}: ProfileSidePanelProps) {
    const [desc, setDesc] = useState<ProfileDescription | null>(null);
    const [topo, setTopo] = useState<ProfileTopologyResponse | null>(null);

    useEffect(() => {
        if (!profileName) return;
        fetchProfileDescription(profileName).then(setDesc).catch(() => setDesc(null));
        fetchProfileTopology(profileName).then(setTopo).catch(() => setTopo(null));
    }, [profileName]);

    return (
        <div style={{ fontSize: 12, lineHeight: 1.6 }}>
            {/* Profile Selector */}
            <div style={sectionStyle}>
                <div style={labelStyle}>Profile</div>
                <select
                    value={profileName}
                    onChange={(e) => onSelectProfile(e.target.value)}
                    style={selectStyle}
                >
                    {profiles.map((p) => (
                        <option key={p.name} value={p.name}>
                            {p.name} (v{p.version})
                        </option>
                    ))}
                </select>
            </div>

            {/* Summary Stats */}
            {desc && topo && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Summary</div>
                    <div style={statsGridStyle}>
                        <StatBadge label="Elements" value={desc.element_count} color="#3b82f6" />
                        <StatBadge label="Relations" value={desc.relation_count} color="#a855f7" />
                        <StatBadge label="Rules" value={desc.rule_count} color="#f97316" />
                        <StatBadge label="Edges" value={topo.edge_count} color="#22c55e" />
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', gap: 6 }}>
                        <span style={{ ...miniPill, background: '#dcfce7', color: '#166534' }}>
                            Allow {desc.rule_summary.allow}
                        </span>
                        <span style={{ ...miniPill, background: '#fee2e2', color: '#991b1b' }}>
                            Deny {desc.rule_summary.deny}
                        </span>
                    </div>
                </div>
            )}

            {/* Layer Filter */}
            {desc && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Layers</div>
                    {desc.elements_by_layer.map((lb) => {
                        const active = visibleLayers.has(lb.layer);
                        const color = LAYER_COLORS[lb.layer] || '#64748b';
                        return (
                            <label
                                key={lb.layer}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    padding: '3px 0',
                                    cursor: 'pointer',
                                    opacity: active ? 1 : 0.5,
                                }}
                            >
                                <input
                                    type="checkbox"
                                    checked={active}
                                    onChange={() => onToggleLayer(lb.layer)}
                                    style={{ accentColor: color }}
                                />
                                <span style={{
                                    width: 8, height: 8, borderRadius: '50%',
                                    background: color, display: 'inline-block',
                                }} />
                                <span style={{ flex: 1 }}>{lb.layer}</span>
                                <span style={{ color: '#94a3b8' }}>{lb.count}</span>
                            </label>
                        );
                    })}
                </div>
            )}

            {/* Elements by Layer */}
            {desc && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Elements</div>
                    {desc.elements_by_layer
                        .filter((lb) => visibleLayers.has(lb.layer))
                        .map((lb) => (
                            <div key={lb.layer} style={{ marginBottom: 8 }}>
                                <div style={{
                                    fontSize: 11, fontWeight: 600,
                                    color: LAYER_COLORS[lb.layer] || '#64748b',
                                    marginBottom: 2,
                                }}>
                                    {lb.layer} ({lb.count})
                                </div>
                                {lb.elements.map((e) => (
                                    <div key={e.name} style={{
                                        padding: '2px 0 2px 10px',
                                        fontSize: 11,
                                        color: '#475569',
                                        borderLeft: `2px solid ${LAYER_COLORS[lb.layer] || '#e2e8f0'}`,
                                        marginBottom: 1,
                                    }}>
                                        {e.name}
                                        <span style={{ color: '#94a3b8', marginLeft: 4 }}>
                                            {e.kernel_type}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        ))}
                </div>
            )}

            {/* Relation Distribution */}
            {topo && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Relations</div>
                    {Object.entries(topo.relation_distribution)
                        .sort(([, a], [, b]) => b - a)
                        .map(([rel, count]) => (
                            <div key={rel} style={{
                                display: 'flex', justifyContent: 'space-between',
                                padding: '2px 0', fontSize: 11,
                            }}>
                                <span style={{ color: '#475569' }}>{rel}</span>
                                <span style={{ color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>{count}</span>
                            </div>
                        ))}
                </div>
            )}
        </div>
    );
}

function StatBadge({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div style={{
            textAlign: 'center',
            padding: '6px 4px',
            background: `${color}08`,
            borderRadius: 6,
            border: `1px solid ${color}20`,
        }}>
            <div style={{ fontSize: 16, fontWeight: 700, color }}>{value}</div>
            <div style={{ fontSize: 9, color: '#94a3b8', textTransform: 'uppercase' }}>{label}</div>
        </div>
    );
}

const sectionStyle = { marginBottom: 16 };
const labelStyle = {
    fontSize: 10 as const,
    fontWeight: 700 as const,
    color: '#94a3b8',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: 6,
};
const selectStyle = {
    width: '100%',
    padding: '6px 8px',
    fontSize: 12,
    border: '1px solid #cbd5e1',
    borderRadius: 4,
    background: '#fff',
};
const statsGridStyle = {
    display: 'grid' as const,
    gridTemplateColumns: '1fr 1fr',
    gap: 6,
};
const miniPill = {
    fontSize: 10,
    fontWeight: 600 as number,
    padding: '1px 6px',
    borderRadius: 3,
};
