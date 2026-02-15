
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import {
    fetchNeedsCatalogs,
    createNeedsCatalog,
    fetchCatalogNeeds,
    fetchNeedDetail,
    fetchNeedsCatalogDetail,
} from '@/api/client';
import type { NeedsCatalogSummary, NeedSummary, NeedDetail } from '@/api/types';

interface NeedsCatalogViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

// --- Priority/Status colors ---
const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
    DRAFT: { bg: '#f1f5f9', fg: '#64748b' },
    EXPRESSED: { bg: '#eff6ff', fg: '#3b82f6' },
    ACKNOWLEDGED: { bg: '#f0fdf4', fg: '#16a34a' },
    ADDRESSED: { bg: '#dcfce7', fg: '#166534' },
    WITHDRAWN: { bg: '#fef2f2', fg: '#991b1b' },
};
const PRIORITY_COLORS: Record<string, { bg: string; fg: string }> = {
    LOW: { bg: '#f1f5f9', fg: '#64748b' },
    MEDIUM: { bg: '#fefce8', fg: '#a16207' },
    HIGH: { bg: '#fff7ed', fg: '#c2410c' },
    CRITICAL: { bg: '#fef2f2', fg: '#dc2626' },
};

function Badge({ label, colors }: { label: string; colors?: { bg: string; fg: string } }) {
    const c = colors || { bg: '#f1f5f9', fg: '#64748b' };
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
            <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 12 }}>
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
                    <div style={{ color: '#475569' }}>{detail.purpose}</div>
                </Section>
            )}

            {detail.justifications.length > 0 && (
                <Section label="Justifications">
                    {detail.justifications.map((j, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                            <Badge label={j.type} />
                            <span style={{ color: '#475569', marginLeft: 6 }}>{j.description}</span>
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
                                background: '#eff6ff', color: '#3b82f6', cursor: 'pointer',
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
                            padding: '6px 8px', marginBottom: 4, background: '#f8fafc',
                            borderRadius: 4, border: '1px solid #e2e8f0',
                        }}>
                            <div style={{ fontWeight: 600, fontSize: 11 }}>
                                #{pu.sequence} {pu.label}
                            </div>
                            <div style={{ fontSize: 10, color: '#64748b' }}>
                                Stage: {pu.stage} {pu.description && `— ${pu.description}`}
                            </div>
                        </div>
                    ))}
                </Section>
            )}

            <Section label="Metadata">
                <div style={{ fontSize: 10, color: '#94a3b8' }}>
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
                fontSize: 10, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase',
                letterSpacing: '0.05em', marginBottom: 4,
            }}>
                {label}
            </div>
            {children}
        </div>
    );
}

export default function NeedsCatalogView({ onShowDetail }: NeedsCatalogViewProps) {
    const [catalogs, setCatalogs] = useState<NeedsCatalogSummary[]>([]);
    const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
    const [needs, setNeeds] = useState<NeedSummary[]>([]);
    const [stakeholders, setStakeholders] = useState<{ id: string; name: string; role: string }[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    // Filters
    const [filterStatus, setFilterStatus] = useState('');
    const [filterPriority, setFilterPriority] = useState('');
    const [filterStakeholder, setFilterStakeholder] = useState('');

    // Create catalog form
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [newCatalogName, setNewCatalogName] = useState('');
    const [newCatalogDesc, setNewCatalogDesc] = useState('');

    // Load catalogs
    const loadCatalogs = useCallback(() => {
        setLoading(true);
        setError(null);
        fetchNeedsCatalogs()
            .then(setCatalogs)
            .catch(() => setError('unavailable'))
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => { loadCatalogs(); }, [loadCatalogs]);

    // Load needs when catalog selected
    useEffect(() => {
        if (!selectedCatalogId) {
            setNeeds([]);
            setStakeholders([]);
            return;
        }
        const opts: Record<string, string> = {};
        if (filterStatus) opts.status = filterStatus;
        if (filterPriority) opts.priority = filterPriority;
        if (filterStakeholder) opts.stakeholder_id = filterStakeholder;

        fetchCatalogNeeds(selectedCatalogId, opts).then(setNeeds).catch(() => setNeeds([]));
        fetchNeedsCatalogDetail(selectedCatalogId)
            .then((detail) => setStakeholders(detail.stakeholders || []))
            .catch(() => setStakeholders([]));
    }, [selectedCatalogId, filterStatus, filterPriority, filterStakeholder]);

    const handleCreateCatalog = useCallback(() => {
        if (!newCatalogName.trim()) return;
        createNeedsCatalog(newCatalogName.trim(), newCatalogDesc.trim())
            .then(() => {
                setNewCatalogName('');
                setNewCatalogDesc('');
                setShowCreateForm(false);
                loadCatalogs();
            })
            .catch((err) => setError(String(err)));
    }, [newCatalogName, newCatalogDesc, loadCatalogs]);

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
                padding: '10px 16px', borderBottom: '1px solid #e2e8f0', background: '#fafbfc',
                display: 'flex', alignItems: 'center', gap: 8,
            }}>
                {selectedCatalogId && (
                    <button
                        onClick={() => { setSelectedCatalogId(null); setNeeds([]); }}
                        style={{
                            padding: '4px 10px', fontSize: 12, fontWeight: 600,
                            border: '1px solid #e2e8f0', borderRadius: 4, background: '#fff',
                            color: '#64748b', cursor: 'pointer',
                        }}
                    >
                        ← Back
                    </button>
                )}
                <span style={{
                    fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase',
                }}>
                    {selectedCatalog ? selectedCatalog.name : 'Needs Catalogs'}
                </span>
                {selectedCatalog && (
                    <span style={{ fontSize: 10, color: '#94a3b8' }}>
                        {selectedCatalog.needs_count} needs · {selectedCatalog.stakeholder_count} stakeholders
                    </span>
                )}
                <div style={{ marginLeft: 'auto' }}>
                    {!selectedCatalogId && error !== 'unavailable' && (
                        <button
                            onClick={() => setShowCreateForm((v) => !v)}
                            style={{
                                padding: '4px 12px', fontSize: 11, fontWeight: 600,
                                border: '1px solid #3b82f6', borderRadius: 4,
                                background: showCreateForm ? '#eff6ff' : '#3b82f6',
                                color: showCreateForm ? '#3b82f6' : '#fff',
                                cursor: 'pointer',
                            }}
                        >
                            {showCreateForm ? 'Cancel' : 'Create Catalog'}
                        </button>
                    )}
                </div>
            </div>

            {error === 'unavailable' && (
                <div style={{
                    margin: '12px 16px', padding: '14px 16px',
                    border: '1px solid #e2e8f0', borderRadius: 8, background: '#f8fafc',
                    fontSize: 12, color: '#64748b', display: 'flex', alignItems: 'center', gap: 10,
                }}>
                    <span>Unable to load catalogs — API server may be unavailable.</span>
                    <button
                        onClick={loadCatalogs}
                        style={{
                            padding: '4px 12px', fontSize: 11, fontWeight: 600,
                            border: '1px solid #cbd5e1', borderRadius: 4,
                            background: '#fff', color: '#475569', cursor: 'pointer',
                        }}
                    >
                        Retry
                    </button>
                </div>
            )}
            {error && error !== 'unavailable' && (
                <div style={{
                    margin: '12px 16px', padding: '10px 14px',
                    border: '1px solid #fecaca', borderRadius: 8, background: '#fef2f2',
                    fontSize: 12, color: '#991b1b',
                }}>
                    {error}
                </div>
            )}

            {/* Create form */}
            {showCreateForm && (
                <div style={{
                    margin: '12px 16px', padding: 12, border: '1px solid #e2e8f0',
                    borderRadius: 8, background: '#f8fafc',
                }}>
                    <div style={{ marginBottom: 8 }}>
                        <input
                            placeholder="Catalog name"
                            value={newCatalogName}
                            onChange={(e) => setNewCatalogName(e.target.value)}
                            style={{
                                width: '100%', boxSizing: 'border-box', padding: '6px 10px',
                                fontSize: 13, border: '1px solid #cbd5e1', borderRadius: 4,
                            }}
                        />
                    </div>
                    <div style={{ marginBottom: 8 }}>
                        <input
                            placeholder="Description (optional)"
                            value={newCatalogDesc}
                            onChange={(e) => setNewCatalogDesc(e.target.value)}
                            style={{
                                width: '100%', boxSizing: 'border-box', padding: '6px 10px',
                                fontSize: 13, border: '1px solid #cbd5e1', borderRadius: 4,
                            }}
                        />
                    </div>
                    <button onClick={handleCreateCatalog} style={{
                        padding: '6px 16px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #3b82f6', borderRadius: 4,
                        background: '#3b82f6', color: '#fff', cursor: 'pointer',
                    }}>
                        Create
                    </button>
                </div>
            )}

            <div style={{ padding: 16 }}>
                {/* Catalog grid (no catalog selected) */}
                {!selectedCatalogId && (
                    <>
                        {loading && <div style={{ color: '#94a3b8', fontSize: 13 }}>Loading...</div>}
                        {!loading && catalogs.length === 0 && (
                            <div style={{ color: '#94a3b8', fontSize: 13 }}>
                                No catalogs yet. Create one to get started.
                            </div>
                        )}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
                            {catalogs.map((cat) => (
                                <div
                                    key={cat.id}
                                    onClick={() => setSelectedCatalogId(cat.id)}
                                    style={{
                                        padding: 14, border: '1px solid #e2e8f0', borderRadius: 8,
                                        background: '#fff', cursor: 'pointer',
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.borderColor = '#3b82f6';
                                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(59,130,246,0.08)';
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.borderColor = '#e2e8f0';
                                        e.currentTarget.style.boxShadow = 'none';
                                    }}
                                >
                                    <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>
                                        {cat.name}
                                    </div>
                                    {cat.description && (
                                        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 8 }}>
                                            {cat.description}
                                        </div>
                                    )}
                                    <div style={{ display: 'flex', gap: 10, fontSize: 10, color: '#94a3b8' }}>
                                        <span>{cat.needs_count} needs</span>
                                        <span>{cat.stakeholder_count} stakeholders</span>
                                        <span>{cat.use_case_count} use cases</span>
                                    </div>
                                    <div style={{ fontSize: 9, color: '#cbd5e1', marginTop: 6 }}>
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
                                fontSize: 10, fontWeight: 700, color: '#94a3b8',
                                textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
                            }}>
                                Stakeholders
                            </div>
                            {stakeholders.length === 0 && (
                                <div style={{ fontSize: 11, color: '#cbd5e1' }}>No stakeholders</div>
                            )}
                            {stakeholders.map((sh) => (
                                <div
                                    key={sh.id}
                                    onClick={() => setFilterStakeholder(filterStakeholder === sh.id ? '' : sh.id)}
                                    style={{
                                        padding: '6px 8px', marginBottom: 4, borderRadius: 4,
                                        border: `1px solid ${filterStakeholder === sh.id ? '#3b82f6' : '#e2e8f0'}`,
                                        background: filterStakeholder === sh.id ? '#eff6ff' : '#fff',
                                        cursor: 'pointer', fontSize: 11,
                                    }}
                                >
                                    <div style={{ fontWeight: 600, color: '#1e293b' }}>{sh.name}</div>
                                    <div style={{ fontSize: 10, color: '#94a3b8' }}>{sh.role}</div>
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
                                            padding: '4px 10px', fontSize: 11, border: '1px solid #e2e8f0',
                                            borderRadius: 4, background: '#fff', color: '#64748b', cursor: 'pointer',
                                        }}
                                    >
                                        Clear filters
                                    </button>
                                )}
                            </div>

                            {needs.length === 0 && (
                                <div style={{ color: '#94a3b8', fontSize: 13, padding: 16 }}>
                                    No needs found. Express a need via the API to see it here.
                                </div>
                            )}

                            {needs.map((need) => (
                                <div
                                    key={need.id}
                                    onClick={() => handleNeedClick(need)}
                                    style={{
                                        padding: '10px 12px', marginBottom: 6,
                                        border: '1px solid #e2e8f0', borderRadius: 6,
                                        background: '#fff', cursor: 'pointer',
                                        transition: 'border-color 0.15s',
                                    }}
                                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#3b82f6'; }}
                                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = '#e2e8f0'; }}
                                >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                        <Badge label={need.status} colors={STATUS_COLORS[need.status]} />
                                        <Badge label={need.priority} colors={PRIORITY_COLORS[need.priority]} />
                                        <span style={{ fontSize: 10, color: '#cbd5e1', marginLeft: 'auto' }}>v{need.version}</span>
                                    </div>
                                    <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>
                                        {need.action} {need.subject}
                                        {need.target && <span style={{ color: '#64748b' }}> → {need.target}</span>}
                                    </div>
                                    {need.kernel_refs.length > 0 && (
                                        <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                                            {need.kernel_refs.map((ref) => (
                                                <span key={ref} style={{
                                                    fontSize: 9, padding: '1px 6px', borderRadius: 3,
                                                    background: '#eff6ff', color: '#3b82f6', fontWeight: 600,
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
    border: '1px solid #e2e8f0',
    borderRadius: 4,
    background: '#fff',
    color: '#1e293b',
    cursor: 'pointer' as const,
};
