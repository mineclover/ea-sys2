
import { Panel } from '@xyflow/react';
import type { CSSProperties } from 'react';

interface TraversalPanelProps {
    lang?: string;
    selectedNode: string | null;
    reachableCount: number;
    relationOptions: string[];
    relationFilter: string;
    blockedRelations: string[];
    direction: 'outgoing' | 'incoming' | 'both';
    depth: number;
    maxNodes: number;
    autoTraverse: boolean;
    traversalMeta?: {
        traversedEdges: number;
        capped: boolean;
    } | null;
    onRelationFilterChange: (value: string) => void;
    onBlockedRelationsChange: (relations: string[]) => void;
    onDirectionChange: (value: 'outgoing' | 'incoming' | 'both') => void;
    onDepthChange: (value: number) => void;
    onMaxNodesChange: (value: number) => void;
    onAutoTraverseChange: (value: boolean) => void;
    onRunTraversal: () => void;
    onClear: () => void;
}

export default function TraversalPanel({
    lang = 'en',
    selectedNode,
    reachableCount,
    relationOptions,
    relationFilter,
    blockedRelations,
    direction,
    depth,
    maxNodes,
    autoTraverse,
    traversalMeta,
    onRelationFilterChange,
    onBlockedRelationsChange,
    onDirectionChange,
    onDepthChange,
    onMaxNodesChange,
    onAutoTraverseChange,
    onRunTraversal,
    onClear,
}: TraversalPanelProps) {
    if (!selectedNode) return null;

    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--card)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                padding: '12px 16px',
                boxShadow: `0 4px 6px -1px var(--shadow-lg)`,
                minWidth: 280,
                fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ fontSize: 11, color: 'var(--muted-foreground)', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
                    {lang === 'ko' ? '탐색 제어' : 'Traversal Control'}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', marginBottom: 4 }}>
                    {selectedNode}
                </div>
                <div style={{ fontSize: 12, color: 'var(--foreground)', marginBottom: 8 }}>
                    {lang === 'ko'
                        ? `${reachableCount}개 도달 가능 요소`
                        : `${reachableCount} reachable element${reachableCount !== 1 ? 's' : ''}`}
                    {traversalMeta && (
                        <span style={{ color: 'var(--muted-foreground)' }}>
                            {lang === 'ko'
                                ? ` · ${traversalMeta.traversedEdges}개 엣지 탐색`
                                : ` · traversed ${traversalMeta.traversedEdges} edge${traversalMeta.traversedEdges !== 1 ? 's' : ''}`}
                            {traversalMeta.capped ? (lang === 'ko' ? ' (상한 적용)' : ' (capped)') : ''}
                        </span>
                    )}
                </div>
                <div style={{ display: 'grid', gap: 6, marginBottom: 8 }}>
                    <label style={labelStyle}>
                        {lang === 'ko' ? '방향' : 'Direction'}
                        <select
                            value={direction}
                            onChange={(e) => onDirectionChange(e.target.value as 'outgoing' | 'incoming' | 'both')}
                            style={selectStyle}
                        >
                            <option value="outgoing">{lang === 'ko' ? 'outgoing(정방향)' : 'outgoing'}</option>
                            <option value="incoming">{lang === 'ko' ? 'incoming(역방향)' : 'incoming'}</option>
                            <option value="both">{lang === 'ko' ? '양방향' : 'both'}</option>
                        </select>
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                        <label style={labelStyle}>
                            {lang === 'ko' ? '깊이' : 'Depth'}
                            <select
                                value={String(depth)}
                                onChange={(e) => onDepthChange(Number(e.target.value) || 1)}
                                style={selectStyle}
                            >
                                {[1, 2, 3, 4, 5, 6].map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </label>
                        <label style={labelStyle}>
                            {lang === 'ko' ? '최대 노드' : 'Max nodes'}
                            <select
                                value={String(maxNodes)}
                                onChange={(e) => onMaxNodesChange(Number(e.target.value) || 20)}
                                style={selectStyle}
                            >
                                {[20, 40, 80, 120, 200, 300, 500].map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </label>
                    </div>
                    <label style={labelStyle}>
                        {lang === 'ko' ? '관계 포커스' : 'Relation focus'}
                        <select
                            value={relationFilter}
                            onChange={(e) => onRelationFilterChange(e.target.value)}
                            style={selectStyle}
                        >
                            <option value="all">{lang === 'ko' ? '전체 관계' : 'all relations'}</option>
                            {relationOptions.map((relation) => (
                                <option key={relation} value={relation}>{relation}</option>
                            ))}
                        </select>
                    </label>
                    <label style={labelStyle}>
                        {lang === 'ko' ? '차단 관계' : 'Block relations'}
                        <select
                            multiple
                            value={blockedRelations}
                            onChange={(e) => {
                                const values = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                                onBlockedRelationsChange(values);
                            }}
                            style={{ ...selectStyle, minHeight: 72 }}
                        >
                            {relationOptions.map((relation) => (
                                <option key={relation} value={relation}>{relation}</option>
                            ))}
                        </select>
                    </label>
                    <label style={{ ...labelStyle, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input
                            type="checkbox"
                            checked={autoTraverse}
                            onChange={(e) => onAutoTraverseChange(e.target.checked)}
                        />
                        {lang === 'ko' ? '노드 클릭 시 자동 실행' : 'auto-run on node click'}
                    </label>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                    <button
                        onClick={onRunTraversal}
                        style={{
                            fontSize: 12,
                            padding: '4px 12px',
                            border: '1px solid var(--input)',
                            borderRadius: 4,
                            background: 'var(--card)',
                            color: 'var(--foreground)',
                            cursor: 'pointer',
                        }}
                    >
                        {lang === 'ko' ? '실행' : 'Run'}
                    </button>
                    <button
                        onClick={onClear}
                        style={{
                            fontSize: 12,
                            padding: '4px 12px',
                            border: '1px solid var(--input)',
                            borderRadius: 4,
                            background: 'var(--secondary)',
                            color: 'var(--foreground)',
                            cursor: 'pointer',
                        }}
                    >
                        {lang === 'ko' ? '초기화' : 'Clear'}
                    </button>
                </div>
            </div>
        </Panel>
    );
}

const labelStyle: CSSProperties = {
    fontSize: 11,
    color: 'var(--muted-foreground)',
    display: 'grid',
    gap: 4,
};

const selectStyle: CSSProperties = {
    fontSize: 11,
    padding: '4px 6px',
    border: '1px solid var(--input)',
    borderRadius: 4,
    background: 'var(--card)',
    color: 'var(--foreground)',
};
