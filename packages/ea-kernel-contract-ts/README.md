# @ea-sys2/kernel-contract-sdk

TypeScript SDK package for deterministic `ea-kernel` contract snapshots.

## What It Provides

- Snapshot loader for:
  - `kernel_schema.snapshot.json`
  - `kernel_rules.snapshot.json`
  - `kernel_judgment_vectors.snapshot.json`
- Bundle shape validation (including `layer_constraints[].id` uniqueness)
- Summary helper for backend diagnostics

## Directory Resolution Order

1. `options.contractDir`
2. `EA_KERNEL_CONTRACT_DIR` environment variable
3. packaged fallback: `contracts/`

## Build

```bash
pnpm --dir packages/ea-kernel-contract-ts run build
```

This build automatically syncs latest snapshots from:

`packages/ea-kernel/docs/reference/contracts`

## Usage

```ts
import { loadKernelContractBundle } from "@ea-sys2/kernel-contract-sdk";

const bundle = loadKernelContractBundle();
console.log(bundle.kernelVersion);
```

## Consume From `ea-web`

For local cross-repo development, add a file dependency in `ea-web`:

```json
{
  "dependencies": {
    "@ea-sys2/kernel-contract-sdk": "file:/Users/junwoobang/workflow/ea-sys2/packages/ea-kernel-contract-ts"
  }
}
```
