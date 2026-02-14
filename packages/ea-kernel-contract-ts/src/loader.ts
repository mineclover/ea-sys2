import fs from "node:fs";
import path from "node:path";

import type {
  IContractLoadOptions,
  IContractPaths,
  IKernelContractBundle,
  IKernelContractSummary,
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

function requireString(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): string {
  const value: unknown = payload[key];
  if (typeof value !== "string")
    throw new Error(`${context}.${key} must be a string`);
  return value;
}

function requireArray(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): unknown[] {
  const value: unknown = payload[key];
  if (!Array.isArray(value))
    throw new Error(`${context}.${key} must be an array`);
  return value;
}

function requireObject(
  payload: Record<string, unknown>,
  key: string,
  context: string,
): Record<string, unknown> {
  const value: unknown = payload[key];
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new Error(`${context}.${key} must be an object`);
  return value as Record<string, unknown>;
}

function loadJson(filePath: string): Record<string, unknown> {
  if (!fs.existsSync(filePath))
    throw new Error(`contract snapshot not found: ${filePath}`);
  const raw = fs.readFileSync(filePath, "utf8");
  return asRecord(JSON.parse(raw), filePath);
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

export function validateKernelContractBundle(
  bundle: IKernelContractBundle,
): string[] {
  const issues: string[] = [];

  try {
    const schemaKind = requireString(bundle.schema, "snapshot_kind", "schema");
    const schemaVersion = requireString(bundle.schema, "kernel_version", "schema");
    requireObject(bundle.schema, "stats", "schema");
    requireArray(bundle.schema, "entities", "schema");

    if (schemaKind !== "ea_kernel_schema_contract")
      issues.push(`schema.snapshot_kind unexpected: ${schemaKind}`);

    const rulesKind = requireString(bundle.rules, "snapshot_kind", "rules");
    const rulesVersion = requireString(bundle.rules, "kernel_version", "rules");
    requireObject(bundle.rules, "stats", "rules");
    requireArray(bundle.rules, "explicit_rules", "rules");
    requireArray(bundle.rules, "fallback_rules", "rules");
    const layerConstraints = requireArray(bundle.rules, "layer_constraints", "rules");

    const constraintIds = new Set<string>();
    for (const [index, row] of layerConstraints.entries()) {
      const constraint = asRecord(row, `rules.layer_constraints[${index}]`);
      const constraintId = requireString(
        constraint,
        "id",
        `rules.layer_constraints[${index}]`,
      );
      if (constraintIds.has(constraintId))
        issues.push(`rules.layer_constraints.id duplicated: ${constraintId}`);
      constraintIds.add(constraintId);
    }

    if (rulesKind !== "ea_kernel_rules_contract")
      issues.push(`rules.snapshot_kind unexpected: ${rulesKind}`);

    const vectorsKind = requireString(bundle.vectors, "snapshot_kind", "vectors");
    const vectorsVersion = requireString(bundle.vectors, "kernel_version", "vectors");
    requireObject(bundle.vectors, "stats", "vectors");
    requireArray(bundle.vectors, "vectors", "vectors");
    if (vectorsKind !== "ea_kernel_judgment_vectors_contract")
      issues.push(`vectors.snapshot_kind unexpected: ${vectorsKind}`);

    const versions = new Set<string>([schemaVersion, rulesVersion, vectorsVersion]);
    if (versions.size > 1)
      issues.push(
        `kernel_version mismatch across snapshots: ${Array.from(versions).join(", ")}`,
      );
  } catch (error) {
    const message: string =
      error instanceof Error ? error.message : String(error);
    issues.push(message);
  }

  return issues;
}

export function loadKernelContractBundle(
  options?: IContractLoadOptions,
): IKernelContractBundle {
  const paths = resolveKernelContractPaths(options);
  const schema = loadJson(paths.schemaPath);
  const rules = loadJson(paths.rulesPath);
  const vectors = loadJson(paths.vectorsPath);
  const kernelVersion = requireString(schema, "kernel_version", "schema");
  const bundle: IKernelContractBundle = {
    kernelVersion,
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

export function summarizeKernelContract(
  options?: IContractLoadOptions,
): IKernelContractSummary {
  try {
    const bundle = loadKernelContractBundle(options);
    const schemaStats = bundle.schema.stats as Record<string, unknown> | undefined;
    const rulesStats = bundle.rules.stats as Record<string, unknown> | undefined;
    const vectorsStats = bundle.vectors.stats as Record<string, unknown> | undefined;

    return {
      available: true,
      contractDir: bundle.paths.contractDir,
      kernelVersion: bundle.kernelVersion,
      entityCount: Number(schemaStats?.entities ?? 0),
      relationCount: Number(schemaStats?.relations ?? 0),
      totalRules: Number(rulesStats?.total_rules ?? 0),
      vectors: Number(vectorsStats?.vectors ?? 0),
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
