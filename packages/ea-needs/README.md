# ea-needs

Needs Layer for EA System — Stakeholder Desires & Justifications.

Captures stakeholder needs as structured expressions before decision-making (ea-decision).

## Core Pattern

```
"A wants to do B, because C"
 → Stakeholder + Desire(action, subject) + Justification(BECAUSE)

"A wants to move B to C, in order to D"
 → Stakeholder + Desire(action, subject, target) + Justification(IN_ORDER_TO)
```

## Dependencies

- `ea-kernel` (foundation)
