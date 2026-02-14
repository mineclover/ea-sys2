# System Evolution Proposal: From Tool to Engine

Based on the completion of the `Core Structure (Kernel)`, `Decision Narrative (Brain)`, and `Execution Logic (Flow)`, this proposal outlines three critical agendas for evolving the system into a robust, autonomous "Living Governance Engine".

## Core Premise: ea-flow as ea-kernel's Data & Process Layer

`ea-flow` is **not** an independent execution engine — it is structurally dependent on `ea-kernel`. The relationship is:

- **ea-kernel** = Conceptual Modeling (what entities, relationships, and behavioral structures can exist)
- **ea-flow** = Data & Process Modeling (concrete data definitions and process execution grounded in ea-kernel's model)

Every expression in `ea-flow` — whether it represents a data object, a processing step, or an entire workflow — **must correspond to ea-kernel representations**. This is the foundational constraint: the kernel defines the vocabulary, and flow speaks it.

### Granularity Mapping

The mapping between ea-kernel and ea-flow is not necessarily 1:1:

1. **1:1 with Parameters**: When ea-kernel's `Step`/`Action` is already a sufficient abstraction, ea-flow adds only the concrete parameters (input data schema, output target, execution config) without introducing new structural elements.
2. **1:N Decomposition**: When a single ea-kernel edge (e.g., a `flow` or `succession`) represents a conceptually atomic relationship but requires multiple concrete operations, ea-flow decomposes it into a sequence of finer-grained steps — each still traceable back to the originating kernel element.

```
ea-kernel (Conceptual)          ea-flow (Concrete)
┌────────────────────┐          ┌──────────────────────────────┐
│ Step A ──flow──→ B │    →     │ Step A                       │
│   (single edge)    │          │   ├─ flow-1: extract(params) │
│                    │          │   ├─ flow-2: transform(spec) │
│                    │          │   └─ flow-3: load(target)    │
│                    │          │ → Step B                     │
└────────────────────┘          └──────────────────────────────┘
```

---

## 1. Scope: Kernel-Grounded Execution

**Agenda**: Defining ea-flow's operational scope as an extension of ea-kernel's behavioral model.

### Current State
- `ea-flow` is implemented primarily for **Meta-Ops** (modifying the Governance Kernel itself, e.g., Adding Rules).
- Flow definitions use independent abstractions (`Step` ABC, `Workflow` ABC) that do not yet reference ea-kernel's L3/L4 behavioral types.

### Proposal: Kernel-Anchored Flow

1. **Phase 1 (Current → Consolidation)**: Align existing governance automation with ea-kernel's behavioral metamodel.
    - Map ea-flow's `Step` to ea-kernel's `step`/`action` (L4 Concrete).
    - Map ea-flow's sequential step ordering to ea-kernel's `succession` (L3 Behavioral).
    - Ensure every flow definition is traceable to a kernel graph structure.

2. **Phase 2 (Extension)**: Expand to **Domain Data & Process Modeling**.
    - Define data pipelines where the *process topology* is described in ea-kernel and the *concrete parameters & data schemas* are specified in ea-flow.
    - ea-kernel remains the **map**; ea-flow becomes the **detailed route instructions** for navigating that map.
    - A single kernel `flow` edge may expand into an ea-flow workflow with multiple parameterized steps.

---

## 2. Autonomy: Policy-Driven Decision Engine

**Agenda**: Defining the locus of control for AI autonomy.

### Current State
- `ea-decision` relies on explicit human input for finalized `DesignReport`s.

### Proposal: Brain vs. Body

1. **Policy in `ea-decision` (The Brain)**:
    - **Fast-Track Policy**: Define rules within `ea-decision` that allow skipping full human review (e.g., "Tag Updates with confidence > 90% are auto-approved").
    - **AI Drafting**: The `Brain` automatically generates `Topics` and drafts `Options`.

2. **Concrete Logic in `ea-flow` (The Body)**:
    - **Kernel-Grounded Specification**: Defines *how* data should be processed, using ea-kernel's behavioral types as the structural frame and attaching concrete parameters:
        - **Multi-format Schemas**: Supports **JSON Schema 2020-12**, **Database Schemas (DDL)**, and other extensible formats (e.g., Protobuf, GraphQL) to define data at rest and in motion.
        - **Transformation Rules**: Logical mapping and validation specs anchored to kernel edges.
    - **Decomposition Authority**: ea-flow may decompose a single ea-kernel edge into multiple operational steps, but each must remain traceable to the kernel origin.
    - **Separation of Concerns**: ea-kernel = "What exists and how it connects"; ea-flow = "What data flows through and how it's processed"; External Engine = "The runtime that executes it".

---

## 3. Atomicity: Transactional Integrity

**Agenda**: Ensuring system consistency during `ModelingAction` execution.

### Current State
- `SimpleFlowExecutor` runs steps sequentially. Failure in Step N creates a "partial state" (Steps 1..N-1 applied, subsequent steps failed).

### Proposal: Saga Pattern / Rollback
1. **Transaction Scope**: Introduce `Transaction` context in `ea-governance`.
2. **Compensating Actions**: Require every `Step` implementation in `ea-flow` to define a `rollback()` method.
3. **Automatic Rollback**: If execution fails, `ExecutionService` automatically triggers the reverse workflow to restore `ea-kernel` to its pre-decision state, ensuring the system never remains in an inconsistent "limbo".
4. **Kernel Consistency Invariant**: Since ea-flow is grounded in ea-kernel, rollback must restore not just data state but also the kernel graph to a consistent topology — no dangling edges, no orphaned decompositions.

---

## Conclusion

The fundamental insight is that **ea-flow is not parallel to ea-kernel but built on top of it**. ea-kernel provides the conceptual vocabulary (entities, relationships, behavioral structures), and ea-flow provides the concrete operational semantics (data definitions, process parameters, execution sequences). Adopting these proposals will transition the system from a **"Passive Record"** to an **"Active, Kernel-Grounded Governance Engine"** where the model doesn't just describe — it drives.
