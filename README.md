# EA-Sys2

EA System - Kernel, Decision, Flow, Governance & Infrastructure packages.

## Packages

| Package | Description |
|---------|-------------|
| `ea-kernel` | Lightweight kernel metamodel (KerML-inspired), zero dependency |
| `ea-decision` | Decision layer - Design Thinking & Intent Management |
| `ea-flow` | Execution Flows & Automation |
| `ea-governance` | Governance integration - Unifies Kernel, Decision, Flow |
| `ea-infra` | Infrastructure - Resource Indexing & Vector Store |

## Frontend

| App | Description |
|-----|-------------|
| `web-kernel-viz` | Kernel topology visualization (Vite + React + XYFlow) |

## Setup

```bash
uv sync
```

## Testing

```bash
make test          # all packages
make test-kernel   # ea-kernel only
```
