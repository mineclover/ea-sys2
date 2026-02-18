
import { useEffect, useState } from 'react';
import { fetchNeedsByKernelRef, fetchProfileDescription, fetchProfileTopology } from '@/api/client';
import type { NeedsByKernelRefResult, ProfileDescription, ProfileTopologyResponse } from '@/api/types';
import { getLayerColor } from '@/lib/layer-colors';


interface ProfileSidePanelProps {
    profileName: string;
    visibleLayers: Set<string>;
    onToggleLayer: (layer: string) => void;
    crossLayerOnly: boolean;
    onToggleCrossLayer: () => void;
    goalScope: string | null;
    onSelectGoalScope: (goal: string | null) => void;
    scopeCount: { visible: number; total: number } | null;
    needScope: string | null;
    onSelectNeedScope: (needId: string | null) => void;
    needScopeCount: { visible: number; total: number } | null;
    needOptions: { id: string; label: string }[];
    selectedNode?: string | null;
}

export default function ProfileSidePanel({
    profileName,
    visibleLayers,
    onToggleLayer,
    crossLayerOnly,
    onToggleCrossLayer,
    goalScope,
    onSelectGoalScope,
    scopeCount,
    needScope,
    onSelectNeedScope,
    needScopeCount,
    needOptions,
    selectedNode,
}: ProfileSidePanelProps) {
    const [desc, setDesc] = useState<ProfileDescription | null>(null);
    const [topo, setTopo] = useState<ProfileTopologyResponse | null>(null);
    const [linkedNeeds, setLinkedNeeds] = useState<NeedsByKernelRefResult | null>(null);
    const [loadingNeeds, setLoadingNeeds] = useState(false);

    useEffect(() => {
        if (!profileName) return;
        fetchProfileDescription(profileName).then(setDesc).catch(() => setDesc(null));
        fetchProfileTopology(profileName, {
            view_mode: 'summary',
            surface_only: true,
            max_edges: 600,
        }).then(setTopo).catch(() => setTopo(null));
    }, [profileName]);

    useEffect(() => {
        if (!selectedNode) { setLinkedNeeds(null); return; }
        setLoadingNeeds(true);
        fetchNeedsByKernelRef(selectedNode)
            .then((res) => { setLinkedNeeds(res); setLoadingNeeds(false); })
            .catch(() => { setLinkedNeeds(null); setLoadingNeeds(false); });
    }, [selectedNode]);

    const summaryText = desc && topo
        ? [
            `Profile: ${profileName}`,
            `Elements: ${desc.element_count}`,
            `Relations: ${desc.relation_count}`,
            `Rules: ${desc.rule_count} (Allow ${desc.rule_summary.allow} / Deny ${desc.rule_summary.deny})`,
            `Edges: ${topo.edge_count}`,
        ].join('\n')
        : '';

    const encodedName = encodeURIComponent(profileName);
    const endpointsText = [
        `# ${profileName}`,
        `/profiles/${encodedName}`,
        `/profiles/${encodedName}/topology`,
        `/profiles/${encodedName}/reachable?element={element}&max_depth=3`,
        `/profiles/${encodedName}/paths?source={src}&target={tgt}`,
        `/profiles/${encodedName}/impact?element={element}`,
    ].join('\n');

    return (
        <div style={{ fontSize: 12, lineHeight: 1.6 }}>
            {/* Current Profile */}
            {profileName && (
                <div style={{ marginBottom: 14, padding: '8px 10px', background: 'var(--accent)', borderRadius: 6 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 2 }}>
                        Current Profile
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--foreground)', wordBreak: 'break-all' }}>
                        {profileName}
                    </div>
                    {desc && (
                        <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 2 }}>
                            v{desc.version} · {desc.standard} · {desc.organization}
                        </div>
                    )}
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                        {Array.from(visibleLayers).map((layer) => (
                            <span key={layer} style={{
                                fontSize: 9, fontWeight: 600,
                                padding: '1px 6px', borderRadius: 3,
                                background: `${getLayerColor(layer).color}18`,
                                color: getLayerColor(layer).color,
                                border: `1px solid ${getLayerColor(layer).color}40`,
                            }}>
                                {layer}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Summary Stats */}
            {desc && topo && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Summary</div>
                    <div style={statsGridStyle}>
                        <StatBadge label="Elements" value={desc.element_count} color={getLayerColor('Kernel').color} />
                        <StatBadge label="Relations" value={desc.relation_count} color={getLayerColor('Decision').color} />
                        <StatBadge label="Rules" value={desc.rule_count} color="var(--status-warning-text)" />
                        <StatBadge label="Edges" value={topo.edge_count} color={getLayerColor('Flow').color} />
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', gap: 6, marginBottom: 8 }}>
                        <span style={{ ...miniPill, background: 'var(--status-success-bg)', color: 'var(--status-success-text)' }}>
                            Allow {desc.rule_summary.allow}
                        </span>
                        <span style={{ ...miniPill, background: 'var(--status-error-bg)', color: 'var(--status-error-text)' }}>
                            Deny {desc.rule_summary.deny}
                        </span>
                    </div>
                    <textarea
                        readOnly
                        value={summaryText}
                        onFocus={(e) => e.target.select()}
                        rows={5}
                        style={{
                            width: '100%', boxSizing: 'border-box',
                            fontSize: 10, fontFamily: 'monospace',
                            color: 'var(--foreground)', background: 'var(--secondary)',
                            border: '1px solid var(--border)', borderRadius: 4,
                            padding: '6px 8px', resize: 'vertical',
                            lineHeight: 1.6,
                        }}
                    />
                </div>
            )}

            {/* Goal Scope */}
            {topo && (() => {
                const goals = topo.nodes.filter((n) => n.category === 'Goal');
                if (goals.length === 0) return null;
                return (
                    <div style={sectionStyle}>
                        <div style={labelStyle}>Goal Scope</div>
                        <select
                            value={goalScope ?? ''}
                            onChange={(e) => onSelectGoalScope(e.target.value || null)}
                            style={{
                                width: '100%', boxSizing: 'border-box',
                                fontSize: 11, padding: '5px 6px',
                                border: '1px solid var(--border)', borderRadius: 4,
                                background: goalScope ? 'var(--muted)' : 'var(--card)',
                                color: 'var(--foreground)', cursor: 'pointer',
                            }}
                        >
                            <option value="">All (no scope)</option>
                            {goals.map((g) => (
                                <option key={g.name} value={g.name}>{g.name}</option>
                            ))}
                        </select>
                        {scopeCount && (
                            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4 }}>
                                Showing {scopeCount.visible} of {scopeCount.total} elements
                            </div>
                        )}
                    </div>
                );
            })()}

            {/* Need Scope */}
            {needOptions.length > 0 && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Need Scope</div>
                    <select
                        value={needScope ?? ''}
                        onChange={(e) => onSelectNeedScope(e.target.value || null)}
                        style={{
                            width: '100%', boxSizing: 'border-box',
                            fontSize: 11, padding: '5px 6px',
                            border: '1px solid var(--border)', borderRadius: 4,
                            background: needScope ? 'var(--status-success-bg)' : 'var(--card)',
                            color: 'var(--foreground)', cursor: 'pointer',
                        }}
                    >
                        <option value="">All (no scope)</option>
                        {needOptions.map((n) => (
                            <option key={n.id} value={n.id}>{n.label}</option>
                        ))}
                    </select>
                    {needScopeCount && (
                        <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4 }}>
                            Showing {needScopeCount.visible} of {needScopeCount.total} elements
                        </div>
                    )}
                </div>
            )}

            {/* Linked Needs (selected node) */}
            {selectedNode && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Linked Needs</div>
                    <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 6 }}>
                        Element: <strong style={{ color: 'var(--foreground)' }}>{selectedNode}</strong>
                    </div>
                    {loadingNeeds ? (
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>Loading...</div>
                    ) : !linkedNeeds || linkedNeeds.matches.length === 0 ? (
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', padding: '4px 0' }}>No linked needs found</div>
                    ) : (
                        linkedNeeds.matches.map((m) => (
                            <div key={`${m.catalog_id}-${m.need_id}`} style={{
                                padding: '5px 8px', marginBottom: 4,
                                border: '1px solid var(--border)', borderRadius: 4,
                                fontSize: 11, background: 'var(--secondary)',
                            }}>
                                <div style={{ fontWeight: 600, color: 'var(--foreground)' }}>
                                    {m.action} {m.subject}
                                </div>
                                <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
                                    <span style={{ color: 'var(--muted-foreground)' }}>{m.catalog_name}</span>
                                    <span style={{
                                        padding: '0 4px', borderRadius: 2, fontSize: 10, fontWeight: 600,
                                        background: m.status === 'active' ? 'var(--status-success-bg)' : 'var(--accent)',
                                        color: m.status === 'active' ? 'var(--status-success-text)' : 'var(--muted-foreground)',
                                    }}>
                                        {m.status}
                                    </span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}

            {/* Layer Filter */}
            {desc && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>Layers</div>
                    {desc.elements_by_layer.map((lb) => {
                        const active = visibleLayers.has(lb.layer);
                        const color = getLayerColor(lb.layer).color;
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
                                <span style={{ color: 'var(--muted-foreground)' }}>{lb.count}</span>
                            </label>
                        );
                    })}
                    <label style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '6px 0 0', marginTop: 4,
                        borderTop: '1px solid var(--border)',
                        cursor: 'pointer',
                    }}>
                        <input
                            type="checkbox"
                            checked={crossLayerOnly}
                            onChange={onToggleCrossLayer}
                            style={{ accentColor: 'var(--status-warning-text)' }}
                        />
                        <span style={{ fontSize: 11, fontWeight: 600, color: crossLayerOnly ? 'var(--status-warning-text)' : 'var(--muted-foreground)' }}>
                            Cross-layer only
                        </span>
                    </label>
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
                                    color: getLayerColor(lb.layer).color,
                                    marginBottom: 2,
                                }}>
                                    {lb.layer} ({lb.count})
                                </div>
                                {lb.elements.map((e) => (
                                    <div key={e.name} style={{
                                        padding: '2px 0 2px 10px',
                                        fontSize: 11,
                                        color: 'var(--foreground)',
                                        borderLeft: `2px solid ${getLayerColor(lb.layer).color}`,
                                        marginBottom: 1,
                                    }}>
                                        {e.name}
                                        <span style={{ color: 'var(--muted-foreground)', marginLeft: 4 }}>
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
                                <span style={{ color: 'var(--foreground)' }}>{rel}</span>
                                <span style={{ color: 'var(--muted-foreground)', fontVariantNumeric: 'tabular-nums' }}>{count}</span>
                            </div>
                        ))}
                </div>
            )}

            {/* API Endpoints */}
            {profileName && (
                <div style={sectionStyle}>
                    <div style={labelStyle}>API Endpoints</div>
                    <textarea
                        readOnly
                        value={endpointsText}
                        onFocus={(e) => e.target.select()}
                        rows={6}
                        style={{
                            width: '100%', boxSizing: 'border-box',
                            fontSize: 10, fontFamily: 'monospace',
                            color: 'var(--foreground)', background: 'var(--secondary)',
                            border: '1px solid var(--border)', borderRadius: 4,
                            padding: '6px 8px', resize: 'vertical',
                            lineHeight: 1.6,
                        }}
                    />
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
            <div style={{ fontSize: 9, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>{label}</div>
        </div>
    );
}

const sectionStyle = { marginBottom: 16 };
const labelStyle = {
    fontSize: 10 as const,
    fontWeight: 700 as const,
    color: 'var(--muted-foreground)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: 6,
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
