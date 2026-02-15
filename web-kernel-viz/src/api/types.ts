
export interface ProfileListItem {
    name: string;
    version: string;
}

export interface ProfileDescription {
    name: string;
    version: string;
    standard: string;
    organization: string;
    element_count: number;
    relation_count: number;
    rule_count: number;
    elements_by_layer: {
        layer: string;
        count: number;
        elements: { name: string; kernel_type: string }[];
    }[];
    relations: { name: string; kernel_relation: string }[];
    rule_summary: { allow: number; deny: number };
}

export interface TopologyNode {
    name: string;
    layer: string;
    category: string;
    kernel_type: string;
    description: string;
}

export interface TopologyEdge {
    source: string;
    target: string;
    relation: string;
    rule_id: string;
    priority: number;
}

export interface ProfileTopologyResponse {
    profile: string;
    nodes: TopologyNode[];
    edges: TopologyEdge[];
    node_count: number;
    edge_count: number;
    relation_distribution: Record<string, number>;
}

export interface ReachableResponse {
    profile: string;
    source: string;
    max_depth: number;
    relation_filter: string | null;
    reachable: string[];
    count: number;
}

export interface PathEdge {
    source: string;
    target: string;
    relation: string;
    rule_id: string;
}

export interface PathsResponse {
    profile: string;
    source: string;
    target: string;
    max_depth: number;
    relation_filter: string | null;
    paths: { length: number; edges: PathEdge[] }[];
    count: number;
}

export interface ImpactResponse {
    profile: string;
    element: string;
    direction: string;
    max_depth: number;
    impact: Record<string, { length: number; edges: { source: string; target: string; relation: string }[] }[]>;
    affected_count: number;
}

// --- Kernel Schema (Entities & Relations) ---

/** I18n string: either a plain string or a language-keyed dict */
export type I18nString = string | Record<string, string>;

export interface KernelEntityItem {
    name: string;
    parent: string | null;
    is_abstract: boolean;
    description: I18nString;
    display_name: I18nString | null;
}

export interface KernelEntityLayer {
    name: string;
    count: number;
    entities: KernelEntityItem[];
}

export interface KernelEntitiesResponse {
    total: number;
    layers: KernelEntityLayer[];
}

export interface KernelRoleItem {
    name: string;
    player: string;
}

export interface KernelRelationItem {
    name: string;
    parent: string | null;
    roles: KernelRoleItem[];
    description: I18nString;
    display_name: I18nString | null;
}

export interface KernelRelationLayer {
    name: string;
    count: number;
    relations: KernelRelationItem[];
}

export interface KernelRelationsResponse {
    total: number;
    layers: KernelRelationLayer[];
}

// --- Kernel Rules Exploration ---

export interface KernelRuleSummary {
    id: string;
    source: string;
    target: string;
    relation: string;
    valid: boolean;
    priority: number;
    notes: string;
}

export interface KernelRulesResponse {
    total: number;
    group?: string;
    relation?: string;
    groups?: { name: string; count: number }[];
    rules?: KernelRuleSummary[];
}

export interface KernelRuleDetail {
    id: string;
    source: string;
    target: string;
    relation: string;
    valid: boolean;
    priority: number;
    conditions: { type: string; parameters: Record<string, string> }[];
    notes: string;
    metadata: {
        group: string;
        category: string;
        confidence: string;
        source: string;
        rationale: string;
        tags: string[];
        established_version: string;
    };
}

export interface JudgeResponse {
    verdict: string;
    confidence: string;
    evidence: {
        rule_id: string;
        matched: boolean;
        winner: boolean;
        valid: boolean;
        source: string;
        target: string;
        priority: number;
    }[];
    conflicts: string[];
}

// --- Governance ---

export interface GovernanceRuleItem {
    id: string;
    state: string;
    domain: string;
    version: string;
}

export interface GovernanceJudgmentResult {
    verdict: string;
    confidence: string;
    evidence: string[];
    messages: string[];
}

export interface ModelState {
    model_name: string;
    status: string;
    active_version_id: string | null;
    owner: string;
    [key: string]: unknown;
}

export interface PromotionProposal {
    id: string;
    rule_id: string;
    change_type: string;
    rationale: string;
    status: string;
}

export interface SimulationResult {
    simulation_id: string;
    impact_level: string;
    total_decisions_analyzed: number;
    affected_decisions: number;
    safe_to_apply: boolean;
    risk_factors: string[];
    verdict_changes: {
        triple: string[];
        original: string;
        simulated: string;
        winning_rule_change: { from: string; to: string };
    }[];
}
