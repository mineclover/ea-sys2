# EA Governance (Management/Control)

The **Coordination Truth** layer of the EA System.

## Role
`ea-governance` is the management-plane entrypoint for layer model control.
It does not define each layer's meta/meta-meta semantics, but manages registration,
versioning, validation, activation, transaction history, and cross-layer routing.

## Key Responsibilities
- **Orchestration**: Coordinating `ea-infra`, `ea-decision`, `ea-needs`, `ea-kernel`, and `ea-flow` through a unified API.
- **Transaction Management**: Ensuring that changes spanning multiple layers are atomic and consistent.
- **Layer Data Management**: Owning DB-backed persistence adapters (e.g., `ea-needs` catalog storage).
- **Change History**: Recording DB-backed layer changes as transaction events for traceability.
- **Use Case Execution**: Providing the primary entry point for executing business processes (`UseCase`) through the `GovernanceContainer`.
- **Lifecycle Control**: Tracking the transition of initiatives from proposal to execution.

## Key Concepts
- **`GovernanceContainer`**: The main interface for the horizontal governance system.
- **`TransactionManager`**: Handles the locking, committing, and failing of coordinated actions.
- **`ExecutionService`**: Bridges Use Cases to their corresponding kernel impact.

## Architecture
`ea-governance` manages other layers without owning their internal modeling logic,
preserving independent layer responsibility.

- Main model order: `infra > decision > needs > kernel > flow`
- Runtime model entrypoint chain: `decision > needs > kernel > flow`
- `infra`: row data design responsibility
- `governance`: system entrypoint design responsibility

## Needs Governance APIs
- `create_needs_catalog`
- `add_needs_stakeholder`
- `add_needs_use_case`
- `express_need_in_catalog`
- `revise_need_in_catalog`
- `add_need_process_unit`
- `inherit_need_decision_evidence`
- `get_needs_catalog_history`

## Kernel Governance APIs
- `submit_kernel_rule`
- `approve_kernel_rule`
- `reject_kernel_rule`
- `deprecate_kernel_rule`
- `evaluate_kernel`
- `create_kernel_snapshot`
- `list_kernel_rules`
- `list_kernel_versions`
- `get_kernel_promotion_proposals`
- `simulate_kernel_proposal`
- `get_kernel_rule_snapshot`
- `get_kernel_judgment_snapshot`
- `get_kernel_corpus_version_snapshot`

## Layer-Scoped Store APIs
- `save_layer_snapshot`
- `get_layer_snapshot`
- `list_layer_snapshots`

Each layer (`infra/governance/decision/needs/kernel/flow`) is backed by its own store instance and DB file under governance data.

## Ops Event API Docs
- Canonical spec + runbook:
  - `packages/ea-governance/docs/ops-events-api-runbook.md`
- Lineage replay focused reference:
  - `packages/ea-governance/docs/ops-lineage-replay-api.md`
