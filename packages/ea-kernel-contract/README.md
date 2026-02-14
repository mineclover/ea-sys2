# ea-kernel-contract

`ea-kernel-contract` loads deterministic `ea-kernel` contract snapshots and provides
runtime utilities for governance/backend consumers.

Default snapshot source:
- `packages/ea-kernel/docs/reference/contracts`

Snapshot files:
1. `kernel_schema.snapshot.json`
2. `kernel_rules.snapshot.json`
3. `kernel_judgment_vectors.snapshot.json`

## What It Provides

- Contract bundle loading + strict shape/integrity validation
- Deterministic fingerprint (`sha256`) for cache/version checks
- Indexed contract model (`entity/rule/relation/layer_constraint` lookups)
- Relationship evaluator (`source/target/relation`)
  - layer constraint enforcement
  - winner rule resolution
  - condition-level diagnostics
- Feedback target canonicalization/resolution
  - `entity_type:*`, `relation_type:*`, `rule:*`, `layer_constraint:*`
- Governance layer catalog utilities based on
  `kernel_governance_reference_v1.snapshot.json`
  - expected managed layers: `infra`, `decision`, `needs`, `kernel`, `flow`

## Quick usage

```python
from ea_kernel_contract import (
    build_contract_model,
    evaluate_relationship,
    resolve_feedback_target,
)

model = build_contract_model()
print(model.bundle.kernel_version)
print(model.fingerprint)

result = evaluate_relationship(model, "structure", "structure", "association")
print(result.allowed, result.winner_rule_id)

target = resolve_feedback_target("layer_constraint:lc-00-l4-l4-association", model)
print(target.canonical_id)
```

## Governance layer catalog (5 managed layers)

```python
from ea_kernel_contract import (
    build_governance_layer_catalog,
    validate_governance_layer_catalog,
)

catalog = build_governance_layer_catalog()
issues = validate_governance_layer_catalog(catalog)
print(catalog.managed_layers)
print(issues)
```

Optional environment overrides:

```bash
export EA_KERNEL_CONTRACT_DIR=/path/to/contracts
export EA_KERNEL_GOVERNANCE_REFERENCE_PATH=/path/to/kernel_governance_reference_v1.snapshot.json
```

## TypeScript SDK Supply

This repo also ships a TypeScript SDK package:
- `packages/ea-kernel-contract-ts` (`@ea-sys2/kernel-contract-sdk`)

Sync and verify packaged snapshot contracts:

```bash
make sync-kernel-contract-ts-sdk
make verify-kernel-contract-ts-sdk
```
