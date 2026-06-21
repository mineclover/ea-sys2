"""Needs-layer schema definition (N2.5 Schema).

Lightweight SchemaPort-compatible schema for needs-layer profile validation.
Follows ea-kernel's KernelSchema pattern but with needs-specific vocabulary.

Zero internal dependencies — this module defines pure schema vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NeedsEntity:
    """A needs-layer entity type."""
    name: str
    is_abstract: bool = False
    description: str = ""


@dataclass(frozen=True)
class NeedsRelation:
    """A needs-layer relation type."""
    name: str
    description: str = ""


@dataclass(frozen=True)
class NeedsSchema:
    """Schema definition for the needs layer.

    Satisfies SchemaPort protocol (entities + relations properties).
    """
    entities: tuple[NeedsEntity, ...] = ()
    relations: tuple[NeedsRelation, ...] = ()

    def get_entity(self, name: str) -> NeedsEntity | None:
        """Find an entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> NeedsRelation | None:
        """Find a relation by name."""
        for r in self.relations:
            if r.name == name:
                return r
        return None


# ── Singleton ──────────────────────────────────────────────────

NEEDS_SCHEMA = NeedsSchema(
    entities=(
        NeedsEntity("need_catalog", is_abstract=True, description="Abstract container for needs"),
        NeedsEntity("stakeholder", description="The subject who has the need"),
        NeedsEntity("desire", description="What the stakeholder wants"),
        NeedsEntity("justification", description="Why the stakeholder has this desire"),
        NeedsEntity("need_statement", description="Complete expression of a stakeholder need"),
        NeedsEntity("use_case", description="Use-case vocabulary captured by the needs layer"),
        NeedsEntity("process_unit", description="Modeling unit for need processes"),
        NeedsEntity("need", description="Mutable need wrapper with lifecycle"),
        NeedsEntity("need_relation", description="Directed relationship between two needs"),
        # N1 Enums
        NeedsEntity("need_status", description="Need lifecycle state enum (DRAFT/EXPRESSED/ACKNOWLEDGED/ADDRESSED/WITHDRAWN)"),
        NeedsEntity("need_priority", description="Need priority level enum (CRITICAL/HIGH/MEDIUM/LOW)"),
        NeedsEntity("need_purpose", description="User intent taxonomy enum (SAFETY/EFFICIENCY/USABILITY/COMPLIANCE/GROWTH/TRUST)"),
        NeedsEntity("need_cause_type", description="Root cause domain enum (EMOTIONAL/SITUATIONAL/PHYSICAL/LOGICAL/MENTAL/PHILOSOPHICAL)"),
        NeedsEntity("need_resolution_complexity", description="Resolution complexity enum (SIMPLE/PROCEDURAL/COMPLEX)"),
        NeedsEntity("need_process_stage", description="Process stage enum (IDENTIFY/QUERY/MODEL_DETAIL)"),
        NeedsEntity("justification_type", description="Justification type enum (BECAUSE/IN_ORDER_TO)"),
        # S3 Recording
        NeedsEntity("need_store", description="S3 need snapshot store (ABC/InMemory/SQLite)"),
        # S4 Analysis
        NeedsEntity("needs_analyzer", description="S4 stakeholder coverage and priority distribution analyzer"),
        # S5 Evolution
        NeedsEntity("needs_simulator", description="S5 stakeholder/need change what-if simulator"),
        NeedsEntity("need_promotion_engine", description="S5 need promotion/deprecation workflow engine"),
        # Scenario flow entities
        NeedsEntity("scenario_flow", description="Scenario flow describing use-case interaction sequences"),
        NeedsEntity("scenario_step", description="A single step in a scenario flow"),
        NeedsEntity("scenario_type", description="Scenario type enum (MAIN/ALTERNATIVE/EXCEPTION)"),
    ),
    relations=(
        # NeedRelationType relations (5)
        NeedsRelation("depends_on", description="Need depends on another need"),
        NeedsRelation("conflicts_with", description="Need conflicts with another need"),
        NeedsRelation("supports", description="Need supports another need"),
        NeedsRelation("refines", description="Need refines another need"),
        NeedsRelation("supersedes", description="Need supersedes another need"),
        # Structural relations (3)
        NeedsRelation("contains", description="Catalog contains needs/stakeholders"),
        NeedsRelation("expresses", description="Stakeholder expresses a desire"),
        NeedsRelation("justifies", description="Justification justifies a desire"),
        # Additional semantic relations (2)
        NeedsRelation("addresses", description="Need addresses a stakeholder desire or use case"),
        NeedsRelation("withdraws", description="Need withdrawal supersedes an active need"),
        # Scenario relations
        NeedsRelation("branches_from", description="Scenario flow branches from a main scenario step"),
    ),
)
