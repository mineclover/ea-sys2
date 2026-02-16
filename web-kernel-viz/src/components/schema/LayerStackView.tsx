import { useMemo, useState, type CSSProperties } from 'react';

import FlowGraph from '@/components/FlowGraph';
import ProfileGraph from '@/components/ProfileGraph';
import { useLayerStack } from '@/api/hooks';
import LayerSchemaView from './LayerSchemaView';

interface LayerStackViewProps {
    layerKey: string;
    lang: string;
}

type StackLevel = 'm2' | 'm1' | 'm0';

const STACK_LEVELS: { key: StackLevel; label: string; hint: string }[] = [
    { key: 'm2', label: 'M2 Schema', hint: 'metamodel + rules' },
    { key: 'm1', label: 'M1 Topology', hint: 'profile graph' },
    { key: 'm0', label: 'M0 Runtime', hint: 'snapshots + models' },
];

export default function LayerStackView({ layerKey, lang }: LayerStackViewProps) {
    const [level, setLevel] = useState<StackLevel>('m2');

    const stackQuery = useLayerStack(layerKey, { lang, m0_limit: 40 });
    const stack = stackQuery.data;

    const statsText = useMemo(() => {
        if (!stack) return null;
        return `${stack.profile_name} v${stack.version} · M2 ${stack.m2.element_count}E/${stack.m2.rule_count}R · M1 ${stack.m1.node_count}N/${stack.m1.edge_count}E · M0 ${stack.m0.snapshot_total}S/${stack.m0.model_candidate_total}M`;
    }, [stack]);
    const m1VisibleLayers = useMemo(
        () => new Set((stack?.m1.nodes || []).map((node) => node.layer)),
        [stack],
    );

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{
                padding: '10px 12px',
                borderBottom: '1px solid var(--border)',
                background: 'var(--bg-card)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
                flexWrap: 'wrap',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    {STACK_LEVELS.map((item) => (
                        <button
                            key={item.key}
                            onClick={() => setLevel(item.key)}
                            style={{
                                padding: '5px 10px',
                                borderRadius: 6,
                                border: `1px solid ${level === item.key ? 'var(--accent)' : 'var(--border)'}`,
                                background: level === item.key ? 'var(--accent-bg)' : 'var(--bg-card)',
                                color: level === item.key ? 'var(--accent)' : 'var(--text-secondary)',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                            title={item.hint}
                        >
                            {item.label}
                        </button>
                    ))}
                </div>

                {statsText && (
                    <span style={{
                        fontSize: 11,
                        color: 'var(--text-secondary)',
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        padding: '4px 8px',
                    }}>
                        {statsText}
                    </span>
                )}
            </div>

            <div style={{ flex: 1, minHeight: 0 }}>
                {level === 'm2' && (
                    layerKey === 'kernel'
                        ? <FlowGraph lang={lang} />
                        : <LayerSchemaView layerKey={layerKey} lang={lang} />
                )}

                {level === 'm1' && (
                    stack?.profile_name
                        ? <ProfileGraph
                            profileName={stack.profile_name}
                            lang={lang}
                            visibleLayers={m1VisibleLayers}
                        />
                        : <StateMessage
                            kind={stackQuery.isLoading ? 'loading' : 'error'}
                            message={stackQuery.isLoading ? 'Loading layer stack...' : 'Failed to resolve profile topology for this layer.'}
                            onRetry={() => stackQuery.refetch()}
                        />
                )}

                {level === 'm0' && (
                    <LayerM0Panel
                        isLoading={stackQuery.isLoading}
                        isError={stackQuery.isError}
                        onRetry={() => stackQuery.refetch()}
                        snapshots={stack?.m0.snapshots ?? []}
                        modelCandidates={stack?.m0.model_candidates ?? []}
                    />
                )}
            </div>
        </div>
    );
}

function StateMessage({ kind, message, onRetry }: { kind: 'loading' | 'error'; message: string; onRetry?: () => void }) {
    return (
        <div style={{ padding: 20, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{
                padding: '12px 14px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: kind === 'error' ? 'var(--bg-secondary)' : 'var(--bg-card)',
                color: 'var(--text-secondary)',
                fontSize: 12,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
            }}>
                {message}
                {kind === 'error' && onRetry && (
                    <button
                        onClick={onRetry}
                        style={{
                            marginLeft: 'auto',
                            padding: '4px 10px',
                            fontSize: 11,
                            borderRadius: 5,
                            border: '1px solid var(--border-strong)',
                            background: 'var(--bg-card)',
                            color: 'var(--text-secondary)',
                            cursor: 'pointer',
                        }}
                    >
                        Retry
                    </button>
                )}
            </div>
        </div>
    );
}

function LayerM0Panel({
    isLoading,
    isError,
    onRetry,
    snapshots,
    modelCandidates,
}: {
    isLoading: boolean;
    isError: boolean;
    onRetry: () => void;
    snapshots: {
        layer: string;
        model_id: string;
        updated_at: string;
        kind: string;
        payload_keys: string[];
    }[];
    modelCandidates: {
        model_id: string | null;
        model_name: string;
        owner: string | null;
        status: string | null;
        active_version_id: string | null;
        updated_at: string | null;
        score: number;
        match_rules: string[];
    }[];
}) {
    if (isLoading) {
        return <StateMessage kind="loading" message="Loading M0 runtime data..." />;
    }
    if (isError) {
        return <StateMessage kind="error" message="Failed to load M0 runtime data." onRetry={onRetry} />;
    }

    return (
        <div style={{
            height: '100%',
            overflow: 'auto',
            padding: 16,
            display: 'grid',
            gap: 16,
            gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
            alignContent: 'start',
        }}>
            <section style={panelCardStyle}>
                <h3 style={panelTitleStyle}>Model Candidates</h3>
                {modelCandidates.length === 0 ? (
                    <EmptyLabel text="No matched models for this layer." />
                ) : (
                    <div style={{ display: 'grid', gap: 8 }}>
                        {modelCandidates.map((model) => (
                            <div key={model.model_name} style={rowCardStyle}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{model.model_name}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                    status={model.status || '-'} · owner={model.owner || '-'} · score={model.score}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                    match: {model.match_rules.join(', ') || '-'}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section style={panelCardStyle}>
                <h3 style={panelTitleStyle}>Layer Snapshots</h3>
                {snapshots.length === 0 ? (
                    <EmptyLabel text="No runtime snapshots recorded for this layer." />
                ) : (
                    <div style={{ display: 'grid', gap: 8 }}>
                        {snapshots.map((snapshot) => (
                            <div key={`${snapshot.layer}-${snapshot.model_id}`} style={rowCardStyle}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{snapshot.model_id}</div>
                                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                                    kind={snapshot.kind} · updated={snapshot.updated_at || '-'}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                    payload keys: {snapshot.payload_keys.join(', ') || '-'}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>
        </div>
    );
}

function EmptyLabel({ text }: { text: string }) {
    return (
        <div style={{
            fontSize: 12,
            color: 'var(--text-muted)',
            border: '1px dashed var(--border)',
            borderRadius: 8,
            padding: '12px 10px',
            background: 'var(--bg-secondary)',
        }}>
            {text}
        </div>
    );
}

const panelCardStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 12,
    background: 'var(--bg-card)',
    boxShadow: '0 1px 2px var(--shadow)',
    display: 'grid',
    gap: 10,
    alignContent: 'start',
};

const panelTitleStyle: CSSProperties = {
    margin: 0,
    fontSize: 14,
    color: 'var(--text-primary)',
};

const rowCardStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 8,
    background: 'var(--bg-secondary)',
    padding: '8px 10px',
    display: 'grid',
    gap: 3,
};
