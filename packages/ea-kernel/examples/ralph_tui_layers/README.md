# Ralph TUI Independent Layer Profiles (Legacy Path)

This path is kept for backward compatibility.
Canonical system-level layer models now live in:

- `packages/ea-kernel/examples/ea-sys`

This directory stores standalone-valid layer profiles.
Each file is an independently valid `ea-kernel` profile.
There is no merge/composition step.

- `00-infra.toml` - infra layer elements (draft)
- `10-governance.toml` - governance management system for layer registration/version/validation and bid/layer-scoped data partition control
- `20-decision.toml` - decision layer elements/rules (draft, includes context stubs)
- `30-needs.toml` - needs layer elements (draft)
- `40-kernel.toml` - stable baseline (profile metadata, categories, relations, core rules)
- `50-flow.toml` - flow layer elements/rules (draft, includes context stubs)

Layer ordering and control flow:

- Main model order: `infra > decision > needs > kernel > flow`
- `governance` is a management system that controls registration/version/evolution of the layer models and enforces data processing/segregation boundaries.
- Meta/meta-meta definitions and relation vocabulary are defined independently inside each layer profile.
- Infrastructure may define meta-meta contracts (for example DB ports), but governance implements control logic on top of those contracts.

## Validate Layers

Validate all layers:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py
```

Validate one layer:

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --layer infra
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --layer governance
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --layer decision
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --layer needs
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --layer kernel
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --layer flow
```

Run static data-flow simulation (no runtime execution):

```bash
PYTHONPATH=packages/ea-kernel/src uv run python packages/ea-kernel/examples/validate_ralph_tui_layers.py --simulate
```

## Validation Strategy

- Keep `40-kernel.toml` strict and stable.
- Evolve non-kernel fragments incrementally.
- Validate each layer independently after changes.
- Prefer simulation-first checks for data/control consistency before runtime integration.
