"""
Needs Layer for EA System.

This package captures stakeholder needs before decision-making:

- N1 Vocabulary: Immutable types (types.py — Stakeholder, Desire, Justification, NeedStatement, enums)
- N2 Catalog: Aggregate root (catalog.py — Need mutable wrapper, NeedRelation, NeedCatalog)
- N2.5 Schema: Needs-layer schema + condition vocabulary (needs_schema.py, condition_registry.py)
- N2.5 Modeling: Use-case capture + process-unit modeling + need versioning
- N3 Integration: Kernel bridge, profile bridge, persistence (kernel_bridge.py, profile_bridge.py, repository.py)

Core sentence patterns:
- "A wants to do B, because C" -> Stakeholder + Desire(action, subject) + Justification(BECAUSE)
- "A wants to move B to C, in order to D" -> Stakeholder + Desire(action, subject, target) + Justification(IN_ORDER_TO)
"""

from ea_needs.ops_feedback import NeedsFeedbackDraft, build_needs_feedback_draft

__all__ = [
    "NeedsFeedbackDraft",
    "build_needs_feedback_draft",
]

__version__ = "0.1.0"
