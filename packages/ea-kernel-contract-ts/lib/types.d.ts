export interface IContractLoadOptions {
    contractDir?: string;
    validate?: boolean;
}
export interface IContractPaths {
    contractDir: string;
    schemaPath: string;
    rulesPath: string;
    vectorsPath: string;
}
export type KernelLayer = "L1" | "L2" | "L3" | "L4";
export type ManagedGovernanceLayer = "infra" | "decision" | "needs" | "kernel" | "flow";
export type KernelRuleConditionType = "same_layer" | "layer_order" | "ancestor_of" | "same_branch" | "same_category" | (string & {});
export type KernelFeedbackTargetType = "entity_type" | "relation_type" | "rule" | "layer_constraint";
export interface IKernelSchemaStats {
    attributes: number;
    entities: number;
    relations: number;
}
export interface IKernelSchemaAttribute {
    name: string;
    value_type: string;
}
export interface IKernelSchemaEntity {
    name: string;
    layer: KernelLayer;
    is_abstract: boolean;
    owns: string[];
    plays: string[];
    description: string;
    parent?: string;
    owns_key?: string;
}
export interface IKernelSchemaRole {
    name: string;
    player: string;
}
export interface IKernelSchemaRelation {
    name: string;
    layer: KernelLayer;
    roles: IKernelSchemaRole[];
    owns: string[];
    description: string;
    parent?: string;
    owns_key?: string;
}
export interface IKernelSchemaSnapshot {
    snapshot_kind: "ea_kernel_schema_contract";
    contract_version: string;
    kernel_version: string;
    generated_by: string;
    stats: IKernelSchemaStats;
    attributes: IKernelSchemaAttribute[];
    entities: IKernelSchemaEntity[];
    relations: IKernelSchemaRelation[];
}
export interface IKernelRuleCondition {
    type: KernelRuleConditionType;
    parameters: Record<string, string>;
}
export interface IKernelRuleMetadata {
    domain: string;
    tags: string[];
    category: string;
    confidence: string;
    source: string;
    established_version: string;
    rationale: string;
    group: string;
}
export interface IKernelRule {
    id: string;
    source_pattern: string;
    target_pattern: string;
    relation: string;
    valid: boolean;
    priority: number;
    conditions: IKernelRuleCondition[];
    notes: string;
    metadata?: IKernelRuleMetadata;
}
export interface IKernelLayerConstraint {
    id: string;
    source_layer: KernelLayer;
    target_layer: KernelLayer;
    forbidden_relations: string[];
    allowed_pairs: [string, string][];
    priority: number;
    notes: string;
}
export interface IKernelRulesStats {
    total_rules: number;
    explicit_rules: number;
    fallback_rules: number;
    layer_constraints: number;
    metadata_entries: number;
}
export interface IKernelRulesSnapshot {
    snapshot_kind: "ea_kernel_rules_contract";
    contract_version: string;
    kernel_version: string;
    generated_by: string;
    stats: IKernelRulesStats;
    explicit_rules: IKernelRule[];
    fallback_rules: IKernelRule[];
    layer_constraints: IKernelLayerConstraint[];
}
export interface IKernelJudgmentVector {
    id: string;
    triple: [string, string, string];
    expected_verdict: boolean;
    expected_confidence: string;
    expected_winner_rule_id: string | null;
}
export interface IKernelVectorsStats {
    vectors: number;
    allow_vectors: number;
    deny_vectors: number;
}
export interface IKernelJudgmentVectorsSnapshot {
    snapshot_kind: "ea_kernel_judgment_vectors_contract";
    contract_version: string;
    kernel_version: string;
    generated_by: string;
    stats: IKernelVectorsStats;
    vectors: IKernelJudgmentVector[];
}
export interface IKernelContractBundle {
    kernelVersion: string;
    paths: IContractPaths;
    schema: IKernelSchemaSnapshot;
    rules: IKernelRulesSnapshot;
    vectors: IKernelJudgmentVectorsSnapshot;
}
export interface IKernelContractSummary {
    available: boolean;
    contractDir: string | null;
    kernelVersion: string | null;
    fingerprint: string | null;
    entityCount: number;
    relationCount: number;
    totalRules: number;
    vectors: number;
    error?: string;
}
export interface IKernelContractIndex {
    entityByName: ReadonlyMap<string, IKernelSchemaEntity>;
    relationByName: ReadonlyMap<string, IKernelSchemaRelation>;
    attributeByName: ReadonlyMap<string, IKernelSchemaAttribute>;
    ruleById: ReadonlyMap<string, IKernelRule>;
    fallbackRuleByRelation: ReadonlyMap<string, IKernelRule>;
    layerConstraintById: ReadonlyMap<string, IKernelLayerConstraint>;
    vectorById: ReadonlyMap<string, IKernelJudgmentVector>;
}
export interface IKernelContractModel {
    bundle: IKernelContractBundle;
    index: IKernelContractIndex;
    fingerprint: string;
}
export interface IKernelFeedbackTarget {
    targetType: KernelFeedbackTargetType;
    targetId: string;
    canonicalId: string;
}
export interface IKernelRelationshipEvaluationInput {
    sourceEntity: string;
    targetEntity: string;
    relation: string;
}
export type KernelRelationshipEvaluationReason = "unknown_entity" | "unknown_relation" | "constraint_denied" | "no_matching_rule" | "condition_failed" | "rule_verdict";
export interface IKernelConditionEvaluation {
    type: KernelRuleConditionType;
    passed: boolean;
    note: string;
}
export interface IKernelRelationshipEvaluation {
    allowed: boolean;
    reason: KernelRelationshipEvaluationReason;
    winnerRuleId: string | null;
    matchedRuleIds: string[];
    blockingConstraintId: string | null;
    conditionChecks: IKernelConditionEvaluation[];
    notes: string;
}
export interface ILayerContractOverlay {
    layerId: string;
    source?: string;
    explicitRules?: IKernelRule[];
    fallbackRules?: IKernelRule[];
    layerConstraints?: IKernelLayerConstraint[];
    vectors?: IKernelJudgmentVector[];
}
export interface ILayerContractComposeOptions {
    namespaceIds?: boolean;
    namespaceSeparator?: string;
    mergeVectors?: boolean;
    allowRuleIdCollision?: boolean;
    allowConstraintIdCollision?: boolean;
}
export interface ILayerContractConvention {
    layerId: string;
    layerSlug: string;
    tsPackageName: string;
    pyPackageName: string;
    contractsDir: string;
    schemaFile: string;
    rulesFile: string;
    vectorsFile: string;
    feedbackIdPrefix: string;
}
