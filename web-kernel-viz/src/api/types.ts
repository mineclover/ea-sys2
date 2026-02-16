
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
    description: I18nString;
    display_name?: I18nString;
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

export interface ElementScopeResponse {
    profile: string;
    seeds: string[];
    scope: string[];
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

// --- Dashboard ---

export interface DashboardLayerInfo {
    layer_key: string;
    profile_name: string;
    loaded: boolean;
    name: string;
    version: string;
    element_count: number;
    relation_count: number;
    rule_count: number;
}

export interface DashboardGovernanceStackInfo {
    stack_id: string;
    profile_name: string;
    loaded: boolean;
    name: string;
    version: string;
    element_count: number;
    relation_count: number;
    rule_count: number;
}

export interface GovernanceDashboardResponse {
    managed_layers: {
        layers: DashboardLayerInfo[];
        governance_stack: DashboardGovernanceStackInfo[];
        total_profiles: number;
    };
    schema: {
        entity_count: number;
        relation_count: number;
        entities: string[];
        relations: string[];
    };
    frameworks: {
        name: string;
        version: string;
        element_count: number;
        relation_count: number;
        rule_count: number;
    }[];
}

export interface CrossLayerSummaryResponse {
    layers: {
        layer_key: string;
        loaded: boolean;
        node_count: number;
        edge_count: number;
        top_relations: { relation: string; count: number }[];
    }[];
    total_nodes: number;
    total_edges: number;
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

// --- Needs ---

export interface NeedsCatalogSummary {
    id: string;
    name: string;
    description: string;
    needs_count: number;
    stakeholder_count: number;
    use_case_count: number;
    updated_at: string;
}

export interface NeedSummary {
    id: string;
    lineage_id: string;
    version: number;
    status: string;
    priority: string;
    stakeholder_id: string;
    action: string;
    subject: string;
    target: string | null;
    kernel_refs: string[];
    tags: string[];
    updated_at: string;
}

export interface NeedDetail extends NeedSummary {
    justifications: { type: string; description: string }[];
    purpose: string;
    cause_types: string[];
    complexity: string;
    use_case_id: string | null;
    created_at: string;
    process_units: {
        id: string;
        stage: string;
        label: string;
        description: string;
        sequence: number;
    }[];
}

export interface NeedsCatalogDetail {
    id: string;
    name: string;
    description: string;
    created_at: string;
    updated_at: string;
    stakeholders: { id: string; name: string; role: string; context: string }[];
    needs: unknown[];
    use_cases: { id: string; title: string; actor: string; situation: string; purpose: string }[];
    relations: { id: string; source_id: string; target_id: string; type: string; description: string }[];
}

export interface NeedsByKernelRefResult {
    kernel_ref: string;
    matches: {
        catalog_id: string;
        catalog_name: string;
        need_id: string;
        action: string;
        subject: string;
        status: string;
    }[];
}

// --- Layer Schema (M2 profile data) ---

export interface LayerSchemaElement {
    name: string;
    kernel_type: string;
    category: string;
    description: I18nString;
    display_name: I18nString | null;
}

export interface LayerSchemaElementGroup {
    layer: string;
    count: number;
    elements: LayerSchemaElement[];
}

export interface LayerSchemaRelation {
    name: string;
    kernel_relation: string;
    description: I18nString;
    display_name: I18nString | null;
    direction: string | null;
}

export interface LayerSchemaRule {
    source: string;
    target: string;
    relation: string;
    valid: boolean;
    priority: number;
    notes: string;
}

export interface LayerSchemaResponse {
    layer_key: string;
    profile_name: string;
    version: string;
    element_count: number;
    relation_count: number;
    rule_count: number;
    elements_by_layer: LayerSchemaElementGroup[];
    relations: LayerSchemaRelation[];
    rules: LayerSchemaRule[];
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
