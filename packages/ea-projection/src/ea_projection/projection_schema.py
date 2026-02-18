"""Projection-layer schema definition.

Lightweight SchemaPort-compatible schema for projection-layer profile validation.
Follows ea-kernel's KernelSchema pattern but with projection-specific vocabulary.

Zero internal dependencies — this module defines pure schema vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectionEntity:
    """A projection-layer entity type."""
    name: str
    is_abstract: bool = False
    description: str = ""


@dataclass(frozen=True)
class ProjectionRelation:
    """A projection-layer relation type."""
    name: str
    description: str = ""


@dataclass(frozen=True)
class ProjectionSchema:
    """Schema definition for the projection layer.

    Satisfies SchemaPort protocol (entities + relations properties).
    """
    entities: tuple[ProjectionEntity, ...] = ()
    relations: tuple[ProjectionRelation, ...] = ()

    def get_entity(self, name: str) -> ProjectionEntity | None:
        """Find an entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> ProjectionRelation | None:
        """Find a relation by name."""
        for r in self.relations:
            if r.name == name:
                return r
        return None


# ── Singleton ──────────────────────────────────────────────────

PROJECTION_SCHEMA = ProjectionSchema(
    entities=(
        # Core abstraction model
        ProjectionEntity("projection_layer", is_abstract=True, description="Abstract projection/abstraction boundary"),
        ProjectionEntity("projection_policy", description="M2 meta-meta policy definition for projection levels and lenses"),
        ProjectionEntity("projection_level", description="L0-L4 level specification (panorama/capability/interaction/execution/trace)"),
        ProjectionEntity("projection_lens", description="Lens type (panorama/overview/capability/interaction/execution/trace)"),
        ProjectionEntity("view_mode", description="Base view mode (raw/summary/focus)"),
        ProjectionEntity("focus_mode", description="Focus mode (core/relation/layer/actor/topic)"),
        # Indexing
        ProjectionEntity("topic_index", description="Topic-based element indexing for domain navigation"),
        ProjectionEntity("actor_index", description="Actor-based seed/depth indexing for interaction views"),
        ProjectionEntity("budget_controller", description="Edge budget allocation strategy for projection reduction"),
        # Service
        ProjectionEntity("projection_service", description="Projection execution service orchestrating level/lens/filter"),
        ProjectionEntity("projection_filter", description="Filter/reduction engine for topology simplification"),
        # Output
        ProjectionEntity("projected_view", description="M1P projected output artifact"),
        ProjectionEntity("reduction_report", description="Projection reduction metadata (node/edge counts, ratios)"),
        ProjectionEntity("drilldown_spec", description="Level transition specification for progressive disclosure"),
        # S3/S4/S5 Governance lifecycle
        ProjectionEntity("projection_store", description="S3: Projected view cache/persistence"),
        ProjectionEntity("projection_analyzer", description="S4: View quality/coverage analysis engine"),
        ProjectionEntity("projection_simulator", description="S5: Policy change simulation engine"),
        ProjectionEntity("projection_promotion_engine", description="S5: Policy promotion workflow engine"),
    ),
    relations=(
        ProjectionRelation("contains", description="Namespace or component containment"),
        ProjectionRelation("registers", description="Registry membership between components and ports"),
        ProjectionRelation("coordinates", description="Runtime orchestration or collaboration linkage"),
        ProjectionRelation("depends_on", description="Structural dependency on data or policies"),
        ProjectionRelation("produces", description="Behavior produces artifacts"),
        ProjectionRelation("consumes", description="Behavior consumes artifacts"),
        ProjectionRelation("next", description="Execution sequence transition"),
        ProjectionRelation("triggers", description="Event-driven execution trigger"),
        ProjectionRelation("constrains", description="Policy or guard constrains execution"),
        ProjectionRelation("available_in", description="Context provides access to element"),
    ),
)
