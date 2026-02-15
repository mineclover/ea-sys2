# @ea-sys2/kernel-contract-sdk

TypeScript SDK for deterministic `ea-kernel` contract snapshots.

## What It Provides

- Snapshot loader for:
  - `kernel_schema.snapshot.json`
  - `kernel_rules.snapshot.json`
  - `kernel_judgment_vectors.snapshot.json`
- Strict shape and integrity validation:
  - snapshot kind / kernel version consistency
  - unique ids and names
  - schema-reference integrity (rules, roles, layer constraints, vectors)
- Prebuilt runtime index for fast lookup in Nestia/backends
- Deterministic contract fingerprint (`sha256`) for cache/version checks
- Built-in relationship evaluation (`source/target/relation`) with:
  - layer constraint enforcement
  - winner rule resolution
  - condition evaluation trace
- Feedback-target utilities for canonical governance ids
- Decision-trace contract typings for `/models/decisions/*` responses
  - `IDecisionTraceContract`, `IDecisionTraceExploration`

## Directory Resolution Order

1. `options.contractDir`
2. `EA_KERNEL_CONTRACT_DIR` environment variable
3. packaged fallback: `contracts/`

## Build

```bash
pnpm --dir packages/ea-kernel-contract-ts run build
```

This build automatically syncs latest snapshots from:

`packages/ea-kernel/docs/reference/contracts`

## Usage

```ts
import {
  buildLayerContractConvention,
  buildManagedLayerContractConventions,
  buildLayerContractModel,
  buildKernelContractModel,
  evaluateKernelRelationship,
  getEntityRequiredKeys,
  resolveKernelFeedbackTarget,
} from "@ea-sys2/kernel-contract-sdk";

const model = buildKernelContractModel();
const required = getEntityRequiredKeys(model, "structure");
const target = resolveKernelFeedbackTarget(
  "layer_constraint:lc-00-l4-l4-association",
  model,
);

console.log(model.bundle.kernelVersion);
console.log(model.fingerprint);
console.log(required);
console.log(target.canonicalId);

const verdict = evaluateKernelRelationship(model, {
  sourceEntity: "structure",
  targetEntity: "structure",
  relation: "association",
});
console.log(verdict.allowed, verdict.winnerRuleId);

const layerConvention = buildLayerContractConvention("decision");
console.log(layerConvention.tsPackageName);

const managedConventions = buildManagedLayerContractConventions();
console.log(managedConventions.map((row) => row.layerId));

const decisionModel = buildLayerContractModel([
  {
    layerId: "decision",
    explicitRules: [
      {
        id: "allow-event-trigger-structure",
        source_pattern: "event",
        target_pattern: "structure",
        relation: "triggering",
        valid: true,
        priority: 95,
        conditions: [],
        notes: "Decision-layer override example",
      },
    ],
  },
]);
console.log(decisionModel.fingerprint);
```

## Feedback Canonical IDs

- `entity_type:{entityName}`
- `relation_type:{relationName}`
- `rule:{ruleId}`
- `layer_constraint:{constraintId}`

## Layer Package Convention

Use the same filenames per package (`contracts/` inside each layer package):

- `kernel_schema.snapshot.json`
- `kernel_rules.snapshot.json`
- `kernel_judgment_vectors.snapshot.json`

Recommended package names:

- TS: `@ea-sys2/<layer>-contract-sdk`
- Python: `ea-<layer>-contract`

Use namespaced ids for layer overlays by default:

- rule id: `<layer>:<rule_id>`
- layer constraint id: `<layer>:<constraint_id>`

## Consume From `ea-web`

Use workspace consumption (recommended in mono/submodule setup):

```json
{
  "dependencies": {
    "@ea-sys2/kernel-contract-sdk": "workspace:*"
  }
}
```
