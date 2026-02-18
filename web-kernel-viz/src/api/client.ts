
import type {
    ProfileListItem,
    ProfileDescription,
    ProfileTopologyResponse,
    ProfileProjectionResponse,
    ReachableResponse,
    ElementScopeResponse,
    PathsResponse,
    ImpactResponse,
    KernelEntitiesResponse,
    KernelRelationsResponse,
    KernelRulesResponse,
    KernelRuleDetail,
    JudgeResponse,
    GovernanceDashboardResponse,
    CrossLayerSummaryResponse,
    GovernanceRuleItem,
    GovernanceJudgmentResult,
    ModelState,
    PromotionProposal,
    SimulationResult,
    BusinessFlowTopologyResponse,
    LayerSchemaResponse,
    LayerStackResponse,
    NeedsCatalogSummary,
    NeedSummary,
    NeedDetail,
    ExpressNeedPayload,
    ExpressNeedResponse,
    AddNeedsUseCasePayload,
    ReviseNeedPayload,
    ReviseNeedResponse,
    AddNeedProcessUnitPayload,
    AddNeedProcessUnitResponse,
    InheritNeedDecisionEvidencePayload,
    InheritNeedDecisionEvidenceResponse,
    NeedsCatalogDetail,
    NeedsByKernelRefResult,
    ModelRegisterPayload,
    ModelValidatePayload,
    ModelActivatePayload,
    ModelRegistrationResult,
    ModelValidationResult,
    ModelActivationResult,
    BusinessModelSummary,
    TagSchemaSummary,
    I18nAuditResult,
    I18nProfileAuditResult,
    I18nTranslationsResult,
    ProfileVersionEntry,
    ProfileVersionsResponse,
    ProfileDiffResponse,
} from './types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:9000';

class ApiRequestError extends Error {
    status: number;
    detail: string;

    constructor(status: number, detail: string) {
        super(`API ${status}: ${detail}`);
        this.name = 'ApiRequestError';
        this.status = status;
        this.detail = detail;
    }
}

async function fetchJson<T>(path: string): Promise<T> {
    const res = await fetch(`${API_URL}${path}`);
    if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new ApiRequestError(res.status, detail);
    }
    return res.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${API_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new ApiRequestError(res.status, detail);
    }
    return res.json();
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${API_URL}${path}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new ApiRequestError(res.status, detail);
    }
    return res.json();
}

async function fetchJsonWithMethod<T>(path: string, method: string): Promise<T> {
    const res = await fetch(`${API_URL}${path}`, { method });
    if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new ApiRequestError(res.status, detail);
    }
    return res.json();
}

// --- Profile ---

export function fetchProfiles(): Promise<ProfileListItem[]> {
    return fetchJson('/profiles');
}

export function fetchProfileDescription(
    name: string,
    opts?: { lang?: string },
): Promise<ProfileDescription> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    const qs = params.toString();
    return fetchJson(`/profiles/${encodeURIComponent(name)}${qs ? `?${qs}` : ''}`);
}

export function fetchProfileTopology(
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
    },
): Promise<ProfileTopologyResponse> {
    const params = new URLSearchParams();
    if (opts?.cross_layer) params.set('cross_layer', 'true');
    if (opts?.lang) params.set('lang', opts.lang);
    if (opts?.max_edges != null) params.set('max_edges', String(opts.max_edges));
    if (opts?.view_mode) params.set('view_mode', opts.view_mode);
    if (opts?.surface_only) params.set('surface_only', 'true');
    if (opts?.domain_scope) params.set('domain_scope', opts.domain_scope);
    if (opts?.focus) params.set('focus', opts.focus);
    if (opts?.focus_relation) params.set('focus_relation', opts.focus_relation);
    if (opts?.focus_layer) params.set('focus_layer', opts.focus_layer);
    if (opts?.focus_actor) params.set('focus_actor', opts.focus_actor);
    if (opts?.focus_topic) params.set('focus_topic', opts.focus_topic);
    if (opts?.focus_depth != null) params.set('focus_depth', String(opts.focus_depth));
    const qs = params.toString();
    return fetchJson(`/profiles/${encodeURIComponent(name)}/topology${qs ? `?${qs}` : ''}`);
}

export function fetchProfileProjection(
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
    },
): Promise<ProfileProjectionResponse> {
    const params = new URLSearchParams();
    if (opts?.level) params.set('level', opts.level);
    if (opts?.lens) params.set('lens', opts.lens);
    if (opts?.cross_layer) params.set('cross_layer', 'true');
    if (opts?.domain_scope) params.set('domain_scope', opts.domain_scope);
    if (opts?.lang) params.set('lang', opts.lang);
    if (opts?.actor) params.set('actor', opts.actor);
    if (opts?.depth != null) params.set('depth', String(opts.depth));
    if (opts?.max_edges != null) params.set('max_edges', String(opts.max_edges));
    const qs = params.toString();
    return fetchJson(`/profiles/${encodeURIComponent(name)}/projection${qs ? `?${qs}` : ''}`);
}

export function fetchProfileComposedTopology(
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
    },
): Promise<ProfileTopologyResponse> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    if (opts?.max_edges != null) params.set('max_edges', String(opts.max_edges));
    if (opts?.surface_only) params.set('surface_only', 'true');
    if (opts?.domain_scope) params.set('domain_scope', opts.domain_scope);
    if (opts?.include_profiles && opts.include_profiles.length > 0) {
        params.set('include_profiles', opts.include_profiles.join(','));
    }
    if (opts?.focus) params.set('focus', opts.focus);
    if (opts?.focus_relation) params.set('focus_relation', opts.focus_relation);
    if (opts?.focus_layer) params.set('focus_layer', opts.focus_layer);
    if (opts?.focus_actor) params.set('focus_actor', opts.focus_actor);
    if (opts?.focus_topic) params.set('focus_topic', opts.focus_topic);
    if (opts?.focus_depth != null) params.set('focus_depth', String(opts.focus_depth));
    const qs = params.toString();
    return fetchJson(`/profiles/${encodeURIComponent(name)}/composed${qs ? `?${qs}` : ''}`);
}

export function fetchReachable(
    name: string,
    element: string,
    opts?: { max_depth?: number; relation?: string },
): Promise<ReachableResponse> {
    const params = new URLSearchParams({ element });
    if (opts?.max_depth != null) params.set('max_depth', String(opts.max_depth));
    if (opts?.relation) params.set('relation', opts.relation);
    return fetchJson(`/profiles/${encodeURIComponent(name)}/reachable?${params}`);
}

export function fetchElementScope(
    name: string,
    elements: string[],
    opts?: { max_depth?: number },
): Promise<ElementScopeResponse> {
    const body: Record<string, unknown> = { elements };
    if (opts?.max_depth != null) body.max_depth = opts.max_depth;
    return postJson(`/profiles/${encodeURIComponent(name)}/element-scope`, body);
}

export function fetchPaths(
    name: string,
    source: string,
    target: string,
    opts?: { max_depth?: number; relation?: string },
): Promise<PathsResponse> {
    const params = new URLSearchParams({ source, target });
    if (opts?.max_depth != null) params.set('max_depth', String(opts.max_depth));
    if (opts?.relation) params.set('relation', opts.relation);
    return fetchJson(`/profiles/${encodeURIComponent(name)}/paths?${params}`);
}

export function fetchImpact(
    name: string,
    element: string,
    opts?: { direction?: string; max_depth?: number },
): Promise<ImpactResponse> {
    const params = new URLSearchParams({ element });
    if (opts?.direction) params.set('direction', opts.direction);
    if (opts?.max_depth != null) params.set('max_depth', String(opts.max_depth));
    return fetchJson(`/profiles/${encodeURIComponent(name)}/impact?${params}`);
}

// --- Kernel Schema (Entities & Relations) ---

export function fetchKernelEntities(opts?: { lang?: string }): Promise<KernelEntitiesResponse> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    const qs = params.toString();
    return fetchJson(`/kernel/entities${qs ? `?${qs}` : ''}`);
}

export function fetchKernelRelations(opts?: { lang?: string }): Promise<KernelRelationsResponse> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    const qs = params.toString();
    return fetchJson(`/kernel/relations${qs ? `?${qs}` : ''}`);
}

// --- Kernel Rules Exploration ---

export function fetchKernelRules(opts?: {
    group?: string;
    relation?: string;
}): Promise<KernelRulesResponse> {
    const params = new URLSearchParams();
    if (opts?.group) params.set('group', opts.group);
    if (opts?.relation) params.set('relation', opts.relation);
    const qs = params.toString();
    return fetchJson(`/kernel/rules${qs ? `?${qs}` : ''}`);
}

export function fetchKernelRuleDetail(ruleId: string): Promise<KernelRuleDetail> {
    return fetchJson(`/kernel/rules/${encodeURIComponent(ruleId)}`);
}

export function fetchJudge(
    source: string,
    target: string,
    relation: string,
): Promise<JudgeResponse> {
    return postJson('/kernel/judge', { source, target, relation });
}

// --- Dashboard ---

export function fetchGovernanceDashboard(): Promise<GovernanceDashboardResponse> {
    return fetchJson('/governance/dashboard');
}

export function fetchCrossLayerSummary(): Promise<CrossLayerSummaryResponse> {
    return fetchJson('/governance/layers/summary');
}

export async function fetchLayerSchema(
    layerKey: string,
    opts?: { lang?: string },
): Promise<LayerSchemaResponse> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    const qs = params.toString();
    return fetchJson(`/layers/${encodeURIComponent(layerKey)}/m2${qs ? `?${qs}` : ''}`);
}

export async function fetchLayerStack(
    layerKey: string,
    opts?: { lang?: string; m0_limit?: number },
): Promise<LayerStackResponse> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    if (opts?.m0_limit != null) params.set('m0_limit', String(opts.m0_limit));
    const qs = params.toString();
    return fetchJson(`/layers/${encodeURIComponent(layerKey)}/stack${qs ? `?${qs}` : ''}`);
}

// --- Business Flow ---

export function fetchBusinessFlowTopology(
    opts?: { lang?: string },
): Promise<BusinessFlowTopologyResponse> {
    const params = new URLSearchParams();
    if (opts?.lang) params.set('lang', opts.lang);
    const qs = params.toString();
    return fetchJson(`/governance/business-flow${qs ? `?${qs}` : ''}`);
}

// --- Governance ---

export function fetchGovernanceRules(state?: string): Promise<GovernanceRuleItem[]> {
    const qs = state ? `?state=${encodeURIComponent(state)}` : '';
    return fetchJson(`/rules${qs}`);
}

export function approveRule(ruleId: string): Promise<{ status: string; rule_id: string }> {
    return postJson(`/rules/${encodeURIComponent(ruleId)}/approve`, {});
}

export function fetchModelState(modelName: string): Promise<ModelState> {
    return fetchJson(`/models/${encodeURIComponent(modelName)}`);
}

export function executeJudgment(
    source: string,
    target: string,
    relation: string,
): Promise<GovernanceJudgmentResult> {
    return postJson('/judgment/execute', { source, target, relation });
}

export function fetchPromotionProposals(): Promise<PromotionProposal[]> {
    return fetchJson('/automation/promotions');
}

export function simulatePromotion(
    ruleId: string,
    newConfidence: string,
): Promise<SimulationResult> {
    return postJson('/simulation/what-if', {
        rule_id: ruleId,
        new_confidence: newConfidence,
    });
}

export function fetchDecisionTrace(decisionId: string): Promise<Record<string, unknown>> {
    return fetchJson(`/models/decisions/${encodeURIComponent(decisionId)}`);
}

// --- Needs ---

export function fetchNeedsCatalogs(): Promise<NeedsCatalogSummary[]> {
    return fetchJson('/needs/catalogs');
}

export function createNeedsCatalog(name: string, description = ''): Promise<{ catalog_id: string; transaction_id: string }> {
    return postJson('/needs/catalogs', { name, description });
}

export function fetchNeedsCatalogDetail(catalogId: string): Promise<NeedsCatalogDetail> {
    return fetchJson(`/needs/catalogs/${encodeURIComponent(catalogId)}`);
}

export function fetchCatalogNeeds(
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
): Promise<NeedSummary[]> {
    const params = new URLSearchParams();
    if (opts?.status) params.set('status', opts.status);
    if (opts?.priority) params.set('priority', opts.priority);
    if (opts?.stakeholder_id) params.set('stakeholder_id', opts.stakeholder_id);
    if (opts?.purpose) params.set('purpose', opts.purpose);
    if (opts?.complexity) params.set('complexity', opts.complexity);
    if (opts?.use_case_id) params.set('use_case_id', opts.use_case_id);
    if (opts?.cause_type) params.set('cause_type', opts.cause_type);
    if (opts?.kernel_change_phase) params.set('kernel_change_phase', opts.kernel_change_phase);
    if (opts?.decision_id) params.set('decision_id', opts.decision_id);
    if (opts?.decision_linked != null) params.set('decision_linked', opts.decision_linked ? 'true' : 'false');
    const qs = params.toString();
    return fetchJson(`/needs/catalogs/${encodeURIComponent(catalogId)}/needs${qs ? `?${qs}` : ''}`);
}

export function fetchNeedDetail(catalogId: string, needId: string): Promise<NeedDetail> {
    return fetchJson(`/needs/catalogs/${encodeURIComponent(catalogId)}/needs/${encodeURIComponent(needId)}`);
}

export function addStakeholder(
    catalogId: string,
    data: { name: string; role: string; context?: string },
): Promise<Record<string, string>> {
    return postJson(`/needs/catalogs/${encodeURIComponent(catalogId)}/stakeholders`, data);
}

export function addNeedsUseCase(
    catalogId: string,
    data: AddNeedsUseCasePayload,
): Promise<Record<string, string>> {
    return postJson(`/needs/catalogs/${encodeURIComponent(catalogId)}/use-cases`, data);
}

export function expressNeed(
    catalogId: string,
    data: ExpressNeedPayload,
): Promise<ExpressNeedResponse> {
    return postJson(`/needs/catalogs/${encodeURIComponent(catalogId)}/needs`, data);
}

export function reviseNeed(
    catalogId: string,
    needId: string,
    data: ReviseNeedPayload,
): Promise<ReviseNeedResponse> {
    return postJson(
        `/needs/catalogs/${encodeURIComponent(catalogId)}/needs/${encodeURIComponent(needId)}/revise`,
        data,
    );
}

export function addNeedProcessUnit(
    catalogId: string,
    needId: string,
    data: AddNeedProcessUnitPayload,
): Promise<AddNeedProcessUnitResponse> {
    return postJson(
        `/needs/catalogs/${encodeURIComponent(catalogId)}/needs/${encodeURIComponent(needId)}/process-units`,
        data,
    );
}

export function inheritNeedDecisionEvidence(
    catalogId: string,
    needId: string,
    data: InheritNeedDecisionEvidencePayload,
): Promise<InheritNeedDecisionEvidenceResponse> {
    return postJson(
        `/needs/catalogs/${encodeURIComponent(catalogId)}/needs/${encodeURIComponent(needId)}/inherit-decision-evidence`,
        data,
    );
}

export function fetchCatalogHistory(catalogId: string): Promise<Record<string, unknown>[]> {
    return fetchJson(`/needs/catalogs/${encodeURIComponent(catalogId)}/history`);
}

export function fetchNeedsByKernelRef(ref: string): Promise<NeedsByKernelRefResult> {
    return fetchJson(`/needs/by-kernel-ref/${encodeURIComponent(ref)}`);
}

// --- Model Registration ---

export function registerModel(body: ModelRegisterPayload): Promise<ModelRegistrationResult> {
    return postJson('/models/register', body);
}

export function validateModel(body: ModelValidatePayload): Promise<ModelValidationResult> {
    return postJson('/models/validate', body);
}

export function activateModel(body: ModelActivatePayload): Promise<ModelActivationResult> {
    return postJson('/models/activate', body);
}

// --- Decision Explore ---

export function exploreDecision(decisionId: string): Promise<Record<string, unknown>> {
    return fetchJson(`/models/decisions/${encodeURIComponent(decisionId)}/explore`);
}

// --- Business Models ---

export function fetchBusinessModels(): Promise<BusinessModelSummary[]> {
    return fetchJson('/business');
}

export function fetchBusinessModel(bid: string): Promise<BusinessModelSummary> {
    return fetchJson(`/business/${encodeURIComponent(bid)}`);
}

export function createBusiness(name: string, description?: string): Promise<Record<string, unknown>> {
    return postJson('/business', { name, description: description || '' });
}

export function deleteBusiness(bid: string): Promise<{ status: string }> {
    return fetchJsonWithMethod(`/business/${encodeURIComponent(bid)}`, 'DELETE');
}

export function fetchBusinessTags(bid: string): Promise<TagSchemaSummary[]> {
    return fetchJson(`/business/${encodeURIComponent(bid)}/tags`);
}

export function fetchBusinessTag(bid: string, tag: string): Promise<Record<string, unknown>> {
    return fetchJson(`/business/${encodeURIComponent(bid)}/tags/${encodeURIComponent(tag)}`);
}

export function createBusinessTag(bid: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
    return postJson(`/business/${encodeURIComponent(bid)}/tags`, data);
}

export function updateBusinessTag(bid: string, tag: string, data: Record<string, unknown>): Promise<Record<string, unknown>> {
    return putJson(`/business/${encodeURIComponent(bid)}/tags/${encodeURIComponent(tag)}`, data);
}

export function deleteBusinessTag(bid: string, tag: string): Promise<{ status: string }> {
    return fetchJsonWithMethod(`/business/${encodeURIComponent(bid)}/tags/${encodeURIComponent(tag)}`, 'DELETE');
}

export function fetchBusinessIndexingSpec(bid: string): Promise<Record<string, unknown>> {
    return fetchJson(`/business/${encodeURIComponent(bid)}/indexing-spec`);
}

export function exportBusiness(bid: string): Promise<Record<string, unknown>> {
    return fetchJson(`/business/${encodeURIComponent(bid)}/export`);
}

export function importBusiness(data: { meta: Record<string, unknown>; tags?: Record<string, unknown>[] }): Promise<Record<string, unknown>> {
    return postJson('/business/import', data);
}

// --- I18n ---

export function fetchI18nAudit(lang: string): Promise<I18nAuditResult> {
    return fetchJson(`/i18n/audit?lang=${encodeURIComponent(lang)}`);
}

export function fetchI18nProfileAudit(name: string, lang: string): Promise<I18nProfileAuditResult> {
    return fetchJson(`/i18n/audit/profiles/${encodeURIComponent(name)}?lang=${encodeURIComponent(lang)}`);
}

export function fetchI18nTranslations(lang: string, kind?: string): Promise<I18nTranslationsResult> {
    const params = new URLSearchParams({ lang });
    if (kind) params.set('kind', kind);
    return fetchJson(`/i18n/translations?${params}`);
}

export function fetchI18nTranslation(kind: string, name: string, lang: string, field: string): Promise<Record<string, unknown>> {
    return fetchJson(`/i18n/translations/${encodeURIComponent(kind)}/${encodeURIComponent(name)}/${encodeURIComponent(lang)}/${encodeURIComponent(field)}`);
}

export function updateI18nTranslation(kind: string, name: string, lang: string, field: string, value: string): Promise<Record<string, unknown>> {
    return putJson(`/i18n/translations/${encodeURIComponent(kind)}/${encodeURIComponent(name)}/${encodeURIComponent(lang)}/${encodeURIComponent(field)}`, { value });
}

export function fetchTranslationHistory(kind: string, name: string, lang: string, field: string): Promise<Record<string, unknown>> {
    return fetchJson(`/i18n/translations/${encodeURIComponent(kind)}/${encodeURIComponent(name)}/${encodeURIComponent(lang)}/${encodeURIComponent(field)}/history`);
}

// --- Flow Logic ---

export function fetchFlowLogic(anchorId: string): Promise<Record<string, unknown>> {
    return fetchJson(`/governance/flow/${encodeURIComponent(anchorId)}`);
}

// --- System Self-Model ---

export function fetchSystemSelfModel(): Promise<string> {
    return fetch(`${API_URL}/system/self-model`).then(res => {
        if (!res.ok) throw new Error(`API ${res.status}`);
        return res.text();
    });
}

// --- Profile Versions ---

export function fetchProfileVersions(name: string, limit?: number): Promise<ProfileVersionsResponse> {
    const params = new URLSearchParams();
    if (limit) params.set('limit', String(limit));
    const qs = params.toString();
    return fetchJson(`/profiles/${encodeURIComponent(name)}/versions${qs ? `?${qs}` : ''}`);
}

export function fetchProfileVersionDetail(name: string, version: string): Promise<ProfileVersionEntry> {
    return fetchJson(`/profiles/${encodeURIComponent(name)}/versions/${encodeURIComponent(version)}`);
}

export function fetchProfileVersionDiff(name: string, a: string, b: string): Promise<ProfileDiffResponse> {
    const params = new URLSearchParams({ a, b });
    return fetchJson(`/profiles/${encodeURIComponent(name)}/versions/diff?${params}`);
}

export function fetchProfileTags(name: string): Promise<Record<string, string>> {
    return fetchJson(`/profiles/${encodeURIComponent(name)}/tags`);
}
