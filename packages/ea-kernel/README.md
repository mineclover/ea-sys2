# EA Kernel (Layer 3: Realistic System Definition)

**"The Reality"**

## Role
`ea-kernel` defines the **Realistic System**—the business processes and structural entities as they essentially exist in the real world. It provides the "Ontology" or "Physics" of the domain.
This is distinct from the *Data System* (Layer 4), which is merely an implementation of this reality.

## Key Responsibilities
- **Reality Modeling**: Defining "What Is" (Entities) and "How it Happens in Reality" (Business Processes).
- **Structural Integrity**: Providing the invariants that the data system must respect.
- **Judgment Logic**: Evaluating whether the system state matches the defined reality.
- **Diagramming**: Projecting the business reality into visual representations.

## Key Concepts
- **`KernelSystem`**: The main entry point for interacting with the structural layer.
- **`RuleCorpus`**: The collection of all structural truths and invariants.
- **`TopologyGraph`**: A graph-based projection of the kernel for visualization.

## Relationship
`ea-kernel` provides the anchor points for `ea-flow` (actions) and `ea-decision` (intent), ensuring that all behavioral and strategic changes are structurally valid.
