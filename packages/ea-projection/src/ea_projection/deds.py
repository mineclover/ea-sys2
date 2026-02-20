"""DEDS (Decision-Embedded Depth Structure) vocabulary constants.

7-component metamodel vocabulary for projection enrichment:
  Surface, DepthLevel, DecisionGate, Element, Relation, DepthPolicy, TraversalPath.

Internal to ea-projection — stdlib only.
"""

from __future__ import annotations

from enum import StrEnum


class DepthSemantic(StrEnum):
    """Semantic meaning of a depth level in the DEDS metamodel."""

    EXISTENCE = "existence"
    INSTANCE = "instance"
    CONFIGURATION = "configuration"
    EXECUTION = "execution"
    TRACE = "trace"


class GateType(StrEnum):
    """Decision gate classification types."""

    QUALITY = "quality"
    LIFECYCLE = "lifecycle"
    APPROVAL = "approval"
    EVIDENCE = "evidence"
    PROMOTION = "promotion"


# ── DepthLevel DEDS mappings ──────────────────────────────────────

DEPTH_LEVEL_SEMANTIC: dict[str, DepthSemantic] = {
    "l0": DepthSemantic.EXISTENCE,
    "l1": DepthSemantic.INSTANCE,
    "l2": DepthSemantic.CONFIGURATION,
    "l3": DepthSemantic.EXECUTION,
    "l4": DepthSemantic.TRACE,
}

DEPTH_LEVEL_ENTRY_QUESTION: dict[str, str] = {
    "l0": "What structural boundaries exist in this domain?",
    "l1": "What capabilities and instances are arranged here?",
    "l2": "How are actor interactions configured?",
    "l3": "How do steps and actions execute?",
    "l4": "What decisions and data drive this execution?",
}

DEPTH_LEVEL_ENTRY_INTENT: dict[str, str] = {
    "l0": "orientation",
    "l1": "capability_survey",
    "l2": "interaction_map",
    "l3": "execution_trace",
    "l4": "decision_evidence",
}

# ── Relation depth semantics ─────────────────────────────────────

RELATION_DEPTH_SEMANTIC: dict[str, DepthSemantic] = {
    # structural (L0 existence)
    "contains": DepthSemantic.EXISTENCE,
    "depends_on": DepthSemantic.EXISTENCE,
    "next": DepthSemantic.EXECUTION,
    # causal (L3 execution)
    "triggers": DepthSemantic.EXECUTION,
    "constrains": DepthSemantic.EXECUTION,
    # operational (L4 trace)
    "produces": DepthSemantic.TRACE,
    "consumes": DepthSemantic.TRACE,
    "coordinates": DepthSemantic.CONFIGURATION,
    # self_description (L1 instance)
    "registers": DepthSemantic.INSTANCE,
    "available_in": DepthSemantic.INSTANCE,
    # inheritance_meta (L0 existence)
    "specialization": DepthSemantic.EXISTENCE,
    "redefinition": DepthSemantic.EXISTENCE,
    "subsetting": DepthSemantic.EXISTENCE,
    "feature_typing": DepthSemantic.EXISTENCE,
}

# ── Gate classification ──────────────────────────────────────────

GATE_NAME_PATTERNS: dict[str, GateType] = {
    "quality": GateType.QUALITY,
    "qualitygate": GateType.QUALITY,
    "lifecycle": GateType.LIFECYCLE,
    "approval": GateType.APPROVAL,
    "evidence": GateType.EVIDENCE,
    "promotion": GateType.PROMOTION,
    "promote": GateType.PROMOTION,
}

GATE_CATEGORIES: frozenset[str] = frozenset({"Assessment", "Governance"})
