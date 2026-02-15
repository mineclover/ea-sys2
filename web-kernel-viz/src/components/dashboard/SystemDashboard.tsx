
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchGovernanceDashboard, fetchCrossLayerSummary, fetchNeedsCatalogs } from '@/api/client';
import type {
    GovernanceDashboardResponse,
    CrossLayerSummaryResponse,
    NeedsCatalogSummary,
} from '@/api/types';

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

/* ---------- local helpers ---------- */

function SectionHeader({ title, right }: { title: string; right?: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {title}
            </h3>
            {right && <span style={{ fontSize: 12, color: '#94a3b8' }}>{right}</span>}
        </div>
    );
}

function StatCard({ label, value, sub, onClick }: { label: string; value: string | number; sub?: string; onClick?: () => void }) {
    const [hovered, setHovered] = useState(false);
    return (
        <div
            onClick={onClick}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                flex: 1,
                minWidth: 180,
                padding: '16px 20px',
                background: '#fff',
                border: `1px solid ${hovered && onClick ? '#3b82f6' : '#e2e8f0'}`,
                borderRadius: 8,
                cursor: onClick ? 'pointer' : 'default',
                boxShadow: hovered && onClick ? '0 2px 8px rgba(59,130,246,0.10)' : 'none',
                transition: 'border-color 0.15s, box-shadow 0.15s',
            }}
        >
            <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: '#1e293b' }}>{value}</div>
            {sub && <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>{sub}</div>}
        </div>
    );
}

function LayerCard({ layerKey, name, version, profileName, elementCount, relationCount, ruleCount, loaded, onClick }: {
    layerKey: string; name: string; version: string; profileName: string;
    elementCount: number; relationCount: number; ruleCount: number; loaded: boolean;
    onClick: () => void;
}) {
    const [hovered, setHovered] = useState(false);
    const color = layerColor(layerKey);
    return (
        <div
            onClick={onClick}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                flex: '1 1 140px',
                minWidth: 140,
                maxWidth: 200,
                padding: '12px 14px',
                background: '#fff',
                border: `1px solid ${hovered ? '#3b82f6' : '#e2e8f0'}`,
                borderLeft: `4px solid ${color}`,
                borderRadius: 8,
                cursor: 'pointer',
                boxShadow: hovered ? '0 2px 8px rgba(59,130,246,0.10)' : 'none',
                transition: 'border-color 0.15s, box-shadow 0.15s',
            }}
        >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#1e293b' }}>{name}</span>
                <span style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: loaded ? '#22c55e' : '#e2e8f0',
                    flexShrink: 0,
                }} />
            </div>
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 8 }}>{profileName} v{version}</div>
            <div style={{ display: 'flex', gap: 8, fontSize: 11, color: '#64748b' }}>
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
            flex: '1 1 220px',
            minWidth: 220,
            padding: '12px 16px',
            background: '#fff',
            border: '1px solid #e2e8f0',
            borderLeft: `4px solid ${LAYER_COLORS.governance}`,
            borderRadius: 8,
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#1e293b' }}>{name || stackId}</span>
                <span style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: loaded ? '#22c55e' : '#e2e8f0',
                    flexShrink: 0,
                }} />
            </div>
            <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 8 }}>{profileName} v{version}</div>
            <div style={{ display: 'flex', gap: 8, fontSize: 11, color: '#64748b' }}>
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
            padding: '8px 12px',
            background: '#f8fafc',
            border: '1px solid #e2e8f0',
            borderRadius: 6,
            fontSize: 12,
        }}>
            <span style={{ fontWeight: 600, color: '#1e293b' }}>{name} {version}</span>
            <span style={{ fontSize: 10, color: '#64748b' }}>E:{elementCount} R:{relationCount} Ru:{ruleCount}</span>
        </div>
    );
}

/* ---------- Main component ---------- */

export default function SystemDashboard() {
    const navigate = useNavigate();
    const [dashboard, setDashboard] = useState<GovernanceDashboardResponse | null>(null);
    const [crossLayer, setCrossLayer] = useState<CrossLayerSummaryResponse | null>(null);
    const [catalogs, setCatalogs] = useState<NeedsCatalogSummary[] | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.allSettled([
            fetchGovernanceDashboard(),
            fetchCrossLayerSummary(),
            fetchNeedsCatalogs(),
        ]).then(([dashRes, crossRes, catRes]) => {
            if (dashRes.status === 'fulfilled') setDashboard(dashRes.value);
            if (crossRes.status === 'fulfilled') setCrossLayer(crossRes.value);
            if (catRes.status === 'fulfilled') setCatalogs(catRes.value);
            setLoading(false);
        });
    }, []);

    if (loading) {
        return (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', fontSize: 14 }}>
                Loading dashboard...
            </div>
        );
    }

    const totalNeeds = catalogs?.reduce((s, c) => s + c.needs_count, 0) ?? 0;

    return (
        <div style={{
            flex: 1,
            overflow: 'auto',
            padding: '24px 32px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            background: '#f8fafc',
        }}>
            {/* Page header */}
            <div style={{ marginBottom: 24 }}>
                <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: '#1e293b' }}>System Overview</h1>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#64748b' }}>EA-Sys Governance Framework</p>
            </div>

            {/* Top stat cards */}
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

            {/* Layer Profiles */}
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

            {/* Governance Stack */}
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

            {/* Bottom row: Frameworks + Needs */}
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
