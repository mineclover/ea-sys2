import fs from "node:fs";
import path from "node:path";

import type {
  IContractLoadOptions,
  IContractPaths,
  IKernelContractBundle,
  IKernelContractIndex,
  IKernelContractModel,
  IKernelContractSummary,
  IKernelFeedbackTarget,
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
  KernelFeedbackTargetType,
  KernelLayer,
} from "./types";

export const EA_KERNEL_CONTRACT_DIR = "EA_KERNEL_CONTRACT_DIR";

export const SCHEMA_FILE = "kernel_schema.snapshot.json";
export const RULES_FILE = "kernel_rules.snapshot.json";
export const VECTORS_FILE = "kernel_judgment_vectors.snapshot.json";

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
  return {
    bundle,
    index: buildKernelContractIndex(bundle),
  };
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
      entityCount: 0,
      relationCount: 0,
      totalRules: 0,
      vectors: 0,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
