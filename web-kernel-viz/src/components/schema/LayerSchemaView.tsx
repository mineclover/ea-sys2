
import { useCallback, useEffect, useState } from 'react';
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    BackgroundVariant,
    type Node,
    type Edge,
    useReactFlow,
    Panel,
    ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { CustomEdge } from '../edges';
import { CustomMarkers } from '../markers';
import { DynamicNode } from '../nodes';
import { getLayoutedElements } from '@/utils/layout';
import { routeEdges } from '@/utils/routing';
import { fetchLayerSchema } from '@/api/client';
import type {
    LayerSchemaResponse,
    LayerSchemaElement,
    LayerSchemaRule,
    I18nString,
} from '@/api/types';
import type { MarkerType } from '@/types/diagram';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

const nodeTypes = { dynamic: DynamicNode };
const edgeTypes = { custom: CustomEdge };

// --- Relation style mapping (kernel_relation based) ---

interface RelationStyle {
    connector?: string;
    endMarker?: MarkerType;
    startMarker?: MarkerType;
}

const RELATION_STYLES: Record<string, RelationStyle> = {
    ownership:      { endMarker: 'composition' },
    membership:     { endMarker: 'composition' },
    specialization: { connector: 'solid', endMarker: 'directed' },
    feature_typing: { connector: 'dashed', endMarker: 'none' },
    association:    { connector: 'solid' },
    connector:      { connector: 'solid' },
    redefinition:   { connector: 'dashed', startMarker: 'none', endMarker: 'none' },
    subsetting:     { connector: 'dashed' },
    flow:           { connector: 'solid', endMarker: 'directed' },
    succession:     { connector: 'dashed', endMarker: 'directed' },
    triggering:     { connector: 'dashed', endMarker: 'directed' },
    guarding:       { connector: 'dashed', startMarker: 'none' },
    transition:     { connector: 'solid', endMarker: 'directed' },
};

const getMarkerUrl = (m?: MarkerType) => {
    if (!m || m === 'none') return undefined;
    return `url(#${m})`;
};

// --- Resolve kernel_relation for a profile relation name ---

function resolveKernelRelation(
    schema: LayerSchemaResponse,
    relationName: string,
): string | undefined {
    const rel = schema.relations.find((r) => r.name === relationName);
    return rel?.kernel_relation;
}

// --- Build ReactFlow elements from M2 schema data ---

interface NodeLookup {
    byName: Map<string, LayerSchemaElement & { layer: string }>;
    ruleByIdx: Map<string, LayerSchemaRule>;
}

function buildElements(
    schema: LayerSchemaResponse,
    lang: string,
): { nodes: Node[]; edges: Edge[]; lookup: NodeLookup } {
    const byName = new Map<string, LayerSchemaElement & { layer: string }>();
    const ruleByIdx = new Map<string, LayerSchemaRule>();

    // Build element name set for filtering rules to concrete elements
    const elementNames = new Set<string>();
    const rfNodes: Node[] = [];

    for (const group of schema.elements_by_layer) {
        for (const elem of group.elements) {
            elementNames.add(elem.name);
            byName.set(elem.name, { ...elem, layer: group.layer });
            const label = i18n(elem.display_name, lang) || elem.name;
            rfNodes.push({
                id: elem.name,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: {
                    label,
                    description: i18n(elem.description, lang),
                    layer: group.layer,
                },
            });
        }
    }

    // Build edges from rules — only rules that reference concrete element names
    const rfEdges: Edge[] = [];
    let edgeIdx = 0;
    for (const rule of schema.rules) {
        if (!rule.valid) continue;
        // Skip pattern-based rules (starting with @ or #)
        if (rule.source.startsWith('@') || rule.source.startsWith('#')) continue;
        if (rule.target.startsWith('@') || rule.target.startsWith('#')) continue;
        // Both source and target must be known elements
        if (!elementNames.has(rule.source) || !elementNames.has(rule.target)) continue;

        const eid = `e-${edgeIdx++}-${rule.source}-${rule.target}`;
        ruleByIdx.set(eid, rule);

        const kernelRel = resolveKernelRelation(schema, rule.relation);
        const style = RELATION_STYLES[kernelRel || rule.relation] || { connector: 'solid', endMarker: 'directed' };

        rfEdges.push({
            id: eid,
            source: rule.source,
            target: rule.target,
            type: 'custom',
            data: { style: { ...style, strokeColor: '#555' } },
            markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
            markerStart: getMarkerUrl(style.startMarker),
            label: rule.relation,
        });
    }

    const layouted = getLayoutedElements(rfNodes, rfEdges, 'TB');
    const routed = routeEdges(layouted.nodes, layouted.edges);
    return { nodes: routed.nodes, edges: routed.edges, lookup: { byName, ruleByIdx } };
}

// --- Info panel ---

type InfoData =
    | { kind: 'node'; elem: LayerSchemaElement & { layer: string } }
    | { kind: 'edge'; rule: LayerSchemaRule };

const lbl = { fontSize: 10, fontWeight: 700 as const, color: '#94a3b8', textTransform: 'uppercase' as const };

function InfoPanel({ info, lang, onClose }: { info: InfoData; lang: string; onClose: () => void }) {
    const isNode = info.kind === 'node';
    return (
        <Panel position="bottom-right">
            <div style={{
                background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8,
                padding: '12px 16px', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                minWidth: 220, maxWidth: 340, fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={lbl}>{isNode ? 'Element' : 'Rule'}</div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: '#94a3b8', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                {isNode ? (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 2 }}>
                            {i18n(info.elem.display_name, lang) || info.elem.name}
                            {info.elem.display_name && (
                                <span style={{ fontWeight: 400, color: '#94a3b8', marginLeft: 6, fontSize: 11 }}>{info.elem.name}</span>
                            )}
                        </div>
                        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 2 }}>
                            {info.elem.layer}
                            {info.elem.category ? ` \u00b7 ${info.elem.category}` : ''}
                        </div>
                        <div style={{ marginTop: 4 }}>
                            <span style={{
                                padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                background: '#ede9fe', color: '#6d28d9', borderRadius: 3,
                            }}>{info.elem.kernel_type}</span>
                        </div>
                        {i18n(info.elem.description, lang) && (
                            <div style={{ fontSize: 11, color: '#475569', marginTop: 6, lineHeight: 1.5 }}>
                                {i18n(info.elem.description, lang)}
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#1e293b', marginBottom: 4 }}>
                            {info.rule.source} <span style={{ color: '#94a3b8' }}>{'\u2192'}</span> {info.rule.target}
                        </div>
                        <div style={{ fontSize: 11, color: '#475569', marginBottom: 2 }}>
                            Relation: <strong>{info.rule.relation}</strong>
                        </div>
                        <div style={{ fontSize: 11, color: '#94a3b8' }}>
                            Priority {info.rule.priority}
                        </div>
                        {info.rule.notes && (
                            <div style={{ fontSize: 11, color: '#475569', marginTop: 6, lineHeight: 1.5 }}>
                                {info.rule.notes}
                            </div>
                        )}
                    </>
                )}
            </div>
        </Panel>
    );
}

// --- Inner graph component (needs ReactFlow context) ---

interface InnerProps {
    layerKey: string;
    lang: string;
}

function InnerGraph({ layerKey, lang }: InnerProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
    const { fitView } = useReactFlow();
    const [error, setError] = useState<string | null>(null);
    const [rawSchema, setRawSchema] = useState<LayerSchemaResponse | null>(null);
    const [lookup, setLookup] = useState<NodeLookup | null>(null);
    const [info, setInfo] = useState<InfoData | null>(null);
    const [stats, setStats] = useState<{ nodes: number; edges: number; rules: number } | null>(null);

    const load = useCallback(() => {
        setError(null);
        setNodes([]);
        setEdges([]);
        setInfo(null);
        setStats(null);
        setRawSchema(null);

        fetchLayerSchema(layerKey, { lang })
            .then((schema) => {
                setRawSchema(schema);
                const { nodes: n, edges: e, lookup: lk } = buildElements(schema, lang);
                setLookup(lk);
                setNodes(n);
                setEdges(e);
                setStats({ nodes: schema.element_count, edges: e.length, rules: schema.rule_count });
            })
            .catch(() => {
                setError('unavailable');
            });
    }, [layerKey, lang, setNodes, setEdges]);

    useEffect(() => { load(); }, [load]);

    // Rebuild when lang changes and we have raw data
    useEffect(() => {
        if (!rawSchema) return;
        const { nodes: n, edges: e, lookup: lk } = buildElements(rawSchema, lang);
        setLookup(lk);
        setNodes(n);
        setEdges(e);
        window.requestAnimationFrame(() => fitView());
    }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        if (nodes.length > 0) window.requestAnimationFrame(() => fitView());
    }, [nodes.length, fitView]);

    const onLayout = useCallback((dir: string) => {
        const layouted = getLayoutedElements(nodes, edges, dir);
        const routed = routeEdges(layouted.nodes, layouted.edges);
        setNodes([...routed.nodes]);
        setEdges([...routed.edges]);
        window.requestAnimationFrame(() => fitView());
    }, [nodes, edges, setNodes, setEdges, fitView]);

    const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
        if (!lookup) return;
        const elem = lookup.byName.get(node.id);
        if (elem) setInfo({ kind: 'node', elem });
    }, [lookup]);

    const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
        if (!lookup) return;
        const rule = lookup.ruleByIdx.get(edge.id);
        if (rule) setInfo({ kind: 'edge', rule });
    }, [lookup]);

    const onPaneClick = useCallback(() => setInfo(null), []);

    if (error === 'unavailable') {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid #e2e8f0', borderRadius: 8,
                    background: '#f8fafc', fontSize: 12, color: '#64748b',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load layer schema — API server may be unavailable.
                    <button onClick={load} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid #cbd5e1', borderRadius: 4,
                        background: '#fff', color: '#475569', cursor: 'pointer',
                    }}>Retry</button>
                </div>
            </div>
        );
    }

    return (
        <div style={{ width: '100%', height: '100%' }}>
            <CustomMarkers />
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={onNodeClick}
                onEdgeClick={onEdgeClick}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                <Panel position="top-right">
                    <div style={{
                        display: 'flex', gap: 8, alignItems: 'center',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}>
                        {rawSchema && (
                            <span style={{
                                fontSize: 11, fontWeight: 600, color: '#64748b',
                                padding: '4px 8px', background: '#f1f5f9', borderRadius: 4,
                            }}>
                                {rawSchema.profile_name} v{rawSchema.version}
                                {stats && ` · ${stats.nodes}E / ${stats.edges}R`}
                            </span>
                        )}
                        <button onClick={() => onLayout('TB')} style={layoutBtnStyle}>Vertical</button>
                        <button onClick={() => onLayout('LR')} style={layoutBtnStyle}>Horizontal</button>
                    </div>
                </Panel>
                {info && <InfoPanel info={info} lang={lang} onClose={() => setInfo(null)} />}
            </ReactFlow>
        </div>
    );
}

const layoutBtnStyle: React.CSSProperties = {
    padding: '4px 10px', fontSize: 11, fontWeight: 500,
    border: '1px solid #cbd5e1', borderRadius: 4,
    background: '#fff', color: '#475569', cursor: 'pointer',
};

// --- Exported wrapper ---

interface LayerSchemaViewProps {
    layerKey: string;
    lang: string;
}

export default function LayerSchemaView({ layerKey, lang }: LayerSchemaViewProps) {
    return (
        <ReactFlowProvider>
            <InnerGraph layerKey={layerKey} lang={lang} />
        </ReactFlowProvider>
    );
}
