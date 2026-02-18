
import { useCallback, useEffect, useMemo, useState } from 'react';
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
    type EdgeMouseHandler,
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
import { useLayerSchema } from '@/api/hooks';
import type {
    LayerSchemaResponse,
    LayerSchemaElement,
    LayerSchemaRelation,
    LayerSchemaRule,
    I18nString,
} from '@/api/types';
import type { MarkerType } from '@/types/diagram';
import { DESIGN_SYSTEM } from '@/styles/design-system';

function i18n(v: I18nString | null | undefined, lang: string): string {
    if (!v) return '';
    if (typeof v === 'string') return v;
    return v[lang] || v['en'] || Object.values(v)[0] || '';
}

const CATEGORY_KO: Record<string, string> = {
    Composite: '복합 구조',
    ActiveStructure: '능동 구조',
    PassiveStructure: '수동 구조',
    Interface: '인터페이스',
    Governance: '거버넌스',
    Behavior: '행동',
    Event: '이벤트',
    Goal: '목표',
    Executable: '실행 항목',
    Context: '컨텍스트',
    Assessment: '평가',
};

const nodeTypes = { dynamic: DynamicNode };
const edgeTypes = { custom: CustomEdge };
const DEFAULT_BLUEPRINT_LAYERS = new Set(['infra', 'needs']);

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

const EDGE_LAYER_COLORS = DESIGN_SYSTEM.colors.layers;

function getKernelLayerColor(kernelLayer?: string): string {
    if (!kernelLayer) return 'var(--muted-foreground)';
    const palette = EDGE_LAYER_COLORS[kernelLayer as keyof typeof EDGE_LAYER_COLORS];
    return palette?.color || 'var(--muted-foreground)';
}

function compactDirection(direction?: string | null): string | null {
    if (!direction) return null;
    if (direction === 'source_to_target') return 'S→T';
    if (direction === 'bidirectional') return '↔';
    return direction.replace(/_/g, ' ');
}

function composeEdgeDetail(
    kernelRel?: string,
    direction?: string | null,
    extra?: string,
): string | undefined {
    const bits = [kernelRel, compactDirection(direction), extra].filter(Boolean) as string[];
    return bits.length > 0 ? bits.join(' · ') : undefined;
}

// --- Resolve kernel_relation for a profile relation name ---

function resolveKernelRelation(
    schema: LayerSchemaResponse,
    relationName: string,
): string | undefined {
    const rel = schema.relations.find((r) => r.name === relationName);
    return rel?.kernel_relation;
}

function resolveKernelRelationLayer(
    schema: LayerSchemaResponse,
    relationName: string,
): string | undefined {
    const rel = schema.relations.find((r) => r.name === relationName);
    return rel?.kernel_layer;
}

// --- Build ReactFlow elements from M2 schema data ---

interface NodeLookup {
    byName: Map<string, LayerSchemaElement & { layer: string }>;
    ruleByIdx: Map<string, LayerSchemaRule>;
}

interface BuildOptions {
    viewMode: 'elements' | 'blueprint';
    edgeMode: 'summary' | 'rules';
    relationFilter: string;
    crossLayerOnly: boolean;
    showEdgeLabels: boolean;
    compactNodes: boolean;
}

interface M2RuleProjectionStats {
    sourceMode: 'blueprint' | 'elements';
    totalRules: number;
    afterValidityFilter: number;
    afterRelationFilter: number;
    afterStructuralFilter: number;
    afterCrossLayerFilter: number;
    summaryGroups: number;
    outputEdges: number;
}

function summaryRulePairKey(rule: Pick<LayerSchemaRule, 'source' | 'target' | 'relation'>): string {
    return `${rule.relation}|${rule.source}|${rule.target}`;
}

function preferSummaryRule(next: LayerSchemaRule, current: LayerSchemaRule): boolean {
    if (next.priority !== current.priority) return next.priority > current.priority;
    const nextKey = `${next.source}->${next.target}`;
    const currentKey = `${current.source}->${current.target}`;
    return nextKey < currentKey;
}

function sortSummaryRules(a: LayerSchemaRule, b: LayerSchemaRule): number {
    if (a.priority !== b.priority) return b.priority - a.priority;
    if (a.source !== b.source) return a.source.localeCompare(b.source);
    return a.target.localeCompare(b.target);
}

function selectCoverageSummaryRules(candidates: LayerSchemaRule[]): LayerSchemaRule[] {
    const byRelation = new Map<string, LayerSchemaRule[]>();
    for (const rule of candidates) {
        const bucket = byRelation.get(rule.relation);
        if (bucket) {
            bucket.push(rule);
        } else {
            byRelation.set(rule.relation, [rule]);
        }
    }

    const selected: LayerSchemaRule[] = [];
    for (const relation of [...byRelation.keys()].sort()) {
        const relationRules = byRelation.get(relation) || [];
        const bestByPair = new Map<string, LayerSchemaRule>();
        for (const rule of relationRules) {
            const key = summaryRulePairKey(rule);
            const existing = bestByPair.get(key);
            if (!existing || preferSummaryRule(rule, existing)) {
                bestByPair.set(key, rule);
            }
        }
        const pool = [...bestByPair.values()].sort(sortSummaryRules);
        if (pool.length === 0) continue;

        const relationSelected = new Map<string, LayerSchemaRule>();
        const sourceCovered = new Set<string>();
        const targetCovered = new Set<string>();
        const addRule = (rule: LayerSchemaRule) => {
            const key = summaryRulePairKey(rule);
            if (relationSelected.has(key)) return;
            relationSelected.set(key, rule);
            sourceCovered.add(rule.source);
            targetCovered.add(rule.target);
        };

        // Seed with the strongest edge first.
        addRule(pool[0]);

        const uniqueSources = [...new Set(pool.map((rule) => rule.source))].sort();
        for (const source of uniqueSources) {
            if (sourceCovered.has(source)) continue;
            const candidate = pool.find((rule) => rule.source === source);
            if (candidate) addRule(candidate);
        }

        const uniqueTargets = [...new Set(pool.map((rule) => rule.target))].sort();
        for (const target of uniqueTargets) {
            if (targetCovered.has(target)) continue;
            const candidate = pool.find((rule) => rule.target === target);
            if (candidate) addRule(candidate);
        }

        selected.push(...[...relationSelected.values()].sort(sortSummaryRules));
    }

    return selected;
}

function buildBlueprintElements(
    schema: LayerSchemaResponse,
    lang: string,
    options: BuildOptions,
): { nodes: Node[]; edges: Edge[]; lookup: NodeLookup } {
    const byName = new Map<string, LayerSchemaElement & { layer: string }>();
    const ruleByIdx = new Map<string, LayerSchemaRule>();
    const layerOf = new Map<string, string>();
    const relationKernel = new Map(
        (schema.m2_blueprint?.relations || []).map((rel) => [rel.name, rel.kernel_relation]),
    );
    const relationLayer = new Map(
        (schema.m2_blueprint?.relations || []).map((rel) => [rel.name, rel.kernel_layer]),
    );
    const relationDirection = new Map(
        (schema.m2_blueprint?.relations || []).map((rel) => [rel.name, rel.direction]),
    );
    const elementByName = new Map(
        schema.elements_by_layer.flatMap((group) =>
            group.elements.map((elem) => [elem.name, elem] as const),
        ),
    );

    const rfNodes: Node[] = [];
    for (const category of schema.m2_blueprint?.categories || []) {
        const localizedCategoryName = i18n(category.display_name || {
            en: category.name,
            ko: CATEGORY_KO[category.name] || category.name,
        }, lang) || category.name;
        const samplePrefix = lang === 'ko' ? '샘플' : 'sample';
        const sampleNames = category.sample_elements.map((name) => {
            const elem = elementByName.get(name);
            return i18n(elem?.display_name || null, lang) || name;
        });
        const pseudoElem: LayerSchemaElement & { layer: string } = {
            identifier: category.identifier,
            name: category.name,
            kernel_type: category.kernel_type,
            kernel_layer: category.kernel_layer,
            category: `category · ${category.element_count} elements`,
            description: category.description || `${samplePrefix}: ${sampleNames.join(', ') || '-'}`,
            display_name: category.display_name || {
                en: category.name,
                ko: CATEGORY_KO[category.name] || category.name,
            },
            layer: category.kernel_layer || 'M2',
        };
        byName.set(category.name, pseudoElem);
        layerOf.set(category.name, pseudoElem.layer);
        rfNodes.push({
            id: category.name,
            type: 'dynamic',
            position: { x: 0, y: 0 },
            data: {
                label: localizedCategoryName,
                subLabel: localizedCategoryName === category.name ? undefined : category.name,
                description: options.compactNodes ? undefined : i18n(pseudoElem.description, lang),
                layer: pseudoElem.layer,
            },
        });
    }

    const summaryCandidates: LayerSchemaRule[] = [];
    const ruleCountBySummaryKey = new Map<string, number>();

    const rfEdges: Edge[] = [];
    let edgeIdx = 0;
    for (const ruleEdge of schema.m2_blueprint?.rules || []) {
        if (options.relationFilter !== 'all' && ruleEdge.relation !== options.relationFilter) continue;
        if (!byName.has(ruleEdge.source_category) || !byName.has(ruleEdge.target_category)) continue;
        if (options.crossLayerOnly && layerOf.get(ruleEdge.source_category) === layerOf.get(ruleEdge.target_category)) {
            continue;
        }

        const pseudoRule: LayerSchemaRule = {
            identifier: ruleEdge.identifier,
            source: ruleEdge.source_category,
            target: ruleEdge.target_category,
            relation: ruleEdge.relation,
            valid: true,
            priority: ruleEdge.priority_max,
            notes: `${ruleEdge.rule_count} aggregated rules`,
        };
        summaryCandidates.push(pseudoRule);
        ruleCountBySummaryKey.set(summaryRulePairKey(pseudoRule), ruleEdge.rule_count);
        if (options.edgeMode === 'summary') continue;

        const eid = `e-blueprint-${edgeIdx++}-${pseudoRule.source}-${pseudoRule.target}-${pseudoRule.relation}`;
        ruleByIdx.set(eid, pseudoRule);
        const kernelRel = relationKernel.get(pseudoRule.relation) || resolveKernelRelation(schema, pseudoRule.relation);
        const kernelLayer = ruleEdge.kernel_layer || relationLayer.get(pseudoRule.relation) || resolveKernelRelationLayer(schema, pseudoRule.relation);
        const strokeColor = getKernelLayerColor(kernelLayer);
        const style = RELATION_STYLES[kernelRel || pseudoRule.relation] || { connector: 'solid', endMarker: 'directed' };
        rfEdges.push({
            id: eid,
            source: pseudoRule.source,
            target: pseudoRule.target,
            type: 'custom',
            data: {
                style: { ...style, strokeColor, strokeWidth: kernelLayer === 'L3' ? 1.85 : 1.6 },
                relation: pseudoRule.relation,
                priority: pseudoRule.priority,
                kernelLayer,
                edgeType: 'm2_blueprint',
                labelDetail: composeEdgeDetail(
                    kernelRel,
                    relationDirection.get(pseudoRule.relation),
                    `${ruleEdge.rule_count} rules`,
                ),
            },
            markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
            markerStart: getMarkerUrl(style.startMarker),
            label: options.showEdgeLabels ? `${pseudoRule.relation} (${ruleEdge.rule_count})` : undefined,
        });
    }

    if (options.edgeMode === 'summary') {
        const selectedSummary = selectCoverageSummaryRules(summaryCandidates);
        for (const rule of selectedSummary) {
            const eid = `e-blueprint-summary-${rule.relation}-${rule.source}-${rule.target}`;
            ruleByIdx.set(eid, rule);
            const kernelRel = relationKernel.get(rule.relation) || resolveKernelRelation(schema, rule.relation);
            const kernelLayer = relationLayer.get(rule.relation) || resolveKernelRelationLayer(schema, rule.relation);
            const ruleCount = ruleCountBySummaryKey.get(summaryRulePairKey(rule));
            const strokeColor = getKernelLayerColor(kernelLayer);
            const style = RELATION_STYLES[kernelRel || rule.relation] || { connector: 'solid', endMarker: 'directed' };
            rfEdges.push({
                id: eid,
                source: rule.source,
                target: rule.target,
                type: 'custom',
                data: {
                    style: { ...style, strokeColor, strokeWidth: kernelLayer === 'L3' ? 1.85 : 1.6 },
                    relation: rule.relation,
                    priority: rule.priority,
                    kernelLayer,
                    edgeType: 'm2_blueprint_summary',
                    labelDetail: composeEdgeDetail(
                        kernelRel,
                        relationDirection.get(rule.relation),
                        ruleCount != null ? `${ruleCount} rules` : undefined,
                    ),
                },
                markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
                markerStart: getMarkerUrl(style.startMarker),
                label: options.showEdgeLabels
                    ? `${rule.relation}${ruleCount != null ? ` (${ruleCount})` : ''}`
                    : undefined,
            });
        }
    }

    const layouted = getLayoutedElements(rfNodes, rfEdges, 'TB');
    const routed = routeEdges(layouted.nodes, layouted.edges);
    return { nodes: routed.nodes, edges: routed.edges, lookup: { byName, ruleByIdx } };
}

function buildElements(
    schema: LayerSchemaResponse,
    lang: string,
    options: BuildOptions,
): { nodes: Node[]; edges: Edge[]; lookup: NodeLookup } {
    if (options.viewMode === 'blueprint' && schema.m2_blueprint) {
        return buildBlueprintElements(schema, lang, options);
    }

    const byName = new Map<string, LayerSchemaElement & { layer: string }>();
    const ruleByIdx = new Map<string, LayerSchemaRule>();
    const layerOf = new Map<string, string>();
    const relationByName = new Map(
        schema.relations.map((relation) => [relation.name, relation] as const),
    );

    // Build element name set for filtering rules to concrete elements
    const elementNames = new Set<string>();
    const rfNodes: Node[] = [];

    for (const group of schema.elements_by_layer) {
        for (const elem of group.elements) {
            elementNames.add(elem.name);
            byName.set(elem.name, { ...elem, layer: group.layer });
            layerOf.set(elem.name, group.layer);
            const label = i18n(elem.display_name, lang) || elem.name;
            rfNodes.push({
                id: elem.name,
                type: 'dynamic',
                position: { x: 0, y: 0 },
                data: {
                    label,
                    subLabel: label === elem.name ? undefined : elem.name,
                    description: options.compactNodes ? undefined : i18n(elem.description, lang),
                    layer: group.layer,
                },
            });
        }
    }

    // Build edges from rules — only rules that reference concrete element names
    const rfEdges: Edge[] = [];
    let edgeIdx = 0;
    const summaryCandidates: LayerSchemaRule[] = [];

    for (const rule of schema.rules) {
        if (!rule.valid) continue;
        if (options.relationFilter !== 'all' && rule.relation !== options.relationFilter) continue;
        // Skip pattern-based rules (starting with @ or #)
        if (rule.source.startsWith('@') || rule.source.startsWith('#')) continue;
        if (rule.target.startsWith('@') || rule.target.startsWith('#')) continue;
        // Both source and target must be known elements
        if (!elementNames.has(rule.source) || !elementNames.has(rule.target)) continue;
        if (options.crossLayerOnly && layerOf.get(rule.source) === layerOf.get(rule.target)) continue;
        summaryCandidates.push(rule);
        if (options.edgeMode === 'summary') continue;

        const eid = `e-${edgeIdx++}-${rule.source}-${rule.target}`;
        ruleByIdx.set(eid, rule);

        const kernelRel = resolveKernelRelation(schema, rule.relation);
        const kernelLayer = resolveKernelRelationLayer(schema, rule.relation);
        const relationMeta = relationByName.get(rule.relation);
        const strokeColor = getKernelLayerColor(kernelLayer);
        const style = RELATION_STYLES[kernelRel || rule.relation] || { connector: 'solid', endMarker: 'directed' };

        rfEdges.push({
            id: eid,
            source: rule.source,
            target: rule.target,
            type: 'custom',
            data: {
                style: { ...style, strokeColor, strokeWidth: kernelLayer === 'L3' ? 1.85 : 1.6 },
                relation: rule.relation,
                priority: rule.priority,
                kernelLayer,
                edgeType: 'm2_rule',
                labelDetail: composeEdgeDetail(kernelRel, relationMeta?.direction),
            },
            markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
            markerStart: getMarkerUrl(style.startMarker),
            label: options.showEdgeLabels ? rule.relation : undefined,
        });
    }

    if (options.edgeMode === 'summary') {
        const selectedSummary = selectCoverageSummaryRules(summaryCandidates);
        for (const rule of selectedSummary) {
            const eid = `e-summary-${rule.relation}-${rule.source}-${rule.target}`;
            ruleByIdx.set(eid, rule);
            const kernelRel = resolveKernelRelation(schema, rule.relation);
            const kernelLayer = resolveKernelRelationLayer(schema, rule.relation);
            const relationMeta = relationByName.get(rule.relation);
            const strokeColor = getKernelLayerColor(kernelLayer);
            const style = RELATION_STYLES[kernelRel || rule.relation] || { connector: 'solid', endMarker: 'directed' };

            rfEdges.push({
                id: eid,
                source: rule.source,
                target: rule.target,
                type: 'custom',
                data: {
                    style: { ...style, strokeColor, strokeWidth: kernelLayer === 'L3' ? 1.85 : 1.6 },
                    relation: rule.relation,
                    priority: rule.priority,
                    kernelLayer,
                    edgeType: 'm2_rule_summary',
                    labelDetail: composeEdgeDetail(kernelRel, relationMeta?.direction),
                },
                markerEnd: getMarkerUrl(style.endMarker) || 'url(#directed)',
                markerStart: getMarkerUrl(style.startMarker),
                label: options.showEdgeLabels ? rule.relation : undefined,
            });
        }
    }

    const layouted = getLayoutedElements(rfNodes, rfEdges, 'TB');
    const routed = routeEdges(layouted.nodes, layouted.edges);
    return { nodes: routed.nodes, edges: routed.edges, lookup: { byName, ruleByIdx } };
}

function computeM2RuleProjection(
    schema: LayerSchemaResponse,
    options: BuildOptions,
): M2RuleProjectionStats {
    if (options.viewMode === 'blueprint' && schema.m2_blueprint) {
        const categories = new Set(schema.m2_blueprint.categories.map((cat) => cat.name));
        const layerOf = new Map(schema.m2_blueprint.categories.map((cat) => [cat.name, cat.kernel_layer]));
        const totalRules = schema.m2_blueprint.rules.length;
        let afterRelationFilter = 0;
        let afterStructuralFilter = 0;
        let afterCrossLayerFilter = 0;
        const summaryCandidates: LayerSchemaRule[] = [];

        for (const ruleEdge of schema.m2_blueprint.rules) {
            if (options.relationFilter !== 'all' && ruleEdge.relation !== options.relationFilter) continue;
            afterRelationFilter += 1;
            if (!categories.has(ruleEdge.source_category) || !categories.has(ruleEdge.target_category)) continue;
            afterStructuralFilter += 1;
            if (
                options.crossLayerOnly
                && layerOf.get(ruleEdge.source_category) === layerOf.get(ruleEdge.target_category)
            ) continue;
            afterCrossLayerFilter += 1;
            summaryCandidates.push({
                identifier: ruleEdge.identifier,
                source: ruleEdge.source_category,
                target: ruleEdge.target_category,
                relation: ruleEdge.relation,
                valid: true,
                priority: ruleEdge.priority_max,
                notes: `${ruleEdge.rule_count} aggregated rules`,
            });
        }

        const summaryGroups = new Set(summaryCandidates.map((rule) => rule.relation)).size;
        const summarySelectedEdges = selectCoverageSummaryRules(summaryCandidates).length;
        return {
            sourceMode: 'blueprint',
            totalRules,
            afterValidityFilter: totalRules,
            afterRelationFilter,
            afterStructuralFilter,
            afterCrossLayerFilter,
            summaryGroups,
            outputEdges: options.edgeMode === 'summary' ? summarySelectedEdges : afterCrossLayerFilter,
        };
    }

    const elementNames = new Set<string>();
    const layerOf = new Map<string, string>();
    for (const group of schema.elements_by_layer) {
        for (const elem of group.elements) {
            elementNames.add(elem.name);
            layerOf.set(elem.name, group.layer);
        }
    }

    const totalRules = schema.rules.length;
    let afterValidityFilter = 0;
    let afterRelationFilter = 0;
    let afterStructuralFilter = 0;
    let afterCrossLayerFilter = 0;
    const summaryCandidates: LayerSchemaRule[] = [];

    for (const rule of schema.rules) {
        if (!rule.valid) continue;
        afterValidityFilter += 1;
        if (options.relationFilter !== 'all' && rule.relation !== options.relationFilter) continue;
        afterRelationFilter += 1;
        if (rule.source.startsWith('@') || rule.source.startsWith('#')) continue;
        if (rule.target.startsWith('@') || rule.target.startsWith('#')) continue;
        if (!elementNames.has(rule.source) || !elementNames.has(rule.target)) continue;
        afterStructuralFilter += 1;
        if (options.crossLayerOnly && layerOf.get(rule.source) === layerOf.get(rule.target)) continue;
        afterCrossLayerFilter += 1;
        summaryCandidates.push(rule);
    }

    const summaryGroups = new Set(summaryCandidates.map((rule) => rule.relation)).size;
    const summarySelectedEdges = selectCoverageSummaryRules(summaryCandidates).length;
    return {
        sourceMode: 'elements',
        totalRules,
        afterValidityFilter,
        afterRelationFilter,
        afterStructuralFilter,
        afterCrossLayerFilter,
        summaryGroups,
        outputEdges: options.edgeMode === 'summary' ? summarySelectedEdges : afterCrossLayerFilter,
    };
}

// --- Info panel ---

type InfoData =
    | { kind: 'node'; elem: LayerSchemaElement & { layer: string } }
    | { kind: 'edge'; rule: LayerSchemaRule; relation?: LayerSchemaRelation };

const lbl = { fontSize: 10, fontWeight: 700 as const, color: 'var(--muted-foreground)', textTransform: 'uppercase' as const };

function InfoPanel({ info, lang, onClose }: { info: InfoData; lang: string; onClose: () => void }) {
    const isNode = info.kind === 'node';
    const nodeName = isNode ? i18n(info.elem.display_name, lang) || info.elem.name : '';
    const nodeNameEn = isNode ? i18n(info.elem.display_name, 'en') || info.elem.name : '';
    const nodeDesc = isNode ? i18n(info.elem.description, lang) : '';
    const nodeDescEn = isNode ? i18n(info.elem.description, 'en') : '';

    const edgeRelationName = !isNode
        ? (i18n(info.relation?.display_name || null, lang) || info.rule.relation)
        : '';
    const edgeRelationNameEn = !isNode
        ? (i18n(info.relation?.display_name || null, 'en') || info.rule.relation)
        : '';
    const edgeRelationDesc = !isNode
        ? i18n(info.relation?.description || null, lang)
        : '';
    const edgeRelationDescEn = !isNode
        ? i18n(info.relation?.description || null, 'en')
        : '';

    return (
        <Panel position="bottom-right">
            <div style={{
                background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
                padding: '12px 16px', boxShadow: '0 4px 6px -1px var(--shadow-lg)',
                minWidth: 220, maxWidth: 340, fontFamily: 'system-ui, -apple-system, sans-serif',
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={lbl}>{isNode ? 'Element' : 'Rule'}</div>
                    <button onClick={onClose} style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--muted-foreground)', fontSize: 14, lineHeight: 1, padding: 0,
                    }}>&times;</button>
                </div>
                {isNode ? (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', marginBottom: 2 }}>
                            {nodeName}
                            {nodeName !== info.elem.name && (
                                <span style={{ fontWeight: 400, color: 'var(--muted-foreground)', marginLeft: 6, fontSize: 11 }}>{info.elem.name}</span>
                            )}
                        </div>
                        {lang !== 'en' && nodeNameEn && nodeNameEn !== nodeName && (
                            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                                en: {nodeNameEn}
                            </div>
                        )}
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                            {info.elem.layer}
                            {info.elem.category ? ` \u00b7 ${info.elem.category}` : ''}
                            {info.elem.kernel_layer ? ` \u00b7 ${info.elem.kernel_layer}` : ''}
                        </div>
                        <div style={{ marginTop: 4 }}>
                            <span style={{
                                padding: '1px 6px', fontSize: 10, fontWeight: 600,
                                background: 'var(--status-indigo-bg)', color: 'var(--status-indigo-text)', borderRadius: 3,
                            }}>{info.elem.kernel_type}</span>
                        </div>
                        {info.elem.identifier && (
                            <div style={{
                                fontSize: 10,
                                color: 'var(--muted-foreground)',
                                marginTop: 6,
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            }}>
                                id: {info.elem.identifier}
                            </div>
                        )}
                        {nodeDesc && (
                            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 6, lineHeight: 1.5 }}>
                                {nodeDesc}
                            </div>
                        )}
                        {lang !== 'en' && nodeDescEn && nodeDescEn !== nodeDesc && (
                            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4, lineHeight: 1.5 }}>
                                en: {nodeDescEn}
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)', marginBottom: 4 }}>
                            {info.rule.source} <span style={{ color: 'var(--muted-foreground)' }}>{'\u2192'}</span> {info.rule.target}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                            Relation: <strong>{edgeRelationName}</strong>
                        </div>
                        {lang !== 'en' && edgeRelationNameEn && edgeRelationNameEn !== edgeRelationName && (
                            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                                en: {edgeRelationNameEn}
                            </div>
                        )}
                        <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                            Priority {info.rule.priority}
                        </div>
                        {info.rule.identifier && (
                            <div style={{
                                fontSize: 10,
                                color: 'var(--muted-foreground)',
                                marginTop: 6,
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            }}>
                                id: {info.rule.identifier}
                            </div>
                        )}
                        {info.rule.notes && (
                            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 6, lineHeight: 1.5 }}>
                                {info.rule.notes}
                            </div>
                        )}
                        {edgeRelationDesc && (
                            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginTop: 6, lineHeight: 1.5 }}>
                                {edgeRelationDesc}
                            </div>
                        )}
                        {lang !== 'en' && edgeRelationDescEn && edgeRelationDescEn !== edgeRelationDesc && (
                            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4, lineHeight: 1.5 }}>
                                en: {edgeRelationDescEn}
                            </div>
                        )}
                    </>
                )}
            </div>
        </Panel>
    );
}

interface EdgeHoverInfo {
    x: number;
    y: number;
    rule: LayerSchemaRule;
    relation?: LayerSchemaRelation;
}

function EdgeHoverTooltip({ info, lang }: { info: EdgeHoverInfo; lang: string }) {
    const relationName = i18n(info.relation?.display_name || null, lang) || info.rule.relation;
    const relationNameEn = i18n(info.relation?.display_name || null, 'en') || info.rule.relation;
    const relationDesc = i18n(info.relation?.description || null, lang);
    const layer = info.relation?.kernel_layer || '-';
    const layerColor = getKernelLayerColor(layer);

    return (
        <div style={{
            position: 'fixed',
            left: info.x + 12,
            top: info.y - 8,
            zIndex: 1000,
            pointerEvents: 'none',
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 8,
            padding: '8px 10px',
            boxShadow: '0 4px 12px var(--shadow-lg)',
            maxWidth: 320,
            fontFamily: 'system-ui, -apple-system, sans-serif',
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--foreground)' }}>
                    {relationName}
                </span>
                <span style={{
                    fontSize: 9,
                    fontWeight: 700,
                    borderRadius: 4,
                    padding: '1px 5px',
                    background: `${layerColor}1a`,
                    color: layerColor,
                    border: `1px solid ${layerColor}40`,
                }}>
                    {layer}
                </span>
            </div>
            {lang !== 'en' && relationNameEn && relationNameEn !== relationName && (
                <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                    en: {relationNameEn}
                </div>
            )}
            <div style={{ fontSize: 10, color: 'var(--foreground)', marginBottom: 2 }}>
                {info.rule.source} {'\u2192'} {info.rule.target}
            </div>
            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginBottom: 2 }}>
                priority {info.rule.priority}
                {info.relation?.kernel_relation ? ` · kernel=${info.relation.kernel_relation}` : ''}
                {info.relation?.direction ? ` · dir=${compactDirection(info.relation.direction)}` : ''}
            </div>
            {relationDesc && (
                <div style={{ fontSize: 10, color: 'var(--muted-foreground)', lineHeight: 1.4 }}>
                    {relationDesc}
                </div>
            )}
        </div>
    );
}

interface LayerProjectionItem {
    label: string;
    meta?: string;
}

function EdgeLegend({ lang }: { lang: string }) {
    const l2Color = getKernelLayerColor('L2');
    const l3Color = getKernelLayerColor('L3');
    return (
        <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 4 }}>
                {lang === 'ko' ? '엣지 범례' : 'Edge Legend'}
            </div>
            <LegendLine color={l2Color} label={lang === 'ko' ? 'L2 구조 관계' : 'L2 structural'} />
            <LegendLine color={l3Color} dash label={lang === 'ko' ? 'L3 동작 관계' : 'L3 behavioral'} />
            <LegendLine color="var(--muted-foreground)" label={lang === 'ko' ? '기본 관계' : 'default relation'} />
            <div style={{ marginTop: 4 }}>
                <MarkerLegendItem symbol="&#9670;" label="composition" />
                <MarkerLegendItem symbol="&#9654;" label="directed" />
            </div>
            <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--accent)', fontSize: 10, color: 'var(--muted-foreground)' }}>
                chip = Lx · P{lang === 'ko' ? '우선순위' : 'priority'} · type
            </div>
        </div>
    );
}

function LegendLine({
    color,
    label,
    dash = false,
}: {
    color: string;
    label: string;
    dash?: boolean;
}) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
            <svg width={26} height={8}>
                <line
                    x1={0}
                    y1={4}
                    x2={26}
                    y2={4}
                    stroke={color}
                    strokeWidth={2}
                    strokeDasharray={dash ? '4 4' : undefined}
                />
            </svg>
            <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>{label}</span>
        </div>
    );
}

function MarkerLegendItem({ symbol, label }: { symbol: string; label: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <span style={{ fontSize: 12, width: 26, textAlign: 'center', lineHeight: 1 }}>{symbol}</span>
            <span style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>{label}</span>
        </div>
    );
}

function LayerSpecLine({
    title,
    role,
    count,
    items,
}: {
    title: string;
    role: string;
    count: number;
    items: LayerProjectionItem[];
}) {
    return (
        <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--foreground)' }}>
                {title} <span style={{ color: 'var(--muted-foreground)', fontWeight: 500 }}>({count})</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{role}</div>
            {items.length === 0 ? (
                <div style={{ fontSize: 11, color: 'var(--foreground)' }}>-</div>
            ) : (
                <div style={{ display: 'grid', gap: 2, marginTop: 2 }}>
                    {items.map((item) => (
                        <div key={`${item.label}-${item.meta || ''}`} style={{ fontSize: 11, color: 'var(--foreground)', lineHeight: 1.4 }}>
                            {item.label}
                            {item.meta && (
                                <span style={{
                                    color: 'var(--muted-foreground)',
                                    marginLeft: 6,
                                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                    fontSize: 10,
                                }}>
                                    ({item.meta})
                                </span>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function M2LogicProjection({
    lang,
    viewMode,
    edgeMode,
    relationFilter,
    crossLayerOnly,
    showEdgeLabels,
    compactNodes,
    hasBlueprint,
    projection,
    renderedStats,
}: {
    lang: string;
    viewMode: 'elements' | 'blueprint';
    edgeMode: 'summary' | 'rules';
    relationFilter: string;
    crossLayerOnly: boolean;
    showEdgeLabels: boolean;
    compactNodes: boolean;
    hasBlueprint: boolean;
    projection: M2RuleProjectionStats | null;
    renderedStats: { nodes: number; edges: number; rules: number } | null;
}) {
    const sourceLine = hasBlueprint
        ? `source mode = ${projection?.sourceMode || viewMode} (requested=${viewMode})`
        : `source mode = elements (requested=${viewMode}, blueprint=unavailable)`;
    return (
        <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase', marginBottom: 4 }}>
                {lang === 'ko' ? 'M2 로직 투영' : 'M2 Logic Projection'}
            </div>
            <div style={logicLineStyle}>{sourceLine}</div>
            <div style={logicLineStyle}>
                {`controls: edgeMode=${edgeMode} · relationFilter=${relationFilter} · crossLayerOnly=${crossLayerOnly} · labels=${showEdgeLabels} · compactNodes=${compactNodes}`}
            </div>
            <div style={logicLineStyle}>rules edge id = e-blueprint-{'{idx}'}-{'{source_category}'}-{'{target_category}'}-{'{relation}'}</div>
            <div style={logicLineStyle}>summary edge id = e-blueprint-summary-{'{relation}'}-{'{source_category}'}-{'{target_category}'}</div>
            <div style={logicLineStyle}>{'summary selector = max(priority), tie -> lexical(source->target)'}</div>
            <div style={logicLineStyle}>{'edge style key = kernel_relation -> RELATION_STYLES'}</div>
            <div style={logicLineStyle}>edge color/width = kernel_layer(L2/L3) palette + rule priority</div>
            <div style={logicLineStyle}>summary coverage = strongest edge + source/target category coverage per relation</div>
            <div style={logicLineStyle}>edge detail chip = kernel_relation · direction · rule_count</div>
            {projection && (
                <>
                    <div style={logicLineStyle}>
                        {`pipeline: total=${projection.totalRules} -> valid=${projection.afterValidityFilter} -> relation=${projection.afterRelationFilter} -> structural=${projection.afterStructuralFilter} -> crossLayer=${projection.afterCrossLayerFilter}`}
                    </div>
                    <div style={logicLineStyle}>
                        {`output: relationGroups=${projection.summaryGroups} -> renderedEdges=${projection.outputEdges}`}
                    </div>
                </>
            )}
            {renderedStats && (
                <div style={logicLineStyle}>
                    {`reactflow: nodes=${renderedStats.nodes} · edges=${renderedStats.edges} · ruleCount(api)=${renderedStats.rules}`}
                </div>
            )}
            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4 }}>
                {lang === 'ko'
                    ? `현재 edge mode = ${edgeMode}`
                    : `current edge mode = ${edgeMode}`}
            </div>
        </div>
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
    const [info, setInfo] = useState<InfoData | null>(null);
    const [hoverInfo, setHoverInfo] = useState<EdgeHoverInfo | null>(null);
    const [viewMode, setViewMode] = useState<'elements' | 'blueprint'>(
        DEFAULT_BLUEPRINT_LAYERS.has(layerKey) ? 'blueprint' : 'elements',
    );
    const [edgeMode, setEdgeMode] = useState<'summary' | 'rules'>('rules');
    const [relationFilter, setRelationFilter] = useState('all');
    const [crossLayerOnly, setCrossLayerOnly] = useState(false);
    const [showEdgeLabels, setShowEdgeLabels] = useState(false);
    const [compactNodes, setCompactNodes] = useState(!DEFAULT_BLUEPRINT_LAYERS.has(layerKey));

    const { data: rawSchema, isError, refetch } = useLayerSchema(layerKey, { lang });
    const relationByName = useMemo(
        () => new Map((rawSchema?.relations || []).map((rel) => [rel.name, rel] as const)),
        [rawSchema],
    );
    const relationOptions = useMemo(
        () => rawSchema ? [...rawSchema.relations.map((r) => r.name)].sort() : [],
        [rawSchema],
    );
    const hasBlueprint = !!rawSchema?.m2_blueprint;
    const kernelLayerStats = useMemo(() => {
        if (!rawSchema?.m2_blueprint) return null;
        const entityCounts = { L1: 0, L2: 0, L3: 0, L4: 0 };
        const relationCounts = { L1: 0, L2: 0, L3: 0, L4: 0 };
        for (const cat of rawSchema.m2_blueprint.categories) {
            if (cat.kernel_layer in entityCounts) {
                entityCounts[cat.kernel_layer as keyof typeof entityCounts] += cat.element_count;
            }
        }
        for (const rel of rawSchema.m2_blueprint.relations) {
            if (rel.kernel_layer in relationCounts) {
                relationCounts[rel.kernel_layer as keyof typeof relationCounts] += 1;
            }
        }
        return { entityCounts, relationCounts };
    }, [rawSchema]);
    const identifierSystem = rawSchema?.identifier_system ?? null;
    const layerSummary = useMemo(() => {
        if (!rawSchema?.m2_blueprint || !kernelLayerStats) return null;

        const roleFallback = lang === 'ko' ? '(명시되지 않음)' : '(not declared)';
        const roleByLayer = new Map(
            (rawSchema.m2_blueprint.layer_responsibilities || [])
                .map((item) => [item.layer, i18n(item.role_i18n || item.role, lang) || item.role] as const),
        );

        const categories = {
            L1: [] as LayerProjectionItem[],
            L2: [] as LayerProjectionItem[],
            L3: [] as LayerProjectionItem[],
            L4: [] as LayerProjectionItem[],
        };
        for (const category of rawSchema.m2_blueprint.categories) {
            const layer = category.kernel_layer as keyof typeof categories;
            if (!(layer in categories)) continue;
            categories[layer].push({
                label: i18n(category.display_name || null, lang) || category.name,
                meta: `id=${category.identifier} · type=${category.kernel_type} · elements=${category.element_count}`,
            });
        }
        const relations = {
            L1: [] as LayerProjectionItem[],
            L2: [] as LayerProjectionItem[],
            L3: [] as LayerProjectionItem[],
            L4: [] as LayerProjectionItem[],
        };
        for (const relation of rawSchema.m2_blueprint.relations) {
            const layer = relation.kernel_layer as keyof typeof relations;
            if (!(layer in relations)) continue;
            relations[layer].push({
                label: i18n(relation.display_name || null, lang) || relation.name,
                meta: `id=${relation.identifier} · kernel=${relation.kernel_relation} · dir=${compactDirection(relation.direction) || '-'}`,
            });
        }

        return {
            lines: [
                {
                    title: 'L1 Structure',
                    role: roleByLayer.get('L1') || roleFallback,
                    count: kernelLayerStats.entityCounts.L1,
                    items: categories.L1,
                },
                {
                    title: 'L2 Relationship',
                    role: roleByLayer.get('L2') || roleFallback,
                    count: kernelLayerStats.relationCounts.L2,
                    items: relations.L2,
                },
                {
                    title: 'L3 Behavioral',
                    role: roleByLayer.get('L3') || roleFallback,
                    count: kernelLayerStats.relationCounts.L3,
                    items: relations.L3,
                },
                {
                    title: 'L4 Concrete',
                    role: roleByLayer.get('L4') || roleFallback,
                    count: kernelLayerStats.entityCounts.L4,
                    items: categories.L4,
                },
            ],
        };
    }, [rawSchema, kernelLayerStats, lang]);

    useEffect(() => {
        setViewMode(DEFAULT_BLUEPRINT_LAYERS.has(layerKey) ? 'blueprint' : 'elements');
        setEdgeMode('rules');
        setCompactNodes(!DEFAULT_BLUEPRINT_LAYERS.has(layerKey));
    }, [layerKey]);

    const buildOptions = useMemo(
        () => ({
            viewMode,
            edgeMode,
            relationFilter,
            crossLayerOnly,
            showEdgeLabels,
            compactNodes,
        }),
        [viewMode, edgeMode, relationFilter, crossLayerOnly, showEdgeLabels, compactNodes],
    );

    const highlightEdge = useCallback((edgeId: string | null) => {
        setEdges((prev) => prev.map((edge) => {
            const nextHighlighted = edgeId !== null && edge.id === edgeId;
            const prevHighlighted = !!(edge.data as Record<string, unknown> | undefined)?.highlighted;
            if (prevHighlighted === nextHighlighted) return edge;
            return {
                ...edge,
                data: {
                    ...(edge.data || {}),
                    highlighted: nextHighlighted,
                },
            };
        }));
    }, [setEdges]);

    const { lookup, stats } = useMemo(() => {
        if (!rawSchema) return { lookup: null, stats: null };
        const { lookup: lk, nodes: n, edges: e } = buildElements(rawSchema, lang, buildOptions);
        return {
            lookup: lk,
            stats: { nodes: n.length, edges: e.length, rules: rawSchema.rule_count },
        };
    }, [rawSchema, lang, buildOptions]);
    const projectionStats = useMemo(() => {
        if (!rawSchema) return null;
        return computeM2RuleProjection(rawSchema, buildOptions);
    }, [rawSchema, buildOptions]);

    // Build ReactFlow elements when API data or lang changes
    useEffect(() => {
        if (!rawSchema) return;
        const { nodes: n, edges: e } = buildElements(rawSchema, lang, buildOptions);
        setNodes(n);
        setEdges(e);
        setHoverInfo(null);
        window.requestAnimationFrame(() => fitView());
    }, [rawSchema, lang, buildOptions, setNodes, setEdges, fitView]);

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
        setHoverInfo(null);
        highlightEdge(null);
        if (!lookup) return;
        const elem = lookup.byName.get(node.id);
        if (elem) setInfo({ kind: 'node', elem });
    }, [lookup, highlightEdge]);

    const onEdgeClick = useCallback((_: React.MouseEvent, edge: Edge) => {
        highlightEdge(edge.id);
        if (!lookup) return;
        const rule = lookup.ruleByIdx.get(edge.id);
        if (rule) setInfo({ kind: 'edge', rule, relation: relationByName.get(rule.relation) });
    }, [lookup, relationByName, highlightEdge]);

    const onEdgeMouseEnter: EdgeMouseHandler = useCallback((event: React.MouseEvent, edge: Edge) => {
        highlightEdge(edge.id);
        if (!lookup) return;
        const rule = lookup.ruleByIdx.get(edge.id);
        if (!rule) return;
        setHoverInfo({
            x: event.clientX,
            y: event.clientY,
            rule,
            relation: relationByName.get(rule.relation),
        });
    }, [lookup, relationByName, highlightEdge]);

    const onEdgeMouseLeave: EdgeMouseHandler = useCallback(() => {
        setHoverInfo(null);
        highlightEdge(null);
    }, [highlightEdge]);

    const onPaneClick = useCallback(() => {
        setInfo(null);
        setHoverInfo(null);
        highlightEdge(null);
    }, [highlightEdge]);

    if (isError) {
        return (
            <div style={{ padding: 40, fontFamily: 'system-ui' }}>
                <div style={{
                    padding: '14px 16px', border: '1px solid var(--border)', borderRadius: 8,
                    background: 'var(--secondary)', fontSize: 12, color: 'var(--muted-foreground)',
                    display: 'flex', alignItems: 'center', gap: 12,
                }}>
                    Unable to load layer schema — API server may be unavailable.
                    <button onClick={() => refetch()} style={{
                        padding: '4px 12px', fontSize: 11, fontWeight: 600,
                        border: '1px solid var(--input)', borderRadius: 4,
                        background: 'var(--card)', color: 'var(--muted-foreground)', cursor: 'pointer',
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
                onEdgeMouseEnter={onEdgeMouseEnter}
                onEdgeMouseLeave={onEdgeMouseLeave}
                onPaneClick={onPaneClick}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                {hasBlueprint && layerSummary && (
                    <Panel position="top-left">
                        <div style={{
                            width: 380,
                            maxWidth: '48vw',
                            maxHeight: '42vh',
                            overflow: 'auto',
                            border: '1px solid var(--border)',
                            borderRadius: 8,
                            background: 'var(--card)',
                            boxShadow: `0 2px 8px var(--shadow-md)`,
                            padding: '10px 12px',
                            fontFamily: 'system-ui, -apple-system, sans-serif',
                        }}>
                            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>
                                {lang === 'ko'
                                    ? `레이어 책임 (${layerKey.toUpperCase()} · M2)`
                                    : `Layer Responsibility (${layerKey.toUpperCase()} · M2)`}
                            </div>
                            <div style={{ fontSize: 12, color: 'var(--foreground)', marginTop: 6, marginBottom: 8 }}>
                                {lang === 'ko'
                                    ? 'L1/L4는 엔티티 카테고리, L2/L3는 관계 엣지 규칙으로 동작합니다.'
                                    : 'L1/L4 work as entity categories; L2/L3 work as relation edge rules.'}
                            </div>
                            {layerSummary.lines.map((line) => (
                                <LayerSpecLine
                                    key={line.title}
                                    title={line.title}
                                    role={line.role}
                                    count={line.count}
                                    items={line.items}
                                />
                            ))}
                            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted-foreground)' }}>
                                {lang === 'ko' ? '룰 총량' : 'Rules total'}: <strong style={{ color: 'var(--foreground)' }}>{stats?.rules ?? rawSchema.rule_count}</strong>
                            </div>
                            {identifierSystem && (
                                <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)', textTransform: 'uppercase' }}>
                                        {lang === 'ko' ? '식별 체계 (Layer Native)' : 'Identifier System (Layer Native)'}
                                    </div>
                                    <div style={{ marginTop: 4, display: 'grid', gap: 4 }}>
                                        <div style={idRuleLabelStyle}>element</div>
                                        <div style={idRuleValueStyle}>{identifierSystem.object_identifiers.element}</div>
                                        <div style={idRuleLabelStyle}>relation</div>
                                        <div style={idRuleValueStyle}>{identifierSystem.object_identifiers.relation}</div>
                                        <div style={idRuleLabelStyle}>category</div>
                                        <div style={idRuleValueStyle}>{identifierSystem.object_identifiers.category}</div>
                                        <div style={idRuleLabelStyle}>rule</div>
                                        <div style={idRuleValueStyle}>{identifierSystem.rule_identifier.pattern}</div>
                                        <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 2 }}>
                                            hash: {identifierSystem.rule_identifier.digest_algorithm}/{identifierSystem.rule_identifier.digest_length} · input: {identifierSystem.rule_identifier.input_template}
                                        </div>
                                    </div>
                                </div>
                            )}
                            <EdgeLegend lang={lang} />
                            <M2LogicProjection
                                lang={lang}
                                viewMode={viewMode}
                                edgeMode={edgeMode}
                                relationFilter={relationFilter}
                                crossLayerOnly={crossLayerOnly}
                                showEdgeLabels={showEdgeLabels}
                                compactNodes={compactNodes}
                                hasBlueprint={hasBlueprint}
                                projection={projectionStats}
                                renderedStats={stats}
                            />
                        </div>
                    </Panel>
                )}
                <Panel position="top-right">
                    <div style={{
                        display: 'grid', gap: 8, alignItems: 'center',
                        fontFamily: 'system-ui, -apple-system, sans-serif',
                    }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            {rawSchema && (
                                <span style={{
                                    fontSize: 11, fontWeight: 600, color: 'var(--muted-foreground)',
                                    padding: '4px 8px', background: 'var(--accent)', borderRadius: 4,
                                }}>
                                    {rawSchema.profile_name} v{rawSchema.version}
                                    {stats && ` · ${stats.nodes}N / ${stats.edges}E`}
                                </span>
                            )}
                            {kernelLayerStats && (
                                <span style={{
                                    fontSize: 11, color: 'var(--muted-foreground)',
                                    padding: '4px 8px', background: 'var(--card)', borderRadius: 4,
                                    border: '1px solid var(--border)',
                                }}>
                                    L1 {kernelLayerStats.entityCounts.L1}E · L2 {kernelLayerStats.relationCounts.L2}R · L3 {kernelLayerStats.relationCounts.L3}R · L4 {kernelLayerStats.entityCounts.L4}E
                                </span>
                            )}
                            <button onClick={() => onLayout('TB')} style={layoutBtnStyle}>Vertical</button>
                            <button onClick={() => onLayout('LR')} style={layoutBtnStyle}>Horizontal</button>
                        </div>

                        <div style={{
                            display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap',
                            padding: '6px 8px', border: '1px solid var(--border)', borderRadius: 6,
                            background: 'var(--card)', boxShadow: '0 1px 2px var(--shadow-md)',
                        }}>
                            {hasBlueprint && (
                                <label style={filterLabelStyle}>
                                    View
                                    <select
                                        value={viewMode}
                                        onChange={(e) => setViewMode(e.target.value as 'elements' | 'blueprint')}
                                        style={filterSelectStyle}
                                    >
                                        <option value="elements">elements</option>
                                        <option value="blueprint">kernel-style M2</option>
                                    </select>
                                </label>
                            )}
                            <label style={filterLabelStyle}>
                                Edge mode
                                <select
                                    value={edgeMode}
                                    onChange={(e) => setEdgeMode(e.target.value as 'summary' | 'rules')}
                                    style={filterSelectStyle}
                                >
                                    <option value="summary">summary</option>
                                    <option value="rules">rules</option>
                                </select>
                            </label>

                            <label style={filterLabelStyle}>
                                Relation
                                <select
                                    value={relationFilter}
                                    onChange={(e) => setRelationFilter(e.target.value)}
                                    style={filterSelectStyle}
                                >
                                    <option value="all">all</option>
                                    {relationOptions.map((rel) => (
                                        <option key={rel} value={rel}>{rel}</option>
                                    ))}
                                </select>
                            </label>

                            <label style={toggleLabelStyle}>
                                <input
                                    type="checkbox"
                                    checked={crossLayerOnly}
                                    onChange={(e) => setCrossLayerOnly(e.target.checked)}
                                />
                                Cross-layer
                            </label>
                            <label style={toggleLabelStyle}>
                                <input
                                    type="checkbox"
                                    checked={showEdgeLabels}
                                    onChange={(e) => setShowEdgeLabels(e.target.checked)}
                                />
                                Labels
                            </label>
                            <label style={toggleLabelStyle}>
                                <input
                                    type="checkbox"
                                    checked={compactNodes}
                                    onChange={(e) => setCompactNodes(e.target.checked)}
                                />
                                Compact nodes
                            </label>
                        </div>
                    </div>
                </Panel>
                {info && <InfoPanel info={info} lang={lang} onClose={() => setInfo(null)} />}
            </ReactFlow>
            {hoverInfo && <EdgeHoverTooltip info={hoverInfo} lang={lang} />}
        </div>
    );
}

const layoutBtnStyle: React.CSSProperties = {
    padding: '4px 10px', fontSize: 11, fontWeight: 500,
    border: '1px solid var(--input)', borderRadius: 4,
    background: 'var(--card)', color: 'var(--muted-foreground)', cursor: 'pointer',
};

const filterLabelStyle: React.CSSProperties = {
    fontSize: 11,
    color: 'var(--muted-foreground)',
    display: 'flex',
    alignItems: 'center',
    gap: 6,
};

const filterSelectStyle: React.CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 4,
    background: 'var(--card)',
    color: 'var(--muted-foreground)',
    fontSize: 11,
    padding: '2px 6px',
};

const toggleLabelStyle: React.CSSProperties = {
    fontSize: 11,
    color: 'var(--muted-foreground)',
    display: 'flex',
    alignItems: 'center',
    gap: 4,
};

const idRuleLabelStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    color: 'var(--muted-foreground)',
    textTransform: 'uppercase',
};

const idRuleValueStyle: React.CSSProperties = {
    fontSize: 10,
    color: 'var(--foreground)',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
};

const logicLineStyle: React.CSSProperties = {
    fontSize: 10,
    color: 'var(--foreground)',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    lineHeight: 1.45,
    marginBottom: 2,
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
