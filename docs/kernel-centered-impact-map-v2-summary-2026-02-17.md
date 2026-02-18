# Kernel-Centered Impact Map v2 Summary (2026-02-17)

## Node Set Changes

- v1 nodes: `['KernelLayer', 'ConstraintSystem', 'KernelModelPort']`
- v2 nodes: `['KernelLayer', 'RequirementConstraintBridge', 'KernelModelPort']`
- change: `ConstraintSystem` -> `RequirementConstraintBridge`

## Core Metrics (v2)

- kernel M1 nodes: `106`
- kernel M1 edges (returned): `1200`
- kernel M1 edges (raw): `3304`
- kernel M1 edge truncated: `True`

## Node Impact Comparison

| Node | Reachable (v1) | Reachable (v2) | Impact both (v1) | Impact both (v2) |
| --- | ---: | ---: | ---: | ---: |
| KernelLayer | 103 | 103 | 103 | 103 |
| KernelModelPort | 0 | 0 | 71 | 71 |
| ConstraintSystem / RequirementConstraintBridge | missing | 75 | missing | 104 |

## Pairwise Paths (max_depth=4, v2)

| Source | Target | Path Count |
| --- | --- | ---: |
| KernelLayer | RequirementConstraintBridge | 28523 |
| KernelLayer | KernelModelPort | 13927 |
| RequirementConstraintBridge | KernelLayer | 0 |
| RequirementConstraintBridge | KernelModelPort | 448 |
| KernelModelPort | KernelLayer | 0 |
| KernelModelPort | RequirementConstraintBridge | 0 |
