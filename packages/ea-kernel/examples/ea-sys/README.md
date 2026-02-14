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
