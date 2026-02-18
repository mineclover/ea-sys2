import { useState } from 'react';
import { useSystemSelfModel } from '@/api/hooks';
import { Card, LoadingSpinner, ErrorBanner } from '@/components/ui';
import { PageHeader } from '@/components/layout';

export default function SystemSelfModelPage() {
  const { data, isLoading, error } = useSystemSelfModel();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (data) {
      navigator.clipboard.writeText(data);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div style={{ padding: '24px' }}>
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <ErrorBanner message={error instanceof Error ? error.message : 'Failed to load system self-model'} />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <PageHeader metaKey="admin.self-model" compact />

      <div style={{ padding: '24px' }}>
        <Card>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)' }}>
              Mermaid Source
            </h2>
            <button
              onClick={handleCopy}
              style={{
                padding: '8px 16px',
                backgroundColor: copied ? 'var(--status-success-text)' : 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
            >
              {copied ? 'Copied!' : 'Copy Source'}
            </button>
          </div>

          <pre style={{
            backgroundColor: 'var(--secondary)',
            padding: '16px',
            borderRadius: '6px',
            overflow: 'auto',
            fontSize: '13px',
            lineHeight: '1.6',
            color: 'var(--foreground)',
            border: '1px solid var(--border)',
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
          }}>
            <code>{data || 'No mermaid source available'}</code>
          </pre>
        </Card>
      </div>
    </div>
  );
}
