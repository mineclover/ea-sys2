# Ralph TUI Independent Layer Profiles

This directory stores standalone-valid layer profiles.
Each file is an independently valid `ea-kernel` profile.
There is no merge/composition step.

- `00-infra.toml` - infra layer elements (draft)
- `10-governance.toml` - governance layer elements/rules (draft, includes context stubs)
- `20-decision.toml` - decision layer elements/rules (draft, includes context stubs)
- `30-needs.toml` - needs layer elements (draft)
- `40-kernel.toml` - stable baseline (profile metadata, categories, relations, core rules)
- `50-flow.toml` - flow layer elements/rules (draft, includes context stubs)

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

## Validation Strategy

- Keep `40-kernel.toml` strict and stable.
- Evolve non-kernel fragments incrementally.
- Validate each layer independently after changes.
