import { useEffect, useMemo, useState } from 'react';
import {
  useI18nAudit,
  useI18nProfileAudit,
  useI18nTranslations,
  useProfiles,
  useUpdateTranslation,
} from '@/api/hooks';
import { useAppState } from '@/contexts/AppStateContext';
import { Card, ErrorBanner, LoadingSpinner, Badge } from '@/components/ui';
import { PageHeader } from '@/components/layout';
import type { I18nAuditItem, I18nTranslationItem } from '@/api/types';

type TranslationKind = 'all' | 'element' | 'relation' | 'rule' | 'layer';
type AuditScope = 'm2' | 'm1';
type AuditIssueType = 'missing' | 'orphan' | 'stale';
type AuditIssueFilter = 'all' | AuditIssueType;
type AuditIssueRow = I18nAuditItem & { issue: AuditIssueType };

export default function TranslationManager() {
  const { lang } = useAppState();
  const [auditScope, setAuditScope] = useState<AuditScope>('m2');
  const [selectedProfile, setSelectedProfile] = useState('');
  const [selectedKind, setSelectedKind] = useState<TranslationKind>('all');
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [selectedAuditKind, setSelectedAuditKind] = useState('all');
  const [selectedAuditIssue, setSelectedAuditIssue] = useState<AuditIssueFilter>('all');
  const [auditSearch, setAuditSearch] = useState('');
  const [copiedIdentifier, setCopiedIdentifier] = useState<string | null>(null);

  const { data: profiles } = useProfiles();
  const m2AuditQuery = useI18nAudit(lang, { enabled: auditScope === 'm2' });
  const m1AuditQuery = useI18nProfileAudit(selectedProfile, lang, {
    enabled: auditScope === 'm1' && !!selectedProfile,
  });
  const { data: translationsResult, isLoading: isLoadingTranslations, error: translationsError } = useI18nTranslations(lang);
  const updateTranslation = useUpdateTranslation();

  const profileNames = useMemo(
    () => (profiles ?? []).map((p) => p.name),
    [profiles],
  );

  useEffect(() => {
    if (!selectedProfile && profileNames.length > 0) {
      setSelectedProfile(profileNames[0]);
    }
  }, [profileNames, selectedProfile]);

  const audit = auditScope === 'm1' ? m1AuditQuery.data : m2AuditQuery.data;
  const isLoadingAudit = auditScope === 'm1' ? m1AuditQuery.isLoading : m2AuditQuery.isLoading;
  const auditError = auditScope === 'm1' ? m1AuditQuery.error : m2AuditQuery.error;

  const translations = translationsResult?.translations ?? [];

  const filteredTranslations = useMemo(() => {
    if (selectedKind === 'all') return translations;
    return translations.filter((t: I18nTranslationItem) => t.kind === selectedKind);
  }, [translations, selectedKind]);

  const makeKey = (t: I18nTranslationItem) => `${t.kind}:${t.name}:${t.field}`;

  const handleStartEdit = (key: string, currentValue: string) => {
    setEditingKey(key);
    setEditValue(currentValue);
  };

  const handleCancelEdit = () => {
    setEditingKey(null);
    setEditValue('');
  };

  const handleSaveEdit = async (t: I18nTranslationItem) => {
    try {
      await updateTranslation.mutateAsync({
        kind: t.kind,
        name: t.name,
        lang,
        field: t.field,
        value: editValue
      });
      setEditingKey(null);
      setEditValue('');
    } catch (error) {
      console.error('Failed to update translation:', error);
    }
  };

  const totalCount = audit ? (audit.total_schema_items ?? audit.total) : 0;
  const translatedCount = audit ? (audit.total_translated ?? audit.translated) : 0;
  const missingItems: I18nAuditItem[] = audit ? (audit.missing_items ?? audit.missing ?? []) : [];
  const missingCount = audit ? (audit.missing_count ?? missingItems.length) : 0;
  const orphanItems: I18nAuditItem[] = audit?.orphan ?? [];
  const staleItems: I18nAuditItem[] = audit?.stale ?? [];
  const auditIssues: AuditIssueRow[] = useMemo(
    () => [
      ...missingItems.map((item) => ({ ...item, issue: 'missing' as const })),
      ...orphanItems.map((item) => ({ ...item, issue: 'orphan' as const })),
      ...staleItems.map((item) => ({ ...item, issue: 'stale' as const })),
    ],
    [missingItems, orphanItems, staleItems],
  );
  const auditKinds = useMemo(
    () => Array.from(new Set(auditIssues.map((item) => item.kind))).sort(),
    [auditIssues],
  );
  const filteredAuditIssues = useMemo(() => {
    const q = auditSearch.trim().toLowerCase();
    return auditIssues.filter((item) => {
      const matchesKind = selectedAuditKind === 'all' || item.kind === selectedAuditKind;
      const matchesIssue = selectedAuditIssue === 'all' || item.issue === selectedAuditIssue;
      if (!matchesKind) return false;
      if (!matchesIssue) return false;
      if (!q) return true;
      return (
        item.name.toLowerCase().includes(q) ||
        (item.field ?? '').toLowerCase().includes(q) ||
        item.identifier.toLowerCase().includes(q)
      );
    });
  }, [auditIssues, selectedAuditKind, selectedAuditIssue, auditSearch]);
  const coveragePercent = totalCount > 0
    ? Math.round((translatedCount / totalCount) * 100)
    : 0;

  const handleCopyIdentifier = async (identifier: string) => {
    try {
      await navigator.clipboard.writeText(identifier);
      setCopiedIdentifier(identifier);
      setTimeout(() => setCopiedIdentifier(null), 1200);
    } catch (error) {
      console.error('Failed to copy identifier:', error);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <PageHeader metaKey="admin.i18n" compact />
      {/* Audit Summary */}
      <Card>
        <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)', marginBottom: '16px' }}>
          Translation Coverage - {lang.toUpperCase()}
        </h2>

        <div style={{ display: 'grid', gap: '12px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {(['m2', 'm1'] as AuditScope[]).map((scope) => (
              <button
                key={scope}
                onClick={() => setAuditScope(scope)}
                style={{
                  padding: '6px 12px',
                  backgroundColor: auditScope === scope ? 'var(--primary)' : 'var(--secondary)',
                  color: auditScope === scope ? 'white' : 'var(--foreground)',
                  border: '1px solid',
                  borderColor: auditScope === scope ? 'var(--primary)' : 'var(--border)',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '500',
                  cursor: 'pointer',
                  textTransform: 'uppercase',
                }}
              >
                {scope}
              </button>
            ))}
          </div>

          {auditScope === 'm1' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <label style={{ fontSize: '13px', color: 'var(--muted-foreground)', fontWeight: 500 }}>
                Profile
              </label>
              <select
                value={selectedProfile}
                onChange={(e) => setSelectedProfile(e.target.value)}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: '1px solid var(--input)',
                  backgroundColor: 'var(--card)',
                  color: 'var(--foreground)',
                  fontSize: '13px',
                  minWidth: '260px',
                }}
              >
                {profileNames.length === 0 && <option value="">No profiles</option>}
                {profileNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {auditError && (
          <ErrorBanner message={auditError instanceof Error ? auditError.message : 'Failed to load audit'} />
        )}

        {isLoadingAudit ? (
          <LoadingSpinner />
        ) : audit ? (
          <div>
            {/* Coverage Bar */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '8px',
                fontSize: '14px',
                color: 'var(--muted-foreground)'
              }}>
                <span>Coverage</span>
                <span style={{ fontWeight: '600', color: 'var(--foreground)' }}>{coveragePercent}%</span>
              </div>
              <div style={{
                width: '100%',
                height: '12px',
                backgroundColor: 'var(--accent)',
                borderRadius: '6px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${coveragePercent}%`,
                  height: '100%',
                  backgroundColor: coveragePercent === 100 ? 'var(--status-success-text)' : coveragePercent > 50 ? 'var(--primary)' : 'var(--status-warning-text)',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>

            {/* Stats */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '16px',
              padding: '16px',
              backgroundColor: 'var(--secondary)',
              borderRadius: '6px'
            }}>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>
                  Total
                </div>
                <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--foreground)' }}>
                  {totalCount}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>
                  Translated
                </div>
                <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--status-success-text)' }}>
                  {translatedCount}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>
                  Missing
                </div>
                <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--destructive)' }}>
                  {missingCount}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>
                  Scope
                </div>
                <div style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)', textTransform: 'uppercase' }}>
                  {audit.scope}
                </div>
                {audit.scope === 'm1' && (
                  <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginTop: '4px' }}>
                    {(audit as { profile?: string }).profile || selectedProfile}
                  </div>
                )}
              </div>
            </div>

            {/* Audit Issues */}
            <div style={{ marginTop: '16px' }}>
              <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '8px' }}>
                Audit Issues ({filteredAuditIssues.length})
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                <span style={{ padding: '3px 8px', borderRadius: '999px', backgroundColor: 'var(--status-error-bg)', color: 'var(--destructive)', fontSize: '11px', fontWeight: 600 }}>
                  missing {missingItems.length}
                </span>
                <span style={{ padding: '3px 8px', borderRadius: '999px', backgroundColor: 'var(--status-warning-bg)', color: 'var(--status-warning-text)', fontSize: '11px', fontWeight: 600 }}>
                  orphan {orphanItems.length}
                </span>
                <span style={{ padding: '3px 8px', borderRadius: '999px', backgroundColor: 'var(--status-indigo-bg)', color: 'var(--status-indigo-text)', fontSize: '11px', fontWeight: 600 }}>
                  stale {staleItems.length}
                </span>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '10px' }}>
                <select
                  value={selectedAuditIssue}
                  onChange={(e) => setSelectedAuditIssue(e.target.value as AuditIssueFilter)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '1px solid var(--input)',
                    backgroundColor: 'var(--card)',
                    color: 'var(--foreground)',
                    fontSize: '12px',
                  }}
                >
                  <option value="all">All issues</option>
                  <option value="missing">missing</option>
                  <option value="orphan">orphan</option>
                  <option value="stale">stale</option>
                </select>
                <select
                  value={selectedAuditKind}
                  onChange={(e) => setSelectedAuditKind(e.target.value)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '1px solid var(--input)',
                    backgroundColor: 'var(--card)',
                    color: 'var(--foreground)',
                    fontSize: '12px',
                  }}
                >
                  <option value="all">All kinds</option>
                  {auditKinds.map((kind) => (
                    <option key={kind} value={kind}>{kind}</option>
                  ))}
                </select>
                <input
                  value={auditSearch}
                  onChange={(e) => setAuditSearch(e.target.value)}
                  placeholder="Search name or identifier"
                  style={{
                    padding: '6px 10px',
                    borderRadius: '6px',
                    border: '1px solid var(--input)',
                    color: 'var(--foreground)',
                    fontSize: '12px',
                    minWidth: '260px',
                    flex: 1,
                  }}
                />
              </div>

              {filteredAuditIssues.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {filteredAuditIssues.slice(0, 50).map((item, idx) => (
                    <div
                      key={`${item.issue}:${item.identifier}:${idx}`}
                      style={{
                        padding: '8px 10px',
                        backgroundColor: 'var(--card)',
                        border: '1px solid var(--border)',
                        borderRadius: '6px',
                        fontSize: '12px',
                        minWidth: '320px',
                        maxWidth: '560px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', flexWrap: 'wrap' }}>
                        <span
                          style={{
                            padding: '2px 6px',
                            borderRadius: '999px',
                            fontSize: '10px',
                            fontWeight: 700,
                            textTransform: 'uppercase',
                            backgroundColor: item.issue === 'missing' ? 'var(--status-error-bg)' : item.issue === 'orphan' ? 'var(--status-warning-bg)' : 'var(--status-indigo-bg)',
                            color: item.issue === 'missing' ? 'var(--destructive)' : item.issue === 'orphan' ? 'var(--status-warning-text)' : 'var(--status-indigo-text)',
                          }}
                        >
                          {item.issue}
                        </span>
                        <span style={{ fontWeight: '600', color: 'var(--foreground)' }}>{item.name}</span>
                        <span style={{ color: 'var(--muted-foreground)' }}>.{item.field ?? '-'}</span>
                        <span style={{ color: 'var(--muted-foreground)' }}>({item.kind})</span>
                      </div>

                      <div style={{ marginBottom: '6px', color: 'var(--muted-foreground)', fontFamily: 'monospace', wordBreak: 'break-all' }}>
                        {item.identifier}
                      </div>

                      {item.issue === 'stale' && (item.en_recorded || item.en_current) && (
                        <div style={{ marginBottom: '6px', color: 'var(--muted-foreground)' }}>
                          EN source: {item.en_recorded || '(empty)'} → {item.en_current || '(empty)'}
                        </div>
                      )}

                      <button
                        onClick={() => handleCopyIdentifier(item.identifier)}
                        style={{
                          padding: '4px 8px',
                          backgroundColor: copiedIdentifier === item.identifier ? 'var(--status-success-text)' : 'var(--secondary)',
                          color: copiedIdentifier === item.identifier ? 'white' : 'var(--foreground)',
                          border: '1px solid',
                          borderColor: copiedIdentifier === item.identifier ? 'var(--status-success-text)' : 'var(--input)',
                          borderRadius: '4px',
                          fontSize: '11px',
                          cursor: 'pointer',
                        }}
                      >
                        {copiedIdentifier === item.identifier ? 'Copied' : 'Copy ID'}
                      </button>
                    </div>
                  ))}
                  {filteredAuditIssues.length > 50 && (
                    <div style={{ padding: '6px 10px', fontSize: '12px', color: 'var(--muted-foreground)' }}>
                      +{filteredAuditIssues.length - 50} more
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ fontSize: '12px', color: 'var(--muted-foreground)' }}>
                  No audit issues match the current filters
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Card>

      {/* Translation Table */}
      <Card>
        <div style={{ marginBottom: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)', marginBottom: '12px' }}>
            Translations
          </h2>

          {/* Kind Filter */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {(['all', 'element', 'relation', 'rule', 'layer'] as TranslationKind[]).map((kind) => (
              <button
                key={kind}
                onClick={() => setSelectedKind(kind)}
                style={{
                  padding: '6px 12px',
                  backgroundColor: selectedKind === kind ? 'var(--primary)' : 'var(--secondary)',
                  color: selectedKind === kind ? 'white' : 'var(--foreground)',
                  border: '1px solid',
                  borderColor: selectedKind === kind ? 'var(--primary)' : 'var(--border)',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: '500',
                  cursor: 'pointer',
                  textTransform: 'capitalize'
                }}
              >
                {kind}
              </button>
            ))}
          </div>
        </div>

        {translationsError && (
          <ErrorBanner message={translationsError instanceof Error ? translationsError.message : 'Failed to load translations'} />
        )}

        {isLoadingTranslations ? (
          <LoadingSpinner />
        ) : filteredTranslations.length > 0 ? (
          <div style={{
            backgroundColor: 'var(--secondary)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            overflow: 'hidden'
          }}>
            {/* Header */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: '200px 1fr 120px 100px',
              gap: '16px',
              padding: '12px 16px',
              backgroundColor: 'var(--accent)',
              borderBottom: '1px solid var(--border)',
              fontSize: '12px',
              fontWeight: '600',
              color: 'var(--muted-foreground)'
            }}>
              <div>Key</div>
              <div>Translation</div>
              <div>Kind</div>
              <div>Action</div>
            </div>

            {/* Rows */}
            <div style={{ maxHeight: '600px', overflow: 'auto' }}>
              {filteredTranslations.map((translation: I18nTranslationItem) => {
                const key = makeKey(translation);
                const isEditing = editingKey === key;
                const isMissing = !translation.value;

                return (
                  <div
                    key={key}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '200px 1fr 120px 100px',
                      gap: '16px',
                      padding: '12px 16px',
                      borderBottom: '1px solid var(--border)',
                      alignItems: 'center',
                      backgroundColor: isMissing ? 'var(--status-error-bg)' : 'var(--card)'
                    }}
                  >
                    <div style={{
                      fontSize: '13px',
                      color: 'var(--muted-foreground)',
                      fontFamily: 'monospace',
                      wordBreak: 'break-all'
                    }}>
                      {translation.name}.{translation.field}
                    </div>

                    <div>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          style={{
                            width: '100%',
                            padding: '6px 8px',
                            border: '1px solid var(--primary)',
                            borderRadius: '4px',
                            fontSize: '14px'
                          }}
                          autoFocus
                        />
                      ) : (
                        <div style={{
                          fontSize: '14px',
                          color: isMissing ? 'var(--destructive)' : 'var(--foreground)'
                        }}>
                          {translation.value || '(missing)'}
                        </div>
                      )}
                    </div>

                    <div>
                      <Badge label={translation.kind} />
                    </div>

                    <div style={{ display: 'flex', gap: '4px' }}>
                      {isEditing ? (
                        <>
                          <button
                            onClick={() => handleSaveEdit(translation)}
                            disabled={updateTranslation.isPending}
                            style={{
                              padding: '4px 8px',
                              backgroundColor: 'var(--status-success-text)',
                              color: 'white',
                              border: 'none',
                              borderRadius: '4px',
                              fontSize: '12px',
                              cursor: 'pointer',
                              opacity: updateTranslation.isPending ? 0.5 : 1
                            }}
                          >
                            Save
                          </button>
                          <button
                            onClick={handleCancelEdit}
                            disabled={updateTranslation.isPending}
                            style={{
                              padding: '4px 8px',
                              backgroundColor: 'var(--border)',
                              color: 'var(--foreground)',
                              border: 'none',
                              borderRadius: '4px',
                              fontSize: '12px',
                              cursor: 'pointer'
                            }}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleStartEdit(key, translation.value)}
                          style={{
                            padding: '4px 8px',
                            backgroundColor: 'var(--secondary)',
                            color: 'var(--foreground)',
                            border: '1px solid var(--input)',
                            borderRadius: '4px',
                            fontSize: '12px',
                            cursor: 'pointer'
                          }}
                        >
                          Edit
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{
            padding: '32px',
            textAlign: 'center',
            color: 'var(--muted-foreground)',
            fontSize: '14px'
          }}>
            No translations found for selected filter
          </div>
        )}
      </Card>
    </div>
  );
}
