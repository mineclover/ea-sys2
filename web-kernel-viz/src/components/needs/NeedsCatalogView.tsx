
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    useNeedsCatalogs,
    useCatalogNeeds,
    useNeedsCatalogDetail,
    useExpressNeed,
} from '@/api/hooks';
import { fetchNeedDetail } from '@/api/client';
import type {
    NeedSummary,
    NeedDetail,
    NeedPurpose,
    NeedKernelChangePhase,
    ExpressNeedPayload,
} from '@/api/types';
import { ErrorBanner } from '@/components/ui';
import { PageHeader } from '@/components/layout';
import type { Lang } from '@/components/layout/TopNav';

interface NeedsCatalogViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
    lang: Lang;
}

// --- Priority/Status colors ---
const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
    DRAFT: { bg: 'var(--accent)', fg: 'var(--muted-foreground)' },
    EXPRESSED: { bg: 'var(--muted)', fg: 'var(--primary)' },
    ACKNOWLEDGED: { bg: 'var(--status-success-bg)', fg: 'var(--status-success-text)' },
    ADDRESSED: { bg: 'var(--status-success-bg)', fg: 'var(--status-success-text)' },
    WITHDRAWN: { bg: 'var(--status-error-bg)', fg: 'var(--status-error-text)' },
};
const PRIORITY_COLORS: Record<string, { bg: string; fg: string }> = {
    LOW: { bg: 'var(--accent)', fg: 'var(--muted-foreground)' },
    MEDIUM: { bg: 'var(--status-warning-bg)', fg: 'var(--status-warning-text)' },
    HIGH: { bg: 'var(--status-warning-bg)', fg: 'var(--status-warning-text)' },
    CRITICAL: { bg: 'var(--status-error-bg)', fg: 'var(--status-error-text)' },
};

const PURPOSE_OPTIONS: NeedPurpose[] = [
    'unspecified',
    'safety',
    'efficiency',
    'usability',
    'compliance',
    'growth',
    'trust',
];

const PURPOSE_LABELS: Record<NeedPurpose, { en: string; ko: string }> = {
    unspecified: { en: 'Unspecified', ko: '미지정' },
    safety: { en: 'Safety', ko: '안전' },
    efficiency: { en: 'Efficiency', ko: '효율' },
    usability: { en: 'Usability', ko: '사용성' },
    compliance: { en: 'Compliance', ko: '컴플라이언스' },
    growth: { en: 'Growth', ko: '성장' },
    trust: { en: 'Trust', ko: '신뢰' },
};

const COMPLEXITY_LABELS: Record<'simple' | 'procedural' | 'complex', { en: string; ko: string }> = {
    simple: { en: 'Simple', ko: '단순' },
    procedural: { en: 'Procedural', ko: '절차형' },
    complex: { en: 'Complex', ko: '복합' },
};

const KERNEL_CHANGE_PHASE_OPTIONS: NeedKernelChangePhase[] = [
    'planned',
    'applied',
    'superseded',
    'rolled_back',
];

const KERNEL_CHANGE_PHASE_LABELS: Record<NeedKernelChangePhase, { en: string; ko: string }> = {
    planned: { en: 'Planned', ko: '계획됨' },
    applied: { en: 'Applied', ko: '적용됨' },
    superseded: { en: 'Superseded', ko: '대체됨' },
    rolled_back: { en: 'Rolled Back', ko: '롤백됨' },
};

const KERNEL_CHANGE_PHASE_COLORS: Record<NeedKernelChangePhase, { bg: string; fg: string }> = {
    planned: { bg: 'var(--status-warning-bg)', fg: 'var(--status-warning-text)' },
    applied: { bg: 'var(--status-success-bg)', fg: 'var(--status-success-text)' },
    superseded: { bg: 'var(--muted)', fg: 'var(--muted-foreground)' },
    rolled_back: { bg: 'var(--status-error-bg)', fg: 'var(--status-error-text)' },
};

function normalizePurposeToken(value: string): NeedPurpose | null {
    const token = value.trim().toLowerCase().replace('-', '_');
    const normalized =
        token.startsWith('need_purpose_') ? token.slice('need_purpose_'.length)
            : token.startsWith('needpurpose') ? token.slice('needpurpose'.length).replace(/^_+/, '')
                : token;
    return PURPOSE_OPTIONS.includes(normalized as NeedPurpose) ? (normalized as NeedPurpose) : null;
}

function purposeLabel(value: string, lang: Lang): string {
    const token = normalizePurposeToken(value);
    if (!token) return value;
    return PURPOSE_LABELS[token][lang];
}

function enumKey(value: string): string {
    return value.trim().toUpperCase();
}

function formatKernelChangePhase(value: string, lang: Lang): string {
    const token = value.trim().toLowerCase() as NeedKernelChangePhase;
    return KERNEL_CHANGE_PHASE_LABELS[token]?.[lang] || value;
}

function compactId(value: string, max = 22): string {
    if (value.length <= max) return value;
    return `${value.slice(0, max - 3)}...`;
}

function Badge({ label, colors }: { label: string; colors?: { bg: string; fg: string } }) {
    const c = colors || { bg: 'var(--accent)', fg: 'var(--muted-foreground)' };
    return (
        <span style={{
            fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
            background: c.bg, color: c.fg, whiteSpace: 'nowrap',
        }}>
            {label}
        </span>
    );
}

function NeedDetailView({
    detail,
    lang,
    onDrillDownDecision,
}: {
    detail: NeedDetail;
    lang: Lang;
    onDrillDownDecision: (decisionId: string) => void;
}) {
    const statusKey = enumKey(detail.status);
    const priorityKey = enumKey(detail.priority);
    const complexityKey = detail.complexity.toLowerCase() as 'simple' | 'procedural' | 'complex';
    const phaseToken = detail.kernel_change_phase.toLowerCase() as NeedKernelChangePhase;
    return (
        <div style={{ fontSize: 12, lineHeight: 1.7 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--foreground)', marginBottom: 12 }}>
                wants to <em>{detail.action}</em> {detail.subject}
                {detail.target && <> for <strong>{detail.target}</strong></>}
            </div>

            <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
                <Badge label={statusKey} colors={STATUS_COLORS[statusKey]} />
                <Badge label={priorityKey} colors={PRIORITY_COLORS[priorityKey]} />
                <Badge label={`v${detail.version}`} />
                {detail.complexity && <Badge label={COMPLEXITY_LABELS[complexityKey]?.[lang] || detail.complexity} />}
                <Badge
                    label={`${lang === 'ko' ? '커널 반영' : 'Kernel'}: ${formatKernelChangePhase(detail.kernel_change_phase, lang)}`}
                    colors={KERNEL_CHANGE_PHASE_COLORS[phaseToken]}
                />
                {detail.decision_linked && (
                    <Badge
                        label={lang === 'ko' ? 'Decision 연결됨' : 'Decision-linked'}
                        colors={{ bg: 'var(--status-info-bg)', fg: 'var(--primary)' }}
                    />
                )}
            </div>

            {detail.purpose && (
                <Section label={lang === 'ko' ? 'Purpose(목적)' : 'Purpose'}>
                    <div style={{ color: 'var(--muted-foreground)' }}>
                        {purposeLabel(detail.purpose, lang)} <span style={{ opacity: 0.75 }}>({detail.purpose})</span>
                    </div>
                </Section>
            )}

            {detail.justifications.length > 0 && (
                <Section label="Justifications">
                    {detail.justifications.map((j, i) => (
                        <div key={i} style={{ marginBottom: 4 }}>
                            <Badge label={j.type} />
                            <span style={{ color: 'var(--muted-foreground)', marginLeft: 6 }}>{j.description}</span>
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
                                background: 'var(--muted)', color: 'var(--primary)', cursor: 'pointer',
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

            <Section label={lang === 'ko' ? 'Decision Linkage' : 'Decision Linkage'}>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 6 }}>
                    {detail.inherited_from_decisions.map((decisionId) => (
                        <button
                            key={decisionId}
                            onClick={() => onDrillDownDecision(decisionId)}
                            style={{
                                border: 'none',
                                padding: 0,
                                background: 'transparent',
                                cursor: 'pointer',
                            }}
                            title={lang === 'ko' ? 'Decision 상세로 이동' : 'Open decision detail'}
                        >
                            <Badge
                                label={`decision:${compactId(decisionId)}`}
                                colors={{ bg: 'var(--status-info-bg)', fg: 'var(--primary)' }}
                            />
                        </button>
                    ))}
                    {detail.decision_evidence_refs.map((ref) => (
                        <Badge key={ref} label={`evidence:${compactId(ref)}`} />
                    ))}
                </div>
                {!detail.decision_linked && (
                    <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                        {lang === 'ko'
                            ? '연결된 decision/evidence가 없습니다.'
                            : 'No linked decision/evidence.'}
                    </div>
                )}
            </Section>

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
                            padding: '6px 8px', marginBottom: 4, background: 'var(--secondary)',
                            borderRadius: 4, border: '1px solid var(--border)',
                        }}>
                            <div style={{ fontWeight: 600, fontSize: 11 }}>
                                #{pu.sequence} {pu.label}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                                Stage: {pu.stage} {pu.description && `— ${pu.description}`}
                            </div>
                        </div>
                    ))}
                </Section>
            )}

            <Section label="Metadata">
                <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
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
                fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase',
                letterSpacing: '0.05em', marginBottom: 4,
            }}>
                {label}
            </div>
            {children}
        </div>
    );
}

export default function NeedsCatalogView({ onShowDetail, lang }: NeedsCatalogViewProps) {
    const navigate = useNavigate();
    const [selectedCatalogId, setSelectedCatalogId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [submitInfo, setSubmitInfo] = useState<string | null>(null);

    // Filters
    const [filterStatus, setFilterStatus] = useState('');
    const [filterPriority, setFilterPriority] = useState('');
    const [filterStakeholder, setFilterStakeholder] = useState('');
    const [filterKernelChangePhase, setFilterKernelChangePhase] = useState('');
    const [filterDecisionLinked, setFilterDecisionLinked] = useState<'all' | 'linked' | 'unlinked'>('all');
    const [filterDecisionId, setFilterDecisionId] = useState('');

    // Express Need form
    const [formStakeholderId, setFormStakeholderId] = useState('');
    const [formAction, setFormAction] = useState('');
    const [formSubject, setFormSubject] = useState('');
    const [formTarget, setFormTarget] = useState('');
    const [formPurpose, setFormPurpose] = useState<NeedPurpose>('unspecified');
    const [formPriority, setFormPriority] = useState<'critical' | 'high' | 'medium' | 'low'>('medium');
    const [formComplexity, setFormComplexity] = useState<'simple' | 'procedural' | 'complex'>('procedural');

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
        ...(filterKernelChangePhase ? { kernel_change_phase: filterKernelChangePhase } : {}),
        ...(filterDecisionId.trim() ? { decision_id: filterDecisionId.trim() } : {}),
        ...(filterDecisionLinked === 'linked' ? { decision_linked: true } : {}),
        ...(filterDecisionLinked === 'unlinked' ? { decision_linked: false } : {}),
    };

    const {
        data: needs = [],
    } = useCatalogNeeds(selectedCatalogId || '', Object.keys(filterOpts).length > 0 ? filterOpts : undefined);

    const {
        data: catalogDetail,
    } = useNeedsCatalogDetail(selectedCatalogId || '');
    const expressNeedMutation = useExpressNeed();

    const stakeholders = catalogDetail?.stakeholders || [];

    useEffect(() => {
        if (selectedCatalogId === null) {
            setFormStakeholderId('');
            setFormAction('');
            setFormSubject('');
            setFormTarget('');
            setFormPurpose('unspecified');
            setFormPriority('medium');
            setFormComplexity('procedural');
            setSubmitInfo(null);
        }
    }, [selectedCatalogId]);

    useEffect(() => {
        if (!stakeholders.length) {
            setFormStakeholderId('');
            return;
        }
        const exists = stakeholders.some((s) => s.id === formStakeholderId);
        if (!exists) setFormStakeholderId(stakeholders[0].id);
    }, [stakeholders, formStakeholderId]);

    const handleNeedClick = useCallback((need: NeedSummary) => {
        if (!selectedCatalogId) return;
        fetchNeedDetail(selectedCatalogId, need.id)
            .then((detail) => {
                onShowDetail(
                    `${detail.action} ${detail.subject}`,
                    <NeedDetailView
                        detail={detail}
                        lang={lang}
                        onDrillDownDecision={(decisionId) => {
                            const normalized = decisionId.trim();
                            if (!normalized) return;
                            navigate(`/governance/decisions?decision_id=${encodeURIComponent(normalized)}`);
                        }}
                    />,
                );
            })
            .catch((err) => setError(String(err)));
    }, [selectedCatalogId, onShowDetail, lang, navigate]);

    const handleExpressNeed = useCallback(() => {
        if (!selectedCatalogId) return;
        if (!formStakeholderId || !formAction.trim() || !formSubject.trim()) {
            setError(
                lang === 'ko'
                    ? '이해관계자, action, subject는 필수입니다.'
                    : 'Stakeholder, action, and subject are required.',
            );
            return;
        }
        const payload: ExpressNeedPayload = {
            stakeholder_id: formStakeholderId,
            action: formAction.trim(),
            subject: formSubject.trim(),
            purpose: formPurpose,
            priority: formPriority,
            complexity: formComplexity,
        };
        if (formTarget.trim()) payload.target = formTarget.trim();
        setError(null);
        setSubmitInfo(null);
        expressNeedMutation.mutate(
            { catalogId: selectedCatalogId, data: payload },
            {
                onSuccess: (result) => {
                    setFormAction('');
                    setFormSubject('');
                    setFormTarget('');
                    setSubmitInfo(
                        lang === 'ko'
                            ? `Need 생성 완료: ${result.need_id}`
                            : `Need created: ${result.need_id}`,
                    );
                },
                onError: (err) => {
                    setError(err instanceof Error ? err.message : String(err));
                },
            },
        );
    }, [
        selectedCatalogId,
        formStakeholderId,
        formAction,
        formSubject,
        formPurpose,
        formPriority,
        formComplexity,
        formTarget,
        expressNeedMutation,
        lang,
    ]);

    const selectedCatalog = catalogs.find((c) => c.id === selectedCatalogId);

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif', overflow: 'auto' }}>
            <PageHeader
                metaKey="needs.catalog"
                compact
                title={selectedCatalog ? selectedCatalog.name : undefined}
                subtitle={selectedCatalog ? `${selectedCatalog.needs_count} needs · ${selectedCatalog.stakeholder_count} stakeholders` : undefined}
                rightContent={selectedCatalogId ? (
                    <button
                        onClick={() => { setSelectedCatalogId(null); }}
                        style={{
                            padding: '4px 10px', fontSize: 12, fontWeight: 600,
                            border: '1px solid var(--border)', borderRadius: 4, background: 'var(--card)',
                            color: 'var(--muted-foreground)', cursor: 'pointer',
                        }}
                    >
                        ← Back
                    </button>
                ) : undefined}
            />

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
                    border: '1px solid var(--status-error-bg)', borderRadius: 8, background: 'var(--status-error-bg)',
                    fontSize: 12, color: 'var(--status-error-text)',
                }}>
                    {error}
                </div>
            )}
            {submitInfo && (
                <div style={{
                    margin: '12px 16px', padding: '10px 14px',
                    border: '1px solid var(--status-success-bg)', borderRadius: 8, background: 'var(--status-success-bg)',
                    fontSize: 12, color: 'var(--status-success-text)',
                }}>
                    {submitInfo}
                </div>
            )}

            <div style={{ padding: 16 }}>
                {/* Catalog grid (no catalog selected) */}
                {!selectedCatalogId && (
                    <>
                        {catalogsLoading && <div style={{ color: 'var(--muted-foreground)', fontSize: 13 }}>Loading...</div>}
                        {!catalogsLoading && catalogs.length === 0 && (
                            <div style={{ color: 'var(--muted-foreground)', fontSize: 13 }}>
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
                                        background: 'var(--card)', cursor: 'pointer',
                                        transition: 'border-color 0.15s, box-shadow 0.15s',
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.borderColor = 'var(--primary)';
                                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(59,130,246,0.08)';
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.borderColor = 'var(--border)';
                                        e.currentTarget.style.boxShadow = 'none';
                                    }}
                                >
                                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--foreground)', marginBottom: 4 }}>
                                        {cat.name}
                                    </div>
                                    {cat.description && (
                                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 8 }}>
                                            {cat.description}
                                        </div>
                                    )}
                                    <div style={{ display: 'flex', gap: 10, fontSize: 10, color: 'var(--muted-foreground)' }}>
                                        <span>{cat.needs_count} needs</span>
                                        <span>{cat.stakeholder_count} stakeholders</span>
                                        <span>{cat.use_case_count} use cases</span>
                                    </div>
                                    <div style={{ fontSize: 9, color: 'var(--input)', marginTop: 6 }}>
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
                                fontSize: 10, fontWeight: 700, color: 'var(--muted-foreground)',
                                textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
                            }}>
                                Stakeholders
                            </div>
                            {stakeholders.length === 0 && (
                                <div style={{ fontSize: 11, color: 'var(--input)' }}>No stakeholders</div>
                            )}
                            {stakeholders.map((sh) => (
                                <div
                                    key={sh.id}
                                    onClick={() => setFilterStakeholder(filterStakeholder === sh.id ? '' : sh.id)}
                                    style={{
                                        padding: '6px 8px', marginBottom: 4, borderRadius: 4,
                                        border: `1px solid ${filterStakeholder === sh.id ? 'var(--primary)' : 'var(--border)'}`,
                                        background: filterStakeholder === sh.id ? 'var(--muted)' : 'var(--card)',
                                        cursor: 'pointer', fontSize: 11,
                                    }}
                                >
                                    <div style={{ fontWeight: 600, color: 'var(--foreground)' }}>{sh.name}</div>
                                    <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>{sh.role}</div>
                                </div>
                            ))}
                        </div>

                        {/* Needs list */}
                        <div style={{ flex: 1 }}>
                            {/* Express Need */}
                            <div style={{
                                marginBottom: 12,
                                padding: 12,
                                border: '1px solid var(--border)',
                                borderRadius: 8,
                                background: 'var(--card)',
                            }}>
                                <div style={{
                                    fontSize: 10,
                                    fontWeight: 700,
                                    color: 'var(--muted-foreground)',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                    marginBottom: 8,
                                }}>
                                    {lang === 'ko' ? 'Need 표현' : 'Express Need'}
                                </div>

                                <div style={{
                                    display: 'grid',
                                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                                    gap: 8,
                                }}>
                                    <select
                                        value={formStakeholderId}
                                        onChange={(e) => setFormStakeholderId(e.target.value)}
                                        style={formFieldStyle}
                                    >
                                        {!stakeholders.length && (
                                            <option value="">{lang === 'ko' ? '이해관계자 없음' : 'No stakeholders'}</option>
                                        )}
                                        {stakeholders.map((s) => (
                                            <option key={s.id} value={s.id}>
                                                {s.name} ({s.role})
                                            </option>
                                        ))}
                                    </select>
                                    <input
                                        value={formAction}
                                        onChange={(e) => setFormAction(e.target.value)}
                                        placeholder={lang === 'ko' ? 'action (예: stabilize)' : 'action (e.g., stabilize)'}
                                        style={formFieldStyle}
                                    />
                                    <input
                                        value={formSubject}
                                        onChange={(e) => setFormSubject(e.target.value)}
                                        placeholder={lang === 'ko' ? 'subject (예: incident response)' : 'subject (e.g., incident response)'}
                                        style={formFieldStyle}
                                    />
                                    <input
                                        value={formTarget}
                                        onChange={(e) => setFormTarget(e.target.value)}
                                        placeholder={lang === 'ko' ? 'target (선택)' : 'target (optional)'}
                                        style={formFieldStyle}
                                    />
                                    <select
                                        value={formPurpose}
                                        onChange={(e) => setFormPurpose(e.target.value as NeedPurpose)}
                                        style={formFieldStyle}
                                    >
                                        {PURPOSE_OPTIONS.map((value) => (
                                            <option key={value} value={value}>
                                                {purposeLabel(value, lang)} ({value})
                                            </option>
                                        ))}
                                    </select>
                                    <select
                                        value={formPriority}
                                        onChange={(e) => setFormPriority(e.target.value as 'critical' | 'high' | 'medium' | 'low')}
                                        style={formFieldStyle}
                                    >
                                        {(['critical', 'high', 'medium', 'low'] as const).map((value) => (
                                            <option key={value} value={value}>{value.toUpperCase()}</option>
                                        ))}
                                    </select>
                                    <select
                                        value={formComplexity}
                                        onChange={(e) => setFormComplexity(e.target.value as 'simple' | 'procedural' | 'complex')}
                                        style={formFieldStyle}
                                    >
                                        {(['simple', 'procedural', 'complex'] as const).map((value) => (
                                            <option key={value} value={value}>
                                                {COMPLEXITY_LABELS[value][lang]} ({value})
                                            </option>
                                        ))}
                                    </select>
                                </div>

                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                                    <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                                        {lang === 'ko'
                                            ? 'purpose는 M2 Goal taxonomy로 강제됩니다.'
                                            : 'Purpose is enforced by M2 Goal taxonomy.'}
                                    </span>
                                    <button
                                        onClick={handleExpressNeed}
                                        disabled={expressNeedMutation.isPending || !stakeholders.length}
                                        style={{
                                            padding: '6px 12px',
                                            fontSize: 11,
                                            fontWeight: 700,
                                            border: '1px solid var(--primary)',
                                            borderRadius: 6,
                                            background: expressNeedMutation.isPending ? 'var(--muted)' : 'var(--primary)',
                                            color: expressNeedMutation.isPending ? 'var(--muted-foreground)' : 'var(--card)',
                                            cursor: expressNeedMutation.isPending || !stakeholders.length ? 'not-allowed' : 'pointer',
                                        }}
                                    >
                                        {expressNeedMutation.isPending
                                            ? (lang === 'ko' ? '생성 중...' : 'Submitting...')
                                            : (lang === 'ko' ? 'Need 생성' : 'Create Need')}
                                    </button>
                                </div>
                            </div>

                            {/* Filters */}
                            <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                                <select
                                    value={filterStatus}
                                    onChange={(e) => setFilterStatus(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="">{lang === 'ko' ? '전체 상태' : 'All Status'}</option>
                                    {(['draft', 'expressed', 'acknowledged', 'addressed', 'withdrawn'] as const).map((s) => (
                                        <option key={s} value={s}>{s.toUpperCase()}</option>
                                    ))}
                                </select>
                                <select
                                    value={filterPriority}
                                    onChange={(e) => setFilterPriority(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="">{lang === 'ko' ? '전체 우선순위' : 'All Priority'}</option>
                                    {(['low', 'medium', 'high', 'critical'] as const).map((p) => (
                                        <option key={p} value={p}>{p.toUpperCase()}</option>
                                    ))}
                                </select>
                                <select
                                    value={filterKernelChangePhase}
                                    onChange={(e) => setFilterKernelChangePhase(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="">{lang === 'ko' ? '전체 반영 단계' : 'All Kernel Phase'}</option>
                                    {KERNEL_CHANGE_PHASE_OPTIONS.map((phase) => (
                                        <option key={phase} value={phase}>
                                            {formatKernelChangePhase(phase, lang)} ({phase})
                                        </option>
                                    ))}
                                </select>
                                <select
                                    value={filterDecisionLinked}
                                    onChange={(e) => setFilterDecisionLinked(e.target.value as 'all' | 'linked' | 'unlinked')}
                                    style={filterSelectStyle}
                                >
                                    <option value="all">{lang === 'ko' ? 'Decision 전체' : 'All Decision Linkage'}</option>
                                    <option value="linked">{lang === 'ko' ? '연결됨만' : 'Linked only'}</option>
                                    <option value="unlinked">{lang === 'ko' ? '미연결만' : 'Unlinked only'}</option>
                                </select>
                                <input
                                    value={filterDecisionId}
                                    onChange={(e) => setFilterDecisionId(e.target.value)}
                                    placeholder={lang === 'ko' ? 'decision_id 필터 (선택)' : 'decision_id filter (optional)'}
                                    style={filterInputStyle}
                                />
                                {(filterStatus || filterPriority || filterStakeholder || filterKernelChangePhase || filterDecisionLinked !== 'all' || filterDecisionId.trim()) && (
                                    <button
                                        onClick={() => {
                                            setFilterStatus('');
                                            setFilterPriority('');
                                            setFilterStakeholder('');
                                            setFilterKernelChangePhase('');
                                            setFilterDecisionLinked('all');
                                            setFilterDecisionId('');
                                        }}
                                        style={{
                                            padding: '4px 10px', fontSize: 11, border: '1px solid var(--border)',
                                            borderRadius: 4, background: 'var(--card)', color: 'var(--muted-foreground)', cursor: 'pointer',
                                        }}
                                    >
                                        {lang === 'ko' ? '필터 초기화' : 'Clear filters'}
                                    </button>
                                )}
                            </div>

                            {needs.length === 0 && (
                                <div style={{ color: 'var(--muted-foreground)', fontSize: 13, padding: 16 }}>
                                    {lang === 'ko'
                                        ? '조건에 맞는 Need가 없습니다.'
                                        : 'No needs found for current filters.'}
                                </div>
                            )}

                            {needs.map((need) => {
                                const phaseToken = need.kernel_change_phase.toLowerCase() as NeedKernelChangePhase;
                                return (
                                    <div
                                        key={need.id}
                                        onClick={() => handleNeedClick(need)}
                                        style={{
                                            padding: '10px 12px', marginBottom: 6,
                                            border: '1px solid var(--border)', borderRadius: 6,
                                            background: 'var(--card)', cursor: 'pointer',
                                            transition: 'border-color 0.15s',
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--primary)'; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                                            <Badge label={enumKey(need.status)} colors={STATUS_COLORS[enumKey(need.status)]} />
                                            <Badge label={enumKey(need.priority)} colors={PRIORITY_COLORS[enumKey(need.priority)]} />
                                            <Badge
                                                label={formatKernelChangePhase(need.kernel_change_phase, lang)}
                                                colors={KERNEL_CHANGE_PHASE_COLORS[phaseToken]}
                                            />
                                            {need.decision_linked && (
                                                <Badge
                                                    label={lang === 'ko' ? 'Decision 연결' : 'Decision-linked'}
                                                    colors={{ bg: 'var(--status-info-bg)', fg: 'var(--primary)' }}
                                                />
                                            )}
                                            <span style={{ fontSize: 10, color: 'var(--input)', marginLeft: 'auto' }}>v{need.version}</span>
                                        </div>
                                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)' }}>
                                            {need.action} {need.subject}
                                            {need.target && <span style={{ color: 'var(--muted-foreground)' }}> → {need.target}</span>}
                                        </div>
                                        {(need.inherited_from_decisions.length > 0 || need.decision_evidence_refs.length > 0) && (
                                            <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                                                {need.inherited_from_decisions.map((decisionId) => (
                                                    <span
                                                        key={decisionId}
                                                        style={{
                                                            fontSize: 9, padding: '1px 6px', borderRadius: 3,
                                                            background: 'var(--status-info-bg)', color: 'var(--primary)', fontWeight: 600,
                                                        }}
                                                    >
                                                        decision:{compactId(decisionId, 18)}
                                                    </span>
                                                ))}
                                                {need.decision_evidence_refs.map((ref) => (
                                                    <span
                                                        key={ref}
                                                        style={{
                                                            fontSize: 9, padding: '1px 6px', borderRadius: 3,
                                                            background: 'var(--accent)', color: 'var(--muted-foreground)', fontWeight: 600,
                                                        }}
                                                    >
                                                        evidence:{compactId(ref, 20)}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                        {need.kernel_refs.length > 0 && (
                                            <div style={{ display: 'flex', gap: 4, marginTop: 4, flexWrap: 'wrap' }}>
                                                {need.kernel_refs.map((ref) => (
                                                    <span key={ref} style={{
                                                        fontSize: 9, padding: '1px 6px', borderRadius: 3,
                                                        background: 'var(--muted)', color: 'var(--primary)', fontWeight: 600,
                                                    }}>
                                                        {ref}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
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
    background: 'var(--card)',
    color: 'var(--foreground)',
    cursor: 'pointer' as const,
};

const filterInputStyle = {
    padding: '4px 8px',
    fontSize: 11,
    border: '1px solid var(--border)',
    borderRadius: 4,
    background: 'var(--card)',
    color: 'var(--foreground)',
    minWidth: 180,
};

const formFieldStyle = {
    padding: '6px 8px',
    fontSize: 11,
    border: '1px solid var(--border)',
    borderRadius: 4,
    background: 'var(--card)',
    color: 'var(--foreground)',
};
