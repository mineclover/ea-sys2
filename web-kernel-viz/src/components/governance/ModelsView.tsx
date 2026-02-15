
import { useCallback, useState, type ReactNode } from 'react';
import { fetchModelState } from '@/api/client';

interface ModelsViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

function ModelDetail({ data }: { data: Record<string, unknown> }) {
    return (
        <div style={{ fontSize: 12 }}>
            {Object.entries(data).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 8 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>{key}</div>
                    <div style={{ color: '#1e293b', wordBreak: 'break-all' }}>
                        {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '-')}
                    </div>
                </div>
            ))}
        </div>
    );
}

export default function ModelsView({ onShowDetail }: ModelsViewProps) {
    const [modelName, setModelName] = useState('');
    const [error, setError] = useState<string | null>(null);

    const onLookup = useCallback(() => {
        if (!modelName.trim()) return;
        setError(null);
        fetchModelState(modelName.trim())
            .then((state) => {
                onShowDetail(modelName, <ModelDetail data={state} />);
            })
            .catch((err) => setError(String(err)));
    }, [modelName, onShowDetail]);

    return (
        <div style={{ height: '100%', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #e2e8f0', background: '#fafbfc' }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginRight: 8 }}>
                    Model Lookup
                </span>
            </div>

            <div style={{ padding: 16 }}>
                <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                    <input
                        placeholder="Model name"
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && onLookup()}
                        style={{ padding: '6px 10px', fontSize: 13, border: '1px solid #cbd5e1', borderRadius: 4, flex: 1 }}
                    />
                    <button onClick={onLookup} style={{
                        padding: '6px 16px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #3b82f6', borderRadius: 4, background: '#3b82f6', color: '#fff', cursor: 'pointer',
                    }}>
                        Lookup
                    </button>
                </div>
                {error && (
                    <div style={{
                        padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                        background: '#f8fafc', fontSize: 12, color: '#64748b',
                    }}>
                        Unable to look up model — API server may be unavailable.
                    </div>
                )}
                <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 16 }}>
                    Enter a registered model name to inspect its state, versions, and validation history.
                </div>
            </div>
        </div>
    );
}
