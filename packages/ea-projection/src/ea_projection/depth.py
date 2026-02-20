"""Depth level registry — formal types for projection L0-L4 depth specifications.

Extracted from kernel_service.py _PROJECTION_LEVEL_SPECS and related constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DepthLevel:
    """Specification for a single projection depth level."""

    key: str
    lens: str
    description: str
    base_view_mode: str
    base_focus: str | None = None
    allowed_relations: frozenset[str] = frozenset()
    allowed_categories: frozenset[str] = frozenset()
    max_edges: int = 600
    next_levels: tuple[str, ...] = ()
    depth_semantic: str = ""
    entry_question: str = ""
    entry_intent: str = ""
    max_containment_depth: int | None = None  # None = unlimited


class DepthLevelRegistry:
    """Immutable registry of projection depth levels (L0-L4)."""

    def __init__(self, levels: dict[str, DepthLevel]) -> None:
        self._levels = dict(levels)

    @staticmethod
    def from_hardcoded() -> DepthLevelRegistry:
        """Build registry from the canonical L0-L4 definitions."""
        return DepthLevelRegistry(_HARDCODED_LEVELS)

    def get(self, key: str) -> DepthLevel | None:
        return self._levels.get(key.strip().lower())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._levels.keys())

    def to_level_specs(self) -> dict[str, dict[str, Any]]:
        """Convert to the dict-of-dicts format used by policy resolution."""
        result: dict[str, dict[str, Any]] = {}
        for key, level in self._levels.items():
            result[key] = {
                "level": level.key.upper(),
                "lens": level.lens,
                "description": level.description,
                "base_view_mode": level.base_view_mode,
                "base_focus": level.base_focus,
                "allowed_relations": tuple(level.allowed_relations),
                "allowed_categories": tuple(level.allowed_categories),
                "default_max_edges": level.max_edges,
                "next_levels": level.next_levels,
                "depth_semantic": level.depth_semantic,
                "entry_question": level.entry_question,
                "entry_intent": level.entry_intent,
                "max_containment_depth": level.max_containment_depth,
            }
        return result


_ACTOR_INTERACTION_RELATIONS = (
    "available_in",
    "contains",
    "depends_on",
    "coordinates",
    "next",
    "triggers",
    "constrains",
)

_ACTOR_INTERACTION_CATEGORIES = tuple(sorted((
    "Context",
    "Composite",
    "Page",
    "Interface",
    "Behavior",
    "Executable",
    "Event",
    "Goal",
    "Governance",
    "Assessment",
)))


_HARDCODED_LEVELS: dict[str, DepthLevel] = {
    "l0": DepthLevel(
        key="l0",
        lens="panorama",
        description="Strategic panorama for cross-domain orientation.",
        base_view_mode="focus",
        base_focus="core",
        allowed_relations=frozenset(("contains", "depends_on", "next", "triggers", "constrains")),
        allowed_categories=frozenset(("Composite", "Page", "Interface", "Context", "Goal", "Governance")),
        max_edges=180,
        next_levels=("L1",),
        depth_semantic="existence",
        entry_question="What structural boundaries exist in this domain?",
        entry_intent="orientation",
    ),
    "l1": DepthLevel(
        key="l1",
        lens="capability",
        description="Capability and responsibility map around experiences and interfaces.",
        base_view_mode="summary",
        allowed_relations=frozenset(("contains", "depends_on", "next", "triggers", "constrains")),
        allowed_categories=frozenset((
            "Composite", "Page", "Interface", "Context", "Goal",
            "Governance", "Assessment", "Behavior", "Executable",
        )),
        max_edges=320,
        next_levels=("L2",),
        depth_semantic="instance",
        entry_question="What capabilities and instances are arranged here?",
        entry_intent="capability_survey",
    ),
    "l2": DepthLevel(
        key="l2",
        lens="interaction",
        description="Actor-centric valid interaction routes.",
        base_view_mode="focus",
        base_focus="actor",
        allowed_relations=frozenset(_ACTOR_INTERACTION_RELATIONS),
        allowed_categories=frozenset(_ACTOR_INTERACTION_CATEGORIES),
        max_edges=520,
        next_levels=("L3",),
        depth_semantic="configuration",
        entry_question="How are actor interactions configured?",
        entry_intent="interaction_map",
    ),
    "l3": DepthLevel(
        key="l3",
        lens="execution",
        description="Execution chain over steps, actions, and triggering events.",
        base_view_mode="summary",
        allowed_relations=frozenset((
            "next", "triggers", "depends_on", "coordinates",
            "constrains", "produces", "consumes",
        )),
        allowed_categories=frozenset((
            "Behavior", "Executable", "Event", "Interface",
            "Goal", "Governance", "Assessment", "PassiveStructure",
        )),
        max_edges=760,
        next_levels=("L4",),
        depth_semantic="execution",
        entry_question="How do steps and actions execute?",
        entry_intent="execution_trace",
    ),
    "l4": DepthLevel(
        key="l4",
        lens="trace",
        description="Developer-grade decision/data trace view with detailed flow relations.",
        base_view_mode="summary",
        allowed_relations=frozenset((
            "produces", "consumes", "next", "triggers", "depends_on",
            "coordinates", "registers", "available_in", "constrains",
        )),
        allowed_categories=frozenset((
            "Behavior", "Executable", "Event", "Interface", "Goal",
            "Governance", "Assessment", "PassiveStructure",
            "Context", "Page", "Composite",
        )),
        max_edges=980,
        next_levels=(),
        depth_semantic="trace",
        entry_question="What decisions and data drive this execution?",
        entry_intent="decision_evidence",
    ),
}

PROJECTION_LENS_TO_LEVEL: dict[str, str] = {
    "panorama": "l0",
    "overview": "l0",
    "capability": "l1",
    "interaction": "l2",
    "execution": "l3",
    "trace": "l4",
}

PROJECTION_BASE_VIEW_MODES: frozenset[str] = frozenset({"raw", "summary", "focus"})
PROJECTION_FOCUS_MODES: frozenset[str] = frozenset({"core", "relation", "layer", "actor", "topic", "seed"})
PROJECTION_DEFAULT_ACTOR_DEPTH: int = 4
PROJECTION_DEFAULT_SEED_DEPTH: int = 2
