
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchCrossLayerSummary, fetchGovernanceDashboard } from '@/api/client';
import type { CrossLayerSummaryResponse, GovernanceDashboardResponse } from '@/api/types';

interface LayerRow {
    layer_key: string;
    profile_name: string;
    elements: number;
    relations: number;
    rules: number;
    nodes: number;
    edges: number;
}

export default function LayersView() {
    const navigate = useNavigate();
    const [rows, setRows] = useState<LayerRow[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(() => {
        setError(null);
        Promise.all([fetchCrossLayerSummary(), fetchGovernanceDashboard()])
            .then(([cross, dash]: [CrossLayerSummaryResponse, GovernanceDashboardResponse]) => {
                const layerMap = new Map<string, { elements: number; relations: number; rules: number; profile_name: string }>();
                for (const li of dash.managed_layers.layers) {
                    layerMap.set(li.layer_key, {
                        elements: li.element_count,
                        relations: li.relation_count,
                        rules: li.rule_count,
                        profile_name: li.profile_name,
                    });
                }
                for (const gs of dash.managed_layers.governance_stack) {
                    layerMap.set(gs.stack_id, {
                        elements: gs.element_count,
                        relations: gs.relation_count,
                        rules: gs.rule_count,
                        profile_name: gs.profile_name,
                    });
                }
                const built: LayerRow[] = cross.layers.map((cl) => {
                    const info = layerMap.get(cl.layer_key);
                    return {
                        layer_key: cl.layer_key,
                        profile_name: info?.profile_name || cl.layer_key,
                        elements: info?.elements || 0,
                        relations: info?.relations || 0,
                        rules: info?.rules || 0,
                        nodes: cl.node_count,
                        edges: cl.edge_count,
                    };
                });
                setRows(built);
            })
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
                    Unable to load layer summary — API server may be unavailable.
                    <button onClick={load} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid #cbd5e1', borderRadius: 4,
                        background: '#fff', color: '#475569', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    if (!rows) {
        return <div style={{ padding: 40, fontFamily: 'system-ui', fontSize: 13, color: '#94a3b8' }}>Loading layers…</div>;
    }

    const totals = rows.reduce(
        (acc, r) => ({
            elements: acc.elements + r.elements,
            relations: acc.relations + r.relations,
            rules: acc.rules + r.rules,
            nodes: acc.nodes + r.nodes,
            edges: acc.edges + r.edges,
        }),
        { elements: 0, relations: 0, rules: 0, nodes: 0, edges: 0 },
    );

    return (
        <div style={{ padding: '24px 32px', fontFamily: 'system-ui, -apple-system, sans-serif', overflowY: 'auto', width: '100%' }}>
            <div style={{ marginBottom: 20 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1e293b' }}>Layer Comparison</h2>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>{rows.length} layers loaded</span>
            </div>

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                    <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                        <th style={thStyle}>Layer</th>
                        <th style={thStyle}>Profile</th>
                        <th style={thNumStyle}>Elements</th>
                        <th style={thNumStyle}>Relations</th>
                        <th style={thNumStyle}>Rules</th>
                        <th style={thNumStyle}>Nodes</th>
                        <th style={thNumStyle}>Edges</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r) => (
                        <tr
                            key={r.layer_key}
                            onClick={() => navigate(`/explorer/profile/${r.profile_name}`)}
                            style={{ borderBottom: '1px solid #f1f5f9', cursor: 'pointer' }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                        >
                            <td style={{ ...tdStyle, fontWeight: 600 }}>{r.layer_key}</td>
                            <td style={{ ...tdStyle, color: '#64748b' }}>{r.profile_name}</td>
                            <td style={tdNumStyle}>{r.elements}</td>
                            <td style={tdNumStyle}>{r.relations}</td>
                            <td style={tdNumStyle}>{r.rules}</td>
                            <td style={tdNumStyle}>{r.nodes}</td>
                            <td style={tdNumStyle}>{r.edges}</td>
                        </tr>
                    ))}
                    <tr style={{ borderTop: '2px solid #e2e8f0', fontWeight: 700 }}>
                        <td style={tdStyle} colSpan={2}>Total</td>
                        <td style={tdNumStyle}>{totals.elements}</td>
                        <td style={tdNumStyle}>{totals.relations}</td>
                        <td style={tdNumStyle}>{totals.rules}</td>
                        <td style={tdNumStyle}>{totals.nodes}</td>
                        <td style={tdNumStyle}>{totals.edges}</td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
}

const thStyle: React.CSSProperties = {
    textAlign: 'left', padding: '8px 10px', fontSize: 11, fontWeight: 600,
    color: '#94a3b8', textTransform: 'uppercase',
};

const thNumStyle: React.CSSProperties = { ...thStyle, textAlign: 'right' };

const tdStyle: React.CSSProperties = {
    padding: '8px 10px', fontSize: 12, color: '#1e293b',
};

const tdNumStyle: React.CSSProperties = { ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
