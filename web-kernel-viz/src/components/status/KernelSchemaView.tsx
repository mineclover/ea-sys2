
import { useEffect, useState, useCallback } from 'react';
import { fetchKernelEntities, fetchKernelRelations, fetchKernelRules } from '@/api/client';
import type {
    KernelEntitiesResponse, KernelEntityLayer,
    KernelRelationsResponse, KernelRelationLayer,
    KernelRulesResponse, KernelRuleSummary,
    I18nString,
} from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

interface KernelData {
    entities: KernelEntitiesResponse;
    relations: KernelRelationsResponse;
    rules: KernelRulesResponse;
}

export default function KernelSchemaView() {
    const { lang } = useAppState();
    const [data, setData] = useState<KernelData | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [expandedEntities, setExpandedEntities] = useState<Record<string, boolean>>({});
    const [expandedRelations, setExpandedRelations] = useState<Record<string, boolean>>({});
    const [expandedRuleGroup, setExpandedRuleGroup] = useState<string | null>(null);
    const [groupRules, setGroupRules] = useState<KernelRuleSummary[] | null>(null);
    const [groupLoading, setGroupLoading] = useState(false);

    const load = useCallback(() => {
        setError(null);
        setData(null);
        Promise.all([
            fetchKernelEntities({ lang }),
            fetchKernelRelations({ lang }),
            fetchKernelRules(),
        ])
            .then(([entities, relations, rules]) => setData({ entities, relations, rules }))
            .catch(() => setError('unavailable'));
    }, [lang]);

    useEffect(() => { load(); }, [load]);

    const toggleEntity = (key: string) =>
        setExpandedEntities((prev) => ({ ...prev, [key]: !prev[key] }));
    const toggleRelation = (key: string) =>
        setExpandedRelations((prev) => ({ ...prev, [key]: !prev[key] }));

    const toggleRuleGroup = useCallback((groupName: string) => {
        if (expandedRuleGroup === groupName) {
            setExpandedRuleGroup(null);
            setGroupRules(null);
            return;
        }
        setExpandedRuleGroup(groupName);
        setGroupRules(null);
        setGroupLoading(true);
        fetchKernelRules({ group: groupName })
            .then((res) => setGroupRules(res.rules || []))
            .catch(() => setGroupRules([]))
            .finally(() => setGroupLoading(false));
    }, [expandedRuleGroup]);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                    background: '#f8fafc', fontSize: 12, color: '#64748b',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load kernel schema — API server may be unavailable.
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
        return <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>Loading kernel schema…</div>;
    }

    const { entities, relations, rules } = data;
    const groups = rules.groups || [];

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 24 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' }}>Kernel Metamodel Schema</h2>
                <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                    <Stat label="Entity Types" value={entities.total} />
                    <Stat label="Relation Types" value={relations.total} />
                    <Stat label="Rules" value={rules.total} />
                </div>
            </div>

            {/* ─── Entities ─── */}
            <SectionHeader title="Entity Types" subtitle={`${entities.total} types across ${entities.layers.length} layers`} />
            {entities.layers.map((layer: KernelEntityLayer) => {
                const open = expandedEntities[layer.name] !== false;
                return (
                    <div key={layer.name} style={{ marginBottom: 12 }}>
                        <CollapsibleHeader
                            label={layer.name}
                            count={layer.count}
                            open={open}
                            onClick={() => toggleEntity(layer.name)}
                        />
                        {open && (
                            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 4, fontSize: 12 }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                        <th style={thStyle}>Name</th>
                                        <th style={thStyle}>Parent</th>
                                        <th style={thStyle}>Abstract</th>
                                        <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {layer.entities.map((e) => (
                                        <tr key={e.name} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                            <td style={tdStyle}>
                                                {i18n(e.display_name, lang) || e.name}
                                                {e.display_name && <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 4 }}>({e.name})</span>}
                                            </td>
                                            <td style={{ ...tdStyle, color: e.parent ? '#475569' : '#cbd5e1' }}>{e.parent || '\u2014'}</td>
                                            <td style={tdStyle}>
                                                {e.is_abstract && (
                                                    <span style={{
                                                        padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                                        background: '#fef3c7', color: '#92400e', borderRadius: 3,
                                                    }}>abstract</span>
                                                )}
                                            </td>
                                            <td style={{ ...tdStyle, color: '#64748b' }}>{i18n(e.description, lang)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                );
            })}

            <div style={{ height: 24 }} />

            {/* ─── Relations ─── */}
            <SectionHeader title="Relation Types" subtitle={`${relations.total} types across ${relations.layers.length} layers`} />
            {relations.layers.map((layer: KernelRelationLayer) => {
                const open = expandedRelations[layer.name] !== false;
                return (
                    <div key={layer.name} style={{ marginBottom: 12 }}>
                        <CollapsibleHeader
                            label={layer.name}
                            count={layer.count}
                            open={open}
                            onClick={() => toggleRelation(layer.name)}
                        />
                        {open && (
                            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 4, fontSize: 12 }}>
                                <thead>
                                    <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                        <th style={thStyle}>Name</th>
                                        <th style={thStyle}>Parent</th>
                                        <th style={thStyle}>Roles</th>
                                        <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {layer.relations.map((r) => (
                                        <tr key={r.name} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                            <td style={tdStyle}>
                                                {i18n(r.display_name, lang) || r.name}
                                                {r.display_name && <span style={{ fontSize: 10, color: '#94a3b8', marginLeft: 4 }}>({r.name})</span>}
                                            </td>
                                            <td style={{ ...tdStyle, color: r.parent ? '#475569' : '#cbd5e1' }}>{r.parent || '\u2014'}</td>
                                            <td style={tdStyle}>
                                                {r.roles.length > 0 ? (
                                                    <span style={{ fontSize: 11, color: '#475569' }}>
                                                        {r.roles.map((role) => `${role.name}: ${role.player}`).join(' \u2194 ')}
                                                    </span>
                                                ) : (
                                                    <span style={{ color: '#cbd5e1' }}>\u2014</span>
                                                )}
                                            </td>
                                            <td style={{ ...tdStyle, color: '#64748b' }}>{i18n(r.description, lang)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                );
            })}

            <div style={{ height: 24 }} />

            {/* ─── Rules ─── */}
            <SectionHeader title="Rules" subtitle={`${rules.total} rules in ${groups.length} groups`} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
                {groups.map((g) => (
                    <div key={g.name}>
                        <button
                            onClick={() => toggleRuleGroup(g.name)}
                            style={{
                                width: '100%', textAlign: 'left',
                                padding: '10px 12px', border: '1px solid #e2e8f0', borderRadius: 8,
                                background: expandedRuleGroup === g.name ? '#eff6ff' : '#fff',
                                cursor: 'pointer',
                            }}
                        >
                            <div style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{g.name}</div>
                            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 2 }}>{g.count} rules</div>
                        </button>
                        {expandedRuleGroup === g.name && (
                            <div style={{ marginTop: 4, border: '1px solid #e2e8f0', borderRadius: 6, overflow: 'hidden' }}>
                                {groupLoading ? (
                                    <div style={{ padding: 10, fontSize: 12, color: '#94a3b8' }}>Loading…</div>
                                ) : groupRules && groupRules.length > 0 ? (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                <th style={thSmStyle}>Source</th>
                                                <th style={thSmStyle}>Target</th>
                                                <th style={thSmStyle}>Relation</th>
                                                <th style={thSmStyle}>Valid</th>
                                                <th style={thSmStyle}>Pri</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {groupRules.map((r) => (
                                                <tr key={r.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                                    <td style={tdSmStyle}>{r.source}</td>
                                                    <td style={tdSmStyle}>{r.target}</td>
                                                    <td style={tdSmStyle}>{r.relation}</td>
                                                    <td style={tdSmStyle}>
                                                        <span style={{
                                                            padding: '1px 5px', fontSize: 10, fontWeight: 600, borderRadius: 3,
                                                            background: r.valid ? '#dcfce7' : '#fee2e2',
                                                            color: r.valid ? '#166534' : '#991b1b',
                                                        }}>{r.valid ? 'ALLOW' : 'DENY'}</span>
                                                    </td>
                                                    <td style={{ ...tdSmStyle, color: '#94a3b8' }}>{r.priority}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div style={{ padding: 10, fontSize: 12, color: '#94a3b8' }}>No rules</div>
                                )}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
    return (
        <div style={{ marginBottom: 12, borderBottom: '2px solid #e2e8f0', paddingBottom: 6 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#334155' }}>{title}</h3>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>{subtitle}</span>
        </div>
    );
}

function CollapsibleHeader({ label, count, open, onClick }: { label: string; count: number; open: boolean; onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            style={{
                display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                padding: '8px 12px', fontSize: 13, fontWeight: 600,
                border: '1px solid #e2e8f0', borderRadius: 6,
                background: '#f8fafc', color: '#334155', cursor: 'pointer',
                textAlign: 'left',
            }}
        >
            <span style={{ fontSize: 10 }}>{open ? '\u25BC' : '\u25B6'}</span>
            {label}
            <span style={{ fontSize: 11, fontWeight: 400, color: '#94a3b8', marginLeft: 4 }}>({count})</span>
        </button>
    );
}

function Stat({ label, value }: { label: string; value: number }) {
    return (
        <div style={{
            padding: '8px 14px', border: '1px solid #e2e8f0', borderRadius: 6,
            background: '#f8fafc', minWidth: 80,
        }}>
            <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b' }}>{value}</div>
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

const thSmStyle: React.CSSProperties = {
    textAlign: 'left', padding: '5px 6px', fontSize: 10, fontWeight: 600,
    color: '#94a3b8', textTransform: 'uppercase',
};

const tdSmStyle: React.CSSProperties = {
    padding: '5px 6px', fontSize: 11, color: '#1e293b',
};
