"""
Needs Layer for EA System.

This package captures stakeholder needs before decision-making:

- N1 Vocabulary: Immutable types (types.py — Stakeholder, Desire, Justification, NeedStatement, enums)
- N2 Catalog: Aggregate root (catalog.py — Need mutable wrapper, NeedRelation, NeedCatalog)
- N2.5 Modeling: Use-case capture + process-unit modeling + need versioning
- N3 Integration: Kernel bridge and persistence (kernel_bridge.py, repository.py)

Core sentence patterns:
- "A wants to do B, because C" -> Stakeholder + Desire(action, subject) + Justification(BECAUSE)
- "A wants to move B to C, in order to D" -> Stakeholder + Desire(action, subject, target) + Justification(IN_ORDER_TO)
"""

__version__ = "0.1.0"
