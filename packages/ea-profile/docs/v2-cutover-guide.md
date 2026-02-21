# ea-profile v2 Cutover Guide

This guide defines the migration path from legacy `KernelProfile`/`LayerStack` fields to the
canonical `ea_profile.v2.TypeSystemSpec` model.

## Scope

- Legacy layer flow strings (`definition_flow`, `runtime_flow`, `feedback_flow`) migrate to
  `FlowEdgeSpec` entries.
- Legacy profile loading into v2 remains supported temporarily through compatibility adapters.
- Legacy compatibility paths emit a deprecation warning.

## Recommended Cutover Phases

1. Baseline
- Keep writing legacy profile TOML/JSON as-is.
- Add a migration check in CI that converts to v2 and validates the output.

2. Dual-Read / v2 Validation
- Convert legacy profile objects with `legacy_profile_to_type_system(...)`.
- Fix validation gaps surfaced by v2 constraints (IDs, enum values, transition references).
- Keep legacy profile artifacts as source-of-truth during this phase.

3. Flow-Field Migration
- Replace string-based `LayerStack` flow interpretation with explicit `FlowEdgeSpec` generation.
- Use `flow_edges_from_legacy_flows(...)` to produce deterministic edge chains from legacy flow
  strings.

4. Final Cutover
- Persist and transport `TypeSystemSpec` directly (dict/json via `ea_profile.v2.serializer`).
- Remove dependence on legacy-only fields and contracts.

## Compatibility APIs

- `legacy_profile_to_type_system(...)`
  - Converts legacy profile aggregate to `TypeSystemSpec`.
  - Emits deprecation diagnostics for legacy loading paths.
- `flow_edges_from_legacy_flows(...)`
  - Converts legacy flow strings to canonical `FlowEdgeSpec` tuples.
  - Supported separators: `->`, `>`, `,`.

## Minimal Migration Example

```python
from ea_profile.v2.adapters import flow_edges_from_legacy_flows, legacy_profile_to_type_system

spec = legacy_profile_to_type_system(legacy_profile)

edges = flow_edges_from_legacy_flows(
    definition_flow="Infra -> Governance -> Decision",
    runtime_flow="Infra > Kernel > Flow",
    feedback_flow="Projection, Decision",
)
```

## Verification

- Golden conversion test:
  - `packages/ea-profile/tests/test_v2_types.py::test_v2_legacy_flow_migration_matches_golden`
- Story-scoped test command:
  - `uv run pytest packages/ea-profile/tests/test_v2_types.py`
