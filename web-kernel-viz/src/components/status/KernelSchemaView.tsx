
import { useState } from 'react';
import { useKernelEntities, useKernelRelations, useKernelRules } from '@/api/hooks';
import type {
    KernelEntityLayer,
    KernelRelationLayer,
    I18nString,
} from '@/api/types';
import { useAppState } from '@/contexts/AppStateContext';
import { ErrorBanner, LoadingSpinner } from '@/components/ui';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

export default function KernelSchemaView() {
    const { lang } = useAppState();
    const [expandedEntities, setExpandedEntities] = useState<Record<string, boolean>>({});
    const [expandedRelations, setExpandedRelations] = useState<Record<string, boolean>>({});
    const [expandedRuleGroup, setExpandedRuleGroup] = useState<string | null>(null);

    const entitiesQuery = useKernelEntities({ lang });
    const relationsQuery = useKernelRelations({ lang });
    const rulesQuery = useKernelRules();
    const groupRulesQuery = useKernelRules(
        expandedRuleGroup ? { group: expandedRuleGroup } : undefined,
    );

    const toggleEntity = (key: string) =>
        setExpandedEntities((prev) => ({ ...prev, [key]: !prev[key] }));
    const toggleRelation = (key: string) =>
        setExpandedRelations((prev) => ({ ...prev, [key]: !prev[key] }));

    const toggleRuleGroup = (groupName: string) => {
        setExpandedRuleGroup((prev) => (prev === groupName ? null : groupName));
    };

    if (entitiesQuery.isError || relationsQuery.isError || rulesQuery.isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <ErrorBanner
                    message="Unable to load kernel schema — API server may be unavailable."
                    onRetry={() => { entitiesQuery.refetch(); relationsQuery.refetch(); rulesQuery.refetch(); }}
                />
            </div>
        );
    }

    if (entitiesQuery.isLoading || relationsQuery.isLoading || rulesQuery.isLoading) {
        return <LoadingSpinner message="Loading kernel schema..." />;
    }

    const entities = entitiesQuery.data!;
    const relations = relationsQuery.data!;
    const rules = rulesQuery.data!;
    const groups = rules.groups || [];

    const groupRules = expandedRuleGroup ? (groupRulesQuery.data?.rules || null) : null;
    const groupLoading = expandedRuleGroup ? groupRulesQuery.isLoading : false;

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 24 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>Kernel Metamodel Schema</h2>
                <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
                    <Stat label="Entity Types" value={entities.total} />
                    <Stat label="Relation Types" value={relations.total} />
                    <Stat label="Rules" value={rules.total} />
                </div>
            </div>

            {/* --- Entities --- */}
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
                                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                        <th style={thStyle}>Name</th>
                                        <th style={thStyle}>Parent</th>
                                        <th style={thStyle}>Abstract</th>
                                        <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {layer.entities.map((e) => (
                                        <tr key={e.name} style={{ borderBottom: '1px solid var(--bg-hover)' }}>
                                            <td style={tdStyle}>
                                                {i18n(e.display_name, lang) || e.name}
                                                {e.display_name && <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>({e.name})</span>}
                                            </td>
                                            <td style={{ ...tdStyle, color: e.parent ? 'var(--text-secondary)' : 'var(--border-strong)' }}>{e.parent || '\u2014'}</td>
                                            <td style={tdStyle}>
                                                {e.is_abstract && (
                                                    <span style={{
                                                        padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                                        background: '#fef3c7', color: '#92400e', borderRadius: 3,
                                                    }}>abstract</span>
                                                )}
                                            </td>
                                            <td style={{ ...tdStyle, color: 'var(--text-secondary)' }}>{i18n(e.description, lang)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                );
            })}

            <div style={{ height: 24 }} />

            {/* --- Relations --- */}
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
                                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                        <th style={thStyle}>Name</th>
                                        <th style={thStyle}>Parent</th>
                                        <th style={thStyle}>Roles</th>
                                        <th style={{ ...thStyle, minWidth: 200 }}>Description</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {layer.relations.map((r) => (
                                        <tr key={r.name} style={{ borderBottom: '1px solid var(--bg-hover)' }}>
                                            <td style={tdStyle}>
                                                {i18n(r.display_name, lang) || r.name}
                                                {r.display_name && <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 4 }}>({r.name})</span>}
                                            </td>
                                            <td style={{ ...tdStyle, color: r.parent ? 'var(--text-secondary)' : 'var(--border-strong)' }}>{r.parent || '\u2014'}</td>
                                            <td style={tdStyle}>
                                                {r.roles.length > 0 ? (
                                                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                                        {r.roles.map((role) => `${role.name}: ${role.player}`).join(' \u2194 ')}
                                                    </span>
                                                ) : (
                                                    <span style={{ color: 'var(--border-strong)' }}>\u2014</span>
                                                )}
                                            </td>
                                            <td style={{ ...tdStyle, color: 'var(--text-secondary)' }}>{i18n(r.description, lang)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                );
            })}

            <div style={{ height: 24 }} />

            {/* --- Rules --- */}
            <SectionHeader title="Rules" subtitle={`${rules.total} rules in ${groups.length} groups`} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
                {groups.map((g) => (
                    <div key={g.name}>
                        <button
                            onClick={() => toggleRuleGroup(g.name)}
                            style={{
                                width: '100%', textAlign: 'left',
                                padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 8,
                                background: expandedRuleGroup === g.name ? 'var(--accent-bg)' : 'var(--bg-card)',
                                cursor: 'pointer',
                            }}
                        >
                            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{g.name}</div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{g.count} rules</div>
                        </button>
                        {expandedRuleGroup === g.name && (
                            <div style={{ marginTop: 4, border: '1px solid var(--border)', borderRadius: 6, overflow: 'hidden' }}>
                                {groupLoading ? (
                                    <div style={{ padding: 10, fontSize: 12, color: 'var(--text-muted)' }}>Loading...</div>
                                ) : groupRules && groupRules.length > 0 ? (
                                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                                <th style={thSmStyle}>Source</th>
                                                <th style={thSmStyle}>Target</th>
                                                <th style={thSmStyle}>Relation</th>
                                                <th style={thSmStyle}>Valid</th>
                                                <th style={thSmStyle}>Pri</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {groupRules.map((r) => (
                                                <tr key={r.id} style={{ borderBottom: '1px solid var(--bg-hover)' }}>
                                                    <td style={tdSmStyle}>{r.source}</td>
                                                    <td style={tdSmStyle}>{r.target}</td>
                                                    <td style={tdSmStyle}>{r.relation}</td>
                                                    <td style={tdSmStyle}>
                                                        <span style={{
                                                            padding: '1px 5px', fontSize: 10, fontWeight: 600, borderRadius: 3,
                                                            background: r.valid ? 'var(--success-bg)' : 'var(--error-bg)',
                                                            color: r.valid ? 'var(--success-text)' : 'var(--error-text)',
                                                        }}>{r.valid ? 'ALLOW' : 'DENY'}</span>
                                                    </td>
                                                    <td style={{ ...tdSmStyle, color: 'var(--text-muted)' }}>{r.priority}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                ) : (
                                    <div style={{ padding: 10, fontSize: 12, color: 'var(--text-muted)' }}>No rules</div>
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
        <div style={{ marginBottom: 12, borderBottom: '2px solid var(--border)', paddingBottom: 6 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>{title}</h3>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{subtitle}</span>
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
                border: '1px solid var(--border)', borderRadius: 6,
                background: 'var(--bg-secondary)', color: 'var(--text-primary)', cursor: 'pointer',
                textAlign: 'left',
            }}
        >
            <span style={{ fontSize: 10 }}>{open ? '\u25BC' : '\u25B6'}</span>
            {label}
            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4 }}>({count})</span>
        </button>
    );
}

function Stat({ label, value }: { label: string; value: number }) {
    return (
        <div style={{
            padding: '8px 14px', border: '1px solid var(--border)', borderRadius: 6,
            background: 'var(--bg-secondary)', minWidth: 80,
        }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
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

const thSmStyle: React.CSSProperties = {
    textAlign: 'left', padding: '5px 6px', fontSize: 10, fontWeight: 600,
    color: 'var(--text-muted)', textTransform: 'uppercase',
};

const tdSmStyle: React.CSSProperties = {
    padding: '5px 6px', fontSize: 11, color: 'var(--text-primary)',
};
