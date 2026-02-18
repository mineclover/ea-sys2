
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
    home_layer?: string | null;
    ownership?: 'owned' | 'home_port' | 'foreign_port' | 'unknown';
    profile_owners?: string[];
}

export interface TopologyRuleRef {
    profile: string;
    profile_layer_key?: string | null;
    rule_id: string;
    source_pattern: string;
    target_pattern: string;
    relation: string;
    valid: boolean;
    priority: number;
    notes?: string;
    description?: I18nString;
}

export interface TopologyEdge {
    source: string;
    target: string;
    relation: string;
    priority: number;
    rule_count?: number;
    edge_origin?: 'explicit' | 'expanded' | 'mixed';
    explicit_count?: number;
    expanded_count?: number;
    semantic_axis?: string;
    semantic_intent?: string;
    surface_exposed?: boolean;
}

export interface ProfileDomainView {
    profile_layer_key: string | null;
    requested_scope: 'all' | 'owned' | 'bridge';
    scope: 'all' | 'owned' | 'bridge';
    scope_applied: boolean;
    available_scopes: ('all' | 'owned' | 'bridge')[];
    stats: {
        edges_before_scope: number;
        edges_after_scope: number;
        owned_edges: number;
        bridge_edges: number;
        owned_nodes: number;
        foreign_nodes: number;
        home_model_ports: number;
        foreign_model_ports: number;
    };
}

export interface ProfileCompositionView {
    mode: 'cross_profile';
    anchor_profile: string;
    anchor_layer_key: string | null;
    included_profiles: string[];
    requested_profiles: string[];
    missing_profiles: string[];
    source_profile_count: number;
}

export interface SurfaceFilterMeta {
    enabled: boolean;
    applied: boolean;
    visible_relations: string[];
    hidden_relations: string[];
}

export interface ProfileTopologyResponse {
    profile: string;
    nodes: TopologyNode[];
    edges: TopologyEdge[];
    view_mode?: 'raw' | 'summary' | 'focus';
    focus?: {
        mode: 'core' | 'relation' | 'layer' | 'actor' | 'topic';
        relation?: string;
        layer?: string;
        actor?: string;
        actor_depth?: number;
        topic?: string;
        topic_depth?: number;
        topic_tokens?: string[];
        topic_seeds?: string[];
        topic_matches?: {
            name: string;
            layer: string;
            category: string;
            score: number;
            coverage: number;
            matched_in: string[];
        }[];
        selected_relation_profile?: {
            structural?: string[];
            intent?: string[];
        };
        topic_filter_stats?: {
            input_edges: number;
            relation_candidate_edges: number;
            structural_edges?: number;
            intent_edges?: number;
            scope_nodes?: number;
            relation_filtered_out: number;
            scope_filtered_out: number;
        };
        topic_policy?: {
            default_depth?: number;
            seed_score_ratio?: number;
            seed_score_floor?: number;
            min_token_coverage?: number;
            max_seed_count?: number;
            max_match_count?: number;
            max_scope_nodes_per_depth?: number;
        };
        actor_candidates?: {
            name: string;
            layer: string;
            category: string;
            description: I18nString;
            display_name?: I18nString | null;
        }[];
        selected_relations?: string[];
        relation_candidates?: string[];
        layer_candidates?: string[];
        visibility_profile?: Record<string, string[]>;
        visible_relations?: string[];
        hidden_relations?: string[];
    };
    node_count: number;
    edge_count: number;
    edge_total_raw?: number;
    edge_total_before_cap?: number;
    edge_truncated?: boolean;
    relation_distribution: Record<string, number>;
    semantic_view?: {
        profile_scope?: string;
        layer_key?: string;
        axis_distribution?: Record<string, number>;
        intent_distribution?: Record<string, number>;
        surface_edges?: number;
        deep_edges?: number;
        dominant_axis?: string | null;
        dominant_axis_share?: number;
    };
    surface_filter?: SurfaceFilterMeta;
    domain_view?: ProfileDomainView;
    composition?: ProfileCompositionView;
}

export interface ProfileProjectionMeta {
    level: 'L0' | 'L1' | 'L2' | 'L3' | 'L4';
    lens: 'panorama' | 'capability' | 'interaction' | 'execution' | 'trace';
    description: string;
    budget: {
        default_max_edges: number;
        effective_max_edges: number;
    };
    filters: {
        relations: string[];
        categories: string[];
        domain_scope?: string;
    };
    drilldown: {
        next_levels: string[];
    };
    source: {
        view_mode: 'raw' | 'summary' | 'focus';
        focus?: 'core' | 'relation' | 'layer' | 'actor' | 'topic' | null;
        node_count: number;
        edge_count: number;
        edge_total_raw: number;
    };
    reduction?: {
        nodes: {
            source: number;
            projected: number;
            ratio: number;
        };
        edges: {
            source: number;
            source_raw: number;
            before_cap: number;
            projected: number;
            ratio: number;
            raw_ratio: number;
            before_cap_ratio: number;
            truncated?: boolean;
        };
        stages?: {
            node_input?: number;
            node_candidates?: number;
            node_connected_or_preserved?: number;
            edge_input?: number;
            edge_after_node_scope?: number;
            edge_after_relation?: number;
            edge_before_cap?: number;
            edge_after_cap?: number;
        };
        drop_reasons?: {
            node_without_name?: number;
            node_category_filtered?: number;
            node_disconnected?: number;
            edge_invalid_endpoint?: number;
            edge_node_scope_filtered?: number;
            edge_relation_filtered?: number;
            edge_capped?: number;
        };
        preserve?: {
            requested?: number;
            matched?: number;
            retained?: number;
            unmatched?: string[];
        };
    };
    seed?: {
        actor?: string;
        depth?: number;
        actor_candidates?: {
            name: string;
            layer: string;
            category: string;
            description: I18nString;
            display_name?: I18nString | null;
        }[];
    };
}

export interface ProfileProjectionResponse extends ProfileTopologyResponse {
    projection: ProfileProjectionMeta;
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
    owns: string[];
    owns_key: string | null;
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
    kernel_change_phase: NeedKernelChangePhase;
    stakeholder_id: string;
    action: string;
    subject: string;
    target: string | null;
    kernel_refs: string[];
    tags: string[];
    purpose: string;
    cause_types: string[];
    complexity: string;
    use_case_id: string | null;
    decision_evidence_refs: string[];
    inherited_from_decisions: string[];
    decision_linked: boolean;
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

export type NeedPurpose =
    | 'safety'
    | 'efficiency'
    | 'usability'
    | 'compliance'
    | 'growth'
    | 'trust'
    | 'unspecified';

export type NeedKernelChangePhase = 'planned' | 'applied' | 'superseded' | 'rolled_back';

export interface ExpressNeedPayload {
    stakeholder_id: string;
    action: string;
    subject: string;
    target?: string | null;
    justifications?: { type: string; description: string }[];
    priority?: 'critical' | 'high' | 'medium' | 'low';
    kernel_refs?: string[];
    tags?: string[];
    use_case_id?: string | null;
    cause_types?: string[];
    purpose?: NeedPurpose;
    complexity?: 'simple' | 'procedural' | 'complex';
    kernel_change_phase?: NeedKernelChangePhase;
}

export interface ExpressNeedResponse {
    catalog_id: string;
    transaction_id: string;
    need_id: string;
    lineage_id: string;
    version: number;
}

export interface AddNeedsUseCasePayload {
    title: string;
    actor: string;
    situation: string;
    purpose: string;
    outcome?: string;
    tags?: string[];
}

export interface ReviseNeedPayload {
    action?: string;
    subject?: string;
    target?: string | null;
    justifications?: { type: string; description: string }[];
    priority?: 'critical' | 'high' | 'medium' | 'low';
    kernel_refs?: string[];
    tags?: string[];
    use_case_id?: string | null;
    cause_types?: string[];
    purpose?: NeedPurpose;
    complexity?: 'simple' | 'procedural' | 'complex';
    kernel_change_phase?: NeedKernelChangePhase;
    clone_process_units?: boolean;
}

export interface ReviseNeedResponse {
    catalog_id: string;
    transaction_id: string;
    need_id: string;
    lineage_id: string;
    version: number;
}

export interface AddNeedProcessUnitPayload {
    stage: 'identify' | 'query' | 'model_detail' | string;
    label: string;
    description?: string;
    sequence?: number;
    metadata?: Record<string, string>;
}

export interface AddNeedProcessUnitResponse {
    catalog_id: string;
    transaction_id: string;
    process_unit_id: string;
}

export interface InheritNeedDecisionEvidencePayload {
    decision_id: string;
    evidence_refs: string[];
    kernel_change_phase?: NeedKernelChangePhase;
}

export interface InheritNeedDecisionEvidenceResponse {
    catalog_id: string;
    transaction_id: string;
    need_id: string;
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
        kernel_change_phase: NeedKernelChangePhase;
    }[];
}

// --- Layer Schema (M2 profile data) ---

export interface LayerSchemaElement {
    identifier?: string;
    name: string;
    kernel_type: string;
    kernel_layer?: string;
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
    identifier?: string;
    name: string;
    kernel_relation: string;
    kernel_layer?: string;
    description: I18nString;
    display_name: I18nString | null;
    direction: string | null;
}

export interface LayerSchemaRule {
    identifier?: string;
    source: string;
    target: string;
    relation: string;
    valid: boolean;
    priority: number;
    notes: string;
    description?: I18nString;
    source_pattern_kind?: string;
    target_pattern_kind?: string;
    profile_name?: string;
    profile_layer_key?: string;
    profile_rule_id?: string;
    profile_rule_identifier?: string;
}

export interface LayerM2BlueprintCategory {
    identifier: string;
    name: string;
    kernel_type: string;
    kernel_layer: string;
    description?: I18nString;
    display_name?: I18nString | null;
    element_count: number;
    sample_elements: string[];
}

export interface LayerM2BlueprintRelation {
    identifier: string;
    name: string;
    kernel_relation: string;
    kernel_layer: string;
    description?: I18nString;
    display_name?: I18nString | null;
    direction: string;
}

export interface LayerM2BlueprintRule {
    identifier: string;
    source_category: string;
    target_category: string;
    relation: string;
    kernel_relation: string;
    kernel_layer: string;
    rule_count: number;
    priority_max: number;
    source_examples: string[];
    target_examples: string[];
    profile_name?: string;
    profile_layer_key?: string;
    profile_rule_ids?: string[];
    profile_rule_identifiers?: string[];
}

export interface LayerM2Blueprint {
    categories: LayerM2BlueprintCategory[];
    relations: LayerM2BlueprintRelation[];
    rules: LayerM2BlueprintRule[];
    summary: {
        category_count: number;
        relation_count: number;
        rule_edge_count: number;
    };
    layer_responsibilities: {
        layer: string;
        role: string;
        role_i18n?: I18nString;
    }[];
}

export interface LayerM2IdentifierSystem {
    layer_key: string;
    profile_name?: string;
    namespace: string;
    object_identifiers: {
        element: string;
        relation: string;
        category: string;
    };
    rule_identifier: {
        pattern: string;
        digest_algorithm: string;
        digest_length: number;
        input_template: string;
        valid_encoding: { true: number; false: number };
    };
    profile_rule_binding?: {
        profile_rule_identifier_pattern: string;
        binding_fields: string[];
    };
    kernel_layer_mapping: {
        entity: string;
        relation: string;
    };
}

export interface LayerProjectionUIPresetConfig {
    source_mode: 'topology' | 'projection' | 'composed';
    view_mode?: 'raw' | 'summary' | 'focus';
    projection_level?: 'l0' | 'l1' | 'l2' | 'l3' | 'l4';
    focus_mode?: 'core' | 'relation' | 'layer' | 'actor' | 'topic';
    focus_depth?: number;
    domain_scope: 'all' | 'owned' | 'bridge';
    surface_only: boolean;
    max_edges: number;
}

export interface LayerProjectionUIPolicy {
    edge_budget_options: number[];
    preset_order: string[];
    defaults: {
        safety_mode: boolean;
        surface_only: boolean;
        domain_scope: 'all' | 'owned' | 'bridge';
    };
    safety_caps: {
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
    presets: Record<string, LayerProjectionUIPresetConfig>;
}

export interface LayerProjectionPolicy {
    profile_name: string;
    source: string;
    scope: string;
    layer_key?: string | null;
    schema_contract?: Record<string, unknown>;
    actor_default_depth: number;
    lens_to_level: Record<string, string>;
    levels: Record<string, {
        level: string;
        lens: string;
        description: string;
        base_view_mode: string;
        base_focus?: string | null;
        allowed_relations: string[];
        allowed_categories: string[];
        default_max_edges: number;
        next_levels: string[];
    }>;
    topic: Record<string, unknown>;
    ui: LayerProjectionUIPolicy;
}

export interface LayerSchemaResponse {
    layer_key: string;
    profile_name: string;
    version: string;
    identifier_system?: LayerM2IdentifierSystem;
    element_count: number;
    relation_count: number;
    rule_count: number;
    elements_by_layer: LayerSchemaElementGroup[];
    relations: LayerSchemaRelation[];
    rules: LayerSchemaRule[];
    m2_blueprint?: LayerM2Blueprint;
    projection_policy?: LayerProjectionPolicy;
}

export interface LayerStackSnapshotItem {
    layer: string;
    model_id: string;
    updated_at: string;
    kind: string;
    payload_keys: string[];
}

export interface LayerStackModelCandidate {
    model_id: string | null;
    model_name: string;
    owner: string | null;
    status: string | null;
    active_version_id: string | null;
    updated_at: string | null;
    score: number;
    match_rules: string[];
}

export interface LayerStackResponse {
    layer_key: string;
    profile_name: string;
    version: string;
    lang: string;
    m2: LayerSchemaResponse;
    m1: ProfileTopologyResponse;
    m0: {
        snapshot_total: number;
        snapshots: LayerStackSnapshotItem[];
        model_candidate_total: number;
        model_candidates: LayerStackModelCandidate[];
    };
}

// --- Business Flow Topology ---

export interface BusinessFlowElement {
    node_id: string;
    name: string;
    kernel_type: string;
    category: string;
    description: I18nString;
    display_name: I18nString | null;
    domain_layer: string;
    is_model_port: boolean;
}

export interface BusinessFlowLayerGroup {
    layer_key: string;
    loaded: boolean;
    profile_name?: string;
    version?: string;
    element_count?: number;
    elements: BusinessFlowElement[];
}

export interface BusinessFlowEdge {
    source: string;
    target: string;
    relation: string;
    edge_type: 'intra_layer' | 'model_port_bridge' | 'runtime_chain' | 'governance_oversight';
    source_layer: string;
    target_layer: string;
}

export interface BusinessFlowTopologyResponse {
    layers: BusinessFlowLayerGroup[];
    edges: BusinessFlowEdge[];
    runtime_chain: BusinessFlowEdge[];
    total_elements: number;
    total_edges: number;
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

// --- Model Registration ---

export type ModelChangePhase = 'planned' | 'applied' | 'superseded' | 'rolled_back';

export interface ModelRegisterPayload {
    profile_toml: string;
    decision_id: string;
    owner?: string;
    model_name?: string;
    activate?: boolean;
    on_exists?: string;
    evidence_refs?: string[];
    change_phase?: ModelChangePhase;
}

export interface ModelValidatePayload {
    model_name: string;
    version: string;
    decision_id: string;
    evidence_refs?: string[];
    change_phase?: ModelChangePhase;
}

export interface ModelActivatePayload {
    model_name: string;
    version: string;
    decision_id: string;
    evidence_refs?: string[];
    change_phase?: ModelChangePhase;
}

export interface ModelRegistrationResult {
    model_name: string;
    version: string;
    created: boolean;
    validation_run_id: string | null;
    activated: boolean;
    status: string;
    active_version_id: string | null;
    transaction_id: string | null;
    decision_trace: Record<string, unknown> | null;
}

export interface ModelValidationResult {
    model_name: string;
    version: string;
    passed: boolean;
    run_id: string;
    errors: string[];
    transaction_id: string | null;
    decision_trace: Record<string, unknown> | null;
}

export interface ModelActivationResult {
    model_name: string;
    status: string;
    active_version_id: string | null;
    owner: string;
    transaction_id: string | null;
    decision_trace: Record<string, unknown> | null;
}

// --- Business Models ---

export interface BusinessModelSummary {
    bid: string;
    name: string;
    description: string;
    tag_count: number;
    created_at: string;
}

export interface TagSchemaSummary {
    tag: string;
    fields: { name: string; type: string; required?: boolean }[];
    indexes: { name: string; keyPath: string; unique?: boolean }[];
    keyPath: string;
    autoIncrement: boolean;
    kernel_ref: string | null;
    description: string;
}

// --- I18n ---

export interface I18nAuditItem {
    kind: string;
    name: string;
    field: string | null;
    identifier: string;
    profile?: string;
    en_current?: string;
    en_recorded?: string;
}

export interface I18nAuditResult {
    scope: 'm1' | 'm2';
    lang: string;
    coverage: number;
    total_schema_items: number;
    total_translated: number;
    total_issues: number;
    is_clean: boolean;
    missing_count: number;
    orphan_count: number;
    stale_count: number;
    missing: I18nAuditItem[];
    orphan: I18nAuditItem[];
    stale: I18nAuditItem[];
    // Backward-compatible aliases
    total: number;
    translated: number;
    missing_items: I18nAuditItem[];
}

export interface I18nProfileAuditResult extends I18nAuditResult {
    scope: 'm1';
    profile: string;
    patch_path: string | null;
}

export interface I18nTranslationItem {
    kind: string;
    name: string;
    field: string;
    value: string;
    lang: string;
}

export interface I18nTranslationsResult {
    lang: string;
    kind: string | null;
    total: number;
    translations: I18nTranslationItem[];
}

// --- Profile Versions ---

export interface ProfileVersionEntry {
    id: string;
    version: string;
    hash: string;
    content_hash: string;
    author: string;
    created_at: string;
    description: string | null;
    parent_id: string | null;
    origin: string | null;
    element_count: number;
    relation_count: number;
    rule_count: number;
    tags: { name: string }[];
}

export interface ProfileVersionsResponse {
    profile: string;
    versions: ProfileVersionEntry[];
    total: number;
    count: number;
}

export interface ProfileDiffChange {
    name: string;
    type?: string;
    change?: 'added' | 'removed' | 'modified';
    field?: string;
    detail?: Record<string, unknown>;
    [key: string]: unknown;
}

export interface ProfileDiffResponse {
    profile: string;
    from_version: string;
    to_version: string;
    identical: boolean;
    element_changes: ProfileDiffChange[];
    relation_changes: ProfileDiffChange[];
    rule_changes: ProfileDiffChange[];
}
