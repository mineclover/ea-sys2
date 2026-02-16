
import { useEffect, useState, useCallback } from 'react';
import { fetchGovernanceDashboard } from '@/api/client';
import type { GovernanceDashboardResponse } from '@/api/types';

interface FrameworkInfo {
    name: string;
    version: string;
    element_count: number;
    relation_count: number;
    rule_count: number;
}

export default function FrameworksView() {
    const [frameworks, setFrameworks] = useState<FrameworkInfo[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(() => {
        setError(null);
        fetchGovernanceDashboard()
            .then((dash: GovernanceDashboardResponse) => setFrameworks(dash.frameworks))
            .catch(() => setError('unavailable'));
    }, []);

    useEffect(() => { load(); }, [load]);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                    background: '#f8fafc', fontSize: 12, color: '#64748b',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load frameworks — API server may be unavailable.
                    <button onClick={load} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid #cbd5e1', borderRadius: 4,
                        background: '#fff', color: '#475569', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    if (!frameworks) {
        return <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>Loading frameworks…</div>;
    }

    if (frameworks.length === 0) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>
                No frameworks registered.
            </div>
        );
    }

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' }}>Frameworks</h2>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>{frameworks.length} frameworks registered</span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 14 }}>
                {frameworks.map((fw) => (
                    <div key={fw.name} style={{
                        padding: '16px 18px', border: '1px solid #e2e8f0', borderRadius: 8,
                        background: '#fff',
                    }}>
                        <div style={{ fontSize: 14, fontWeight: 700, color: '#1e293b', marginBottom: 2 }}>{fw.name}</div>
                        <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 12 }}>v{fw.version}</div>
                        <div style={{ display: 'flex', gap: 12 }}>
                            <StatChip label="Entities" value={fw.element_count} />
                            <StatChip label="Relations" value={fw.relation_count} />
                            <StatChip label="Rules" value={fw.rule_count} />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function StatChip({ label, value }: { label: string; value: number }) {
    return (
        <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#1e293b' }}>{value}</div>
            <div style={{ fontSize: 10, color: '#94a3b8', fontWeight: 600, textTransform: 'uppercase' }}>{label}</div>
        </div>
    );
}
