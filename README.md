# EA-Sys2

EA System packages centered on kernel-driven formal modeling.

## Packages

| Package | Description |
|---------|-------------|
| `ea-kernel` | Canonical kernel contract and rule model (KerML-inspired core) |
| `ea-kernel-contract` | Python contract snapshot consumer SDK |
| `ea-kernel-contract-ts` | TypeScript contract snapshot consumer SDK (`@ea-sys2/kernel-contract-sdk`) |
| `ea-infra` | Data management and persistence contracts |
| `ea-governance` | Management plane for layer model registration/version/validation/activation |
| `ea-decision` | Decision-flow meta-meta modeling layer |
| `ea-needs` | Use-case and needs modeling layer |
| `ea-flow` | Concrete step/action data-flow modeling and 6x6 contract ownership |

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
