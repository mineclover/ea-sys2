# EA Flow (Flow Layer: Data System Definition)

**"The Implementation"**

## Role
`ea-flow` defines the **Data System Specification**: technical processes, data schemas,
and logical flows that implement kernel-grounded reality.
It is orthogonal to the kernel: kernel defines core formal semantics, flow defines
execution/data movement.

## Key Concepts
- **Data-in-Motion**: Defining the shape of data as it moves through the system.
- **Process Specification**: Implementing `StepSpec` and `WorkflowSpec` that realize Kernel processes.
- **System Orthogonality**: A `Flow` is a specific technical implementation of a `Kernel` reality.
- **`Step`**: The atomic unit of execution, grounding a kernel element.
- **`ExecutionContext`**: State management during process execution.
- **`FlowExecutor`**: The engine responsible for sequence management and automatic **Rollback** on failure.
- **`FlowLayerContractMatrix`**: Flow-owned 6x6 cross-layer contract matrix model.

## Usage
Use cases/needs are modeled in `ea-needs`, then transformed into flow specs and
executed through `ea-governance` as the management-plane entrypoint.
