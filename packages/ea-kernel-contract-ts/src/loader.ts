import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import type {
  IContractLoadOptions,
  IContractPaths,
  IKernelConditionEvaluation,
  IKernelContractBundle,
  IKernelContractIndex,
  IKernelContractModel,
  IKernelContractSummary,
  IKernelFeedbackTarget,
  IKernelRelationshipEvaluation,
  IKernelRelationshipEvaluationInput,
  IKernelJudgmentVector,
  IKernelJudgmentVectorsSnapshot,
  IKernelLayerConstraint,
  IKernelRule,
  IKernelRuleCondition,
  IKernelRuleMetadata,
  IKernelRulesSnapshot,
  IKernelSchemaAttribute,
  IKernelSchemaEntity,
  IKernelSchemaRelation,
  IKernelSchemaRole,
  IKernelSchemaSnapshot,
  ILayerContractComposeOptions,
  ILayerContractConvention,
  ILayerContractOverlay,
  KernelFeedbackTargetType,
  KernelLayer,
  KernelRuleConditionType,
} from "./types";

export const EA_KERNEL_CONTRACT_DIR = "EA_KERNEL_CONTRACT_DIR";

export const SCHEMA_FILE = "kernel_schema.snapshot.json";
export const RULES_FILE = "kernel_rules.snapshot.json";
export const VECTORS_FILE = "kernel_judgment_vectors.snapshot.json";

const LAYER_ORDER: Record<KernelLayer, number> = {
  L1: 1,
  L2: 2,
  L3: 3,
  L4: 4,
};

export const DEFAULT_MANAGED_GOVERNANCE_LAYERS = [
  "infra",
  "decision",
  "needs",
  "kernel",
  "flow",
] as const;

function asRecord(value: unknown, context: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new Error(`${context} must be an object`);
  return value as Record<string, unknown>;
}

function readString(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): string {
  const value: unknown = payload[key];
  if (typeof value !== "string" || value.trim().length === 0)
    throw new Error(`${context}.${key} must be a non-empty string`);
  return value;
}

function readOptionalString(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): string | undefined {
  const value: unknown = payload[key];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string" || value.trim().length === 0)
    throw new Error(`${context}.${key} must be a non-empty string`);
  return value;
}

function readBoolean(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): boolean {
  const value: unknown = payload[key];
  if (typeof value !== "boolean")
    throw new Error(`${context}.${key} must be a boolean`);
  return value;
}

function readNumber(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): number {
  const value: unknown = payload[key];
  if (typeof value !== "number" || Number.isFinite(value) === false)
    throw new Error(`${context}.${key} must be a finite number`);
  return value;
}

function readArray(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): unknown[] {
  const value: unknown = payload[key];
  if (Array.isArray(value) === false)
    throw new Error(`${context}.${key} must be an array`);
  return value;
}

function readStringArray(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): string[] {
  return readArray(payload, key, context).map((value, index) => {
    if (typeof value !== "string")
      throw new Error(`${context}.${key}[${index}] must be a string`);
    return value;
  });
}

function readLayer(value: unknown, context: string): KernelLayer {
  if (value === "L1" || value === "L2" || value === "L3" || value === "L4")
    return value;
  throw new Error(`${context} must be one of L1/L2/L3/L4`);
}

function loadJson(filePath: string): Record<string, unknown> {
  if (!fs.existsSync(filePath))
    throw new Error(`contract snapshot not found: ${filePath}`);
  const raw = fs.readFileSync(filePath, "utf8");
  return asRecord(JSON.parse(raw), filePath);
}

function parseSchemaSnapshot(
  payload: Record<string, unknown>,
): IKernelSchemaSnapshot {
  const context = "schema";
  const snapshotKind = readString(payload, "snapshot_kind", context);
  if (snapshotKind !== "ea_kernel_schema_contract")
    throw new Error(`schema.snapshot_kind unexpected: ${snapshotKind}`);

  const stats = asRecord(payload.stats, "schema.stats");

  const attributes = readArray(payload, "attributes", context).map((entry, index) =>
    parseSchemaAttribute(asRecord(entry, `schema.attributes[${index}]`), index),
  );

  const entities = readArray(payload, "entities", context).map((entry, index) =>
    parseSchemaEntity(asRecord(entry, `schema.entities[${index}]`), index),
  );

  const relations = readArray(payload, "relations", context).map((entry, index) =>
    parseSchemaRelation(asRecord(entry, `schema.relations[${index}]`), index),
  );

  return {
    snapshot_kind: "ea_kernel_schema_contract",
    contract_version: readString(payload, "contract_version", context),
    kernel_version: readString(payload, "kernel_version", context),
    generated_by: readString(payload, "generated_by", context),
    stats: {
      attributes: readNumber(stats, "attributes", "schema.stats"),
      entities: readNumber(stats, "entities", "schema.stats"),
      relations: readNumber(stats, "relations", "schema.stats"),
    },
    attributes,
    entities,
    relations,
  };
}

function parseSchemaAttribute(
  payload: Record<string, unknown>,
  index: number,
): IKernelSchemaAttribute {
  const context = `schema.attributes[${index}]`;
  return {
    name: readString(payload, "name", context),
    value_type: readString(payload, "value_type", context),
  };
}

function parseSchemaEntity(
  payload: Record<string, unknown>,
  index: number,
): IKernelSchemaEntity {
  const context = `schema.entities[${index}]`;
  return {
    name: readString(payload, "name", context),
    layer: readLayer(payload.layer, `${context}.layer`),
    is_abstract: readBoolean(payload, "is_abstract", context),
    owns: readStringArray(payload, "owns", context),
    plays: readStringArray(payload, "plays", context),
    description: readString(payload, "description", context),
    parent: readOptionalString(payload, "parent", context),
    owns_key: readOptionalString(payload, "owns_key", context),
  };
}

function parseSchemaRelation(
  payload: Record<string, unknown>,
  index: number,
): IKernelSchemaRelation {
  const context = `schema.relations[${index}]`;
  const roles = readArray(payload, "roles", context).map((entry, roleIndex) =>
    parseSchemaRole(
      asRecord(entry, `${context}.roles[${roleIndex}]`),
      index,
      roleIndex,
    ),
  );

  return {
    name: readString(payload, "name", context),
    layer: readLayer(payload.layer, `${context}.layer`),
    roles,
    owns: readStringArray(payload, "owns", context),
    description: readString(payload, "description", context),
    parent: readOptionalString(payload, "parent", context),
    owns_key: readOptionalString(payload, "owns_key", context),
  };
}

function parseSchemaRole(
  payload: Record<string, unknown>,
  relationIndex: number,
  roleIndex: number,
): IKernelSchemaRole {
  const context = `schema.relations[${relationIndex}].roles[${roleIndex}]`;
  return {
    name: readString(payload, "name", context),
    player: readString(payload, "player", context),
  };
}

function parseRulesSnapshot(payload: Record<string, unknown>): IKernelRulesSnapshot {
  const context = "rules";
  const snapshotKind = readString(payload, "snapshot_kind", context);
  if (snapshotKind !== "ea_kernel_rules_contract")
    throw new Error(`rules.snapshot_kind unexpected: ${snapshotKind}`);

  const stats = asRecord(payload.stats, "rules.stats");
  const explicitRules = readArray(payload, "explicit_rules", context).map(
    (entry, index) =>
      parseRule(asRecord(entry, `rules.explicit_rules[${index}]`), index, false),
  );
  const fallbackRules = readArray(payload, "fallback_rules", context).map(
    (entry, index) =>
      parseRule(asRecord(entry, `rules.fallback_rules[${index}]`), index, true),
  );
  const layerConstraints = readArray(payload, "layer_constraints", context).map(
    (entry, index) =>
      parseLayerConstraint(
        asRecord(entry, `rules.layer_constraints[${index}]`),
        index,
      ),
  );

  return {
    snapshot_kind: "ea_kernel_rules_contract",
    contract_version: readString(payload, "contract_version", context),
    kernel_version: readString(payload, "kernel_version", context),
    generated_by: readString(payload, "generated_by", context),
    stats: {
      total_rules: readNumber(stats, "total_rules", "rules.stats"),
      explicit_rules: readNumber(stats, "explicit_rules", "rules.stats"),
      fallback_rules: readNumber(stats, "fallback_rules", "rules.stats"),
      layer_constraints: readNumber(stats, "layer_constraints", "rules.stats"),
      metadata_entries: readNumber(stats, "metadata_entries", "rules.stats"),
    },
    explicit_rules: explicitRules,
    fallback_rules: fallbackRules,
    layer_constraints: layerConstraints,
  };
}

function parseRule(
  payload: Record<string, unknown>,
  index: number,
  isFallback: boolean,
): IKernelRule {
  const context = isFallback
    ? `rules.fallback_rules[${index}]`
    : `rules.explicit_rules[${index}]`;

  const conditions = readArray(payload, "conditions", context).map(
    (entry, conditionIndex) =>
      parseRuleCondition(
        asRecord(entry, `${context}.conditions[${conditionIndex}]`),
        context,
        conditionIndex,
      ),
  );

  const metadataValue = payload.metadata;
  const metadata: IKernelRuleMetadata | undefined =
    metadataValue === undefined
      ? undefined
      : parseRuleMetadata(asRecord(metadataValue, `${context}.metadata`), context);

  return {
    id: readString(payload, "id", context),
    source_pattern: readString(payload, "source_pattern", context),
    target_pattern: readString(payload, "target_pattern", context),
    relation: readString(payload, "relation", context),
    valid: readBoolean(payload, "valid", context),
    priority: readNumber(payload, "priority", context),
    conditions,
    notes: readString(payload, "notes", context),
    ...(metadata ? { metadata } : {}),
  };
}

function parseRuleCondition(
  payload: Record<string, unknown>,
  context: string,
  index: number,
): IKernelRuleCondition {
  const conditionContext = `${context}.conditions[${index}]`;
  const parametersRaw = payload.parameters;
  const parameterObject =
    parametersRaw === undefined
      ? {}
      : asRecord(parametersRaw, `${conditionContext}.parameters`);

  const parameters: Record<string, string> = {};
  for (const [key, value] of Object.entries(parameterObject)) {
    if (typeof value !== "string")
      throw new Error(`${conditionContext}.parameters.${key} must be a string`);
    parameters[key] = value;
  }

  return {
    type: readString(payload, "type", conditionContext),
    parameters,
  };
}

function parseRuleMetadata(
  payload: Record<string, unknown>,
  context: string,
): IKernelRuleMetadata {
  return {
    domain: readString(payload, "domain", `${context}.metadata`),
    tags: readStringArray(payload, "tags", `${context}.metadata`),
    category: readString(payload, "category", `${context}.metadata`),
    confidence: readString(payload, "confidence", `${context}.metadata`),
    source: readString(payload, "source", `${context}.metadata`),
    established_version: readString(
      payload,
      "established_version",
      `${context}.metadata`,
    ),
    rationale: readString(payload, "rationale", `${context}.metadata`),
    group: readString(payload, "group", `${context}.metadata`),
  };
}

function parseLayerConstraint(
  payload: Record<string, unknown>,
  index: number,
): IKernelLayerConstraint {
  const context = `rules.layer_constraints[${index}]`;
  const allowedPairsRaw = readArray(payload, "allowed_pairs", context);
  const allowedPairs: [string, string][] = allowedPairsRaw.map((entry, pairIndex) => {
    if (Array.isArray(entry) === false || entry.length !== 2)
      throw new Error(`${context}.allowed_pairs[${pairIndex}] must contain 2 items`);
    const source = entry[0];
    const target = entry[1];
    if (typeof source !== "string" || typeof target !== "string")
      throw new Error(`${context}.allowed_pairs[${pairIndex}] must contain strings`);
    return [source, target];
  });

  return {
    id: readString(payload, "id", context),
    source_layer: readLayer(payload.source_layer, `${context}.source_layer`),
    target_layer: readLayer(payload.target_layer, `${context}.target_layer`),
    forbidden_relations: readStringArray(payload, "forbidden_relations", context),
    allowed_pairs: allowedPairs,
    priority: readNumber(payload, "priority", context),
    notes: readString(payload, "notes", context),
  };
}

function parseVectorsSnapshot(
  payload: Record<string, unknown>,
): IKernelJudgmentVectorsSnapshot {
  const context = "vectors";
  const snapshotKind = readString(payload, "snapshot_kind", context);
  if (snapshotKind !== "ea_kernel_judgment_vectors_contract")
    throw new Error(`vectors.snapshot_kind unexpected: ${snapshotKind}`);

  const stats = asRecord(payload.stats, "vectors.stats");
  const vectors = readArray(payload, "vectors", context).map((entry, index) =>
    parseVector(asRecord(entry, `vectors.vectors[${index}]`), index),
  );

  return {
    snapshot_kind: "ea_kernel_judgment_vectors_contract",
    contract_version: readString(payload, "contract_version", context),
    kernel_version: readString(payload, "kernel_version", context),
    generated_by: readString(payload, "generated_by", context),
    stats: {
      vectors: readNumber(stats, "vectors", "vectors.stats"),
      allow_vectors: readNumber(stats, "allow_vectors", "vectors.stats"),
      deny_vectors: readNumber(stats, "deny_vectors", "vectors.stats"),
    },
    vectors,
  };
}

function parseVector(
  payload: Record<string, unknown>,
  index: number,
): IKernelJudgmentVector {
  const context = `vectors.vectors[${index}]`;
  const tripleRaw = readArray(payload, "triple", context);
  if (tripleRaw.length !== 3)
    throw new Error(`${context}.triple must contain 3 items`);

  const source = tripleRaw[0];
  const target = tripleRaw[1];
  const relation = tripleRaw[2];
  if (
    typeof source !== "string" ||
    typeof target !== "string" ||
    typeof relation !== "string"
  )
    throw new Error(`${context}.triple must contain strings`);

  const winnerRuleIdRaw = payload.expected_winner_rule_id;
  if (
    winnerRuleIdRaw !== null &&
    winnerRuleIdRaw !== undefined &&
    typeof winnerRuleIdRaw !== "string"
  )
    throw new Error(`${context}.expected_winner_rule_id must be string or null`);

  return {
    id: readString(payload, "id", context),
    triple: [source, target, relation],
    expected_verdict: readBoolean(payload, "expected_verdict", context),
    expected_confidence: readString(payload, "expected_confidence", context),
    expected_winner_rule_id:
      winnerRuleIdRaw === undefined ? null : (winnerRuleIdRaw as string | null),
  };
}

function checkUnique(
  values: string[],
  context: string,
  issues: string[],
): void {
  const seen = new Set<string>();
  for (const value of values) {
    if (seen.has(value)) issues.push(`${context} duplicated: ${value}`);
    seen.add(value);
  }
}

function patternBase(pattern: string): string {
  return pattern.endsWith("*") ? pattern.slice(0, -1) : pattern;
}

function isKnownPattern(pattern: string, entities: Set<string>): boolean {
  if (pattern === "*") return true;
  const base = patternBase(pattern);
  return entities.has(base);
}

export function validateKernelContractBundle(
  bundle: IKernelContractBundle,
): string[] {
  const issues: string[] = [];

  const entityNames = bundle.schema.entities.map((entity) => entity.name);
  const relationNames = bundle.schema.relations.map((relation) => relation.name);
  const attributeNames = bundle.schema.attributes.map((attribute) => attribute.name);
  const relationSet = new Set<string>(relationNames);
  const entitySet = new Set<string>(entityNames);

  checkUnique(attributeNames, "schema.attributes.name", issues);
  checkUnique(entityNames, "schema.entities.name", issues);
  checkUnique(relationNames, "schema.relations.name", issues);

  for (const entity of bundle.schema.entities) {
    if (entity.parent !== undefined && entitySet.has(entity.parent) === false)
      issues.push(`schema.entities.parent unknown: ${entity.name} -> ${entity.parent}`);
    if (entity.owns_key !== undefined && attributeNames.includes(entity.owns_key) === false)
      issues.push(`schema.entities.owns_key unknown attribute: ${entity.name} -> ${entity.owns_key}`);
    for (const own of entity.owns)
      if (attributeNames.includes(own) === false)
        issues.push(`schema.entities.owns unknown attribute: ${entity.name} -> ${own}`);
  }

  for (const relation of bundle.schema.relations) {
    if (
      relation.parent !== undefined &&
      relationSet.has(relation.parent) === false
    )
      issues.push(
        `schema.relations.parent unknown: ${relation.name} -> ${relation.parent}`,
      );
    if (
      relation.owns_key !== undefined &&
      attributeNames.includes(relation.owns_key) === false
    )
      issues.push(
        `schema.relations.owns_key unknown attribute: ${relation.name} -> ${relation.owns_key}`,
      );
    for (const own of relation.owns)
      if (attributeNames.includes(own) === false)
        issues.push(`schema.relations.owns unknown attribute: ${relation.name} -> ${own}`);
    for (const role of relation.roles)
      if (entitySet.has(role.player) === false)
        issues.push(
          `schema.relations.roles.player unknown entity: ${relation.name}:${role.name} -> ${role.player}`,
        );
  }

  const explicitRules = bundle.rules.explicit_rules;
  const fallbackRules = bundle.rules.fallback_rules;
  const allRules = [...explicitRules, ...fallbackRules];

  checkUnique(
    allRules.map((rule) => rule.id),
    "rules.rule.id",
    issues,
  );

  for (const rule of allRules) {
    if (relationSet.has(rule.relation) === false)
      issues.push(`rules.rule relation unknown: ${rule.id} -> ${rule.relation}`);
    if (isKnownPattern(rule.source_pattern, entitySet) === false)
      issues.push(`rules.rule source_pattern unknown: ${rule.id} -> ${rule.source_pattern}`);
    if (isKnownPattern(rule.target_pattern, entitySet) === false)
      issues.push(`rules.rule target_pattern unknown: ${rule.id} -> ${rule.target_pattern}`);
  }

  checkUnique(
    fallbackRules.map((rule) => rule.relation),
    "rules.fallback_rules.relation",
    issues,
  );

  const metadataCount = explicitRules.filter((rule) => rule.metadata !== undefined).length;
  if (metadataCount !== bundle.rules.stats.metadata_entries)
    issues.push(
      `rules.stats.metadata_entries mismatch: expected=${bundle.rules.stats.metadata_entries} actual=${metadataCount}`,
    );

  for (const constraint of bundle.rules.layer_constraints) {
    for (const relation of constraint.forbidden_relations)
      if (relationSet.has(relation) === false)
        issues.push(
          `rules.layer_constraints.forbidden_relations unknown relation: ${constraint.id} -> ${relation}`,
        );
    for (const [source, target] of constraint.allowed_pairs) {
      if (isKnownPattern(source, entitySet) === false)
        issues.push(
          `rules.layer_constraints.allowed_pairs source unknown: ${constraint.id} -> ${source}`,
        );
      if (isKnownPattern(target, entitySet) === false)
        issues.push(
          `rules.layer_constraints.allowed_pairs target unknown: ${constraint.id} -> ${target}`,
        );
    }
  }

  checkUnique(
    bundle.rules.layer_constraints.map((constraint) => constraint.id),
    "rules.layer_constraints.id",
    issues,
  );

  const allRuleIds = new Set(allRules.map((rule) => rule.id));
  const vectorIds = bundle.vectors.vectors.map((vector) => vector.id);
  checkUnique(vectorIds, "vectors.vectors.id", issues);
  for (const vector of bundle.vectors.vectors) {
    const [source, target, relation] = vector.triple;
    if (entitySet.has(source) === false)
      issues.push(`vectors.triple source unknown: ${vector.id} -> ${source}`);
    if (entitySet.has(target) === false)
      issues.push(`vectors.triple target unknown: ${vector.id} -> ${target}`);
    if (relationSet.has(relation) === false)
      issues.push(`vectors.triple relation unknown: ${vector.id} -> ${relation}`);
    if (
      vector.expected_winner_rule_id !== null &&
      allRuleIds.has(vector.expected_winner_rule_id) === false
    )
      issues.push(
        `vectors.expected_winner_rule_id unknown: ${vector.id} -> ${vector.expected_winner_rule_id}`,
      );
  }

  if (bundle.schema.stats.attributes !== bundle.schema.attributes.length)
    issues.push(
      `schema.stats.attributes mismatch: expected=${bundle.schema.stats.attributes} actual=${bundle.schema.attributes.length}`,
    );
  if (bundle.schema.stats.entities !== bundle.schema.entities.length)
    issues.push(
      `schema.stats.entities mismatch: expected=${bundle.schema.stats.entities} actual=${bundle.schema.entities.length}`,
    );
  if (bundle.schema.stats.relations !== bundle.schema.relations.length)
    issues.push(
      `schema.stats.relations mismatch: expected=${bundle.schema.stats.relations} actual=${bundle.schema.relations.length}`,
    );

  if (bundle.rules.stats.explicit_rules !== explicitRules.length)
    issues.push(
      `rules.stats.explicit_rules mismatch: expected=${bundle.rules.stats.explicit_rules} actual=${explicitRules.length}`,
    );
  if (bundle.rules.stats.fallback_rules !== fallbackRules.length)
    issues.push(
      `rules.stats.fallback_rules mismatch: expected=${bundle.rules.stats.fallback_rules} actual=${fallbackRules.length}`,
    );
  if (
    bundle.rules.stats.layer_constraints !== bundle.rules.layer_constraints.length
  )
    issues.push(
      `rules.stats.layer_constraints mismatch: expected=${bundle.rules.stats.layer_constraints} actual=${bundle.rules.layer_constraints.length}`,
    );

  const totalRules = explicitRules.length + fallbackRules.length;
  if (bundle.rules.stats.total_rules !== totalRules)
    issues.push(
      `rules.stats.total_rules mismatch: expected=${bundle.rules.stats.total_rules} actual=${totalRules}`,
    );

  if (bundle.vectors.stats.vectors !== bundle.vectors.vectors.length)
    issues.push(
      `vectors.stats.vectors mismatch: expected=${bundle.vectors.stats.vectors} actual=${bundle.vectors.vectors.length}`,
    );

  const allowVectors = bundle.vectors.vectors.filter(
    (vector) => vector.expected_verdict,
  ).length;
  const denyVectors = bundle.vectors.vectors.length - allowVectors;
  if (bundle.vectors.stats.allow_vectors !== allowVectors)
    issues.push(
      `vectors.stats.allow_vectors mismatch: expected=${bundle.vectors.stats.allow_vectors} actual=${allowVectors}`,
    );
  if (bundle.vectors.stats.deny_vectors !== denyVectors)
    issues.push(
      `vectors.stats.deny_vectors mismatch: expected=${bundle.vectors.stats.deny_vectors} actual=${denyVectors}`,
    );

  const versions = new Set<string>([
    bundle.schema.kernel_version,
    bundle.rules.kernel_version,
    bundle.vectors.kernel_version,
  ]);
  if (versions.size > 1)
    issues.push(
      `kernel_version mismatch across snapshots: ${Array.from(versions).join(", ")}`,
    );

  return issues;
}

export function buildKernelContractIndex(
  bundle: IKernelContractBundle,
): IKernelContractIndex {
  return {
    entityByName: new Map(bundle.schema.entities.map((entity) => [entity.name, entity])),
    relationByName: new Map(
      bundle.schema.relations.map((relation) => [relation.name, relation]),
    ),
    attributeByName: new Map(
      bundle.schema.attributes.map((attribute) => [attribute.name, attribute]),
    ),
    ruleById: new Map(
      [...bundle.rules.explicit_rules, ...bundle.rules.fallback_rules].map((rule) => [
        rule.id,
        rule,
      ]),
    ),
    fallbackRuleByRelation: new Map(
      bundle.rules.fallback_rules.map((rule) => [rule.relation, rule]),
    ),
    layerConstraintById: new Map(
      bundle.rules.layer_constraints.map((constraint) => [constraint.id, constraint]),
    ),
    vectorById: new Map(bundle.vectors.vectors.map((vector) => [vector.id, vector])),
  };
}

function computeFingerprintFromPaths(paths: IContractPaths): string {
  const hash = createHash("sha256");
  const files = [paths.schemaPath, paths.rulesPath, paths.vectorsPath];
  for (const filePath of files) {
    hash.update(path.basename(filePath), "utf8");
    hash.update("\0", "utf8");
    hash.update(fs.readFileSync(filePath));
    hash.update("\0", "utf8");
  }
  return hash.digest("hex");
}

export function getKernelContractFingerprint(
  bundle: IKernelContractBundle,
): string {
  return computeFingerprintFromPaths(bundle.paths);
}

function toLayerSlug(layerId: string): string {
  const slug = layerId
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
  if (slug.length === 0)
    throw new Error(`invalid layerId: ${JSON.stringify(layerId)}`);
  return slug;
}

function namespaceId(
  layerSlug: string,
  rawId: string,
  separator: string,
  shouldNamespace: boolean,
): string {
  const id = rawId.trim();
  if (id.length === 0) throw new Error("id cannot be empty");
  if (!shouldNamespace) return id;
  const prefix = `${layerSlug}${separator}`;
  if (id.startsWith(prefix)) return id;
  return `${prefix}${id}`;
}

function stableSerialize(value: unknown): string {
  if (Array.isArray(value))
    return `[${value.map((row) => stableSerialize(row)).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const row = value as Record<string, unknown>;
    const keys = Object.keys(row).sort();
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${stableSerialize(row[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function computeFingerprintFromBundle(bundle: IKernelContractBundle): string {
  const hash = createHash("sha256");
  hash.update(stableSerialize(bundle), "utf8");
  return hash.digest("hex");
}

export function buildLayerContractConvention(
  layerId: string,
): ILayerContractConvention {
  const layerSlug = toLayerSlug(layerId);
  return {
    layerId,
    layerSlug,
    tsPackageName: `@ea-sys2/${layerSlug}-contract-sdk`,
    pyPackageName: `ea-${layerSlug}-contract`,
    contractsDir: "contracts",
    schemaFile: SCHEMA_FILE,
    rulesFile: RULES_FILE,
    vectorsFile: VECTORS_FILE,
    feedbackIdPrefix: `${layerSlug}:`,
  };
}

export function buildManagedLayerContractConventions(
  managedLayers: readonly string[] = DEFAULT_MANAGED_GOVERNANCE_LAYERS,
): ILayerContractConvention[] {
  return managedLayers.map((layerId) => buildLayerContractConvention(layerId));
}

export function composeKernelContractBundle(
  baseBundle: IKernelContractBundle,
  overlays: ILayerContractOverlay[],
  options?: ILayerContractComposeOptions,
): IKernelContractBundle {
  const namespaceIds = options?.namespaceIds ?? true;
  const namespaceSeparator = options?.namespaceSeparator ?? ":";
  const mergeVectors = options?.mergeVectors ?? false;
  const allowRuleIdCollision = options?.allowRuleIdCollision ?? false;
  const allowConstraintIdCollision = options?.allowConstraintIdCollision ?? false;

  const explicitRules = [...baseBundle.rules.explicit_rules];
  const fallbackRulesByRelation = new Map<string, IKernelRule>(
    baseBundle.rules.fallback_rules.map((rule) => [rule.relation, rule]),
  );
  const ruleIds = new Set(
    [...explicitRules, ...fallbackRulesByRelation.values()].map((rule) => rule.id),
  );

  const layerConstraintsById = new Map<string, IKernelLayerConstraint>(
    baseBundle.rules.layer_constraints.map((constraint) => [constraint.id, constraint]),
  );

  const vectors = [...baseBundle.vectors.vectors];
  const vectorIds = new Set(vectors.map((vector) => vector.id));

  for (const overlay of overlays) {
    const layerSlug = toLayerSlug(overlay.layerId);
    const explicit = overlay.explicitRules ?? [];
    const fallback = overlay.fallbackRules ?? [];
    const constraints = overlay.layerConstraints ?? [];
    const overlayVectors = overlay.vectors ?? [];

    for (const row of explicit) {
      const id = namespaceId(layerSlug, row.id, namespaceSeparator, namespaceIds);
      if (!allowRuleIdCollision && ruleIds.has(id))
        throw new Error(`duplicate rule id after composition: ${id}`);
      ruleIds.add(id);
      explicitRules.push({
        ...row,
        id,
      });
    }

    for (const row of fallback) {
      const id = namespaceId(layerSlug, row.id, namespaceSeparator, namespaceIds);
      const previous = fallbackRulesByRelation.get(row.relation);
      if (
        !allowRuleIdCollision &&
        ruleIds.has(id) &&
        (previous === undefined || previous.id !== id)
      )
        throw new Error(`duplicate rule id after composition: ${id}`);

      if (previous !== undefined) ruleIds.delete(previous.id);
      ruleIds.add(id);
      fallbackRulesByRelation.set(row.relation, {
        ...row,
        id,
      });
    }

    for (const row of constraints) {
      const id = namespaceId(layerSlug, row.id, namespaceSeparator, namespaceIds);
      if (!allowConstraintIdCollision && layerConstraintsById.has(id))
        throw new Error(`duplicate layer constraint id after composition: ${id}`);
      layerConstraintsById.set(id, {
        ...row,
        id,
      });
    }

    if (mergeVectors) {
      for (const row of overlayVectors) {
        const id = namespaceId(layerSlug, row.id, namespaceSeparator, namespaceIds);
        if (vectorIds.has(id))
          throw new Error(`duplicate vector id after composition: ${id}`);
        vectorIds.add(id);
        vectors.push({
          ...row,
          id,
        });
      }
    }
  }

  const fallbackRules = Array.from(fallbackRulesByRelation.values());
  const layerConstraints = Array.from(layerConstraintsById.values());
  const metadataEntries = explicitRules.filter(
    (rule) => rule.metadata !== undefined,
  ).length;
  const allowVectors = vectors.filter((vector) => vector.expected_verdict).length;

  const composed: IKernelContractBundle = {
    ...baseBundle,
    rules: {
      ...baseBundle.rules,
      stats: {
        ...baseBundle.rules.stats,
        total_rules: explicitRules.length + fallbackRules.length,
        explicit_rules: explicitRules.length,
        fallback_rules: fallbackRules.length,
        layer_constraints: layerConstraints.length,
        metadata_entries: metadataEntries,
      },
      explicit_rules: explicitRules,
      fallback_rules: fallbackRules,
      layer_constraints: layerConstraints,
    },
    vectors: {
      ...baseBundle.vectors,
      stats: {
        ...baseBundle.vectors.stats,
        vectors: vectors.length,
        allow_vectors: allowVectors,
        deny_vectors: vectors.length - allowVectors,
      },
      vectors,
    },
  };

  const issues = validateKernelContractBundle(composed);
  if (issues.length > 0)
    throw new Error(`invalid composed kernel contract bundle: ${issues.join("; ")}`);

  return composed;
}

export function composeKernelContractModel(
  baseModel: IKernelContractModel,
  overlays: ILayerContractOverlay[],
  options?: ILayerContractComposeOptions,
): IKernelContractModel {
  const bundle = composeKernelContractBundle(baseModel.bundle, overlays, options);
  return {
    bundle,
    index: buildKernelContractIndex(bundle),
    fingerprint: computeFingerprintFromBundle(bundle),
  };
}

export function listKernelFeedbackTargets(
  model: IKernelContractModel,
  targetType?: KernelFeedbackTargetType,
): IKernelFeedbackTarget[] {
  const targets: IKernelFeedbackTarget[] = [];

  if (targetType === undefined || targetType === "entity_type") {
    for (const name of model.index.entityByName.keys())
      targets.push(toKernelFeedbackTarget("entity_type", name));
  }
  if (targetType === undefined || targetType === "relation_type") {
    for (const name of model.index.relationByName.keys())
      targets.push(toKernelFeedbackTarget("relation_type", name));
  }
  if (targetType === undefined || targetType === "rule") {
    for (const id of model.index.ruleById.keys())
      targets.push(toKernelFeedbackTarget("rule", id));
  }
  if (targetType === undefined || targetType === "layer_constraint") {
    for (const id of model.index.layerConstraintById.keys())
      targets.push(toKernelFeedbackTarget("layer_constraint", id));
  }

  return targets.sort((a, b) => a.canonicalId.localeCompare(b.canonicalId));
}

export function listKernelEntityAncestors(
  model: IKernelContractModel,
  entityName: string,
): string[] {
  const ancestors: string[] = [];
  const seen = new Set<string>();
  let cursor = model.index.entityByName.get(entityName);
  while (cursor?.parent !== undefined) {
    if (seen.has(cursor.parent))
      throw new Error(`entity parent cycle detected at: ${cursor.parent}`);
    seen.add(cursor.parent);
    ancestors.push(cursor.parent);
    cursor = model.index.entityByName.get(cursor.parent);
  }
  return ancestors;
}

export function entityMatchesKernelPattern(
  model: IKernelContractModel,
  entityName: string,
  pattern: string,
): boolean {
  if (pattern === "*") return model.index.entityByName.has(entityName);
  if (pattern.endsWith("*")) {
    const base = pattern.slice(0, -1);
    if (entityName === base) return true;
    return listKernelEntityAncestors(model, entityName).includes(base);
  }
  return entityName === pattern;
}

export function findKernelMatchingRules(
  model: IKernelContractModel,
  input: IKernelRelationshipEvaluationInput,
): IKernelRule[] {
  const rules = [
    ...model.bundle.rules.explicit_rules,
    ...model.bundle.rules.fallback_rules,
  ];
  const matched = rules.filter((rule) => {
    if (rule.relation !== input.relation) return false;
    if (
      entityMatchesKernelPattern(model, input.sourceEntity, rule.source_pattern) ===
      false
    )
      return false;
    if (
      entityMatchesKernelPattern(model, input.targetEntity, rule.target_pattern) ===
      false
    )
      return false;
    return true;
  });

  return matched.sort(
    (a, b) =>
      b.priority - a.priority || (a.valid === b.valid ? 0 : a.valid ? 1 : -1),
  );
}

function evaluateRuleCondition(
  model: IKernelContractModel,
  condition: IKernelRuleCondition,
  input: IKernelRelationshipEvaluationInput,
): IKernelConditionEvaluation {
  const source = model.index.entityByName.get(input.sourceEntity);
  const target = model.index.entityByName.get(input.targetEntity);
  if (source === undefined || target === undefined)
    return {
      type: condition.type,
      passed: false,
      note: "entity not found",
    };

  const conditionType = condition.type as KernelRuleConditionType;
  switch (conditionType) {
    case "same_layer": {
      const passed = source.layer === target.layer;
      return {
        type: condition.type,
        passed,
        note: `${input.sourceEntity}.layer=${source.layer} vs ${input.targetEntity}.layer=${target.layer}`,
      };
    }
    case "layer_order": {
      const sourceOrder = LAYER_ORDER[source.layer];
      const targetOrder = LAYER_ORDER[target.layer];
      const passed = sourceOrder <= targetOrder;
      return {
        type: condition.type,
        passed,
        note: `${input.sourceEntity}(L${sourceOrder}) <= ${input.targetEntity}(L${targetOrder})`,
      };
    }
    case "ancestor_of": {
      const passed = listKernelEntityAncestors(
        model,
        input.targetEntity,
      ).includes(input.sourceEntity);
      return {
        type: condition.type,
        passed,
        note: `${input.sourceEntity} ${passed ? "is" : "is not"} ancestor of ${input.targetEntity}`,
      };
    }
    case "same_category": {
      return {
        type: condition.type,
        passed: true,
        note: "same_category is profile-level only (skipped at kernel)",
      };
    }
    case "same_branch": {
      const sourceChain = new Set<string>([
        input.sourceEntity,
        ...listKernelEntityAncestors(model, input.sourceEntity),
      ]);
      const targetChain = new Set<string>([
        input.targetEntity,
        ...listKernelEntityAncestors(model, input.targetEntity),
      ]);

      const shared = Array.from(sourceChain).filter((name) => targetChain.has(name));
      const sharedNonRoot = shared.filter((name) => {
        const entity = model.index.entityByName.get(name);
        return entity !== undefined && entity.parent !== undefined;
      });
      return {
        type: condition.type,
        passed: sharedNonRoot.length > 0,
        note: `shared non-root ancestors: ${
          sharedNonRoot.length > 0 ? sharedNonRoot.join(", ") : "none"
        }`,
      };
    }
    default: {
      return {
        type: condition.type,
        passed: false,
        note: `unknown condition type: ${condition.type}`,
      };
    }
  }
}

export function evaluateKernelRelationship(
  model: IKernelContractModel,
  input: IKernelRelationshipEvaluationInput,
): IKernelRelationshipEvaluation {
  const sourceEntity = model.index.entityByName.get(input.sourceEntity);
  if (sourceEntity === undefined) {
    return {
      allowed: false,
      reason: "unknown_entity",
      winnerRuleId: null,
      matchedRuleIds: [],
      blockingConstraintId: null,
      conditionChecks: [],
      notes: `unknown entity: ${input.sourceEntity}`,
    };
  }
  const targetEntity = model.index.entityByName.get(input.targetEntity);
  if (targetEntity === undefined) {
    return {
      allowed: false,
      reason: "unknown_entity",
      winnerRuleId: null,
      matchedRuleIds: [],
      blockingConstraintId: null,
      conditionChecks: [],
      notes: `unknown entity: ${input.targetEntity}`,
    };
  }
  if (model.index.relationByName.has(input.relation) === false) {
    return {
      allowed: false,
      reason: "unknown_relation",
      winnerRuleId: null,
      matchedRuleIds: [],
      blockingConstraintId: null,
      conditionChecks: [],
      notes: `unknown relation: ${input.relation}`,
    };
  }

  for (const constraint of model.bundle.rules.layer_constraints) {
    if (constraint.forbidden_relations.includes(input.relation) === false) continue;
    if (
      sourceEntity.layer !== constraint.source_layer ||
      targetEntity.layer !== constraint.target_layer
    )
      continue;

    const exempt = constraint.allowed_pairs.some(([sourcePattern, targetPattern]) => {
      return (
        entityMatchesKernelPattern(model, input.sourceEntity, sourcePattern) &&
        entityMatchesKernelPattern(model, input.targetEntity, targetPattern)
      );
    });
    if (exempt === false) {
      return {
        allowed: false,
        reason: "constraint_denied",
        winnerRuleId: null,
        matchedRuleIds: [],
        blockingConstraintId: constraint.id,
        conditionChecks: [],
        notes:
          constraint.notes ||
          `layer constraint: ${constraint.source_layer} entities cannot use ${input.relation} with ${constraint.target_layer} entities`,
      };
    }
  }

  const matched = findKernelMatchingRules(model, input);
  if (matched.length === 0) {
    return {
      allowed: false,
      reason: "no_matching_rule",
      winnerRuleId: null,
      matchedRuleIds: [],
      blockingConstraintId: null,
      conditionChecks: [],
      notes: "no matching rule (deny-by-default)",
    };
  }

  const winner = matched[0];
  const conditionChecks = winner.conditions.map((condition) =>
    evaluateRuleCondition(model, condition, input),
  );
  const failedCondition = conditionChecks.find((row) => row.passed === false);
  if (failedCondition !== undefined) {
    return {
      allowed: false,
      reason: "condition_failed",
      winnerRuleId: winner.id,
      matchedRuleIds: matched.map((rule) => rule.id),
      blockingConstraintId: null,
      conditionChecks,
      notes: `condition failed: ${failedCondition.note}`,
    };
  }

  return {
    allowed: winner.valid,
    reason: "rule_verdict",
    winnerRuleId: winner.id,
    matchedRuleIds: matched.map((rule) => rule.id),
    blockingConstraintId: null,
    conditionChecks,
    notes: winner.notes,
  };
}

export function resolveKernelContractDir(options?: IContractLoadOptions): string {
  const explicit: string | undefined = options?.contractDir;
  if (explicit && explicit.trim().length > 0) return path.resolve(explicit);

  const fromEnv: string | undefined = process.env[EA_KERNEL_CONTRACT_DIR];
  if (fromEnv && fromEnv.trim().length > 0) return path.resolve(fromEnv);

  // Packaged fallback: packages/ea-kernel-contract-ts/contracts
  return path.resolve(__dirname, "..", "contracts");
}

export function resolveKernelContractPaths(
  options?: IContractLoadOptions,
): IContractPaths {
  const contractDir: string = resolveKernelContractDir(options);
  return {
    contractDir,
    schemaPath: path.join(contractDir, SCHEMA_FILE),
    rulesPath: path.join(contractDir, RULES_FILE),
    vectorsPath: path.join(contractDir, VECTORS_FILE),
  };
}

export function loadKernelContractBundle(
  options?: IContractLoadOptions,
): IKernelContractBundle {
  const paths = resolveKernelContractPaths(options);
  const schema = parseSchemaSnapshot(loadJson(paths.schemaPath));
  const rules = parseRulesSnapshot(loadJson(paths.rulesPath));
  const vectors = parseVectorsSnapshot(loadJson(paths.vectorsPath));

  const bundle: IKernelContractBundle = {
    kernelVersion: schema.kernel_version,
    paths,
    schema,
    rules,
    vectors,
  };

  if (options?.validate !== false) {
    const issues = validateKernelContractBundle(bundle);
    if (issues.length > 0)
      throw new Error(`invalid kernel contract bundle: ${issues.join("; ")}`);
  }

  return bundle;
}

export function buildKernelContractModel(
  options?: IContractLoadOptions,
): IKernelContractModel {
  const bundle = loadKernelContractBundle(options);
  const fingerprint = getKernelContractFingerprint(bundle);
  return {
    bundle,
    index: buildKernelContractIndex(bundle),
    fingerprint,
  };
}

export function buildLayerContractModel(
  overlays: ILayerContractOverlay[],
  options?: {
    base?: IContractLoadOptions;
    compose?: ILayerContractComposeOptions;
  },
): IKernelContractModel {
  const baseModel = buildKernelContractModel(options?.base);
  return composeKernelContractModel(baseModel, overlays, options?.compose);
}

export function toKernelFeedbackTarget(
  targetType: KernelFeedbackTargetType,
  targetId: string,
): IKernelFeedbackTarget {
  const trimmed = targetId.trim();
  if (trimmed.length === 0) throw new Error("feedback targetId cannot be empty");
  return {
    targetType,
    targetId: trimmed,
    canonicalId: `${targetType}:${trimmed}`,
  };
}

export function parseKernelFeedbackTarget(raw: string): IKernelFeedbackTarget {
  const normalized = raw.trim();
  const index = normalized.indexOf(":");
  if (index <= 0 || index === normalized.length - 1)
    throw new Error(`invalid feedback target format: ${raw}`);

  const rawType = normalized.slice(0, index);
  const rawTargetId = normalized.slice(index + 1);

  const targetType = asFeedbackTargetType(rawType);
  if (targetType === undefined)
    throw new Error(`unsupported feedback target type: ${rawType}`);

  return toKernelFeedbackTarget(targetType, rawTargetId);
}

export function resolveKernelFeedbackTarget(
  raw: string,
  model: IKernelContractModel,
): IKernelFeedbackTarget {
  const parsed = parseKernelFeedbackTarget(raw);

  switch (parsed.targetType) {
    case "entity_type": {
      if (model.index.entityByName.has(parsed.targetId) === false)
        throw new Error(`unknown entity_type target: ${parsed.targetId}`);
      return parsed;
    }
    case "relation_type": {
      if (model.index.relationByName.has(parsed.targetId) === false)
        throw new Error(`unknown relation_type target: ${parsed.targetId}`);
      return parsed;
    }
    case "rule": {
      if (model.index.ruleById.has(parsed.targetId) === false)
        throw new Error(`unknown rule target: ${parsed.targetId}`);
      return parsed;
    }
    case "layer_constraint": {
      if (model.index.layerConstraintById.has(parsed.targetId) === false)
        throw new Error(`unknown layer_constraint target: ${parsed.targetId}`);
      return parsed;
    }
  }
}

function asFeedbackTargetType(
  raw: string,
): KernelFeedbackTargetType | undefined {
  switch (raw) {
    case "entity_type":
    case "relation_type":
    case "rule":
    case "layer_constraint":
      return raw;
    default:
      return undefined;
  }
}

export function getEntityRequiredKeys(
  model: IKernelContractModel,
  entityName: string,
): string[] {
  const entity = model.index.entityByName.get(entityName);
  if (entity === undefined)
    throw new Error(`unknown entity type: ${entityName}`);

  const lineage: IKernelSchemaEntity[] = [];
  let cursor: IKernelSchemaEntity | undefined = entity;
  while (cursor !== undefined) {
    lineage.unshift(cursor);
    cursor =
      cursor.parent === undefined
        ? undefined
        : model.index.entityByName.get(cursor.parent);
  }

  const required = new Set<string>();
  for (const row of lineage) {
    if (row.owns_key !== undefined) required.add(row.owns_key);
    for (const key of row.owns) required.add(key);
  }

  return Array.from(required);
}

export function summarizeKernelContract(
  options?: IContractLoadOptions,
): IKernelContractSummary {
  try {
    const bundle = loadKernelContractBundle(options);
    return {
      available: true,
      contractDir: bundle.paths.contractDir,
      kernelVersion: bundle.kernelVersion,
      fingerprint: getKernelContractFingerprint(bundle),
      entityCount: bundle.schema.stats.entities,
      relationCount: bundle.schema.stats.relations,
      totalRules: bundle.rules.stats.total_rules,
      vectors: bundle.vectors.stats.vectors,
    };
  } catch (error) {
    return {
      available: false,
      contractDir: process.env.EA_KERNEL_CONTRACT_DIR ?? null,
      kernelVersion: null,
      fingerprint: null,
      entityCount: 0,
      relationCount: 0,
      totalRules: 0,
      vectors: 0,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
