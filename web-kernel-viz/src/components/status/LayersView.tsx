
import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCrossLayerSummary, useGovernanceDashboard } from '@/api/hooks';
import { ErrorBanner, LoadingSpinner } from '@/components/ui';
import { PageHeader } from '@/components/layout';

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
    const cross = useCrossLayerSummary();
    const dash = useGovernanceDashboard();

    const rows = useMemo<LayerRow[] | null>(() => {
        if (!cross.data || !dash.data) return null;

        const layerMap = new Map<string, { elements: number; relations: number; rules: number; profile_name: string }>();
        for (const li of dash.data.managed_layers.layers) {
            layerMap.set(li.layer_key, {
                elements: li.element_count,
                relations: li.relation_count,
                rules: li.rule_count,
                profile_name: li.profile_name,
            });
        }
        for (const gs of dash.data.managed_layers.governance_stack) {
            layerMap.set(gs.stack_id, {
                elements: gs.element_count,
                relations: gs.relation_count,
                rules: gs.rule_count,
                profile_name: gs.profile_name,
            });
        }
        return cross.data.layers.map((cl) => {
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
    }, [cross.data, dash.data]);

    if (cross.isError || dash.isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <ErrorBanner
                    message="Unable to load layer summary — API server may be unavailable."
                    onRetry={() => { cross.refetch(); dash.refetch(); }}
                />
            </div>
        );
    }

    if (cross.isLoading || dash.isLoading || !rows) {
        return <LoadingSpinner message="Loading layers..." />;
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
            <PageHeader metaKey="status.layers" subtitle={`${rows.length} layers loaded`} />

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)' }}>
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
                            style={{ borderBottom: '1px solid var(--accent)', cursor: 'pointer' }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--secondary)')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                        >
                            <td style={{ ...tdStyle, fontWeight: 600 }}>{r.layer_key}</td>
                            <td style={{ ...tdStyle, color: 'var(--muted-foreground)' }}>{r.profile_name}</td>
                            <td style={tdNumStyle}>{r.elements}</td>
                            <td style={tdNumStyle}>{r.relations}</td>
                            <td style={tdNumStyle}>{r.rules}</td>
                            <td style={tdNumStyle}>{r.nodes}</td>
                            <td style={tdNumStyle}>{r.edges}</td>
                        </tr>
                    ))}
                    <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
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
    color: 'var(--muted-foreground)', textTransform: 'uppercase',
};

const thNumStyle: React.CSSProperties = { ...thStyle, textAlign: 'right' };

const tdStyle: React.CSSProperties = {
    padding: '8px 10px', fontSize: 12, color: 'var(--foreground)',
};

const tdNumStyle: React.CSSProperties = { ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' };
