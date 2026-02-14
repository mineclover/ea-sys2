# Layer Contract Package Convention

This convention standardizes how layer-specific contract packages (infra, decision,
needs, kernel, flow) are produced and consumed in both Python and TypeScript.

## Managed Layers

- `infra`
- `decision`
- `needs`
- `kernel`
- `flow`

## Package Naming

- TypeScript: `@ea-sys2/<layer>-contract-sdk`
- Python: `ea-<layer>-contract`

## Snapshot Layout (per package)

Each package must include a `contracts/` directory with the same file names:

- `kernel_schema.snapshot.json`
- `kernel_rules.snapshot.json`
- `kernel_judgment_vectors.snapshot.json`

## ID Namespacing Rules

When composing layer overlays on top of base kernel contracts:

- Rule ID: `<layer>:<rule_id>`
- Layer constraint ID: `<layer>:<constraint_id>`
- Vector ID (optional merge): `<layer>:<vector_id>`

This prevents collisions when multiple layer packages are merged.

## Fallback Rule Merge Rule

Fallback rules are unique per relation. During composition:

- If layer package defines fallback for an existing relation,
  replace base fallback for that relation.
- Final bundle must contain only one fallback rule per relation.

## Validation Requirements

A composed bundle must pass all of:

- snapshot kind / version consistency
- unique entity/relation/rule/layer-constraint/vector ids
- schema-reference integrity
- rules/vectors/stats count consistency

## Consumer APIs

- TypeScript (`@ea-sys2/kernel-contract-sdk`):
  - `buildLayerContractConvention(layerId)`
  - `composeKernelContractBundle(baseBundle, overlays, options)`
  - `composeKernelContractModel(baseModel, overlays, options)`
  - `buildLayerContractModel(overlays, options)`

- Python (`ea-kernel-contract`):
  - `build_governance_layer_catalog(...)`
  - `validate_governance_layer_catalog(...)`

## Governance Coverage Requirement

Governance-managed layer coverage is valid only when all expected managed layers
are present:

- `infra`, `decision`, `needs`, `kernel`, `flow`
