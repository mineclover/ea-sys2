# System Port Configuration (Runtime Reference)

This document provides optional runtime port defaults for local development.
Canonical model architecture and layer contracts are defined in:

- `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/README.md`
- `packages/ea-kernel/docs/system_spec_layers.md`

## 1. Governance API (Management Plane Entry)

- **Port**: `9000`
- **Service**: `ea-kernel.api.server`
- **Purpose**: `/models/*` governance-facing model operations and kernel governance APIs.
- **Config**: `EA_KERNEL_PORT=9000`, `EA_KERNEL_DATA_DIR`
- **Launch Command**:
  ```bash
  export EA_KERNEL_DATA_DIR=./governance_data
  export EA_KERNEL_PORT=9000
  python3 -m ea_kernel.api.server
  ```

## 2. Visualization Frontend (Optional)

- **Port**: `5173` (Vite Dev Server)
- **Service**: `web-kernel-viz`
- **Purpose**: Visualizing governance/kernel topology and state.
- **Integration**: `VITE_API_URL=http://localhost:9000`

## 3. Legacy/Optional Services

- `8000` (`ea-metamodel`) is treated as legacy/internal compatibility.
- It is not part of the EA-SYS canonical governance entrypoint contract.

## Integration Notes

1. Route governance-facing API calls to `http://localhost:9000`.
2. Keep port conventions separate from layer model order:
   - model order: `infra > decision > needs > kernel > flow`
   - runtime model entrypoint chain: `decision > needs > kernel > flow`
3. Interpret supporting roles as:
   - `infra`: row data design
   - `governance`: system entrypoint design
4. Governance profile modeling is separated as:
   - meta-meta contract: `packages/ea-kernel/src/ea_kernel/profiles/governance_profile_stack/00-governance-meta-model.toml`
   - ea-sys internal profile: `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/10-governance.toml`
   - external integration profile: `packages/ea-kernel/src/ea_kernel/profiles/governance_profile_stack/20-external-governance.toml`
