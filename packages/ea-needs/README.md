# ea-needs

Needs Layer for EA System — Stakeholder Desires & Justifications.

Captures stakeholder needs as structured expressions before decision-making (ea-decision).

Core capabilities:

- use-case collection and linkage to needs
- need identity + lineage versioning (`id`, `lineage_id`, `version`)
- decision evidence inheritance (`inherit_decision_evidence`)
- process-unit modeling for need work stages (`identify`, `query`, `model_detail`)
- JSON persistence in-core (`NeedRepository`)
- DB-backed persistence via governance layer

## Core Pattern

```
"A wants to do B, because C"
 → Stakeholder + Desire(action, subject) + Justification(BECAUSE)

"A wants to move B to C, in order to D"
 → Stakeholder + Desire(action, subject, target) + Justification(IN_ORDER_TO)
```

## Dependencies

- `ea-kernel` (foundation)
