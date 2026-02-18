export type M1LayerKey =
    | 'infra'
    | 'governance'
    | 'decision'
    | 'needs'
    | 'kernel'
    | 'flow'
    | 'unknown';

export type M1ViewMode = 'raw' | 'summary' | 'focus';

export interface M1QualitySnapshot {
    profileName: string;
    viewMode: M1ViewMode;
    totalEdges: number;
    renderedEdges: number;
    relationKinds: number;
    dominantRelation: string | null;
    dominantRelationShare: number;
    crossLayerEdges: number;
    intraLayerEdges: number;
    sourceTruncated: boolean;
    uiTruncated: boolean;
    fallbackLayout: boolean;
}

export interface M1QualityIssue {
    code: string;
    severity: 'warn' | 'critical';
    message: string;
}

export interface M1QualityReport {
    layerKey: M1LayerKey;
    status: 'healthy' | 'attention' | 'critical';
    issues: M1QualityIssue[];
    crossLayerShare: number;
    thresholds: {
        maxDominantRelationShare: number;
        minRelationKinds: number;
        maxCrossLayerShare: number;
    };
}

interface M1LayerGuardrail {
    maxDominantRelationShare: Record<M1ViewMode, number>;
    dominantRelationOverrides?: Partial<Record<string, Record<M1ViewMode, number>>>;
    minRelationKinds: Record<M1ViewMode, number>;
    maxCrossLayerShare: Record<M1ViewMode, number>;
}

const DEFAULT_GUARDRAIL: M1LayerGuardrail = {
    maxDominantRelationShare: { summary: 0.4, focus: 0.42, raw: 0.55 },
    minRelationKinds: { summary: 4, focus: 3, raw: 5 },
    maxCrossLayerShare: { summary: 0.55, focus: 0.6, raw: 0.7 },
};

const LAYER_GUARDRAILS: Record<Exclude<M1LayerKey, 'unknown'>, M1LayerGuardrail> = {
    infra: {
        maxDominantRelationShare: { summary: 0.4, focus: 0.44, raw: 0.52 },
        dominantRelationOverrides: {
            registers: { summary: 0.46, focus: 0.5, raw: 0.58 },
        },
        minRelationKinds: { summary: 5, focus: 4, raw: 5 },
        maxCrossLayerShare: { summary: 0.45, focus: 0.5, raw: 0.6 },
    },
    governance: {
        maxDominantRelationShare: { summary: 0.5, focus: 0.54, raw: 0.65 },
        minRelationKinds: { summary: 3, focus: 3, raw: 4 },
        maxCrossLayerShare: { summary: 0.65, focus: 0.72, raw: 0.8 },
    },
    decision: {
        maxDominantRelationShare: { summary: 0.48, focus: 0.52, raw: 0.62 },
        minRelationKinds: { summary: 4, focus: 3, raw: 5 },
        maxCrossLayerShare: { summary: 0.6, focus: 0.66, raw: 0.75 },
    },
    needs: {
        maxDominantRelationShare: { summary: 0.5, focus: 0.56, raw: 0.62 },
        dominantRelationOverrides: {
            contains: { summary: 0.62, focus: 0.68, raw: 0.74 },
        },
        minRelationKinds: { summary: 6, focus: 4, raw: 6 },
        maxCrossLayerShare: { summary: 0.4, focus: 0.46, raw: 0.55 },
    },
    kernel: {
        maxDominantRelationShare: { summary: 0.36, focus: 0.4, raw: 0.48 },
        minRelationKinds: { summary: 5, focus: 4, raw: 6 },
        maxCrossLayerShare: { summary: 0.45, focus: 0.5, raw: 0.6 },
    },
    flow: {
        maxDominantRelationShare: { summary: 0.45, focus: 0.5, raw: 0.6 },
        minRelationKinds: { summary: 4, focus: 3, raw: 5 },
        maxCrossLayerShare: { summary: 0.6, focus: 0.68, raw: 0.75 },
    },
};

export function inferM1LayerKey(profileName: string): M1LayerKey {
    const normalized = profileName.toLowerCase();
    if (normalized.includes('infra')) return 'infra';
    if (normalized.includes('governance')) return 'governance';
    if (normalized.includes('decision')) return 'decision';
    if (normalized.includes('needs')) return 'needs';
    if (normalized.includes('kernel')) return 'kernel';
    if (normalized.includes('flow')) return 'flow';
    return 'unknown';
}

function percentText(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
}

export function evaluateM1Quality(snapshot: M1QualitySnapshot): M1QualityReport {
    const layerKey = inferM1LayerKey(snapshot.profileName);
    const guardrail = layerKey === 'unknown' ? DEFAULT_GUARDRAIL : LAYER_GUARDRAILS[layerKey];
    let maxDominantRelationShare = guardrail.maxDominantRelationShare[snapshot.viewMode];
    if (snapshot.dominantRelation && guardrail.dominantRelationOverrides) {
        const override = guardrail.dominantRelationOverrides[snapshot.dominantRelation];
        if (override) {
            maxDominantRelationShare = override[snapshot.viewMode];
        }
    }
    const thresholds = {
        maxDominantRelationShare,
        minRelationKinds: guardrail.minRelationKinds[snapshot.viewMode],
        maxCrossLayerShare: guardrail.maxCrossLayerShare[snapshot.viewMode],
    };

    const issues: M1QualityIssue[] = [];

    if (snapshot.sourceTruncated) {
        issues.push({
            code: 'api_edge_cap',
            severity: 'critical',
            message: 'API edge cap applied; assessment may hide topology complexity.',
        });
    }
    if (snapshot.uiTruncated) {
        issues.push({
            code: 'ui_edge_cap',
            severity: 'warn',
            message: 'UI edge cap applied; switch to summary/focus or narrow scope for detailed inspection.',
        });
    }

    if (snapshot.totalEdges >= 40 && snapshot.relationKinds < thresholds.minRelationKinds) {
        issues.push({
            code: 'relation_variety_low',
            severity: 'warn',
            message: `Relation kinds ${snapshot.relationKinds} < ${thresholds.minRelationKinds}.`,
        });
    }

    if (snapshot.dominantRelation && snapshot.totalEdges >= 60 && snapshot.dominantRelationShare > thresholds.maxDominantRelationShare) {
        const over = snapshot.dominantRelationShare - thresholds.maxDominantRelationShare;
        issues.push({
            code: 'dominant_relation_high',
            severity: over >= 0.1 ? 'critical' : 'warn',
            message: `${snapshot.dominantRelation} ${percentText(snapshot.dominantRelationShare)} > ${percentText(thresholds.maxDominantRelationShare)}.`,
        });
    }

    const crossLayerShare = snapshot.totalEdges > 0
        ? snapshot.crossLayerEdges / snapshot.totalEdges
        : 0;
    if (snapshot.totalEdges >= 80 && crossLayerShare > thresholds.maxCrossLayerShare) {
        issues.push({
            code: 'cross_layer_density_high',
            severity: 'warn',
            message: `Cross-layer share ${percentText(crossLayerShare)} > ${percentText(thresholds.maxCrossLayerShare)}.`,
        });
    }

    if (snapshot.fallbackLayout && snapshot.renderedEdges > 900) {
        issues.push({
            code: 'layout_fallback',
            severity: 'warn',
            message: 'Grid fallback layout enabled due to high edge density.',
        });
    }

    const status: M1QualityReport['status'] = issues.some((issue) => issue.severity === 'critical')
        ? 'critical'
        : issues.length > 0
            ? 'attention'
            : 'healthy';

    return {
        layerKey,
        status,
        issues,
        crossLayerShare,
        thresholds,
    };
}
