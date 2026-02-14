# EA Governance (Management/Control)

The **Coordination Truth** layer of the EA System.

## Role
`ea-governance` serves as the central orchestrator and control tower. It integrates structure, intelligence, and action into a unified management framework.

## Key Responsibilities
- **Orchestration**: Coordinating `ea-decision` (brain), `ea-flow` (body), and `ea-kernel` (physics) through a unified API.
- **Transaction Management**: Ensuring that changes spanning multiple layers are atomic and consistent.
- **Use Case Execution**: Providing the primary entry point for executing business processes (`UseCase`) through the `GovernanceContainer`.
- **Lifecycle Control**: Tracking the transition of initiatives from proposal to execution.

## Key Concepts
- **`GovernanceContainer`**: The main interface for the horizontal governance system.
- **`TransactionManager`**: Handles the locking, committing, and failing of coordinated actions.
- **`ExecutionService`**: Bridges Use Cases to their corresponding kernel impact.

## Architecture
`ea-governance` manages the other layers without owning their internal logic, ensuring a high degree of modularity and maintainability.
