
import { useState } from 'react';
import { useProfileVersions, useProfileVersionDetail, useProfileVersionDiff } from '@/api/hooks';
import type { ProfileDiffChange } from '@/api/types';
import { Badge, ErrorBanner, LoadingSpinner, EmptyState } from '@/components/ui';

interface ProfileVersionHistoryProps {
    profileName: string;
}

export default function ProfileVersionHistory({ profileName }: ProfileVersionHistoryProps) {
    const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
    const [diffA, setDiffA] = useState<string>('');
    const [diffB, setDiffB] = useState<string>('');
    const [showDiff, setShowDiff] = useState(false);

    const { data: versions, isLoading, isError, refetch } = useProfileVersions(profileName);
    const { data: detail } = useProfileVersionDetail(profileName, selectedVersion || '');
    const { data: diff } = useProfileVersionDiff(profileName, diffA, diffB);

    if (isLoading) return <LoadingSpinner message="Loading version history..." />;
    if (isError) return <div style={{ padding: 24 }}><ErrorBanner onRetry={() => refetch()} /></div>;
    if (!versions || versions.versions.length === 0) return <EmptyState message="No versions found." />;

    return (
        <div style={{ flex: 1, overflow: 'auto', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>Version History</h2>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{profileName} — {versions.count} versions</div>
                </div>
                <button
                    onClick={() => setShowDiff(!showDiff)}
                    style={{
                        padding: '6px 14px', fontSize: 12, fontWeight: 600,
                        border: `1px solid ${showDiff ? '#a855f7' : 'var(--border-strong)'}`,
                        borderRadius: 6, background: showDiff ? '#faf5ff' : 'var(--bg-card)',
                        color: showDiff ? '#a855f7' : 'var(--text-primary)', cursor: 'pointer',
                    }}
                >
                    {showDiff ? 'Hide Diff' : 'Compare Versions'}
                </button>
            </div>

            {/* Diff selector */}
            {showDiff && (
                <div style={{ padding: '12px 24px', background: '#faf5ff', borderBottom: '1px solid var(--border)', display: 'flex', gap: 12, alignItems: 'center' }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>FROM</span>
                    <select value={diffA} onChange={(e) => setDiffA(e.target.value)}
                        style={{ padding: '4px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4 }}>
                        <option value="">Select version...</option>
                        {versions.versions.map((v) => (
                            <option key={v.id} value={v.version}>{v.version}</option>
                        ))}
                    </select>
                    <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>TO</span>
                    <select value={diffB} onChange={(e) => setDiffB(e.target.value)}
                        style={{ padding: '4px 8px', fontSize: 12, border: '1px solid var(--border-strong)', borderRadius: 4 }}>
                        <option value="">Select version...</option>
                        {versions.versions.map((v) => (
                            <option key={v.id} value={v.version}>{v.version}</option>
                        ))}
                    </select>
                </div>
            )}

            {/* Diff result */}
            {showDiff && diff && (
                <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 12 }}>
                        Diff: {diff.from_version} → {diff.to_version}
                        {diff.identical && <Badge label="IDENTICAL" bg="var(--success-bg)" color="var(--success-text)" />}
                    </div>
                    {!diff.identical && (
                        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
                            {diff.element_changes.length > 0 && (
                                <DiffSection title="Element Changes" changes={diff.element_changes} keyField="name" />
                            )}
                            {diff.relation_changes.length > 0 && (
                                <DiffSection title="Relation Changes" changes={diff.relation_changes} keyField="name" />
                            )}
                            {diff.rule_changes.length > 0 && (
                                <DiffSection title="Rule Changes" changes={diff.rule_changes} keyField="id" />
                            )}
                            {diff.element_changes.length === 0 && diff.relation_changes.length === 0 && diff.rule_changes.length === 0 && (
                                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No structural changes detected.</div>
                            )}
                        </div>
                    )}
                </div>
            )}

            <div style={{ display: 'flex' }}>
                {/* Timeline */}
                <div style={{ flex: 1, minWidth: 300 }}>
                    {versions.versions.map((v) => (
                        <div
                            key={v.id}
                            onClick={() => setSelectedVersion(v.version)}
                            style={{
                                padding: '12px 24px',
                                borderBottom: '1px solid var(--bg-hover)',
                                cursor: 'pointer',
                                background: selectedVersion === v.version ? 'var(--accent-bg)' : 'transparent',
                            }}
                            onMouseEnter={(e) => { if (selectedVersion !== v.version) e.currentTarget.style.background = 'var(--bg-secondary)'; }}
                            onMouseLeave={(e) => { if (selectedVersion !== v.version) e.currentTarget.style.background = ''; }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{v.version}</span>
                                <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'monospace' }}>{v.content_hash?.slice(0, 8)}</span>
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                {v.author} — {v.created_at}
                            </div>
                            {v.description && (
                                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{v.description}</div>
                            )}
                        </div>
                    ))}
                </div>

                {/* Detail panel */}
                {detail && (
                    <div style={{ width: 360, borderLeft: '1px solid var(--border)', padding: '16px 20px', background: 'var(--bg-secondary)' }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
                            Version Detail
                        </div>
                        <DetailField label="Version" value={detail.version} />
                        <DetailField label="Author" value={detail.author} />
                        <DetailField label="Created" value={detail.created_at} />
                        <DetailField label="Hash" value={detail.content_hash} mono />
                        <DetailField label="Origin" value={detail.origin || '-'} />
                        <div style={{ display: 'flex', gap: 16, marginTop: 12, marginBottom: 12 }}>
                            <MiniStat label="Elements" value={detail.element_count} />
                            <MiniStat label="Relations" value={detail.relation_count} />
                            <MiniStat label="Rules" value={detail.rule_count} />
                        </div>
                        {detail.tags && detail.tags.length > 0 && (
                            <div>
                                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Tags</div>
                                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                                    {detail.tags.map((t: { name: string }) => (
                                        <Badge key={t.name} label={t.name} bg="var(--indigo-bg)" color="var(--indigo-text)" />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function DetailField({ label, value, mono }: { label: string; value: string | number | null; mono?: boolean }) {
    return (
        <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
            <div style={{
                fontSize: 12, color: 'var(--text-primary)', wordBreak: 'break-all',
                fontFamily: mono ? 'monospace' : 'inherit',
            }}>
                {value ?? '-'}
            </div>
        </div>
    );
}

function MiniStat({ label, value }: { label: string; value: number }) {
    return (
        <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>{value}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</div>
        </div>
    );
}

function DiffSection({ title, changes, keyField }: { title: string; changes: ProfileDiffChange[]; keyField: string }) {
    return (
        <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>{title}</div>
            {changes.map((c, i) => {
                const changeType = String(c.type || c.change || '');
                return (
                    <div key={i} style={{ fontSize: 11, padding: '4px 8px', marginBottom: 2, borderRadius: 4, background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                        <Badge
                            label={changeType.toUpperCase()}
                            bg={changeType === 'added' ? 'var(--success-bg)' : changeType === 'removed' ? 'var(--error-bg)' : 'var(--warning-bg)'}
                            color={changeType === 'added' ? 'var(--success-text)' : changeType === 'removed' ? 'var(--error-text)' : 'var(--warning-text)'}
                            size="sm"
                        />
                        {' '}
                        <span style={{ fontWeight: 600 }}>{String(c[keyField] || '')}</span>
                        {c.field && <span style={{ color: 'var(--text-muted)' }}> .{String(c.field)}</span>}
                    </div>
                );
            })}
        </div>
    );
}
