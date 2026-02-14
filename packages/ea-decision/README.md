# ea-decision (Layer 2: Decision/Intent)

**"The Brain"**

`ea-decision` captures the **Design Thinking process**—the thoughts, ideas, rationale, and strategic intent that drive the system's evolution.
This layer provides the "Why" behind the "What" (Kernel) and "How" (Flow).

## Role in Architecture

While `ea-kernel` acts as the **Executive** (enforcing rules), `ea-decision` acts as the **Research Lab & Archives** (explaining why rules exist).

- **ea-kernel**: Enforces "No direct database access from frontend." (Rule)
- **ea-decision**: Provides the full context:
    1.  **Research**: "Direct access causes security risks (CVE-...)."
    2.  **Options**: "API Gateway vs. Direct Access vs. GraphQL."
    3.  **Evaluation**: "API Gateway offers best security governance."
    4.  **Decision**: "Adopt API Gateway pattern."

## Workflow: Grounds > Process > Plan > Action

The package supports a structured workflow that bridges abstract thinking and concrete modeling:

1.  **Diverge (Grounds)**
    - **Research**: Gather facts, references, and existing patterns.
    - **Questions**: Log inquiries to stakeholders.
    - **Options**: Define potential solutions.

2.  **Converge (Process)**
    - **Evaluate**: Assess options against criteria.
    - **Select**: Choose the best option based on evidence.

3.  **Plan (Report)**
    - **DesignReport**: A formal document consolidating the Decision and the Implementation Plan.
    - **ModelingActions**: Specific tasks defined in the report (e.g., "Create Rule X", "Deprecate Entity Y").

4.  **Action (Modeling)**
    - The `ea-kernel` changes are executed based on the `ModelingActions` defined in the Report.

## Data Model

- **Topic**: Grouping container for a specific design problem.
- **ResearchNote**: Raw data (Grounds).
- **Option / Evaluation**: Alternatives and analysis.
- **DesignReport**: The formalized output containing:
    - **DesignDecision**: The "Why" and "What".
    - **ModelingAction**: The "How" (Execution steps).

## Persistence

All artifacts are persisted as JSON in a structured repository (`Topic`), serving as the **Reference** for all downstream modeling.

