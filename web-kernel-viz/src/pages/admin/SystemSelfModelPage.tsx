import { useState } from 'react';
import { useSystemSelfModel } from '@/api/hooks';
import { Card, LoadingSpinner, ErrorBanner } from '@/components/ui';

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
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{
          fontSize: '24px',
          fontWeight: '600',
          color: 'var(--text-primary)',
          marginBottom: '8px'
        }}>
          System Self-Model
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
          Mermaid diagram representing the system's self-model
        </p>
      </div>

      <Card>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px'
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)' }}>
            Mermaid Source
          </h2>
          <button
            onClick={handleCopy}
            style={{
              padding: '8px 16px',
              backgroundColor: copied ? '#10b981' : 'var(--accent)',
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
          backgroundColor: 'var(--bg-secondary)',
          padding: '16px',
          borderRadius: '6px',
          overflow: 'auto',
          fontSize: '13px',
          lineHeight: '1.6',
          color: 'var(--text-primary)',
          border: '1px solid var(--border)',
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
        }}>
          <code>{data || 'No mermaid source available'}</code>
        </pre>
      </Card>
    </div>
  );
}
