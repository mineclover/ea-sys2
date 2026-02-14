"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.VECTORS_FILE = exports.RULES_FILE = exports.SCHEMA_FILE = exports.EA_KERNEL_CONTRACT_DIR = void 0;
exports.resolveKernelContractDir = resolveKernelContractDir;
exports.resolveKernelContractPaths = resolveKernelContractPaths;
exports.validateKernelContractBundle = validateKernelContractBundle;
exports.loadKernelContractBundle = loadKernelContractBundle;
exports.summarizeKernelContract = summarizeKernelContract;
const node_fs_1 = __importDefault(require("node:fs"));
const node_path_1 = __importDefault(require("node:path"));
exports.EA_KERNEL_CONTRACT_DIR = "EA_KERNEL_CONTRACT_DIR";
exports.SCHEMA_FILE = "kernel_schema.snapshot.json";
exports.RULES_FILE = "kernel_rules.snapshot.json";
exports.VECTORS_FILE = "kernel_judgment_vectors.snapshot.json";
function asRecord(value, context) {
    if (typeof value !== "object" || value === null || Array.isArray(value))
        throw new Error(`${context} must be an object`);
    return value;
}
function requireString(payload, key, context) {
    const value = payload[key];
    if (typeof value !== "string")
        throw new Error(`${context}.${key} must be a string`);
    return value;
}
function requireArray(payload, key, context) {
    const value = payload[key];
    if (!Array.isArray(value))
        throw new Error(`${context}.${key} must be an array`);
    return value;
}
function requireObject(payload, key, context) {
    const value = payload[key];
    if (typeof value !== "object" || value === null || Array.isArray(value))
        throw new Error(`${context}.${key} must be an object`);
    return value;
}
function loadJson(filePath) {
    if (!node_fs_1.default.existsSync(filePath))
        throw new Error(`contract snapshot not found: ${filePath}`);
    const raw = node_fs_1.default.readFileSync(filePath, "utf8");
    return asRecord(JSON.parse(raw), filePath);
}
function resolveKernelContractDir(options) {
    const explicit = options === null || options === void 0 ? void 0 : options.contractDir;
    if (explicit && explicit.trim().length > 0)
        return node_path_1.default.resolve(explicit);
    const fromEnv = process.env[exports.EA_KERNEL_CONTRACT_DIR];
    if (fromEnv && fromEnv.trim().length > 0)
        return node_path_1.default.resolve(fromEnv);
    // Packaged fallback: packages/ea-kernel-contract-ts/contracts
    return node_path_1.default.resolve(__dirname, "..", "contracts");
}
function resolveKernelContractPaths(options) {
    const contractDir = resolveKernelContractDir(options);
    return {
        contractDir,
        schemaPath: node_path_1.default.join(contractDir, exports.SCHEMA_FILE),
        rulesPath: node_path_1.default.join(contractDir, exports.RULES_FILE),
        vectorsPath: node_path_1.default.join(contractDir, exports.VECTORS_FILE),
    };
}
function validateKernelContractBundle(bundle) {
    const issues = [];
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
        const constraintIds = new Set();
        for (const [index, row] of layerConstraints.entries()) {
            const constraint = asRecord(row, `rules.layer_constraints[${index}]`);
            const constraintId = requireString(constraint, "id", `rules.layer_constraints[${index}]`);
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
        const versions = new Set([schemaVersion, rulesVersion, vectorsVersion]);
        if (versions.size > 1)
            issues.push(`kernel_version mismatch across snapshots: ${Array.from(versions).join(", ")}`);
    }
    catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        issues.push(message);
    }
    return issues;
}
function loadKernelContractBundle(options) {
    const paths = resolveKernelContractPaths(options);
    const schema = loadJson(paths.schemaPath);
    const rules = loadJson(paths.rulesPath);
    const vectors = loadJson(paths.vectorsPath);
    const kernelVersion = requireString(schema, "kernel_version", "schema");
    const bundle = {
        kernelVersion,
        paths,
        schema,
        rules,
        vectors,
    };
    if ((options === null || options === void 0 ? void 0 : options.validate) !== false) {
        const issues = validateKernelContractBundle(bundle);
        if (issues.length > 0)
            throw new Error(`invalid kernel contract bundle: ${issues.join("; ")}`);
    }
    return bundle;
}
function summarizeKernelContract(options) {
    var _a, _b, _c, _d, _e;
    try {
        const bundle = loadKernelContractBundle(options);
        const schemaStats = bundle.schema.stats;
        const rulesStats = bundle.rules.stats;
        const vectorsStats = bundle.vectors.stats;
        return {
            available: true,
            contractDir: bundle.paths.contractDir,
            kernelVersion: bundle.kernelVersion,
            entityCount: Number((_a = schemaStats === null || schemaStats === void 0 ? void 0 : schemaStats.entities) !== null && _a !== void 0 ? _a : 0),
            relationCount: Number((_b = schemaStats === null || schemaStats === void 0 ? void 0 : schemaStats.relations) !== null && _b !== void 0 ? _b : 0),
            totalRules: Number((_c = rulesStats === null || rulesStats === void 0 ? void 0 : rulesStats.total_rules) !== null && _c !== void 0 ? _c : 0),
            vectors: Number((_d = vectorsStats === null || vectorsStats === void 0 ? void 0 : vectorsStats.vectors) !== null && _d !== void 0 ? _d : 0),
        };
    }
    catch (error) {
        return {
            available: false,
            contractDir: (_e = process.env.EA_KERNEL_CONTRACT_DIR) !== null && _e !== void 0 ? _e : null,
            kernelVersion: null,
            entityCount: 0,
            relationCount: 0,
            totalRules: 0,
            vectors: 0,
            error: error instanceof Error ? error.message : String(error),
        };
    }
}
