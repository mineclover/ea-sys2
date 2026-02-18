
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGovernanceDashboard, useCrossLayerSummary, useNeedsCatalogs, useGovernanceRules, usePromotionProposals } from '@/api/hooks';
import { LoadingSpinner, StatCard } from '@/components/ui';
import { PageHeader } from '@/components/layout';
import { getLayerColor } from '@/lib/layer-colors';

function SectionHeader({ title, right }: { title: string; right?: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {title}
            </h3>
            {right && <span style={{ fontSize: 12, color: 'var(--muted-foreground)' }}>{right}</span>}
        </div>
    );
}

function LayerCard({ layerKey, name, version, profileName, elementCount, relationCount, ruleCount, loaded, onClick }: {
    layerKey: string; name: string; version: string; profileName: string;
    elementCount: number; relationCount: number; ruleCount: number; loaded: boolean;
    onClick: () => void;
}) {
    const color = getLayerColor(layerKey).color;
    return (
        <div
            onClick={onClick}
            style={{
                flex: '1 1 140px', minWidth: 140, maxWidth: 200,
                padding: '12px 14px', background: 'var(--card)',
                border: '1px solid var(--border)', borderLeft: `4px solid ${color}`,
                borderRadius: 8, cursor: 'pointer',
                transition: 'border-color 0.15s, box-shadow 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--primary)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(59,130,246,0.10)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.borderLeftColor = color; e.currentTarget.style.boxShadow = 'none'; }}
        >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--foreground)' }}>{name}</span>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: loaded ? 'var(--color-layer-flow)' : 'var(--border)', flexShrink: 0 }} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 8 }}>{profileName} v{version}</div>
            <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--muted-foreground)' }}>
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
            flex: '1 1 220px', minWidth: 220, padding: '12px 16px', background: 'var(--card)',
            border: '1px solid var(--border)', borderLeft: `4px solid ${getLayerColor('governance').color}`, borderRadius: 8,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--foreground)' }}>{name || stackId}</span>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: loaded ? 'var(--color-layer-flow)' : 'var(--border)', flexShrink: 0 }} />
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 8 }}>{profileName} v{version}</div>
            <div style={{ display: 'flex', gap: 8, fontSize: 11, color: 'var(--muted-foreground)' }}>
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
            padding: '8px 12px', background: 'var(--secondary)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12,
        }}>
            <span style={{ fontWeight: 600, color: 'var(--foreground)' }}>{name} {version}</span>
            <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>E:{elementCount} R:{relationCount} Ru:{ruleCount}</span>
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
            fontFamily: 'system-ui, -apple-system, sans-serif', background: 'var(--secondary)',
        }}>
            <PageHeader metaKey="dashboard" />

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
                                background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
                            }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted-foreground)', marginBottom: 10 }}>
                                    Rule State Distribution
                                    <span style={{ fontWeight: 400, color: 'var(--muted-foreground)', marginLeft: 8 }}>{ruleStateDist.total} total</span>
                                </div>
                                <div style={{ display: 'flex', gap: 4, height: 20, borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
                                    {Object.entries(ruleStateDist.dist).map(([state, count]) => (
                                        <div
                                            key={state}
                                            title={`${state}: ${count}`}
                                            style={{
                                                flex: count,
                                                background: state === 'active' ? 'var(--color-layer-flow)' : state === 'proposed' ? 'var(--primary)' : state === 'draft' ? 'var(--muted-foreground)' : state === 'deprecated' ? 'var(--destructive)' : 'var(--border)',
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
                                                background: state === 'active' ? 'var(--color-layer-flow)' : state === 'proposed' ? 'var(--primary)' : state === 'draft' ? 'var(--muted-foreground)' : state === 'deprecated' ? 'var(--destructive)' : 'var(--border)',
                                            }} />
                                            <span style={{ color: 'var(--muted-foreground)' }}>{state}</span>
                                            <span style={{ fontWeight: 600, color: 'var(--foreground)' }}>{count}</span>
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
                                    background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
                                    cursor: 'pointer',
                                }}
                                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--color-layer-decision)'; }}
                                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
                            >
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted-foreground)', marginBottom: 8 }}>Pending Promotions</div>
                                <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--color-layer-decision)', marginBottom: 4 }}>{pendingProposals.length}</div>
                                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>proposals awaiting review</div>
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
