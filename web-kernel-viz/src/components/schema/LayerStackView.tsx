import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';

import FlowGraph from '@/components/FlowGraph';
import ProfileGraph, { type ProfileFocusMode, type ProfileGraphQualitySignal, type ProfileViewMode } from '@/components/ProfileGraph';
import {
    useKernelEntities,
    useKernelRelations,
    useKernelRules,
    useLayerSchema,
    useLayerStack,
    useProfileComposedTopology,
    useProfileProjection,
} from '@/api/hooks';
import LayerSchemaView from './LayerSchemaView';
import {
    getM1DebugSnapshot,
    isM1DebugEnabled,
    m1DebugLog,
    resetM1DebugCounters,
    type M1DebugSnapshot,
} from '@/lib/m1Debug';

interface LayerStackViewProps {
    layerKey: string;
    lang: string;
}

type StackLevel = 'm2' | 'm1' | 'm0';
type M1SourceMode = 'topology' | 'projection' | 'composed';
type ProjectionLevel = 'l0' | 'l1' | 'l2' | 'l3' | 'l4';
type DomainScope = 'all' | 'owned' | 'bridge';
type M1Preset = 'overview' | 'actor-route' | 'trace';
type M1SafeCaps = {
    topology: {
        raw: number;
        summary: number;
        focus: number;
    };
    composed: {
        summary: number;
        focus: number;
    };
    projection: {
        l0: number;
        l1: number;
        l2: number;
        l3: number;
        l4: number;
    };
};

const STACK_LEVELS: { key: StackLevel; label: string; hint: string }[] = [
    { key: 'm2', label: 'M2 Schema', hint: 'metamodel + rules' },
    { key: 'm1', label: 'M1 Topology', hint: 'profile graph' },
    { key: 'm0', label: 'M0 Runtime', hint: 'snapshots + models' },
];

const M1_VIEW_MODES: { key: ProfileViewMode; label: string; hint: string }[] = [
    { key: 'summary', label: 'summary', hint: 'grouped edges (source-target-relation)' },
    { key: 'focus', label: 'focus', hint: 'intent-focused topology slice' },
    { key: 'raw', label: 'raw', hint: 'all rule edges' },
];
const M1_COMPOSED_VIEW_MODES: { key: ProfileViewMode; label: string; hint: string }[] = [
    { key: 'summary', label: 'summary', hint: 'cross-profile summary edges' },
    { key: 'focus', label: 'focus', hint: 'cross-profile focus slice' },
];
const M1_SOURCE_MODES: { key: M1SourceMode; label: string; hint: string }[] = [
    { key: 'topology', label: 'topology', hint: 'raw/summary/focus topology rendering' },
    { key: 'projection', label: 'projection', hint: 'L0~L4 abstraction projection rendering' },
    { key: 'composed', label: 'composed', hint: 'cross-profile composed topology with rule ownership' },
];
const PROJECTION_LEVEL_OPTIONS: { key: ProjectionLevel; label: string; hint: string }[] = [
    { key: 'l0', label: 'L0 panorama', hint: 'strategic panorama for cross-domain orientation' },
    { key: 'l1', label: 'L1 capability', hint: 'capability and responsibility map' },
    { key: 'l2', label: 'L2 interaction', hint: 'actor-centric valid interaction routes' },
    { key: 'l3', label: 'L3 execution', hint: 'step/action/event execution chain' },
    { key: 'l4', label: 'L4 trace', hint: 'developer-grade decision/data trace view' },
];
const DOMAIN_SCOPE_OPTIONS: { key: DomainScope; label: string }[] = [
    { key: 'owned', label: 'scope:owned' },
    { key: 'bridge', label: 'scope:bridge' },
    { key: 'all', label: 'scope:all' },
];
const EDGE_BUDGET_OPTIONS = [220, 320, 420, 620, 900, 1200, 1600] as const;
const M1_SAFE_EDGE_CAPS = {
    topology: {
        raw: 700,
        summary: 900,
        focus: 780,
    },
    composed: {
        summary: 760,
        focus: 700,
    },
    projection: {
        l0: 220,
        l1: 320,
        l2: 520,
        l3: 760,
        l4: 900,
    },
} as const;
const M1_PRESETS: { key: M1Preset; label: string; hint: string }[] = [
    { key: 'overview', label: 'overview', hint: 'surface summary for fast orientation' },
    { key: 'actor-route', label: 'actor-route', hint: 'actor-centric interaction route (projection L2)' },
    { key: 'trace', label: 'trace', hint: 'execution/data trace (projection L4)' },
];

type M1PresetConfig = {
    sourceMode: M1SourceMode;
    viewMode?: ProfileViewMode;
    projectionLevel?: ProjectionLevel;
    focusMode?: ProfileFocusMode;
    focusDepth?: number;
    domainScope: DomainScope;
    surfaceOnly: boolean;
    maxEdges: number;
};

const M1_PRESET_BASE: Record<M1Preset, M1PresetConfig> = {
    overview: {
        sourceMode: 'topology',
        viewMode: 'summary',
        focusMode: 'core',
        domainScope: 'owned',
        surfaceOnly: true,
        maxEdges: 420,
    },
    'actor-route': {
        sourceMode: 'projection',
        projectionLevel: 'l2',
        focusDepth: 3,
        domainScope: 'owned',
        surfaceOnly: true,
        maxEdges: 620,
    },
    trace: {
        sourceMode: 'projection',
        projectionLevel: 'l4',
        domainScope: 'all',
        surfaceOnly: true,
        maxEdges: 900,
    },
};

const M1_PRESET_LAYER_TUNING: Record<M1Preset, Record<string, Partial<M1PresetConfig>>> = {
    overview: {
        infra: { maxEdges: 320 },
        needs: { maxEdges: 360 },
        governance: { maxEdges: 420 },
        decision: { maxEdges: 420 },
        kernel: { maxEdges: 420 },
        flow: { maxEdges: 480 },
    },
    'actor-route': {
        infra: { focusDepth: 2, maxEdges: 420 },
        needs: { focusDepth: 3, maxEdges: 480 },
        governance: { focusDepth: 3, maxEdges: 520 },
        decision: { focusDepth: 3, maxEdges: 520 },
        kernel: { focusDepth: 4, maxEdges: 620 },
        flow: { focusDepth: 4, maxEdges: 620 },
    },
    trace: {
        infra: { maxEdges: 620, domainScope: 'all' },
        needs: { maxEdges: 700, domainScope: 'all' },
        governance: { maxEdges: 760, domainScope: 'all' },
        decision: { maxEdges: 760, domainScope: 'all' },
        kernel: { maxEdges: 900, domainScope: 'all' },
        flow: { maxEdges: 900, domainScope: 'all' },
    },
};

const PROFILE_FALLBACK_BY_LAYER: Record<string, string> = {
    kernel: 'EASystem-Kernel',
    infra: 'EASystem-Infra',
    needs: 'EASystem-Needs',
    decision: 'EASystem-Decision',
    governance: 'EASystem-Governance',
    flow: 'EASystem-Flow',
};

const M1_FOCUS_MODES: { key: ProfileFocusMode; label: string }[] = [
    { key: 'core', label: 'core' },
    { key: 'relation', label: 'relation' },
    { key: 'layer', label: 'layer' },
    { key: 'actor', label: 'actor' },
    { key: 'topic', label: 'topic' },
];

const LAYER_LABEL_BY_KEY: Record<string, string> = {
    infra: 'Infra',
    governance: 'Governance',
    decision: 'Decision',
    needs: 'Needs',
    kernel: 'Kernel',
    flow: 'Flow',
};

function focusModeLabel(mode: ProfileFocusMode, lang: string): string {
    if (lang !== 'ko') return mode;
    if (mode === 'core') return '핵심';
    if (mode === 'relation') return '관계';
    if (mode === 'layer') return '레이어';
    if (mode === 'actor') return '액터';
    return '토픽';
}

function relationBucketLabel(bucket: string, lang: string): string {
    if (lang !== 'ko') return bucket;
    if (bucket === 'structural') return '구조';
    if (bucket === 'causal') return '인과';
    if (bucket === 'operational') return '실행';
    if (bucket === 'interaction') return '상호작용';
    if (bucket === 'self_description') return '자기 설명';
    if (bucket === 'inheritance_meta') return '상속/메타';
    if (bucket === 'intent') return '의도';
    return bucket;
}

function domainScopeLabel(scope: DomainScope, lang: string): string {
    if (lang !== 'ko') return `scope:${scope}`;
    if (scope === 'owned') return '범위:소유';
    if (scope === 'bridge') return '범위:브리지';
    return '범위:전체';
}

function statusLabel(status: string, lang: string): string {
    if (lang === 'ko') {
        if (status === 'critical') return 'critical (즉시 보강)';
        if (status === 'attention') return 'attention (점검 필요)';
        return 'healthy';
    }
    return status;
}

function resolveSafeMaxEdges(
    sourceMode: M1SourceMode,
    viewMode: ProfileViewMode,
    projectionLevel: ProjectionLevel,
    caps: M1SafeCaps,
): number {
    if (sourceMode === 'projection') {
        return caps.projection[projectionLevel];
    }
    if (sourceMode === 'composed') {
        return viewMode === 'focus'
            ? caps.composed.focus
            : caps.composed.summary;
    }
    return caps.topology[viewMode];
}

function projectionDensityLabel(edgeCount: number, lang: string): string {
    if (edgeCount <= 260) return lang === 'ko' ? '가벼움' : 'light';
    if (edgeCount <= 620) return lang === 'ko' ? '적정' : 'balanced';
    return lang === 'ko' ? '고밀도' : 'dense';
}

function resolveM1PresetConfig(layerKey: string, preset: M1Preset): M1PresetConfig {
    const base = M1_PRESET_BASE[preset];
    const layerOverrides = M1_PRESET_LAYER_TUNING[preset][layerKey] || {};
    return { ...base, ...layerOverrides };
}

function m1PresetLabel(preset: M1Preset | 'custom', lang: string): string {
    if (preset === 'overview') return lang === 'ko' ? '빠른개요' : 'overview';
    if (preset === 'actor-route') return lang === 'ko' ? '액터경로' : 'actor-route';
    if (preset === 'trace') return lang === 'ko' ? '실행추적' : 'trace';
    return lang === 'ko' ? '커스텀' : 'custom';
}

function normalizePresetKey(raw: string): M1Preset | null {
    const value = raw.trim().toLowerCase().replace('_', '-');
    if (value === 'overview' || value === 'actor-route' || value === 'trace') {
        return value;
    }
    return null;
}

function presetDiffFieldLabel(field: string, lang: string): string {
    if (lang !== 'ko') return field;
    if (field === 'mode') return '모드';
    if (field === 'view') return '뷰';
    if (field === 'level') return '레벨';
    if (field === 'focus') return '포커스';
    if (field === 'depth') return '깊이';
    if (field === 'scope') return '범위';
    if (field === 'surface') return '표층';
    if (field === 'max') return '예산';
    return field;
}

function statusStyle(status: string): CSSProperties {
    if (status === 'critical') {
        return {
            border: '1px solid var(--status-error-border)',
            background: 'var(--status-error-bg)',
            color: 'var(--status-error-text)',
        };
    }
    if (status === 'attention') {
        return {
            border: '1px solid var(--status-warning-border)',
            background: 'var(--status-warning-bg)',
            color: 'var(--status-warning-text)',
        };
    }
    return {
        border: '1px solid var(--status-success-border)',
        background: 'var(--status-success-bg)',
        color: 'var(--status-success-text)',
    };
}

function recommendM1Actions(
    signal: ProfileGraphQualitySignal,
    layerKey: string,
    lang: string,
): string[] {
    const codes = new Set(signal.report.issues.map((issue) => issue.code));
    const actions: string[] = [];

    if (codes.has('api_edge_cap')) {
        actions.push(
            lang === 'ko'
                ? 'API edge cap이 걸렸습니다. M1 진단 신뢰도 확보를 위해 max_edges를 올리거나 scope 기반 조회를 사용하세요.'
                : 'API edge cap is active. Raise max_edges or use scoped topology queries for reliable M1 diagnostics.',
        );
    }
    if (codes.has('relation_variety_low')) {
        actions.push(
            lang === 'ko'
                ? '관계 표현 종류가 부족합니다. 레이어 핵심 관계를 1~2개 이상 추가해 relation 다양성을 보강하세요.'
                : 'Relation variety is low. Add 1-2 layer-native relation families to improve semantic coverage.',
        );
    }
    if (codes.has('dominant_relation_high')) {
        if (layerKey === 'needs' && signal.metrics.dominantRelation === 'contains') {
            actions.push(
                lang === 'ko'
                    ? 'needs에서 contains 비중이 높습니다. behavior→goal, execution→behavior 연결을 늘려 의미 축을 보강하세요.'
                    : 'In needs, `contains` dominates. Add behavior->goal and execution->behavior links to balance semantics.',
            );
        } else {
            actions.push(
                lang === 'ko'
                    ? '단일 relation 집중도가 높습니다. 동일 노드군을 다른 relation 타입으로 분해해 표현력을 확장하세요.'
                    : 'A single relation dominates. Split the same node groups across additional relation types.',
            );
        }
    }
    if (codes.has('cross_layer_density_high')) {
        actions.push(
            lang === 'ko'
                ? 'cross-layer 결합 비율이 높습니다. 포트/브리지 노드를 통해 레이어 경계를 명시적으로 분리하세요.'
                : 'Cross-layer density is high. Isolate boundaries with explicit port/bridge nodes.',
        );
    }
    if (codes.has('ui_edge_cap') || codes.has('layout_fallback')) {
        actions.push(
            lang === 'ko'
                ? '렌더 밀도가 높습니다. M1 summary를 기본으로 유지하고 relation/요소 단위로 scope를 좁혀 점검하세요.'
                : 'Render density is high. Keep summary as default and inspect with narrower relation/element scopes.',
        );
    }

    if (actions.length === 0) {
        actions.push(
            lang === 'ko'
                ? '즉시 보강 필요 이슈가 없습니다. 현재 가드레일 상태를 기준선으로 유지하세요.'
                : 'No immediate guardrail issue detected. Keep the current state as baseline.',
        );
    }

    return actions.slice(0, 3);
}

function qualitySignalKey(signal: ProfileGraphQualitySignal | null): string {
    if (!signal) return 'none';
    const focus = signal.focus;
    const focusSignature = focus
        ? {
            mode: focus.mode,
            relation: focus.relation,
            layer: focus.layer,
            actor: focus.actor,
            actor_depth: focus.actor_depth,
            topic: focus.topic,
            topic_depth: focus.topic_depth,
            selected_relations: focus.selected_relations || [],
            visible_relations: focus.visible_relations || [],
            hidden_relations: focus.hidden_relations || [],
            visibility_profile: focus.visibility_profile || {},
            topic_seeds: focus.topic_seeds || [],
            topic_matches: (focus.topic_matches || []).map((item) => ({
                name: item.name,
                score: item.score,
                coverage: item.coverage,
            })),
            topic_policy: focus.topic_policy || null,
            topic_filter_stats: focus.topic_filter_stats || null,
            relation_candidate_count: (focus.relation_candidates || []).length,
            layer_candidate_count: (focus.layer_candidates || []).length,
            actor_candidate_count: (focus.actor_candidates || []).length,
        }
        : null;
    return JSON.stringify({
        report: {
            layerKey: signal.report.layerKey,
            status: signal.report.status,
            issues: signal.report.issues,
            thresholds: signal.report.thresholds,
        },
        focus: focusSignature,
        metrics: signal.metrics,
    });
}

function useDebouncedText(value: string, delayMs: number): string {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = window.setTimeout(() => {
            setDebounced((prev) => (prev === value ? prev : value));
        }, delayMs);
        return () => window.clearTimeout(timer);
    }, [value, delayMs]);
    return debounced;
}

export default function LayerStackView({ layerKey, lang }: LayerStackViewProps) {
    const [level, setLevel] = useState<StackLevel>('m2');
    const [m1SourceMode, setM1SourceMode] = useState<M1SourceMode>('topology');
    const [m1ViewMode, setM1ViewMode] = useState<ProfileViewMode>(
        layerKey === 'kernel' ? 'focus' : 'summary',
    );
    const [m1ProjectionLevel, setM1ProjectionLevel] = useState<ProjectionLevel>('l1');
    const [m1DomainScope, setM1DomainScope] = useState<DomainScope>('owned');
    const [m1FocusMode, setM1FocusMode] = useState<ProfileFocusMode>('core');
    const [m1FocusRelation, setM1FocusRelation] = useState<string>('');
    const [m1FocusLayer, setM1FocusLayer] = useState<string>(LAYER_LABEL_BY_KEY[layerKey] || 'Kernel');
    const [m1FocusActor, setM1FocusActor] = useState<string>('');
    const [m1FocusTopic, setM1FocusTopic] = useState<string>(LAYER_LABEL_BY_KEY[layerKey] || 'Kernel');
    const m1FocusTopicDebounced = useDebouncedText(m1FocusTopic, 300);
    const m1FocusTopicApplied = m1FocusTopicDebounced.trim();
    const hasM1FocusTopic = m1FocusTopicApplied.length > 0;
    const [m1FocusDepth, setM1FocusDepth] = useState<number>(4);
    const [m1MaxEdges, setM1MaxEdges] = useState<number>(900);
    const [m1SafetyMode, setM1SafetyMode] = useState<boolean>(true);
    const [m1SurfaceOnly, setM1SurfaceOnly] = useState<boolean>(true);
    const [m1QualitySignal, setM1QualitySignal] = useState<ProfileGraphQualitySignal | null>(null);
    const m1QualitySignalKeyRef = useRef<string>('none');
    const [m1DebugEnabled] = useState<boolean>(() => isM1DebugEnabled());
    const [m1DebugSnapshot, setM1DebugSnapshot] = useState<M1DebugSnapshot>(() => getM1DebugSnapshot());
    const isKernel = layerKey === 'kernel';
    const m2Query = useLayerSchema(layerKey, { lang });
    const m2 = m2Query.data;
    const m1ProfileName = m2?.profile_name || PROFILE_FALLBACK_BY_LAYER[layerKey];
    const m1PolicyUi = m2?.projection_policy?.ui;
    const m1EdgeBudgetOptions = useMemo(() => {
        const rawOptions = m1PolicyUi?.edge_budget_options;
        if (!Array.isArray(rawOptions)) return [...EDGE_BUDGET_OPTIONS];
        const options = [...new Set(rawOptions
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value) && value > 0)
            .map((value) => Math.floor(value))
        )].sort((a, b) => a - b);
        return options.length > 0 ? options : [...EDGE_BUDGET_OPTIONS];
    }, [m1PolicyUi?.edge_budget_options]);
    const m1SafeCaps = useMemo<M1SafeCaps>(() => {
        const raw = m1PolicyUi?.safety_caps;
        return {
            topology: {
                raw: Number(raw?.topology?.raw) > 0 ? Number(raw?.topology?.raw) : M1_SAFE_EDGE_CAPS.topology.raw,
                summary: Number(raw?.topology?.summary) > 0 ? Number(raw?.topology?.summary) : M1_SAFE_EDGE_CAPS.topology.summary,
                focus: Number(raw?.topology?.focus) > 0 ? Number(raw?.topology?.focus) : M1_SAFE_EDGE_CAPS.topology.focus,
            },
            composed: {
                summary: Number(raw?.composed?.summary) > 0 ? Number(raw?.composed?.summary) : M1_SAFE_EDGE_CAPS.composed.summary,
                focus: Number(raw?.composed?.focus) > 0 ? Number(raw?.composed?.focus) : M1_SAFE_EDGE_CAPS.composed.focus,
            },
            projection: {
                l0: Number(raw?.projection?.l0) > 0 ? Number(raw?.projection?.l0) : M1_SAFE_EDGE_CAPS.projection.l0,
                l1: Number(raw?.projection?.l1) > 0 ? Number(raw?.projection?.l1) : M1_SAFE_EDGE_CAPS.projection.l1,
                l2: Number(raw?.projection?.l2) > 0 ? Number(raw?.projection?.l2) : M1_SAFE_EDGE_CAPS.projection.l2,
                l3: Number(raw?.projection?.l3) > 0 ? Number(raw?.projection?.l3) : M1_SAFE_EDGE_CAPS.projection.l3,
                l4: Number(raw?.projection?.l4) > 0 ? Number(raw?.projection?.l4) : M1_SAFE_EDGE_CAPS.projection.l4,
            },
        };
    }, [m1PolicyUi?.safety_caps]);
    const m1PresetConfigs = useMemo<Record<M1Preset, M1PresetConfig>>(() => {
        const fallback: Record<M1Preset, M1PresetConfig> = {
            overview: resolveM1PresetConfig(layerKey, 'overview'),
            'actor-route': resolveM1PresetConfig(layerKey, 'actor-route'),
            trace: resolveM1PresetConfig(layerKey, 'trace'),
        };
        const rawPresets = m1PolicyUi?.presets;
        if (!rawPresets || typeof rawPresets !== 'object') return fallback;
        const out: Record<M1Preset, M1PresetConfig> = { ...fallback };
        for (const presetKey of Object.keys(fallback) as M1Preset[]) {
            const raw = rawPresets[presetKey] || rawPresets[presetKey.replace('-', '_')];
            if (!raw || typeof raw !== 'object') continue;
            const current = { ...out[presetKey] };
            const sourceMode = typeof raw.source_mode === 'string'
                && ['topology', 'projection', 'composed'].includes(raw.source_mode)
                ? raw.source_mode as M1SourceMode
                : current.sourceMode;
            current.sourceMode = sourceMode;
            if (typeof raw.view_mode === 'string' && ['raw', 'summary', 'focus'].includes(raw.view_mode)) {
                current.viewMode = raw.view_mode as ProfileViewMode;
            }
            if (typeof raw.projection_level === 'string' && ['l0', 'l1', 'l2', 'l3', 'l4'].includes(raw.projection_level)) {
                current.projectionLevel = raw.projection_level as ProjectionLevel;
            }
            if (typeof raw.focus_mode === 'string' && ['core', 'relation', 'layer', 'actor', 'topic'].includes(raw.focus_mode)) {
                current.focusMode = raw.focus_mode as ProfileFocusMode;
            }
            if (Number(raw.focus_depth) > 0) {
                current.focusDepth = Math.floor(Number(raw.focus_depth));
            }
            if (typeof raw.domain_scope === 'string' && ['all', 'owned', 'bridge'].includes(raw.domain_scope)) {
                current.domainScope = raw.domain_scope as DomainScope;
            }
            if (typeof raw.surface_only === 'boolean') {
                current.surfaceOnly = raw.surface_only;
            }
            if (Number(raw.max_edges) > 0) {
                current.maxEdges = Math.floor(Number(raw.max_edges));
            }
            if (current.sourceMode === 'projection') {
                current.projectionLevel = current.projectionLevel || 'l1';
                current.viewMode = undefined;
                current.focusMode = undefined;
            } else {
                current.viewMode = current.viewMode || 'summary';
                current.projectionLevel = undefined;
                if (current.viewMode !== 'focus') {
                    current.focusMode = undefined;
                    current.focusDepth = undefined;
                }
            }
            out[presetKey] = current;
        }
        return out;
    }, [layerKey, m1PolicyUi?.presets]);
    const m1PresetOrder = useMemo<M1Preset[]>(() => {
        const rawOrder = m1PolicyUi?.preset_order;
        if (!Array.isArray(rawOrder)) return M1_PRESETS.map((item) => item.key);
        const order: M1Preset[] = [];
        const seen = new Set<M1Preset>();
        for (const raw of rawOrder) {
            if (typeof raw !== 'string') continue;
            const key = normalizePresetKey(raw);
            if (!key || seen.has(key)) continue;
            order.push(key);
            seen.add(key);
        }
        if (order.length === 0) {
            return M1_PRESETS.map((item) => item.key);
        }
        for (const preset of M1_PRESETS) {
            if (!seen.has(preset.key)) {
                order.push(preset.key);
            }
        }
        return order;
    }, [m1PolicyUi?.preset_order]);
    const m1SafeLimit = useMemo(() => resolveSafeMaxEdges(m1SourceMode, m1ViewMode, m1ProjectionLevel, m1SafeCaps), [
        m1ProjectionLevel,
        m1SafeCaps,
        m1SourceMode,
        m1ViewMode,
    ]);
    const m1EffectiveMaxEdges = m1SafetyMode
        ? Math.min(m1MaxEdges, m1SafeLimit)
        : m1MaxEdges;
    const m1SafetyCapped = m1EffectiveMaxEdges < m1MaxEdges;
    const m1ActivePreset = useMemo<M1Preset | 'custom'>(() => {
        const isMatch = (config: M1PresetConfig): boolean => {
            if (m1SourceMode !== config.sourceMode) return false;
            if (m1DomainScope !== config.domainScope) return false;
            if (m1SurfaceOnly !== config.surfaceOnly) return false;
            if (m1MaxEdges !== config.maxEdges) return false;
            if (config.sourceMode === 'projection') {
                if (config.projectionLevel && m1ProjectionLevel !== config.projectionLevel) return false;
                if (typeof config.focusDepth === 'number' && m1FocusDepth !== config.focusDepth) return false;
                return true;
            }
            if (config.viewMode && m1ViewMode !== config.viewMode) return false;
            if (config.viewMode === 'focus' && config.focusMode && m1FocusMode !== config.focusMode) return false;
            if (config.viewMode === 'focus' && typeof config.focusDepth === 'number' && m1FocusDepth !== config.focusDepth) return false;
            return true;
        };
        for (const preset of m1PresetOrder) {
            if (isMatch(m1PresetConfigs[preset])) {
                return preset;
            }
        }
        return 'custom';
    }, [
        m1PresetConfigs,
        m1PresetOrder,
        m1DomainScope,
        m1FocusDepth,
        m1FocusMode,
        m1MaxEdges,
        m1ProjectionLevel,
        m1SourceMode,
        m1SurfaceOnly,
        m1ViewMode,
    ]);
    const m1ActiveModeLabel = m1SourceMode === 'projection'
        ? `projection/${m1ProjectionLevel.toUpperCase()}`
        : `${m1SourceMode}/${m1ViewMode}`;
    const m1ClosestPreset = useMemo(() => {
        type DiffItem = { field: string; current: string; target: string };
        let best: { preset: M1Preset; diffs: DiffItem[]; score: number } | null = null;
        for (const preset of m1PresetOrder) {
            const config = m1PresetConfigs[preset];
            const diffs: DiffItem[] = [];
            if (m1SourceMode !== config.sourceMode) {
                diffs.push({ field: 'mode', current: m1SourceMode, target: config.sourceMode });
            }
            if (config.sourceMode === 'projection') {
                const targetLevel = config.projectionLevel || 'l1';
                if (m1ProjectionLevel !== targetLevel) {
                    diffs.push({ field: 'level', current: m1ProjectionLevel, target: targetLevel });
                }
                if (typeof config.focusDepth === 'number' && m1FocusDepth !== config.focusDepth) {
                    diffs.push({ field: 'depth', current: String(m1FocusDepth), target: String(config.focusDepth) });
                }
            } else {
                const targetView = config.viewMode || 'summary';
                if (m1ViewMode !== targetView) {
                    diffs.push({ field: 'view', current: m1ViewMode, target: targetView });
                }
                if (targetView === 'focus' && config.focusMode && m1FocusMode !== config.focusMode) {
                    diffs.push({ field: 'focus', current: m1FocusMode, target: config.focusMode });
                }
            }
            if (m1DomainScope !== config.domainScope) {
                diffs.push({ field: 'scope', current: m1DomainScope, target: config.domainScope });
            }
            if (m1SurfaceOnly !== config.surfaceOnly) {
                diffs.push({
                    field: 'surface',
                    current: m1SurfaceOnly ? 'on' : 'off',
                    target: config.surfaceOnly ? 'on' : 'off',
                });
            }
            if (m1MaxEdges !== config.maxEdges) {
                diffs.push({ field: 'max', current: String(m1MaxEdges), target: String(config.maxEdges) });
            }
            const score = diffs.length
                + (Math.abs(m1MaxEdges - config.maxEdges) / 500)
                + (typeof config.focusDepth === 'number' ? Math.abs(m1FocusDepth - config.focusDepth) / 10 : 0);
            if (!best || score < best.score) {
                best = { preset, diffs, score };
            }
        }
        return best;
    }, [
        m1PresetConfigs,
        m1PresetOrder,
        m1DomainScope,
        m1FocusDepth,
        m1FocusMode,
        m1MaxEdges,
        m1ProjectionLevel,
        m1SourceMode,
        m1SurfaceOnly,
        m1ViewMode,
    ]);
    const m1ClosestPresetText = useMemo(() => {
        if (m1ActivePreset !== 'custom' || !m1ClosestPreset) return null;
        const preview = m1ClosestPreset.diffs
            .slice(0, 3)
            .map((item) => `${presetDiffFieldLabel(item.field, lang)}:${item.current}->${item.target}`)
            .join(' · ');
        const extra = m1ClosestPreset.diffs.length > 3
            ? ` +${m1ClosestPreset.diffs.length - 3}`
            : '';
        return `${lang === 'ko' ? '근접' : 'closest'} ${m1PresetLabel(m1ClosestPreset.preset, lang)} · ${preview || '-'}${extra}`;
    }, [m1ActivePreset, m1ClosestPreset, lang]);

    const applyM1Preset = useCallback((preset: M1Preset) => {
        const config = m1PresetConfigs[preset];
        setLevel('m1');
        setM1SourceMode(config.sourceMode);
        setM1DomainScope(config.domainScope);
        setM1SurfaceOnly(config.surfaceOnly);
        setM1MaxEdges(config.maxEdges);
        if (config.viewMode) setM1ViewMode(config.viewMode);
        if (config.focusMode) setM1FocusMode(config.focusMode);
        if (config.projectionLevel) setM1ProjectionLevel(config.projectionLevel);
        if (typeof config.focusDepth === 'number') setM1FocusDepth(config.focusDepth);
    }, [m1PresetConfigs]);

    const stackQuery = useLayerStack(layerKey, { lang, m0_limit: 40, enabled: level === 'm0' });
    const stack = stackQuery.data;
    const composedFocusMode: ProfileFocusMode | undefined = m1ViewMode === 'focus'
        ? (
            (m1FocusMode === 'relation' && !m1FocusRelation)
            || (m1FocusMode === 'layer' && !m1FocusLayer)
            || (m1FocusMode === 'topic' && !hasM1FocusTopic)
                ? 'core'
                : m1FocusMode
        )
        : undefined;
    const projectionQuery = useProfileProjection(m1ProfileName || '', {
        level: m1ProjectionLevel,
        lang,
        domain_scope: m1DomainScope,
        actor: m1ProjectionLevel === 'l2' ? (m1FocusActor || undefined) : undefined,
        depth: m1ProjectionLevel === 'l2' ? m1FocusDepth : undefined,
        max_edges: m1EffectiveMaxEdges,
        enabled: level === 'm1' && m1SourceMode === 'projection' && !!m1ProfileName,
    });
    const composedQuery = useProfileComposedTopology(m1ProfileName || '', {
        lang,
        domain_scope: m1DomainScope,
        max_edges: m1EffectiveMaxEdges,
        surface_only: m1SurfaceOnly,
        focus: composedFocusMode,
        focus_relation: composedFocusMode === 'relation' && m1FocusRelation
            ? m1FocusRelation
            : undefined,
        focus_layer: composedFocusMode === 'layer'
            ? m1FocusLayer
            : undefined,
        focus_actor: composedFocusMode === 'actor' && m1FocusActor
            ? m1FocusActor
            : undefined,
        focus_topic: composedFocusMode === 'topic' && hasM1FocusTopic
            ? m1FocusTopicApplied
            : undefined,
        focus_depth: composedFocusMode === 'actor' || composedFocusMode === 'topic'
            ? m1FocusDepth
            : undefined,
        enabled: level === 'm1' && m1SourceMode === 'composed' && !!m1ProfileName,
    });
    const projectionModeActive = level === 'm1' && m1SourceMode === 'projection';
    const composedModeActive = level === 'm1' && m1SourceMode === 'composed';
    const projectionData = projectionModeActive ? projectionQuery.data : undefined;
    const composedData = composedModeActive ? composedQuery.data : undefined;
    const projectionViewMode: ProfileViewMode = (projectionData?.view_mode as ProfileViewMode) || 'summary';
    const composedViewMode: ProfileViewMode = (composedData?.view_mode as ProfileViewMode) || 'summary';
    const kernelEntitiesQuery = useKernelEntities({ lang, enabled: isKernel });
    const kernelRelationsQuery = useKernelRelations({ lang, enabled: isKernel });
    const kernelRulesQuery = useKernelRules({ enabled: isKernel });

    const statsText = useMemo(() => {
        if (!m2) return null;
        const m1Label = m1SourceMode === 'projection'
            ? `projection:${m1ProjectionLevel.toUpperCase()}/${m1DomainScope}`
            : m1SourceMode === 'composed'
                ? `composed:${m1ViewMode}/${m1DomainScope}${m1SurfaceOnly ? '/surface' : '/full'}`
            : `${m1ViewMode}/${m1DomainScope}${m1SurfaceOnly ? '/surface' : '/full'}`;
        let m2Label: string;
        if (isKernel) {
            const ent = kernelEntitiesQuery.data?.total;
            const rel = kernelRelationsQuery.data?.total;
            const rule = kernelRulesQuery.data?.total;
            m2Label = ent != null && rel != null && rule != null
                ? `${ent}E/${rel}Rel/${rule}R`
                : 'canonical...';
        } else {
            m2Label = `${m2.element_count}E/${m2.relation_count}Rel/${m2.rule_count}R`;
        }
        const m0Label = stack
            ? `${stack.m0.snapshot_total}S/${stack.m0.model_candidate_total}M`
            : 'on-demand';
        const maxLabel = m1SafetyCapped
            ? `${m1EffectiveMaxEdges}(req:${m1MaxEdges})`
            : String(m1EffectiveMaxEdges);
        return `${m2.profile_name} v${m2.version} · M2 ${m2Label} · M1 ${m1Label} · max_edges ${maxLabel} · M0 ${m0Label}`;
    }, [
        m2,
        stack,
        isKernel,
        m1SourceMode,
        m1ProjectionLevel,
        m1ViewMode,
        m1DomainScope,
        m1SurfaceOnly,
        m1SafetyCapped,
        m1EffectiveMaxEdges,
        m1MaxEdges,
        kernelEntitiesQuery.data,
        kernelRelationsQuery.data,
        kernelRulesQuery.data,
    ]);
    const baseFocusRelationOptions = useMemo(() => {
        const names = new Set((m2?.relations || []).map((rel) => rel.name));
        return [...names].sort((a, b) => a.localeCompare(b));
    }, [m2?.relations]);
    const baseFocusLayerOptions = useMemo(() => {
        const names = new Set<string>();
        for (const group of m2?.elements_by_layer || []) {
            if (group.layer) names.add(group.layer);
        }
        if (names.size === 0) {
            ['Infra', 'Governance', 'Decision', 'Needs', 'Kernel', 'Flow'].forEach((name) => names.add(name));
        }
        return [...names].sort((a, b) => a.localeCompare(b));
    }, [m2?.elements_by_layer]);
    const baseFocusActorOptions = useMemo(() => {
        const names = new Set<string>();
        for (const group of m2?.elements_by_layer || []) {
            for (const element of group.elements) {
                const normalized = element.name.toLowerCase();
                if (
                    element.category === 'Context'
                    || normalized.includes('stakeholder')
                    || normalized.includes('actor')
                    || normalized.includes('context')
                    || normalized.includes('operator')
                    || normalized.includes('user')
                ) {
                    names.add(element.name);
                }
            }
        }
        return [...names].sort((a, b) => a.localeCompare(b));
    }, [m2?.elements_by_layer]);
    const composedFocusRelationOptions = useMemo(() => {
        const names = new Set<string>(composedData?.focus?.relation_candidates || []);
        return [...names].sort((a, b) => a.localeCompare(b));
    }, [composedData?.focus?.relation_candidates]);
    const composedFocusLayerOptions = useMemo(() => {
        const names = new Set<string>(composedData?.focus?.layer_candidates || []);
        return [...names].sort((a, b) => a.localeCompare(b));
    }, [composedData?.focus?.layer_candidates]);
    const composedFocusActorOptions = useMemo(() => {
        const names = new Set<string>(
            (composedData?.focus?.actor_candidates || []).map((candidate) => candidate.name),
        );
        return [...names].sort((a, b) => a.localeCompare(b));
    }, [composedData?.focus?.actor_candidates]);
    const focusRelationOptions = useMemo(() => (
        m1SourceMode === 'composed' && composedFocusRelationOptions.length > 0
            ? composedFocusRelationOptions
            : baseFocusRelationOptions
    ), [m1SourceMode, composedFocusRelationOptions, baseFocusRelationOptions]);
    const focusLayerOptions = useMemo(() => (
        m1SourceMode === 'composed' && composedFocusLayerOptions.length > 0
            ? composedFocusLayerOptions
            : baseFocusLayerOptions
    ), [m1SourceMode, composedFocusLayerOptions, baseFocusLayerOptions]);
    const focusActorOptions = useMemo(() => (
        m1SourceMode === 'composed' && composedFocusActorOptions.length > 0
            ? composedFocusActorOptions
            : baseFocusActorOptions
    ), [m1SourceMode, composedFocusActorOptions, baseFocusActorOptions]);
    const m1Recommendations = useMemo(() => {
        if (!m1QualitySignal) return [];
        return recommendM1Actions(m1QualitySignal, layerKey, lang);
    }, [m1QualitySignal, layerKey, lang]);
    const surfaceVisibleRelations = useMemo(() => (
        m1QualitySignal?.focus?.visible_relations || []
    ), [m1QualitySignal]);
    const surfaceHiddenRelations = useMemo(() => (
        m1QualitySignal?.focus?.hidden_relations || []
    ), [m1QualitySignal]);
    const topicFocusMeta = useMemo(() => {
        const focusMeta = m1QualitySignal?.focus;
        if (!focusMeta || focusMeta.mode !== 'topic') return null;
        return {
            topic: focusMeta.topic || '',
            depth: focusMeta.topic_depth ?? 0,
            seeds: focusMeta.topic_seeds || [],
            matches: focusMeta.topic_matches || [],
            structural: focusMeta.selected_relation_profile?.structural || [],
            intent: focusMeta.selected_relation_profile?.intent || [],
            policy: focusMeta.topic_policy || null,
            filterStats: focusMeta.topic_filter_stats || null,
        };
    }, [m1QualitySignal]);
    const focusVisibilityBuckets = useMemo(() => {
        const profile = m1QualitySignal?.focus?.visibility_profile;
        if (!profile) return [];
        const order = ['structural', 'causal', 'operational', 'interaction', 'self_description', 'inheritance_meta'];
        return order
            .map((bucket) => ({
                bucket,
                label: relationBucketLabel(bucket, lang),
                relations: profile[bucket] || [],
            }))
            .filter((item) => item.relations.length > 0);
    }, [m1QualitySignal?.focus?.visibility_profile, lang]);
    const projectionReduction = useMemo(() => {
        const meta = projectionData?.projection;
        if (!projectionModeActive || !meta) return null;
        const projectedNodes = projectionData?.node_count ?? 0;
        const projectedEdges = projectionData?.edge_count ?? 0;
        const reduction = meta.reduction;
        const sourceNodes = reduction?.nodes?.source ?? meta.source.node_count;
        const sourceEdges = reduction?.edges?.source ?? meta.source.edge_count;
        const sourceEdgesRaw = reduction?.edges?.source_raw ?? meta.source.edge_total_raw;
        const sourceEdgesBeforeCap = reduction?.edges?.before_cap ?? (projectionData?.edge_total_before_cap ?? projectedEdges);
        const nodeRatio = reduction?.nodes?.ratio ?? (sourceNodes > 0 ? projectedNodes / sourceNodes : 0);
        const edgeRatio = reduction?.edges?.ratio ?? (sourceEdges > 0 ? projectedEdges / sourceEdges : 0);
        const rawEdgeRatio = reduction?.edges?.raw_ratio ?? (sourceEdgesRaw > 0 ? projectedEdges / sourceEdgesRaw : 0);
        const relationCount = meta.filters.relations.length;
        const categoryCount = meta.filters.categories.length;
        const relationPreview = meta.filters.relations.slice(0, 8);
        const categoryPreview = meta.filters.categories.slice(0, 8);
        const stage = reduction?.stages;
        const dropReasons = reduction?.drop_reasons;
        const preserve = reduction?.preserve;
        return {
            level: meta.level,
            lens: meta.lens,
            description: meta.description,
            sourceViewMode: meta.source.view_mode,
            sourceFocus: meta.source.focus || '-',
            projectedNodes,
            projectedEdges,
            sourceNodes,
            sourceEdges,
            sourceEdgesRaw,
            sourceEdgesBeforeCap,
            nodeRatio,
            edgeRatio,
            rawEdgeRatio,
            budgetDefault: meta.budget.default_max_edges,
            budgetEffective: meta.budget.effective_max_edges,
            relationCount,
            categoryCount,
            relationPreview,
            categoryPreview,
            relationExtraCount: Math.max(0, relationCount - relationPreview.length),
            categoryExtraCount: Math.max(0, categoryCount - categoryPreview.length),
            domainScope: meta.filters.domain_scope || m1DomainScope,
            nextLevels: meta.drilldown.next_levels || [],
            seedActor: meta.seed?.actor || null,
            seedDepth: meta.seed?.depth ?? null,
            seedCandidates: meta.seed?.actor_candidates?.length ?? 0,
            stage,
            dropReasons,
            preserve,
        };
    }, [projectionModeActive, projectionData, m1DomainScope]);
    const projectionNarrative = useMemo(() => {
        if (!projectionReduction) return null;
        const drops = projectionReduction.dropReasons;
        if (!drops) {
            return lang === 'ko'
                ? '프로젝션 정책으로 탐색 밀도를 안정적으로 낮췄습니다.'
                : 'Projection policy reduced traversal density with stable filters.';
        }
        const relDrop = drops.edge_relation_filtered ?? 0;
        const scopeDrop = drops.edge_node_scope_filtered ?? 0;
        const capDrop = drops.edge_capped ?? 0;
        if (capDrop > 0) {
            return lang === 'ko'
                ? `예산 캡으로 ${capDrop}개 엣지를 추가 축약했습니다.`
                : `Budget cap removed ${capDrop} additional edges.`;
        }
        if (relDrop > 0) {
            return lang === 'ko'
                ? `관계 정책 필터로 ${relDrop}개 엣지를 제외했습니다.`
                : `Relation policy filtered out ${relDrop} edges.`;
        }
        if (scopeDrop > 0) {
            return lang === 'ko'
                ? `스코프/카테고리 정책으로 ${scopeDrop}개 엣지를 제외했습니다.`
                : `Scope/category policy filtered out ${scopeDrop} edges.`;
        }
        return lang === 'ko'
            ? '추가 드롭 없이 핵심 연결만 유지되었습니다.'
            : 'No major drops applied; core links are retained.';
    }, [projectionReduction, lang]);
    const m1DebugTopRenders = useMemo(() => (
        Object.entries(m1DebugSnapshot.renders)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
    ), [m1DebugSnapshot.renders]);
    const m1DebugTopQueries = useMemo(() => (
        Object.entries(m1DebugSnapshot.queries)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3)
    ), [m1DebugSnapshot.queries]);
    const m1DebugLastLog = m1DebugSnapshot.logs[0];

    useEffect(() => {
        if (level !== 'm1') {
            m1QualitySignalKeyRef.current = 'none';
            setM1QualitySignal(null);
        }
    }, [level]);
    useEffect(() => {
        if (!m1DebugEnabled || level !== 'm1') return;
        const timer = window.setInterval(() => {
            const next = getM1DebugSnapshot();
            setM1DebugSnapshot((prev) => {
                const sameTotals = (
                    prev.totals.renders === next.totals.renders
                    && prev.totals.queries === next.totals.queries
                    && prev.totals.logs === next.totals.logs
                );
                const prevLast = prev.logs[0];
                const nextLast = next.logs[0];
                const sameLast = (
                    prevLast?.ts === nextLast?.ts
                    && prevLast?.type === nextLast?.type
                    && prevLast?.key === nextLast?.key
                    && prevLast?.detail === nextLast?.detail
                );
                return sameTotals && sameLast ? prev : next;
            });
        }, 600);
        return () => window.clearInterval(timer);
    }, [m1DebugEnabled, level]);
    useEffect(() => {
        if (!m1DebugEnabled || level !== 'm1') return;
        m1DebugLog('m1.controls', {
            layerKey,
            sourceMode: m1SourceMode,
            viewMode: m1ViewMode,
            focusMode: m1FocusMode,
            projectionLevel: m1ProjectionLevel,
            focusRelation: m1FocusRelation || null,
            focusLayer: m1FocusLayer || null,
            focusActor: m1FocusActor || null,
            focusTopic: hasM1FocusTopic ? m1FocusTopicApplied : null,
            focusDepth: m1FocusDepth,
            domainScope: m1DomainScope,
            maxEdgesRequested: m1MaxEdges,
            maxEdgesEffective: m1EffectiveMaxEdges,
            safetyMode: m1SafetyMode,
            surfaceOnly: m1SurfaceOnly,
        });
    }, [
        m1DebugEnabled,
        level,
        layerKey,
        m1SourceMode,
        m1ViewMode,
        m1FocusMode,
        m1ProjectionLevel,
        m1FocusRelation,
        m1FocusLayer,
        m1FocusActor,
        hasM1FocusTopic,
        m1FocusTopicApplied,
        m1FocusDepth,
        m1DomainScope,
        m1MaxEdges,
        m1EffectiveMaxEdges,
        m1SafetyMode,
        m1SurfaceOnly,
    ]);

    useEffect(() => {
        setM1FocusLayer(LAYER_LABEL_BY_KEY[layerKey] || 'Kernel');
        setM1SourceMode('topology');
        setM1ViewMode(layerKey === 'kernel' ? 'focus' : 'summary');
        setM1ProjectionLevel('l1');
        setM1DomainScope('owned');
        setM1FocusMode('core');
        setM1FocusActor('');
        setM1FocusTopic(LAYER_LABEL_BY_KEY[layerKey] || 'Kernel');
        setM1FocusDepth(4);
        setM1MaxEdges(900);
        setM1SafetyMode(true);
        setM1SurfaceOnly(true);
    }, [layerKey]);

    useEffect(() => {
        if (m1FocusMode !== 'relation') return;
        if (m1FocusRelation && focusRelationOptions.includes(m1FocusRelation)) return;
        const fallback = focusRelationOptions[0] || '';
        if (fallback !== m1FocusRelation) {
            setM1FocusRelation(fallback);
        }
    }, [m1FocusMode, m1FocusRelation, focusRelationOptions]);

    useEffect(() => {
        if (m1FocusMode !== 'actor') return;
        if (m1FocusActor && focusActorOptions.includes(m1FocusActor)) return;
        const fallback = focusActorOptions[0] || '';
        if (fallback !== m1FocusActor) {
            setM1FocusActor(fallback);
        }
    }, [m1FocusMode, m1FocusActor, focusActorOptions]);

    useEffect(() => {
        if (m1SourceMode !== 'projection' || m1ProjectionLevel !== 'l2') return;
        if (m1FocusActor && focusActorOptions.includes(m1FocusActor)) return;
        const fallback = focusActorOptions[0] || '';
        if (fallback !== m1FocusActor) {
            setM1FocusActor(fallback);
        }
    }, [m1SourceMode, m1ProjectionLevel, m1FocusActor, focusActorOptions]);

    useEffect(() => {
        if (m1SourceMode !== 'composed') return;
        if (m1ViewMode !== 'raw') return;
        setM1ViewMode('summary');
    }, [m1SourceMode, m1ViewMode]);

    const handleQualitySignal = useCallback((signal: ProfileGraphQualitySignal | null) => {
        const nextKey = qualitySignalKey(signal);
        if (m1QualitySignalKeyRef.current === nextKey) {
            return;
        }
        m1QualitySignalKeyRef.current = nextKey;
        setM1QualitySignal(signal);
    }, []);

    return (
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div style={{
                padding: '10px 12px',
                borderBottom: '1px solid var(--border)',
                background: 'var(--card)',
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
                                border: `1px solid ${level === item.key ? 'var(--primary)' : 'var(--border)'}`,
                                background: level === item.key ? 'var(--muted)' : 'var(--card)',
                                color: level === item.key ? 'var(--primary)' : 'var(--muted-foreground)',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                            title={item.hint}
                        >
                            {lang === 'ko'
                                ? (item.key === 'm2'
                                    ? 'M2 스키마'
                                    : item.key === 'm1'
                                        ? 'M1 토폴로지'
                                        : 'M0 런타임')
                                : item.label}
                        </button>
                    ))}
                    {level === 'm1' && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 6 }}>
                            {M1_SOURCE_MODES.map((mode) => (
                                <button
                                    key={mode.key}
                                    onClick={() => setM1SourceMode(mode.key)}
                                    style={{
                                        padding: '4px 8px',
                                        borderRadius: 6,
                                        border: `1px solid ${m1SourceMode === mode.key ? 'var(--status-indigo-text)' : 'var(--border)'}`,
                                        background: m1SourceMode === mode.key ? 'var(--status-indigo-bg)' : 'var(--card)',
                                        color: m1SourceMode === mode.key ? 'var(--status-indigo-text)' : 'var(--muted-foreground)',
                                        fontSize: 11,
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                    }}
                                    title={mode.hint}
                                >
                                    {`M1 ${lang === 'ko'
                                        ? (mode.key === 'topology'
                                            ? '토폴로지'
                                            : mode.key === 'projection'
                                                ? '프로젝션'
                                                : '합성')
                                        : mode.label}`}
                                </button>
                            ))}
                            {m1PresetOrder.map((presetKey) => {
                                const presetMeta = M1_PRESETS.find((item) => item.key === presetKey);
                                const presetHint = presetMeta?.hint || presetKey;
                                return (
                                <button
                                    key={presetKey}
                                    onClick={() => applyM1Preset(presetKey)}
                                    style={{
                                        padding: '4px 8px',
                                        borderRadius: 999,
                                        border: '1px solid var(--status-success-border)',
                                        background: 'var(--status-success-bg)',
                                        color: 'var(--status-success-text)',
                                        fontSize: 11,
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                    }}
                                    title={presetHint}
                                >
                                    {lang === 'ko'
                                        ? (presetKey === 'overview'
                                            ? '빠른개요'
                                            : presetKey === 'actor-route'
                                                ? '액터경로'
                                                : '실행추적')
                                        : (presetMeta?.label || presetKey)}
                                </button>
                                );
                            })}
                            <select
                                value={m1DomainScope}
                                onChange={(e) => setM1DomainScope(e.target.value as DomainScope)}
                                style={focusSelectStyle}
                                title={lang === 'ko' ? '도메인 범위' : 'domain scope'}
                            >
                                {DOMAIN_SCOPE_OPTIONS.map((scope) => (
                                    <option key={scope.key} value={scope.key}>{domainScopeLabel(scope.key, lang)}</option>
                                ))}
                            </select>
                            <select
                                value={String(m1MaxEdges)}
                                onChange={(e) => setM1MaxEdges(Number(e.target.value) || 900)}
                                style={{ ...focusSelectStyle, minWidth: 112 }}
                                title={lang === 'ko' ? '탐색 예산(max_edges)' : 'query budget (max_edges)'}
                            >
                                {m1EdgeBudgetOptions.map((limit) => (
                                    <option key={limit} value={limit}>{`max:${limit}`}</option>
                                ))}
                            </select>
                            <button
                                onClick={() => setM1SafetyMode((prev) => !prev)}
                                style={{
                                    padding: '4px 8px',
                                    borderRadius: 6,
                                    border: `1px solid ${m1SafetyMode ? 'var(--status-success-text)' : 'var(--border)'}`,
                                    background: m1SafetyMode ? 'var(--status-success-bg)' : 'var(--card)',
                                    color: m1SafetyMode ? 'var(--status-success-text)' : 'var(--muted-foreground)',
                                    fontSize: 11,
                                    fontWeight: 700,
                                    cursor: 'pointer',
                                }}
                                title={lang === 'ko' ? '안정화 모드: 모드별 권장 상한 자동 적용' : 'stability mode: auto cap by mode'}
                            >
                                {lang === 'ko'
                                    ? (m1SafetyMode ? '안정화 ON' : '안정화 OFF')
                                    : (m1SafetyMode ? 'safety on' : 'safety off')}
                            </button>
                            {m1SafetyCapped && (
                                <span style={pillStyle}>
                                    {`${lang === 'ko' ? '적용 상한' : 'effective cap'}:${m1EffectiveMaxEdges}/${m1MaxEdges}`}
                                </span>
                            )}
                            <span style={pillStyle}>
                                {`${lang === 'ko' ? '프리셋' : 'preset'}:${m1PresetLabel(m1ActivePreset, lang)}`}
                            </span>
                            <span style={pillStyle}>
                                {`${lang === 'ko' ? '파라미터' : 'params'}:${m1ActiveModeLabel} · ${domainScopeLabel(m1DomainScope, lang)} · max ${m1EffectiveMaxEdges}${m1SafetyCapped ? `/${m1MaxEdges}` : ''}${m1SourceMode === 'projection' && m1ProjectionLevel === 'l2' ? ` · depth ${m1FocusDepth}` : ''}`}
                            </span>
                            {m1ClosestPresetText && (
                                <span style={{ ...pillStyle, maxWidth: 460, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={m1ClosestPresetText}>
                                    {m1ClosestPresetText}
                                </span>
                            )}
                            {(m1SourceMode === 'topology' || m1SourceMode === 'composed') && (
                                <button
                                    onClick={() => setM1SurfaceOnly((prev) => !prev)}
                                    style={{
                                        padding: '4px 8px',
                                        borderRadius: 6,
                                        border: `1px solid ${m1SurfaceOnly ? 'var(--status-indigo-text)' : 'var(--border)'}`,
                                        background: m1SurfaceOnly ? 'var(--status-indigo-bg)' : 'var(--card)',
                                        color: m1SurfaceOnly ? 'var(--status-indigo-text)' : 'var(--muted-foreground)',
                                        fontSize: 11,
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                    }}
                                    title={lang === 'ko' ? '표층 관계만 노출(상속/메타 숨김)' : 'surface relations only (hide inheritance/meta)'}
                                >
                                    {lang === 'ko'
                                        ? (m1SurfaceOnly ? '표층만' : '전체관계')
                                        : (m1SurfaceOnly ? 'surface-only' : 'full-relations')}
                                </button>
                            )}
                            {(m1SourceMode === 'topology' || m1SourceMode === 'composed') && (
                                <>
                                    {(m1SourceMode === 'composed' ? M1_COMPOSED_VIEW_MODES : M1_VIEW_MODES).map((mode) => (
                                        <button
                                            key={mode.key}
                                            onClick={() => setM1ViewMode(mode.key)}
                                            style={{
                                                padding: '4px 8px',
                                                borderRadius: 6,
                                                border: `1px solid ${m1ViewMode === mode.key ? 'var(--status-indigo-text)' : 'var(--border)'}`,
                                                background: m1ViewMode === mode.key ? 'var(--status-indigo-bg)' : 'var(--card)',
                                                color: m1ViewMode === mode.key ? 'var(--status-indigo-text)' : 'var(--muted-foreground)',
                                                fontSize: 11,
                                                fontWeight: 700,
                                                cursor: 'pointer',
                                            }}
                                            title={mode.hint}
                                        >
                                            {lang === 'ko'
                                                ? (mode.key === 'summary'
                                                    ? '요약'
                                                    : mode.key === 'focus'
                                                        ? '포커스'
                                                        : '원본')
                                                : mode.label}
                                        </button>
                                    ))}
                                    {m1ViewMode === 'focus' && (
                                        <>
                                            <select
                                                value={m1FocusMode}
                                                onChange={(e) => setM1FocusMode(e.target.value as ProfileFocusMode)}
                                                style={focusSelectStyle}
                                                title={lang === 'ko' ? 'focus 기준' : 'focus strategy'}
                                            >
                                                {M1_FOCUS_MODES.map((mode) => (
                                                    <option key={mode.key} value={mode.key}>{`focus:${focusModeLabel(mode.key, lang)}`}</option>
                                                ))}
                                            </select>
                                            {m1FocusMode === 'relation' && (
                                                <select
                                                    value={m1FocusRelation}
                                                    onChange={(e) => setM1FocusRelation(e.target.value)}
                                                    style={focusSelectStyle}
                                                    title={lang === 'ko' ? 'focus relation' : 'focus relation'}
                                                >
                                                    {focusRelationOptions.length === 0
                                                        ? <option value="">{lang === 'ko' ? 'relation 없음' : 'no relations'}</option>
                                                        : focusRelationOptions.map((name) => (
                                                            <option key={name} value={name}>{name}</option>
                                                        ))
                                                    }
                                                </select>
                                            )}
                                            {m1FocusMode === 'layer' && (
                                                <select
                                                    value={m1FocusLayer}
                                                    onChange={(e) => setM1FocusLayer(e.target.value)}
                                                    style={focusSelectStyle}
                                                    title={lang === 'ko' ? 'focus layer' : 'focus layer'}
                                                >
                                                    {focusLayerOptions.map((name) => (
                                                        <option key={name} value={name}>{name}</option>
                                                    ))}
                                                </select>
                                            )}
                                            {m1FocusMode === 'actor' && (
                                                <>
                                                    <select
                                                        value={m1FocusActor}
                                                        onChange={(e) => setM1FocusActor(e.target.value)}
                                                        style={focusSelectStyle}
                                                        title={lang === 'ko' ? 'focus actor' : 'focus actor'}
                                                    >
                                                        {focusActorOptions.length === 0
                                                            ? <option value="">{lang === 'ko' ? 'actor 없음' : 'no actors'}</option>
                                                            : focusActorOptions.map((name) => (
                                                                <option key={name} value={name}>{name}</option>
                                                            ))
                                                        }
                                                    </select>
                                                    <select
                                                        value={String(m1FocusDepth)}
                                                        onChange={(e) => setM1FocusDepth(Number(e.target.value) || 4)}
                                                        style={{ ...focusSelectStyle, minWidth: 84 }}
                                                        title={lang === 'ko' ? 'focus depth' : 'focus depth'}
                                                    >
                                                        {[2, 3, 4, 5, 6].map((depth) => (
                                                            <option key={depth} value={depth}>{`depth:${depth}`}</option>
                                                        ))}
                                                    </select>
                                                </>
                                            )}
                                            {m1FocusMode === 'topic' && (
                                                <>
                                                    <input
                                                        value={m1FocusTopic}
                                                        onChange={(e) => setM1FocusTopic(e.target.value)}
                                                        style={{ ...focusSelectStyle, minWidth: 180 }}
                                                        placeholder={lang === 'ko' ? '주제 검색어' : 'topic query'}
                                                        title={lang === 'ko' ? 'focus topic' : 'focus topic'}
                                                    />
                                                    <select
                                                        value={String(m1FocusDepth)}
                                                        onChange={(e) => setM1FocusDepth(Number(e.target.value) || 2)}
                                                        style={{ ...focusSelectStyle, minWidth: 84 }}
                                                        title={lang === 'ko' ? 'topic depth' : 'topic depth'}
                                                    >
                                                        {[1, 2, 3, 4, 5, 6].map((depth) => (
                                                            <option key={depth} value={depth}>{`depth:${depth}`}</option>
                                                        ))}
                                                    </select>
                                                </>
                                            )}
                                        </>
                                    )}
                                </>
                            )}
                            {m1SourceMode === 'projection' && (
                                <>
                                    <select
                                        value={m1ProjectionLevel}
                                        onChange={(e) => setM1ProjectionLevel(e.target.value as ProjectionLevel)}
                                        style={{ ...focusSelectStyle, minWidth: 146 }}
                                        title={lang === 'ko' ? 'projection level' : 'projection level'}
                                    >
                                        {PROJECTION_LEVEL_OPTIONS.map((option) => (
                                            <option key={option.key} value={option.key} title={option.hint}>
                                                {option.label}
                                            </option>
                                        ))}
                                    </select>
                                    {m1ProjectionLevel === 'l2' && (
                                        <>
                                            <select
                                                value={m1FocusActor}
                                                onChange={(e) => setM1FocusActor(e.target.value)}
                                                style={focusSelectStyle}
                                                title={lang === 'ko' ? 'projection actor' : 'projection actor'}
                                            >
                                                {focusActorOptions.length === 0
                                                    ? <option value="">{lang === 'ko' ? 'actor 없음' : 'no actors'}</option>
                                                    : focusActorOptions.map((name) => (
                                                        <option key={name} value={name}>{name}</option>
                                                    ))
                                                }
                                            </select>
                                            <select
                                                value={String(m1FocusDepth)}
                                                onChange={(e) => setM1FocusDepth(Number(e.target.value) || 4)}
                                                style={{ ...focusSelectStyle, minWidth: 84 }}
                                                title={lang === 'ko' ? 'projection depth' : 'projection depth'}
                                            >
                                                {[2, 3, 4, 5, 6].map((depth) => (
                                                    <option key={depth} value={depth}>{`depth:${depth}`}</option>
                                                ))}
                                            </select>
                                        </>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>

                {statsText && (
                    <span style={{
                        fontSize: 11,
                        color: 'var(--muted-foreground)',
                        background: 'var(--secondary)',
                        border: '1px solid var(--border)',
                        borderRadius: 6,
                        padding: '4px 8px',
                    }}>
                        {statsText}
                    </span>
                )}
            </div>

            {level === 'm1' && m1QualitySignal && (
                <div style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--border)',
                    background: 'var(--secondary)',
                    display: 'grid',
                    gap: 6,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{
                            ...statusStyle(m1QualitySignal.report.status),
                            borderRadius: 999,
                            padding: '2px 8px',
                            fontSize: 11,
                            fontWeight: 700,
                        }}>
                            {`M1 ${statusLabel(m1QualitySignal.report.status, lang)}`}
                        </span>
                        <span style={pillStyle}>
                            {`${lang === 'ko' ? '렌더' : 'render'} ${m1QualitySignal.metrics.renderedEdges}/${m1QualitySignal.metrics.totalEdges}`}
                        </span>
                        <span style={pillStyle}>
                            {`${lang === 'ko' ? '관계' : 'relations'} ${m1QualitySignal.metrics.relationKinds} · cross ${m1QualitySignal.metrics.crossLayerEdges}`}
                        </span>
                        <span style={pillStyle}>
                            {`${lang === 'ko' ? '예산' : 'budget'} ${m1EffectiveMaxEdges}${m1SafetyCapped ? `/${m1MaxEdges}` : ''} · ${lang === 'ko' ? '안정화' : 'safe'} ${m1SafetyMode ? 'on' : 'off'}`}
                        </span>
                        {m1QualitySignal.metrics.dominantRelation && (
                            <span style={pillStyle}>
                                {`${lang === 'ko' ? '집중' : 'dominant'} ${m1QualitySignal.metrics.dominantRelation} ${(m1QualitySignal.metrics.dominantRelationShare * 100).toFixed(1)}%`}
                            </span>
                        )}
                    </div>
                    <div style={{
                        fontSize: 11,
                        color: 'var(--muted-foreground)',
                        display: 'grid',
                        gap: 3,
                    }}>
                        {m1Recommendations.map((action, index) => (
                            <div key={`${index}-${action}`}>
                                {`${index + 1}. ${action}`}
                            </div>
                        ))}
                    </div>
                    {m1ViewMode === 'focus' && m1QualitySignal.focus && (
                        <div style={{
                            fontSize: 11,
                            color: 'var(--muted-foreground)',
                            borderTop: '1px dashed var(--border)',
                            paddingTop: 6,
                            display: 'grid',
                            gap: 4,
                        }}>
                            <div>
                                {`${lang === 'ko' ? '표층 노출 관계' : 'surface visible'}: ${surfaceVisibleRelations.join(', ') || '-'}`}
                            </div>
                            <div>
                                {`${lang === 'ko' ? '숨김 관계(meta/inheritance)' : 'hidden(meta/inheritance)'}: ${surfaceHiddenRelations.join(', ') || '-'}`}
                            </div>
                            {focusVisibilityBuckets.length > 0 && (
                                <div style={{
                                    display: 'grid',
                                    gap: 2,
                                    borderTop: '1px dotted var(--border)',
                                    paddingTop: 4,
                                }}>
                                    {focusVisibilityBuckets.map((item) => (
                                        <div key={item.bucket}>
                                            {`${lang === 'ko' ? '표현군' : 'bucket'}:${item.label} · ${item.relations.join(', ') || '-'}`}
                                        </div>
                                    ))}
                                </div>
                            )}
                            {topicFocusMeta && (
                                <>
                                    <div>
                                        {`${lang === 'ko' ? '토픽' : 'topic'}: ${topicFocusMeta.topic || '-'} · depth:${topicFocusMeta.depth} · ${lang === 'ko' ? '시드' : 'seeds'}:${topicFocusMeta.seeds.join(', ') || '-'}`}
                                    </div>
                                    <div>
                                        {`${lang === 'ko' ? '토픽 관계(구조)' : 'topic relations(structure)'}: ${topicFocusMeta.structural.join(', ') || '-'}`}
                                    </div>
                                    <div>
                                        {`${lang === 'ko' ? '토픽 관계(의도)' : 'topic relations(intent)'}: ${topicFocusMeta.intent.join(', ') || '-'}`}
                                    </div>
                                    <div>
                                        {`${lang === 'ko' ? '토픽 매치' : 'topic matches'}: ${(topicFocusMeta.matches || []).slice(0, 8).map((item) => `${item.name}(${item.score})`).join(', ') || '-'}`}
                                    </div>
                                    {topicFocusMeta.filterStats && (
                                        <div>
                                            {`${lang === 'ko' ? '필터 통계' : 'filter stats'}: in=${topicFocusMeta.filterStats.input_edges} · relation=${topicFocusMeta.filterStats.relation_candidate_edges} · structural=${topicFocusMeta.filterStats.structural_edges ?? '-'} · intent=${topicFocusMeta.filterStats.intent_edges ?? '-'} · scope=${topicFocusMeta.filterStats.scope_nodes ?? '-'}`}
                                        </div>
                                    )}
                                    <div>
                                        {`${lang === 'ko' ? '토픽 정책' : 'topic policy'}: maxNodes/step=${topicFocusMeta.policy?.max_scope_nodes_per_depth ?? '-'} · maxSeeds=${topicFocusMeta.policy?.max_seed_count ?? '-'} · maxMatches=${topicFocusMeta.policy?.max_match_count ?? '-'} · minCoverage=${topicFocusMeta.policy?.min_token_coverage ?? '-'}`}
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}
            {level === 'm1' && projectionReduction && (
                <div style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--border)',
                    background: 'var(--status-indigo-bg)',
                    display: 'grid',
                    gap: 6,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{
                            border: '1px solid var(--status-indigo-text)',
                            background: 'var(--status-indigo-bg)',
                            color: 'var(--status-indigo-text)',
                            borderRadius: 999,
                            padding: '2px 8px',
                            fontSize: 11,
                            fontWeight: 700,
                        }}>
                            {lang === 'ko' ? '프로젝션 축약 뷰' : 'projection reduction view'}
                        </span>
                        <span style={pillStyle}>{`${projectionReduction.level}/${projectionReduction.lens}`}</span>
                        <span style={pillStyle}>{`${lang === 'ko' ? 'source' : 'source'} ${projectionReduction.sourceViewMode}/${projectionReduction.sourceFocus}`}</span>
                        <span style={pillStyle}>{`${lang === 'ko' ? 'scope' : 'scope'}:${projectionReduction.domainScope}`}</span>
                        <span style={pillStyle}>{`${lang === 'ko' ? '밀도' : 'density'}:${projectionDensityLabel(projectionReduction.projectedEdges, lang)}`}</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--muted-foreground)', display: 'grid', gap: 3 }}>
                        <div>{projectionNarrative || projectionReduction.description}</div>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                            gap: 6,
                        }}>
                            <div style={projectionMetricCardStyle}>
                                <div style={projectionMetricLabelStyle}>{lang === 'ko' ? '노드 가시성' : 'node visibility'}</div>
                                <div style={projectionMetricValueStyle}>{`${projectionReduction.projectedNodes}/${projectionReduction.sourceNodes}`}</div>
                            </div>
                            <div style={projectionMetricCardStyle}>
                                <div style={projectionMetricLabelStyle}>{lang === 'ko' ? '엣지 가시성' : 'edge visibility'}</div>
                                <div style={projectionMetricValueStyle}>{`${projectionReduction.projectedEdges}/${projectionReduction.sourceEdges}`}</div>
                            </div>
                            <div style={projectionMetricCardStyle}>
                                <div style={projectionMetricLabelStyle}>{lang === 'ko' ? '원본 대비' : 'raw baseline'}</div>
                                <div style={projectionMetricValueStyle}>{`${(projectionReduction.rawEdgeRatio * 100).toFixed(1)}%`}</div>
                            </div>
                        </div>
                        <div>
                            {`${lang === 'ko' ? '노드 축약' : 'node reduction'}: ${projectionReduction.sourceNodes} -> ${projectionReduction.projectedNodes} (${(projectionReduction.nodeRatio * 100).toFixed(1)}%)`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '엣지 축약(포커스 소스 기준)' : 'edge reduction (focused source)'}: ${projectionReduction.sourceEdges} -> ${projectionReduction.projectedEdges} (${(projectionReduction.edgeRatio * 100).toFixed(1)}%)`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '엣지 축약(raw 기준)' : 'edge reduction (raw source)'}: ${projectionReduction.sourceEdgesRaw} -> ${projectionReduction.projectedEdges} (${(projectionReduction.rawEdgeRatio * 100).toFixed(1)}%)`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '예산' : 'budget'}: default ${projectionReduction.budgetDefault} -> effective ${projectionReduction.budgetEffective} · ${lang === 'ko' ? '렌더' : 'render'} ${projectionReduction.projectedEdges}`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '캡 적용 전 엣지' : 'pre-cap edges'}: ${projectionReduction.sourceEdgesBeforeCap} -> ${projectionReduction.projectedEdges}`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '관계 필터' : 'relation filters'}(${projectionReduction.relationCount}): ${projectionReduction.relationPreview.join(', ') || '-'}${projectionReduction.relationExtraCount > 0 ? ` +${projectionReduction.relationExtraCount}` : ''}`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '카테고리 필터' : 'category filters'}(${projectionReduction.categoryCount}): ${projectionReduction.categoryPreview.join(', ') || '-'}${projectionReduction.categoryExtraCount > 0 ? ` +${projectionReduction.categoryExtraCount}` : ''}`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '드릴다운' : 'drilldown'}: ${projectionReduction.nextLevels.join(' -> ') || '-'}`}
                        </div>
                        {projectionReduction.stage && (
                            <div>
                                {`${lang === 'ko' ? '스테이지' : 'stages'}: nodes ${projectionReduction.stage.node_input ?? '-'} -> ${projectionReduction.stage.node_candidates ?? '-'} -> ${projectionReduction.stage.node_connected_or_preserved ?? '-'} · edges ${projectionReduction.stage.edge_input ?? '-'} -> ${projectionReduction.stage.edge_after_node_scope ?? '-'} -> ${projectionReduction.stage.edge_after_relation ?? '-'} -> ${projectionReduction.stage.edge_after_cap ?? '-'}`}
                            </div>
                        )}
                        {projectionReduction.dropReasons && (
                            <div>
                                {`${lang === 'ko' ? '드롭 사유' : 'drop reasons'}: node(category ${projectionReduction.dropReasons.node_category_filtered ?? 0}, disconnected ${projectionReduction.dropReasons.node_disconnected ?? 0}, unnamed ${projectionReduction.dropReasons.node_without_name ?? 0}) · edge(scope ${projectionReduction.dropReasons.edge_node_scope_filtered ?? 0}, relation ${projectionReduction.dropReasons.edge_relation_filtered ?? 0}, capped ${projectionReduction.dropReasons.edge_capped ?? 0}, invalid ${projectionReduction.dropReasons.edge_invalid_endpoint ?? 0})`}
                            </div>
                        )}
                        {projectionReduction.preserve && (
                            <div>
                                {`${lang === 'ko' ? '보존 노드' : 'preserve nodes'}: requested ${projectionReduction.preserve.requested ?? 0} · matched ${projectionReduction.preserve.matched ?? 0} · retained ${projectionReduction.preserve.retained ?? 0}${projectionReduction.preserve.unmatched && projectionReduction.preserve.unmatched.length > 0 ? ` · unmatched ${projectionReduction.preserve.unmatched.join(', ')}` : ''}`}
                            </div>
                        )}
                        {projectionReduction.seedActor && (
                            <div>
                                {`${lang === 'ko' ? 'seed 액터' : 'seed actor'}: ${projectionReduction.seedActor} · depth ${projectionReduction.seedDepth ?? '-'} · ${lang === 'ko' ? '후보' : 'candidates'} ${projectionReduction.seedCandidates}`}
                            </div>
                        )}
                    </div>
                </div>
            )}
            {m1DebugEnabled && level === 'm1' && (
                <div style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--border)',
                    background: 'var(--status-info-bg)',
                    display: 'grid',
                    gap: 6,
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{
                            border: '1px solid var(--status-info-text)',
                            background: 'var(--status-info-bg)',
                            color: 'var(--status-info-text)',
                            borderRadius: 999,
                            padding: '2px 8px',
                            fontSize: 11,
                            fontWeight: 700,
                        }}>
                            {lang === 'ko' ? 'M1 디버그' : 'M1 debug'}
                        </span>
                        <span style={pillStyle}>{`renders ${m1DebugSnapshot.totals.renders}`}</span>
                        <span style={pillStyle}>{`queries ${m1DebugSnapshot.totals.queries}`}</span>
                        <span style={pillStyle}>{`logs ${m1DebugSnapshot.totals.logs}`}</span>
                        <button
                            onClick={() => {
                                resetM1DebugCounters();
                                setM1DebugSnapshot(getM1DebugSnapshot());
                            }}
                            style={{
                                padding: '2px 8px',
                                borderRadius: 999,
                                border: '1px solid var(--border)',
                                background: 'var(--card)',
                                color: 'var(--muted-foreground)',
                                fontSize: 11,
                                fontWeight: 700,
                                cursor: 'pointer',
                            }}
                        >
                            {lang === 'ko' ? '리셋' : 'reset'}
                        </button>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--muted-foreground)', display: 'grid', gap: 3 }}>
                        <div>
                            {`${lang === 'ko' ? '상위 렌더' : 'top renders'}: ${m1DebugTopRenders.map(([key, count]) => `${key}=${count}`).join(' · ') || '-'}`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '상위 쿼리' : 'top queries'}: ${m1DebugTopQueries.map(([key, count]) => `${key}=${count}`).join(' · ') || '-'}`}
                        </div>
                        <div>
                            {`${lang === 'ko' ? '최근 이벤트' : 'last event'}: ${m1DebugLastLog ? `${new Date(m1DebugLastLog.ts).toLocaleTimeString()} ${m1DebugLastLog.type}:${m1DebugLastLog.key}${m1DebugLastLog.detail ? ` (${m1DebugLastLog.detail})` : ''}` : '-'}`}
                        </div>
                    </div>
                </div>
            )}

            <div style={{ flex: 1, minHeight: 0 }}>
                {level === 'm2' && (
                    layerKey === 'kernel'
                        ? <FlowGraph lang={lang} />
                        : <LayerSchemaView layerKey={layerKey} lang={lang} />
                )}

                {level === 'm1' && (
                    !m1ProfileName ? (
                        <StateMessage
                            kind={m2Query.isLoading ? 'loading' : 'error'}
                            message={m2Query.isLoading
                                ? (lang === 'ko' ? '레이어 스키마 로딩 중...' : 'Loading layer schema...')
                                : (lang === 'ko' ? '이 레이어에 대한 프로파일 토폴로지 확인에 실패했습니다.' : 'Failed to resolve profile topology for this layer.')}
                            lang={lang}
                            onRetry={() => m2Query.refetch()}
                        />
                    ) : projectionModeActive ? (
                        projectionQuery.isLoading ? (
                            <StateMessage kind="loading" message={lang === 'ko' ? '프로젝션 뷰 로딩 중...' : 'Loading projection view...'} lang={lang} />
                        ) : projectionQuery.isError || !projectionData ? (
                            <StateMessage
                                kind="error"
                                message={lang === 'ko' ? '프로젝션 뷰 로딩에 실패했습니다.' : 'Failed to load projection view.'}
                                lang={lang}
                                onRetry={() => projectionQuery.refetch()}
                            />
                        ) : (
                            <ProfileGraph
                                profileName={m1ProfileName}
                                lang={lang}
                                viewMode={projectionViewMode}
                                surfaceOnly={false}
                                domainScope={m1DomainScope}
                                edgeRenderLimit={m1EffectiveMaxEdges}
                                topologyData={projectionData}
                                onQualitySignal={handleQualitySignal}
                            />
                        )
                    ) : composedModeActive ? (
                        composedQuery.isLoading ? (
                            <StateMessage kind="loading" message={lang === 'ko' ? '합성 M1 뷰 로딩 중...' : 'Loading composed M1 view...'} lang={lang} />
                        ) : composedQuery.isError || !composedData ? (
                            <StateMessage
                                kind="error"
                                message={lang === 'ko' ? '합성 M1 뷰 로딩에 실패했습니다.' : 'Failed to load composed M1 view.'}
                                lang={lang}
                                onRetry={() => composedQuery.refetch()}
                            />
                        ) : (
                            <ProfileGraph
                                profileName={m1ProfileName}
                                lang={lang}
                                viewMode={composedViewMode}
                                surfaceOnly={m1SurfaceOnly}
                                domainScope={m1DomainScope}
                                edgeRenderLimit={m1EffectiveMaxEdges}
                                topologyData={composedData}
                                onQualitySignal={handleQualitySignal}
                            />
                        )
                    ) : (
                            <ProfileGraph
                                profileName={m1ProfileName}
                                lang={lang}
                                viewMode={m1ViewMode}
                                surfaceOnly={m1SurfaceOnly}
                                domainScope={m1DomainScope}
                                edgeRenderLimit={m1EffectiveMaxEdges}
                                focusMode={
                                    m1ViewMode === 'focus' && (
                                        (m1FocusMode === 'relation' && !m1FocusRelation)
                                        || (m1FocusMode === 'topic' && !hasM1FocusTopic)
                                    )
                                        ? 'core'
                                        : m1FocusMode
                                }
                                focusRelation={m1ViewMode === 'focus' && m1FocusMode === 'relation' && m1FocusRelation ? m1FocusRelation : undefined}
                                focusLayer={m1ViewMode === 'focus' && m1FocusMode === 'layer' ? m1FocusLayer : undefined}
                                focusActor={m1ViewMode === 'focus' && m1FocusMode === 'actor' && m1FocusActor ? m1FocusActor : undefined}
                                focusTopic={m1ViewMode === 'focus' && m1FocusMode === 'topic' && hasM1FocusTopic ? m1FocusTopicApplied : undefined}
                                focusDepth={m1ViewMode === 'focus' && (m1FocusMode === 'actor' || m1FocusMode === 'topic') ? m1FocusDepth : undefined}
                                onQualitySignal={handleQualitySignal}
                            />
                    )
                )}

                {level === 'm0' && (
                    <LayerM0Panel
                        lang={lang}
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

function StateMessage({ kind, message, lang, onRetry }: { kind: 'loading' | 'error'; message: string; lang?: string; onRetry?: () => void }) {
    return (
        <div style={{ padding: 20, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{
                padding: '12px 14px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: kind === 'error' ? 'var(--secondary)' : 'var(--card)',
                color: 'var(--muted-foreground)',
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
                            border: '1px solid var(--input)',
                            background: 'var(--card)',
                            color: 'var(--muted-foreground)',
                            cursor: 'pointer',
                        }}
                    >
                        {lang === 'ko' ? '다시 시도' : 'Retry'}
                    </button>
                )}
            </div>
        </div>
    );
}

function LayerM0Panel({
    lang,
    isLoading,
    isError,
    onRetry,
    snapshots,
    modelCandidates,
}: {
    lang: string;
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
        return <StateMessage kind="loading" message={lang === 'ko' ? 'M0 런타임 데이터 로딩 중...' : 'Loading M0 runtime data...'} lang={lang} />;
    }
    if (isError) {
        return <StateMessage kind="error" message={lang === 'ko' ? 'M0 런타임 데이터 로딩에 실패했습니다.' : 'Failed to load M0 runtime data.'} lang={lang} onRetry={onRetry} />;
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
                <h3 style={panelTitleStyle}>{lang === 'ko' ? '모델 후보' : 'Model Candidates'}</h3>
                {modelCandidates.length === 0 ? (
                    <EmptyLabel text={lang === 'ko' ? '이 레이어와 매칭되는 모델이 없습니다.' : 'No matched models for this layer.'} />
                ) : (
                    <div style={{ display: 'grid', gap: 8 }}>
                        {modelCandidates.map((model) => (
                            <div key={model.model_name} style={rowCardStyle}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--foreground)' }}>{model.model_name}</div>
                                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                                    {`${lang === 'ko' ? '상태' : 'status'}=${model.status || '-'} · ${lang === 'ko' ? '소유자' : 'owner'}=${model.owner || '-'} · score=${model.score}`}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                                    {`${lang === 'ko' ? '매치' : 'match'}: ${model.match_rules.join(', ') || '-'}`}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </section>

            <section style={panelCardStyle}>
                <h3 style={panelTitleStyle}>{lang === 'ko' ? '레이어 스냅샷' : 'Layer Snapshots'}</h3>
                {snapshots.length === 0 ? (
                    <EmptyLabel text={lang === 'ko' ? '이 레이어에 기록된 런타임 스냅샷이 없습니다.' : 'No runtime snapshots recorded for this layer.'} />
                ) : (
                    <div style={{ display: 'grid', gap: 8 }}>
                        {snapshots.map((snapshot) => (
                            <div key={`${snapshot.layer}-${snapshot.model_id}`} style={rowCardStyle}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--foreground)' }}>{snapshot.model_id}</div>
                                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                                    {`${lang === 'ko' ? '종류' : 'kind'}=${snapshot.kind} · ${lang === 'ko' ? '업데이트' : 'updated'}=${snapshot.updated_at || '-'}`}
                                </div>
                                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                                    {`${lang === 'ko' ? '페이로드 키' : 'payload keys'}: ${snapshot.payload_keys.join(', ') || '-'}`}
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
            color: 'var(--muted-foreground)',
            border: '1px dashed var(--border)',
            borderRadius: 8,
            padding: '12px 10px',
            background: 'var(--secondary)',
        }}>
            {text}
        </div>
    );
}

const panelCardStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 12,
    background: 'var(--card)',
    boxShadow: '0 1px 2px var(--shadow-md)',
    display: 'grid',
    gap: 10,
    alignContent: 'start',
};

const panelTitleStyle: CSSProperties = {
    margin: 0,
    fontSize: 14,
    color: 'var(--foreground)',
};

const pillStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 999,
    background: 'var(--card)',
    color: 'var(--muted-foreground)',
    fontSize: 11,
    padding: '2px 8px',
    fontWeight: 600,
};

const focusSelectStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 6,
    background: 'var(--card)',
    color: 'var(--muted-foreground)',
    fontSize: 11,
    fontWeight: 600,
    padding: '4px 8px',
    minWidth: 120,
};

const rowCardStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 8,
    background: 'var(--secondary)',
    padding: '8px 10px',
    display: 'grid',
    gap: 3,
};

const projectionMetricCardStyle: CSSProperties = {
    border: '1px solid var(--border)',
    borderRadius: 8,
    background: 'var(--card)',
    padding: '6px 8px',
    display: 'grid',
    gap: 2,
};

const projectionMetricLabelStyle: CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    textTransform: 'uppercase',
    color: 'var(--muted-foreground)',
};

const projectionMetricValueStyle: CSSProperties = {
    fontSize: 13,
    fontWeight: 700,
    color: 'var(--foreground)',
};
