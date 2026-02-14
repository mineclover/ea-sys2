# EA System Independent Layer Profiles

This directory is the canonical location for system-level layer models.
Each file is an independently valid `ea-kernel` profile.
There is no merge/composition step.

All six layers share kernel category/relation vocabulary, but each file models a different responsibility and implementation focus.
Policy/constraint ownership is also layer-local: each layer defines and manages its own control semantics.

- `00-infra.toml` - data management and persistence contracts
- `10-governance.toml` - registration/version/validation/change control across layers
- `20-decision.toml` - decision-flow meta-meta model (vocabulary/schema/state/activity structure)
- `30-needs.toml` - use-case, constraint, and prioritized-needs definition
- `40-kernel.toml` - canonical kernel contract and rule model
- `50-flow.toml` - concrete step/action data-flow model

Main model order:

- `infra > decision > needs > kernel > flow`

Governance role:

- Governance manages meta-meta/meta/instance control for all layer models.
- Infra may define control contracts/ports, while governance implements control workflows on top.
- Runtime/API entrypoint convention uses governance as the single layer gateway:
  - `infra > governance > decision > needs > kernel > flow`
  - requests enter via `GovernanceEntryPort` and are routed to layer-specific model ports.
- Governance also models `/models/*` API as explicit endpoint contracts:
  - endpoints: `ModelRegisterEndpoint`, `ModelValidateEndpoint`, `ModelActivateEndpoint`, `ModelStateEndpoint`
  - records: request/response/error/transaction contracts are modeled as passive structures in `10-governance.toml`

## Validate Layers

Validate all layers:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ea_sys_layers.py
```

Validate one layer:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ea_sys_layers.py --layer governance
```

Run static data-flow simulation (no runtime execution):

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ea_sys_layers.py --simulate
```

Simulation includes:

- governance entrypoint contract check
- governance model API contract check (`/models/*` endpoint/record flow)
- 6x6 delegated contract check (`ea-flow` owns matrix/coordination, other layers keep port declarations)
