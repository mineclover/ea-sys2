# EA Flow (Layer 4: Data System Definition)

**"The Implementation"**

## Role
`ea-flow` defines the **Data System Specification**—the technical processes, data schemas, and logical flows that implement the reality defined in Layer 3 (`ea-kernel`).
It is orthogonal to the Kernel: while Kernel says "What happens in the business", Flow says "How the software handles it".

## Key Concepts
- **Data-in-Motion**: Defining the shape of data as it moves through the system.
- **Process Specification**: Implementing `StepSpec` and `WorkflowSpec` that realize Kernel processes.
- **System Orthogonality**: A `Flow` is a specific technical implementation of a `Kernel` reality.

## Key Concepts
- **`UseCase`**: A first-class business goal (e.g., "Add Security Rule") mapped to a sequence of steps.
- **`Step`**: The atomic unit of execution, grounding a kernel element.
- **`ExecutionContext`**: State management during process execution.
- **`FlowExecutor`**: The engine responsible for sequence management and automatic **Rollback** on failure.

## Usage
Use Cases are defined in `ea-flow` and executed via `ea-governance` to ensure transactional integrity across the entire system.
