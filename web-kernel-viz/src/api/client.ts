
import type {
    ProfileListItem,
    ProfileDescription,
    ProfileTopologyResponse,
    ReachableResponse,
    PathsResponse,
    ImpactResponse,
    KernelRulesResponse,
    KernelRuleDetail,
    JudgeResponse,
    GovernanceRuleItem,
    GovernanceJudgmentResult,
    ModelState,
    PromotionProposal,
    SimulationResult,
} from './types';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:9000';

async function fetchJson<T>(path: string): Promise<T> {
    const res = await fetch(`${API_URL}${path}`);
    if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new Error(`API ${res.status}: ${detail}`);
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
        throw new Error(`API ${res.status}: ${detail}`);
    }
    return res.json();
}

// --- Profile ---

export function fetchProfiles(): Promise<ProfileListItem[]> {
    return fetchJson('/profiles');
}

export function fetchProfileDescription(name: string): Promise<ProfileDescription> {
    return fetchJson(`/profiles/${encodeURIComponent(name)}`);
}

export function fetchProfileTopology(name: string): Promise<ProfileTopologyResponse> {
    return fetchJson(`/profiles/${encodeURIComponent(name)}/topology`);
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

// --- Kernel Schema Exploration ---

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
