
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './client';
import { m1DebugCountQuery } from '@/lib/m1Debug';

const TOPOLOGY_QUERY_DEFAULTS = {
    staleTime: 20_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: 1,
} as const;

// --- Profile Hooks ---

export function useProfiles() {
    return useQuery({
        queryKey: ['profiles'],
        queryFn: api.fetchProfiles,
    });
}

export function useProfileDescription(name: string, opts?: { lang?: string }) {
    return useQuery({
        queryKey: ['profile', name, 'description', opts],
        queryFn: () => api.fetchProfileDescription(name, opts),
        enabled: !!name,
    });
}

export function useProfileTopology(
    name: string,
    opts?: {
        cross_layer?: boolean;
        lang?: string;
        max_edges?: number;
        view_mode?: 'raw' | 'summary' | 'focus';
        surface_only?: boolean;
        domain_scope?: 'all' | 'owned' | 'bridge';
        focus?: 'core' | 'relation' | 'layer' | 'actor' | 'topic';
        focus_relation?: string;
        focus_layer?: string;
        focus_actor?: string;
        focus_topic?: string;
        focus_depth?: number;
        enabled?: boolean;
    },
) {
    const queryOpts = {
        cross_layer: opts?.cross_layer,
        lang: opts?.lang,
        max_edges: opts?.max_edges,
        view_mode: opts?.view_mode,
        surface_only: opts?.surface_only,
        domain_scope: opts?.domain_scope,
        focus: opts?.focus,
        focus_relation: opts?.focus_relation,
        focus_layer: opts?.focus_layer,
        focus_actor: opts?.focus_actor,
        focus_topic: opts?.focus_topic,
        focus_depth: opts?.focus_depth,
    };
    return useQuery({
        queryKey: ['profile', name, 'topology', queryOpts],
        queryFn: () => {
            m1DebugCountQuery(
                `profile.topology:${name}:${queryOpts.view_mode || 'raw'}:${queryOpts.focus || 'none'}`,
            );
            return api.fetchProfileTopology(name, queryOpts);
        },
        enabled: !!name && (opts?.enabled ?? true),
        placeholderData: (previous) => previous,
        ...TOPOLOGY_QUERY_DEFAULTS,
    });
}

export function useProfileProjection(
    name: string,
    opts?: {
        level?: 'l0' | 'l1' | 'l2' | 'l3' | 'l4';
        lens?: 'panorama' | 'overview' | 'capability' | 'interaction' | 'execution' | 'trace';
        cross_layer?: boolean;
        domain_scope?: 'all' | 'owned' | 'bridge';
        lang?: string;
        actor?: string;
        depth?: number;
        max_edges?: number;
        enabled?: boolean;
    },
) {
    const queryOpts = {
        level: opts?.level,
        lens: opts?.lens,
        cross_layer: opts?.cross_layer,
        domain_scope: opts?.domain_scope,
        lang: opts?.lang,
        actor: opts?.actor,
        depth: opts?.depth,
        max_edges: opts?.max_edges,
    };
    return useQuery({
        queryKey: ['profile', name, 'projection', queryOpts],
        queryFn: () => {
            m1DebugCountQuery(`profile.projection:${name}:${queryOpts.level || 'l1'}:${queryOpts.domain_scope || 'all'}`);
            return api.fetchProfileProjection(name, queryOpts);
        },
        enabled: !!name && (opts?.enabled ?? true),
        placeholderData: (previous) => previous,
        ...TOPOLOGY_QUERY_DEFAULTS,
    });
}

export function useProfileComposedTopology(
    name: string,
    opts?: {
        lang?: string;
        max_edges?: number;
        surface_only?: boolean;
        domain_scope?: 'all' | 'owned' | 'bridge';
        include_profiles?: string[];
        focus?: 'core' | 'relation' | 'layer' | 'actor' | 'topic';
        focus_relation?: string;
        focus_layer?: string;
        focus_actor?: string;
        focus_topic?: string;
        focus_depth?: number;
        enabled?: boolean;
    },
) {
    const queryOpts = {
        lang: opts?.lang,
        max_edges: opts?.max_edges,
        surface_only: opts?.surface_only,
        domain_scope: opts?.domain_scope,
        include_profiles: opts?.include_profiles,
        focus: opts?.focus,
        focus_relation: opts?.focus_relation,
        focus_layer: opts?.focus_layer,
        focus_actor: opts?.focus_actor,
        focus_topic: opts?.focus_topic,
        focus_depth: opts?.focus_depth,
    };
    return useQuery({
        queryKey: ['profile', name, 'composed', queryOpts],
        queryFn: () => {
            m1DebugCountQuery(
                `profile.composed:${name}:${queryOpts.domain_scope || 'all'}:${queryOpts.focus || 'none'}`,
            );
            return api.fetchProfileComposedTopology(name, queryOpts);
        },
        enabled: !!name && (opts?.enabled ?? true),
        placeholderData: (previous) => previous,
        ...TOPOLOGY_QUERY_DEFAULTS,
    });
}

export function useReachable(name: string, element: string, opts?: { max_depth?: number; relation?: string }) {
    return useQuery({
        queryKey: ['profile', name, 'reachable', element, opts],
        queryFn: () => api.fetchReachable(name, element, opts),
        enabled: !!name && !!element,
    });
}

export function usePaths(name: string, source: string, target: string, opts?: { max_depth?: number; relation?: string }) {
    return useQuery({
        queryKey: ['profile', name, 'paths', source, target, opts],
        queryFn: () => api.fetchPaths(name, source, target, opts),
        enabled: !!name && !!source && !!target,
    });
}

export function useImpact(name: string, element: string, opts?: { direction?: string; max_depth?: number }) {
    return useQuery({
        queryKey: ['profile', name, 'impact', element, opts],
        queryFn: () => api.fetchImpact(name, element, opts),
        enabled: !!name && !!element,
    });
}

// --- Kernel Schema Hooks ---

export function useKernelEntities(opts?: { lang?: string; enabled?: boolean }) {
    return useQuery({
        queryKey: ['kernel', 'entities', opts],
        queryFn: () => api.fetchKernelEntities({ lang: opts?.lang }),
        enabled: opts?.enabled ?? true,
    });
}

export function useKernelRelations(opts?: { lang?: string; enabled?: boolean }) {
    return useQuery({
        queryKey: ['kernel', 'relations', opts],
        queryFn: () => api.fetchKernelRelations({ lang: opts?.lang }),
        enabled: opts?.enabled ?? true,
    });
}

export function useKernelRules(opts?: { group?: string; relation?: string; enabled?: boolean }) {
    return useQuery({
        queryKey: ['kernel', 'rules', opts],
        queryFn: () => api.fetchKernelRules({ group: opts?.group, relation: opts?.relation }),
        enabled: opts?.enabled ?? true,
    });
}

export function useKernelRuleDetail(ruleId: string) {
    return useQuery({
        queryKey: ['kernel', 'rules', ruleId],
        queryFn: () => api.fetchKernelRuleDetail(ruleId),
        enabled: !!ruleId,
    });
}

// --- Dashboard Hooks ---

export function useGovernanceDashboard() {
    return useQuery({
        queryKey: ['governance', 'dashboard'],
        queryFn: api.fetchGovernanceDashboard,
    });
}

export function useCrossLayerSummary() {
    return useQuery({
        queryKey: ['governance', 'cross-layer-summary'],
        queryFn: api.fetchCrossLayerSummary,
    });
}

export function useLayerSchema(layerKey: string, opts?: { lang?: string }) {
    return useQuery({
        queryKey: ['layer', layerKey, 'schema', opts],
        queryFn: () => api.fetchLayerSchema(layerKey, opts),
        enabled: !!layerKey,
        ...TOPOLOGY_QUERY_DEFAULTS,
    });
}

export function useLayerStack(
    layerKey: string,
    opts?: { lang?: string; m0_limit?: number; enabled?: boolean },
) {
    return useQuery({
        queryKey: ['layer', layerKey, 'stack', opts],
        queryFn: () => {
            m1DebugCountQuery(`layer.stack:${layerKey}`);
            return api.fetchLayerStack(layerKey, { lang: opts?.lang, m0_limit: opts?.m0_limit });
        },
        enabled: !!layerKey && (opts?.enabled ?? true),
        ...TOPOLOGY_QUERY_DEFAULTS,
    });
}

// --- Business Flow Hooks ---

export function useBusinessFlowTopology(opts?: { lang?: string }) {
    return useQuery({
        queryKey: ['governance', 'business-flow', opts],
        queryFn: () => api.fetchBusinessFlowTopology(opts),
    });
}

// --- Governance Hooks ---

export function useGovernanceRules(state?: string) {
    return useQuery({
        queryKey: ['governance', 'rules', state],
        queryFn: () => api.fetchGovernanceRules(state),
        staleTime: 10_000,
    });
}

export function useApproveRule() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (ruleId: string) => api.approveRule(ruleId),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['governance', 'rules'] }),
    });
}

export function useModelState(modelName: string) {
    return useQuery({
        queryKey: ['models', modelName],
        queryFn: () => api.fetchModelState(modelName),
        enabled: !!modelName,
    });
}

export function useExecuteJudgment() {
    return useMutation({
        mutationFn: ({ source, target, relation }: { source: string; target: string; relation: string }) =>
            api.executeJudgment(source, target, relation),
    });
}

export function usePromotionProposals() {
    return useQuery({
        queryKey: ['automation', 'promotions'],
        queryFn: api.fetchPromotionProposals,
    });
}

export function useSimulatePromotion() {
    return useMutation({
        mutationFn: ({ ruleId, newConfidence }: { ruleId: string; newConfidence: string }) =>
            api.simulatePromotion(ruleId, newConfidence),
    });
}

export function useDecisionTrace(decisionId: string) {
    return useQuery({
        queryKey: ['decisions', decisionId],
        queryFn: () => api.fetchDecisionTrace(decisionId),
        enabled: !!decisionId,
    });
}

// --- Model Registration Hooks ---

export function useRegisterModel() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: Parameters<typeof api.registerModel>[0]) => api.registerModel(body),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }),
    });
}

export function useValidateModel() {
    return useMutation({
        mutationFn: (body: Parameters<typeof api.validateModel>[0]) =>
            api.validateModel(body),
    });
}

export function useActivateModel() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: Parameters<typeof api.activateModel>[0]) =>
            api.activateModel(body),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['models'] }),
    });
}

// --- Decision Explore Hook ---

export function useDecisionExplore(decisionId: string) {
    return useQuery({
        queryKey: ['decisions', decisionId, 'explore'],
        queryFn: () => api.exploreDecision(decisionId),
        enabled: !!decisionId,
    });
}

// --- Needs Hooks ---

export function useNeedsCatalogs() {
    return useQuery({
        queryKey: ['needs', 'catalogs'],
        queryFn: api.fetchNeedsCatalogs,
    });
}

export function useCreateNeedsCatalog() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ name, description }: { name: string; description?: string }) =>
            api.createNeedsCatalog(name, description),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['needs', 'catalogs'] }),
    });
}

export function useNeedsCatalogDetail(catalogId: string) {
    return useQuery({
        queryKey: ['needs', 'catalogs', catalogId],
        queryFn: () => api.fetchNeedsCatalogDetail(catalogId),
        enabled: !!catalogId,
    });
}

export function useCatalogNeeds(
    catalogId: string,
    opts?: {
        status?: string;
        priority?: string;
        stakeholder_id?: string;
        purpose?: string;
        complexity?: string;
        use_case_id?: string;
        cause_type?: string;
        kernel_change_phase?: string;
        decision_id?: string;
        decision_linked?: boolean;
    },
) {
    return useQuery({
        queryKey: ['needs', 'catalogs', catalogId, 'needs', opts],
        queryFn: () => api.fetchCatalogNeeds(catalogId, opts),
        enabled: !!catalogId,
    });
}

export function useNeedDetail(catalogId: string, needId: string) {
    return useQuery({
        queryKey: ['needs', 'catalogs', catalogId, 'needs', needId],
        queryFn: () => api.fetchNeedDetail(catalogId, needId),
        enabled: !!catalogId && !!needId,
    });
}

export function useCatalogHistory(catalogId: string) {
    return useQuery({
        queryKey: ['needs', 'catalogs', catalogId, 'history'],
        queryFn: () => api.fetchCatalogHistory(catalogId),
        enabled: !!catalogId,
    });
}

export function useExpressNeed() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ catalogId, data }: { catalogId: string; data: Parameters<typeof api.expressNeed>[1] }) =>
            api.expressNeed(catalogId, data),
        onSuccess: (_result, vars) => {
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs'] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'needs'] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'history'] });
        },
    });
}

export function useAddNeedsUseCase() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ catalogId, data }: { catalogId: string; data: Parameters<typeof api.addNeedsUseCase>[1] }) =>
            api.addNeedsUseCase(catalogId, data),
        onSuccess: (_result, vars) => {
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs'] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'history'] });
        },
    });
}

export function useReviseNeed() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ catalogId, needId, data }: {
            catalogId: string;
            needId: string;
            data: Parameters<typeof api.reviseNeed>[2];
        }) => api.reviseNeed(catalogId, needId, data),
        onSuccess: (_result, vars) => {
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs'] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'needs'] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'history'] });
        },
    });
}

export function useAddNeedProcessUnit() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ catalogId, needId, data }: {
            catalogId: string;
            needId: string;
            data: Parameters<typeof api.addNeedProcessUnit>[2];
        }) => api.addNeedProcessUnit(catalogId, needId, data),
        onSuccess: (_result, vars) => {
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'needs', vars.needId] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'history'] });
        },
    });
}

export function useInheritNeedDecisionEvidence() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ catalogId, needId, data }: {
            catalogId: string;
            needId: string;
            data: Parameters<typeof api.inheritNeedDecisionEvidence>[2];
        }) => api.inheritNeedDecisionEvidence(catalogId, needId, data),
        onSuccess: (_result, vars) => {
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'needs', vars.needId] });
            qc.invalidateQueries({ queryKey: ['needs', 'catalogs', vars.catalogId, 'history'] });
        },
    });
}

// --- Business Model Hooks ---

export function useBusinessModels() {
    return useQuery({
        queryKey: ['business'],
        queryFn: api.fetchBusinessModels,
    });
}

export function useBusinessModel(bid: string) {
    return useQuery({
        queryKey: ['business', bid],
        queryFn: () => api.fetchBusinessModel(bid),
        enabled: !!bid,
    });
}

export function useCreateBusiness() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ name, description }: { name: string; description?: string }) =>
            api.createBusiness(name, description),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['business'] }),
    });
}

export function useDeleteBusiness() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (bid: string) => api.deleteBusiness(bid),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['business'] }),
    });
}

export function useBusinessTags(bid: string) {
    return useQuery({
        queryKey: ['business', bid, 'tags'],
        queryFn: () => api.fetchBusinessTags(bid),
        enabled: !!bid,
    });
}

export function useCreateTag() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ bid, data }: { bid: string; data: Record<string, unknown> }) =>
            api.createBusinessTag(bid, data),
        onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['business', vars.bid, 'tags'] }),
    });
}

export function useUpdateTag() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ bid, tag, data }: { bid: string; tag: string; data: Record<string, unknown> }) =>
            api.updateBusinessTag(bid, tag, data),
        onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['business', vars.bid, 'tags'] }),
    });
}

export function useDeleteTag() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ bid, tag }: { bid: string; tag: string }) =>
            api.deleteBusinessTag(bid, tag),
        onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['business', vars.bid, 'tags'] }),
    });
}

export function useBusinessIndexingSpec(bid: string) {
    return useQuery({
        queryKey: ['business', bid, 'indexing-spec'],
        queryFn: () => api.fetchBusinessIndexingSpec(bid),
        enabled: !!bid,
    });
}

export function useExportBusiness(bid: string) {
    return useQuery({
        queryKey: ['business', bid, 'export'],
        queryFn: () => api.exportBusiness(bid),
        enabled: false, // manual trigger
    });
}

export function useImportBusiness() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (data: { meta: Record<string, unknown>; tags?: Record<string, unknown>[] }) =>
            api.importBusiness(data),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['business'] }),
    });
}

// --- I18n Hooks ---

export function useI18nAudit(lang: string, opts?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ['i18n', 'audit', lang],
        queryFn: () => api.fetchI18nAudit(lang),
        enabled: (opts?.enabled ?? true) && !!lang,
    });
}

export function useI18nProfileAudit(name: string, lang: string, opts?: { enabled?: boolean }) {
    return useQuery({
        queryKey: ['i18n', 'audit', 'profiles', name, lang],
        queryFn: () => api.fetchI18nProfileAudit(name, lang),
        enabled: (opts?.enabled ?? true) && !!name && !!lang,
    });
}

export function useI18nTranslations(lang: string, kind?: string) {
    return useQuery({
        queryKey: ['i18n', 'translations', lang, kind],
        queryFn: () => api.fetchI18nTranslations(lang, kind),
    });
}

export function useUpdateTranslation() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: ({ kind, name, lang, field, value }: {
            kind: string; name: string; lang: string; field: string; value: string;
        }) => api.updateI18nTranslation(kind, name, lang, field, value),
        onSuccess: () => qc.invalidateQueries({ queryKey: ['i18n'] }),
    });
}

export function useTranslationHistory(kind: string, name: string, lang: string, field: string) {
    return useQuery({
        queryKey: ['i18n', 'translations', kind, name, lang, field, 'history'],
        queryFn: () => api.fetchTranslationHistory(kind, name, lang, field),
        enabled: !!kind && !!name && !!lang && !!field,
    });
}

// --- Flow Logic Hook ---

export function useFlowLogic(anchorId: string) {
    return useQuery({
        queryKey: ['governance', 'flow', anchorId],
        queryFn: () => api.fetchFlowLogic(anchorId),
        enabled: !!anchorId,
    });
}

// --- System Self-Model Hook ---

export function useSystemSelfModel() {
    return useQuery({
        queryKey: ['system', 'self-model'],
        queryFn: api.fetchSystemSelfModel,
    });
}

// --- Profile Version Hooks ---

export function useProfileVersions(name: string, limit?: number) {
    return useQuery({
        queryKey: ['profile', name, 'versions', limit],
        queryFn: () => api.fetchProfileVersions(name, limit),
        enabled: !!name,
    });
}

export function useProfileVersionDetail(name: string, version: string) {
    return useQuery({
        queryKey: ['profile', name, 'versions', version],
        queryFn: () => api.fetchProfileVersionDetail(name, version),
        enabled: !!name && !!version,
    });
}

export function useProfileVersionDiff(name: string, a: string, b: string) {
    return useQuery({
        queryKey: ['profile', name, 'versions', 'diff', a, b],
        queryFn: () => api.fetchProfileVersionDiff(name, a, b),
        enabled: !!name && !!a && !!b,
    });
}

export function useProfileTags(name: string) {
    return useQuery({
        queryKey: ['profile', name, 'tags'],
        queryFn: () => api.fetchProfileTags(name),
        enabled: !!name,
    });
}
