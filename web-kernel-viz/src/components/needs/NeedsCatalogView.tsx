
import { useCallback, useState, type ReactNode } from 'react';
import {
    useNeedsCatalogs,
    useCatalogNeeds,
    useNeedsCatalogDetail,
} from '@/api/hooks';
import { fetchNeedDetail } from '@/api/client';
import type { NeedSummary, NeedDetail } from '@/api/types';
import { ErrorBanner } from '@/components/ui';

interface NeedsCatalogViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

// --- Priority/Status colors ---
const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
    DRAFT: { bg: 'var(--bg-hover)', fg: 'var(--text-secondary)' },
    EXPRESSED: { bg: 'var(--accent-bg)', fg: 'var(--accent)' },
    ACKNOWLEDGED: { bg: 'var(--success-bg)', fg: 'var(--success-text)' },
    ADDRESSED: { bg: 'var(--success-bg)', fg: 'var(--success-text)' },
    WITHDRAWN: { bg: 'var(--error-bg)', fg: 'var(--error-text)' },
};
const PRIORITY_COLORS: Record<string, { bg: string; fg: string }> = {
    LOW: { bg: 'var(--bg-hover)', fg: 'var(--text-secondary)' },
    MEDIUM: { bg: 'var(--warning-bg)', fg: 'var(--warning-text)' },
    HIGH: { bg: 'var(--warning-bg)', fg: 'var(--warning-text)' },
    CRITICAL: { bg: 'var(--error-bg)', fg: 'var(--error-text)' },
};

function Badge({ label, colors }: { label: string; colors?: { bg: string; fg: string } }) {
    const c = colors || { bg: 'var(--bg-hover)', fg: 'var(--text-secondary)' };
    return (
        <span style={{
            fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
            background: c.bg, color: c.fg, whiteSpace: 'nowrap',
        }}>
            {label}
        </span>
    );
}

function NeedDetailView({ detail }: { detail: NeedDetail }) {
    return (
        <div style={{ fontSize: 12, lineHeight: 1.7 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
                wants to <em>{detail.action}</em> {detail.subject}
                {detail.target && <> for <strong>{detail.target}</strong></>}
            </div>

            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                <Badge label={detail.status} colors={STATUS_COLORS[detail.status]} />
                <Badge label={detail.priority} colors={PRIORITY_COLORS[detail.priority]} />
                <Badge label={`v${detail.version}`} />
                {detail.complexity && <Badge label={detail.complexity} />}
            </div>

            {detail.purpose && (
                <Section label="Purpose">
                    <div style={{ color: 'var(--text-secondary)' }}>{detail.purpose}</div>
                </Section>
            )}

            {detail.justifications.length > 0 && (
                <Section label="Justifications">
                    {detail.justifications.map((j, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                            <Badge label={j.type} />
                            <span style={{ color: 'var(--text-secondary)', marginLeft: 6 }}>{j.description}</span>
                        </div>
                    ))}
                </Section>
            )}

            {detail.kernel_refs.length > 0 && (
                <Section label="Kernel References">
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {detail.kernel_refs.map((ref) => (
                            <span key={ref} style={{
                                fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                                background: 'var(--accent-bg)', color: 'var(--accent)', cursor: 'pointer',
                            }}>
                                {ref}
                            </span>
                        ))}
                    </div>
                </Section>
            )}

            {detail.cause_types.length > 0 && (
                <Section label="Cause Types">
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {detail.cause_types.map((ct) => <Badge key={ct} label={ct} />)}
                    </div>
                </Section>
            )}

            {detail.tags.length > 0 && (
                <Section label="Tags">
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {detail.tags.map((t) => <Badge key={t} label={t} />)}
                    </div>
                </Section>
            )}

            {detail.process_units.length > 0 && (
                <Section label="Process Units">
                    {detail.process_units.map((pu) => (
                        <div key={pu.id} style={{
                            padding: '6px 8px', marginBottom: 4, background: 'var(--bg-secondary)',
                            borderRadius: 4, border: '1px solid var(--border)',
                        }}>
                            <div style={{ fontWeight: 600, fontSize: 11 }}>
                                #{pu.sequence} {pu.label}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                                Stage: {pu.stage} {pu.description && `— ${pu.description}`}
                            </div>
                        </div>
                    ))}
                </Section>
            )}

            <Section label="Metadata">
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    ID: {detail.id} | Lineage: {detail.lineage_id}
                    <br />
                    Created: {detail.created_at} | Updated: {detail.updated_at}
                </div>
            </Section>
        </div>
    );
}

function Section({ label, children }: { label: string; children: ReactNode }) {
    return (
        <div style={{ marginBottom: 12 }}>
            <div style={{
                fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase',
                letterSpacing: '0.05em', marginBottom: 4,
            }}>
                {label}
            </div>
            {children}
        </div>
    );
}

export default function NeedsCatalogView({ onShowDetail }: NeedsCatalogViewProps) {
    const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Filters
    const [filterStatus, setFilterStatus] = useState('');
    const [filterPriority, setFilterPriority] = useState('');
    const [filterStakeholder, setFilterStakeholder] = useState('');

    // React Query hooks
    const {
        data: catalogs = [],
        isLoading: catalogsLoading,
        isError: catalogsError,
        refetch: refetchCatalogs,
    } = useNeedsCatalogs();

    const filterOpts = {
        ...(filterStatus ? { status: filterStatus } : {}),
        ...(filterPriority ? { priority: filterPriority } : {}),
        ...(filterStakeholder ? { stakeholder_id: filterStakeholder } : {}),
    };

    const {
        data: needs = [],
    } = useCatalogNeeds(selectedCatalogId || '', Object.keys(filterOpts).length > 0 ? filterOpts : undefined);

    const {
        data: catalogDetail,
    } = useNeedsCatalogDetail(selectedCatalogId || '');

    const stakeholders = catalogDetail?.stakeholders || [];

    const handleNeedClick = useCallback((need: NeedSummary) => {
        if (!selectedCatalogId) return;
        fetchNeedDetail(selectedCatalogId, need.id)
            .then((detail) => {
                onShowDetail(
                    `${detail.action} ${detail.subject}`,
                    <NeedDetailView detail={detail} />,
                );
            })
            .catch((err) => setError(String(err)));
    }, [selectedCatalogId, onShowDetail]);

    const selectedCatalog = catalogs.find((c) => c.id === selectedCatalogId);

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif', overflow: 'auto' }}>
            {/* Header */}
            <div style={{
                padding: '10px 16px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)',
                display: 'flex', alignItems: 'center', gap: 8,
            }}>
                {selectedCatalogId && (
                    <button
                        onClick={() => { setSelectedCatalogId(null); }}
                        style={{
                            padding: '4px 10px', fontSize: 12, fontWeight: 600,
                            border: '1px solid var(--border)', borderRadius: 4, background: 'var(--bg-card)',
                            color: 'var(--text-secondary)', cursor: 'pointer',
                        }}
                    >
                        ← Back
                    </button>
                )}
                <span style={{
                    fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase',
                }}>
                    {selectedCatalog ? selectedCatalog.name : 'Needs Catalogs'}
                </span>
                {selectedCatalog && (
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        {selectedCatalog.needs_count} needs · {selectedCatalog.stakeholder_count} stakeholders
                    </span>
                )}
                <div style={{ marginLeft: 'auto' }} />
            </div>

            {catalogsError && (
                <div style={{ margin: '12px 16px' }}>
                    <ErrorBanner
                        message="Unable to load catalogs — API server may be unavailable."
                        onRetry={() => refetchCatalogs()}
                    />
                </div>
            )}
            {error && !catalogsError && (
                <div style={{
                    margin: '12px 16px', padding: '10px 14px',
                    border: '1px solid var(--error-bg)', borderRadius: 8, background: 'var(--error-bg)',
                    fontSize: 12, color: 'var(--error-text)',
                }}>
                    {error}
                </div>
            )}

            <div style={{ padding: 16 }}>
                {/* Catalog grid (no catalog selected) */}
                {!selectedCatalogId && (
                    <>
                        {catalogsLoading && <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading...</div>}
                        {!catalogsLoading && catalogs.length === 0 && (
                            <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                                No catalogs found.
                            </div>
                        )}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
                            {catalogs.map((cat) => (
                                <div
                                    key={cat.id}
                                    onClick={() => setSelectedCatalogId(cat.id)}
                                    style={{
                                        padding: 14, border: '1px solid var(--border)', borderRadius: 8,
                                        background: 'var(--bg-card)', cursor: 'pointer',
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.borderColor = 'var(--accent)';
                                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(59,130,246,0.08)';
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.borderColor = 'var(--border)';
                                        e.currentTarget.style.boxShadow = 'none';
                                    }}
                                >
                                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                                        {cat.name}
                                    </div>
                                    {cat.description && (
                                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8 }}>
                                            {cat.description}
                                        </div>
                                    )}
                                    <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--text-muted)' }}>
                                        <span>{cat.needs_count} needs</span>
                                        <span>{cat.stakeholder_count} stakeholders</span>
                                        <span>{cat.use_case_count} use cases</span>
                                    </div>
                                    <div style={{ fontSize: 9, color: 'var(--border-strong)', marginTop: 6 }}>
                                        Updated: {cat.updated_at}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                )}

                {/* Catalog detail (catalog selected) */}
                {selectedCatalogId && (
                    <div style={{ display: 'flex', gap: 16 }}>
                        {/* Stakeholders sidebar */}
                        <div style={{ width: 180, flexShrink: 0 }}>
                            <div style={{
                                fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
                                textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
                            }}>
                                Stakeholders
                            </div>
                            {stakeholders.length === 0 && (
                                <div style={{ fontSize: 11, color: 'var(--border-strong)' }}>No stakeholders</div>
                            )}
                            {stakeholders.map((sh) => (
                                <div
                                    key={sh.id}
                                    onClick={() => setFilterStakeholder(filterStakeholder === sh.id ? '' : sh.id)}
                                    style={{
                                        padding: '6px 8px', marginBottom: 4, borderRadius: 4,
                                        border: `1px solid ${filterStakeholder === sh.id ? 'var(--accent)' : 'var(--border)'}`,
                                        background: filterStakeholder === sh.id ? 'var(--accent-bg)' : 'var(--bg-card)',
                                        cursor: 'pointer', fontSize: 11,
                                    }}
                                >
                                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{sh.name}</div>
                                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{sh.role}</div>
                                </div>
                            ))}
                        </div>

                        {/* Needs list */}
                        <div style={{ flex: 1 }}>
                            {/* Filters */}
                            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                                <select
                                    value={filterStatus}
                                    onChange={(e) => setFilterStatus(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="">All Status</option>
                                    {['DRAFT', 'EXPRESSED', 'ACKNOWLEDGED', 'ADDRESSED', 'WITHDRAWN'].map((s) => (
                                        <option key={s} value={s}>{s}</option>
                                    ))}
                                </select>
                                <select
                                    value={filterPriority}
                                    onChange={(e) => setFilterPriority(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="">All Priority</option>
                                    {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((p) => (
                                        <option key={p} value={p}>{p}</option>
                                    ))}
                                </select>
                                {(filterStatus || filterPriority || filterStakeholder) && (
                                    <button
                                        onClick={() => { setFilterStatus(''); setFilterPriority(''); setFilterStakeholder(''); }}
                                        style={{
                                            padding: '4px 10px', fontSize: 11, border: '1px solid var(--border)',
                                            borderRadius: 4, background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer',
                                        }}
                                    >
                                        Clear filters
                                    </button>
                                )}
                            </div>

                            {needs.length === 0 && (
                                <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: 16 }}>
                                    No needs found. Express a need via the API to see it here.
                                </div>
                            )}

                            {needs.map((need) => (
                                <div
                                    key={need.id}
                                    onClick={() => handleNeedClick(need)}
                                    style={{
                                        padding: '10px 12px', marginBottom: 6,
                                        border: '1px solid var(--border)', borderRadius: 6,
                                        background: 'var(--bg-card)', cursor: 'pointer',
                                        transition: 'border-color 0.15s',
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--accent)'; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                        <Badge label={need.status} colors={STATUS_COLORS[need.status]} />
                                        <Badge label={need.priority} colors={PRIORITY_COLORS[need.priority]} />
                                        <span style={{ fontSize: 10, color: 'var(--border-strong)', marginLeft: 'auto' }}>v{need.version}</span>
                                    </div>
                                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                                        {need.action} {need.subject}
                                        {need.target && <span style={{ color: 'var(--text-secondary)' }}> → {need.target}</span>}
                                    </div>
                                    {need.kernel_refs.length > 0 && (
                                        <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                                            {need.kernel_refs.map((ref) => (
                                                <span key={ref} style={{
                                                    fontSize: 9, padding: '1px 6px', borderRadius: 3,
                                                    background: 'var(--accent-bg)', color: 'var(--accent)', fontWeight: 600,
                                                }}>
                                                    {ref}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

const filterSelectStyle = {
    padding: '4px 8px',
    fontSize: 11,
    border: '1px solid var(--border)',
    borderRadius: 4,
    background: 'var(--bg-card)',
    color: 'var(--text-primary)',
    cursor: 'pointer' as const,
};
