"""Decision-layer schema definition (D2.5 Schema).

Lightweight SchemaPort-compatible schema for decision-layer profile validation.
Follows ea-kernel's KernelSchema pattern but with decision-specific vocabulary.

Zero internal dependencies — this module defines pure schema vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionEntity:
    """A decision-layer entity type."""
    name: str
    is_abstract: bool = False
    description: str = ""


@dataclass(frozen=True)
class DecisionRelation:
    """A decision-layer relation type."""
    name: str
    description: str = ""


@dataclass(frozen=True)
class DecisionSchema:
    """Schema definition for the decision layer.

    Satisfies SchemaPort protocol (entities + relations properties).
    """
    entities: tuple[DecisionEntity, ...] = ()
    relations: tuple[DecisionRelation, ...] = ()

    def get_entity(self, name: str) -> DecisionEntity | None:
        """Find an entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> DecisionRelation | None:
        """Find a relation by name."""
        for r in self.relations:
            if r.name == name:
                return r
        return None


# ── Singleton ──────────────────────────────────────────────────

DECISION_SCHEMA = DecisionSchema(
    entities=(
        DecisionEntity("decision_topic", is_abstract=True, description="Abstract decision topic container"),
        DecisionEntity("topic", description="Concrete topic aggregate root for Design Thinking process"),
        DecisionEntity("intent", description="Frozen intent value — the 'why' starting point"),
        DecisionEntity("choice_option", description="Frozen candidate option with feasibility/alignment scores"),
        DecisionEntity("choice", description="Frozen selected option with rationale"),
        DecisionEntity("decision_result", description="Frozen decision outcome with artifact and timestamp"),
        DecisionEntity("evidence", description="Structured evidence item with type, uri, relevance score"),
        DecisionEntity("evidence_collection", description="Immutable collection of evidence items"),
        DecisionEntity("evaluation_dimension", description="Single evaluation axis with weight and scale"),
        DecisionEntity("evaluation_result", description="Weighted multi-dimension evaluation outcome"),
        DecisionEntity("decision_pattern", description="Reusable decision template with complexity and heuristics"),
        DecisionEntity("pattern_schema", description="Meta-model for decision patterns with phases and types"),
        DecisionEntity("decision_lifecycle", description="State machine for decision lifecycle transitions"),
        DecisionEntity("rationale", description="Explainability schema for decision justification"),
        # N1 Enums
        DecisionEntity("decision_type", description="Decision type enum (TRADE_OFF/COMPLIANCE/ARCHITECTURE/PROCESS)"),
        DecisionEntity("decision_phase", description="Design Thinking phase enum (DIVERGE/CONVERGE/UTILIZE)"),
        DecisionEntity("decision_status", description="Decision status enum (PROPOSED/ACCEPTED/REJECTED/DEPRECATED)"),
        DecisionEntity("decision_lifecycle_state", description="Lifecycle state enum (DRAFT/PROPOSED/ACCEPTED/REJECTED/DEPRECATED/SUPERSEDED)"),
        DecisionEntity("decision_complexity", description="Pattern complexity enum (TRIVIAL/STRUCTURAL/STRATEGIC)"),
        # S3 Recording
        DecisionEntity("topic_store", description="S3 topic snapshot store (ABC/InMemory/SQLite)"),
        # S4 Analysis
        DecisionEntity("decision_analyzer", description="S4 pattern effectiveness and evaluation consistency analyzer"),
        # S5 Evolution
        DecisionEntity("decision_simulator", description="S5 pattern change what-if simulator"),
        DecisionEntity("pattern_promotion_engine", description="S5 pattern promotion/deprecation workflow engine"),
    ),
    relations=(
        DecisionRelation("evaluates", description="Evaluation dimension evaluates an option"),
        DecisionRelation("selects", description="Choice selects an option from candidates"),
        DecisionRelation("produces", description="Behavior produces artifacts"),
        DecisionRelation("justifies", description="Evidence justifies a decision"),
        DecisionRelation("contains", description="Containment relationship"),
        DecisionRelation("supersedes", description="New decision supersedes an old one"),
        DecisionRelation("applies", description="Pattern applies to a topic"),
        DecisionRelation("refines", description="Decision refines another decision"),
        DecisionRelation("depends_on", description="Dependency relationship"),
        DecisionRelation("transitions_to", description="Lifecycle state transition"),
    ),
)
