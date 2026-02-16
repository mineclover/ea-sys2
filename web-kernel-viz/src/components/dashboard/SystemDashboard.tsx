
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGovernanceDashboard, useCrossLayerSummary, useNeedsCatalogs, useGovernanceRules, usePromotionProposals } from '@/api/hooks';
import { LoadingSpinner, StatCard } from '@/components/ui';

const LAYER_COLORS: Record<string, string> = {
    infra: '#64748b',
    governance: '#ef4444',
    decision: '#a855f7',
    needs: '#06b6d4',
    kernel: '#3b82f6',
    flow: '#22c55e',
};

function layerColor(key: string): string {
    return LAYER_COLORS[key] ?? '#94a3b8';
}

function SectionHeader({ title, right }: { title: string; right?: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {title}
            </h3>
            {right && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{right}</span>}
        </div>
    );
}

function LayerCard({ layerKey, name, version, profileName, elementCount, relationCount, ruleCount, loaded, onClick }: {
    layerKey: string; name: string; version: string; profileName: string;
    elementCount: number; relationCount: number; ruleCount: number; loaded: boolean;
    onClick: () => void;
}) {
    const color = layerColor(layerKey);
    return (
        <div
            onClick={onClick}
            style={{
                flex: '1 1 140px', minWidth: 140, maxWidth: 200,
                padding: '12px 14px', background: 'var(--bg-card)',
                border: '1px solid var(--border)', borderLeft: `4px solid ${color}`,
                borderRadius: 8, cursor: 'pointer',
                transition: 'border-color 0.15s, box-shadow 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(59,130,246,0.10)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.borderLeftColor = color; e.currentTarget.style.boxShadow = 'none'; }}
        >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{name}</span>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: loaded ? '#22c55e' : 'var(--border)', flexShrink: 0 }} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>{profileName} v{version}</div>
            <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
                <span>E:{elementCount}</span>
                <span>R:{relationCount}</span>
                <span>Ru:{ruleCount}</span>
            </div>
        </div>
    );
}

function StackCard({ stackId, name, version, profileName, elementCount, relationCount, ruleCount, loaded }: {
    stackId: string; name: string; version: string; profileName: string;
    elementCount: number; relationCount: number; ruleCount: number; loaded: boolean;
}) {
    return (
        <div style={{
            flex: '1 1 220px', minWidth: 220, padding: '12px 16px', background: 'var(--bg-card)',
            border: '1px solid var(--border)', borderLeft: `4px solid ${LAYER_COLORS.governance}`, borderRadius: 8,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{name || stackId}</span>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: loaded ? '#22c55e' : 'var(--border)', flexShrink: 0 }} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>{profileName} v{version}</div>
            <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--text-secondary)' }}>
                <span>E:{elementCount}</span>
                <span>R:{relationCount}</span>
                <span>Ru:{ruleCount}</span>
            </div>
        </div>
    );
}

function FrameworkBadge({ name, version, elementCount, relationCount, ruleCount }: {
    name: string; version: string; elementCount: number; relationCount: number; ruleCount: number;
}) {
    return (
        <div style={{
            display: 'inline-flex', flexDirection: 'column', gap: 2,
            padding: '8px 12px', background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12,
        }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{name} {version}</span>
            <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>E:{elementCount} R:{relationCount} Ru:{ruleCount}</span>
        </div>
    );
}

export default function SystemDashboard() {
    const navigate = useNavigate();
    const { data: dashboard, isLoading: dashLoading } = useGovernanceDashboard();
    const { data: crossLayer } = useCrossLayerSummary();
    const { data: catalogs } = useNeedsCatalogs();
    const { data: rules } = useGovernanceRules();
    const { data: proposals } = usePromotionProposals();

    const totalNeeds = catalogs?.reduce((s, c) => s + c.needs_count, 0) ?? 0;

    const ruleStateDist = useMemo(() => {
        if (!rules) return null;
        const dist: Record<string, number> = {};
        for (const r of rules) {
            dist[r.state] = (dist[r.state] || 0) + 1;
        }
        return { total: rules.length, dist };
    }, [rules]);

    const pendingProposals = proposals?.filter((p) => p.status === 'pending') ?? [];

    if (dashLoading) {
        return <LoadingSpinner message="Loading dashboard..." />;
    }

    return (
        <div style={{
            flex: 1, overflow: 'auto', padding: '24px 32px',
            fontFamily: 'system-ui, -apple-system, sans-serif', background: 'var(--bg-secondary)',
        }}>
            <div style={{ marginBottom: 24 }}>
                <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>System Overview</h1>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-secondary)' }}>EA-Sys Governance Framework</p>
            </div>

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 28 }}>
                {dashboard && (
                    <StatCard
                        label="Kernel Schema"
                        value={`${dashboard.schema.entity_count} entities`}
                        sub={`${dashboard.schema.relation_count} relations`}
                        onClick={() => navigate('/explorer/kernel-schema')}
                    />
                )}
                {crossLayer && (
                    <StatCard
                        label="Cross-Layer Topology"
                        value={`${crossLayer.total_nodes} nodes`}
                        sub={`${crossLayer.total_edges} edges`}
                    />
                )}
            </div>

            {dashboard && (
                <div style={{ marginBottom: 28 }}>
                    <SectionHeader
                        title="Layer Profiles"
                        right={`${dashboard.managed_layers.layers.filter(l => l.loaded).length}/${dashboard.managed_layers.layers.length} loaded`}
                    />
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        {dashboard.managed_layers.layers.map((layer) => (
                            <LayerCard
                                key={layer.layer_key}
                                layerKey={layer.layer_key}
                                name={layer.name}
                                version={layer.version}
                                profileName={layer.profile_name}
                                elementCount={layer.element_count}
                                relationCount={layer.relation_count}
                                ruleCount={layer.rule_count}
                                loaded={layer.loaded}
                                onClick={() => navigate(`/explorer/profile/${encodeURIComponent(layer.profile_name)}`)}
                            />
                        ))}
                    </div>
                </div>
            )}

            {dashboard && dashboard.managed_layers.governance_stack.length > 0 && (
                <div style={{ marginBottom: 28 }}>
                    <SectionHeader title="Governance Stack" />
                    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                        {dashboard.managed_layers.governance_stack.map((stack) => (
                            <StackCard
                                key={stack.stack_id}
                                stackId={stack.stack_id}
                                name={stack.name}
                                version={stack.version}
                                profileName={stack.profile_name}
                                elementCount={stack.element_count}
                                relationCount={stack.relation_count}
                                ruleCount={stack.rule_count}
                                loaded={stack.loaded}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Governance Activity */}
            {(ruleStateDist || pendingProposals.length > 0) && (
                <div style={{ marginBottom: 28 }}>
                    <SectionHeader title="Governance Activity" />
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                        {ruleStateDist && (
                            <div style={{
                                flex: '1 1 280px', minWidth: 280, padding: '14px 16px',
                                background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
                            }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10 }}>
                                    Rule State Distribution
                                    <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 8 }}>{ruleStateDist.total} total</span>
                                </div>
                                <div style={{ display: 'flex', gap: 4, height: 20, borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
                                    {Object.entries(ruleStateDist.dist).map(([state, count]) => (
                                        <div
                                            key={state}
                                            title={`${state}: ${count}`}
                                            style={{
                                                flex: count,
                                                background: state === 'active' ? '#22c55e' : state === 'proposed' ? 'var(--accent)' : state === 'draft' ? 'var(--text-muted)' : state === 'deprecated' ? '#ef4444' : 'var(--border)',
                                                minWidth: count > 0 ? 4 : 0,
                                            }}
                                        />
                                    ))}
                                </div>
                                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                    {Object.entries(ruleStateDist.dist).map(([state, count]) => (
                                        <div key={state} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                                            <span style={{
                                                width: 8, height: 8, borderRadius: 2,
                                                background: state === 'active' ? '#22c55e' : state === 'proposed' ? 'var(--accent)' : state === 'draft' ? 'var(--text-muted)' : state === 'deprecated' ? '#ef4444' : 'var(--border)',
                                            }} />
                                            <span style={{ color: 'var(--text-secondary)' }}>{state}</span>
                                            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{count}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        {pendingProposals.length > 0 && (
                            <div
                                onClick={() => navigate('/governance/simulation')}
                                style={{
                                    flex: '0 1 240px', minWidth: 200, padding: '14px 16px',
                                    background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8,
                                    cursor: 'pointer',
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#a855f7'; }}
                                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
                            >
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8 }}>Pending Promotions</div>
                                <div style={{ fontSize: 24, fontWeight: 700, color: '#a855f7', marginBottom: 4 }}>{pendingProposals.length}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>proposals awaiting review</div>
                            </div>
                        )}
                        <StatCard
                            label="Rule Lifecycle"
                            value={ruleStateDist?.total ?? '—'}
                            sub="Manage rules"
                            onClick={() => navigate('/governance/rule-lifecycle')}
                        />
                    </div>
                </div>
            )}

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {dashboard && dashboard.frameworks.length > 0 && (
                    <div style={{ flex: 1, minWidth: 280 }}>
                        <SectionHeader title="Framework Coverage" />
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                            {dashboard.frameworks.map((fw) => (
                                <FrameworkBadge
                                    key={fw.name}
                                    name={fw.name}
                                    version={fw.version}
                                    elementCount={fw.element_count}
                                    relationCount={fw.relation_count}
                                    ruleCount={fw.rule_count}
                                />
                            ))}
                        </div>
                    </div>
                )}

                {catalogs && (
                    <div style={{ flex: 1, minWidth: 280 }}>
                        <SectionHeader title="Needs Catalogs" />
                        <StatCard
                            label="Catalogs"
                            value={catalogs.length}
                            sub={`${totalNeeds} needs total`}
                            onClick={() => navigate('/needs/catalog')}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
