"""Governance-layer schema definition.

Lightweight SchemaPort-compatible schema for governance-layer profile validation.
Follows ea-kernel's KernelSchema pattern but with governance-specific vocabulary.

Zero internal dependencies — this module defines pure schema vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceEntity:
    """A governance-layer entity type."""
    name: str
    is_abstract: bool = False
    description: str = ""


@dataclass(frozen=True)
class GovernanceRelation:
    """A governance-layer relation type."""
    name: str
    description: str = ""


@dataclass(frozen=True)
class GovernanceSchema:
    """Schema definition for the governance layer.

    Satisfies SchemaPort protocol (entities + relations properties).
    """
    entities: tuple[GovernanceEntity, ...] = ()
    relations: tuple[GovernanceRelation, ...] = ()

    def get_entity(self, name: str) -> GovernanceEntity | None:
        """Find an entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> GovernanceRelation | None:
        """Find a relation by name."""
        for r in self.relations:
            if r.name == name:
                return r
        return None


# ── Singleton ──────────────────────────────────────────────────

GOVERNANCE_SCHEMA = GovernanceSchema(
    entities=(
        GovernanceEntity("governance_boundary", is_abstract=True, description="Governance control boundary"),
        GovernanceEntity("layer_registry", description="Model registration and indexing"),
        GovernanceEntity("lifecycle_manager", description="Version lifecycle control"),
        GovernanceEntity("coordinator", description="Orchestration and coordination"),
        GovernanceEntity("policy", description="Policy constraint"),
        GovernanceEntity("governance_goal", description="Governance purpose goal"),
        GovernanceEntity("governance_step", description="Workflow action step"),
        GovernanceEntity("governance_action", description="Executable governance action"),
        GovernanceEntity("governance_record", description="Passive data record"),
        GovernanceEntity("entry_port", description="System entry-point interface"),
        GovernanceEntity("model_port", description="Layer model port interface"),
        GovernanceEntity("model_endpoint", description="Model operation endpoint"),
        GovernanceEntity("governance_event", description="Lifecycle event"),
        GovernanceEntity("feedback_loop", description="Iterative correction action"),
        # Transaction / Event Sourcing
        GovernanceEntity("transaction_manager", description="SQLite-backed ACID transaction manager with event sourcing"),
        GovernanceEntity("transaction_unit", description="Transaction unit with status lifecycle (PENDING/IN_PROGRESS/COMMITTED/ROLLED_BACK/FAILED)"),
        GovernanceEntity("transaction_event", description="Frozen event sourcing record for transaction audit"),
        GovernanceEntity("execution_service", description="DesignReport/UseCaseSpec to flow runtime bridge with transaction control"),
        # Projection depth reference
        GovernanceEntity("exposure_depth_policy", description="Projection depth-referenced exposure policy"),
        GovernanceEntity("surface_contract", description="Surface visibility contract referencing projection levels"),
        # Projection execution recording
        GovernanceEntity("projection_result", description="Recorded projection execution result with filter statistics"),
        GovernanceEntity("projection_policy", description="Projection policy reference (level, lens, tier, seed)"),
    ),
    relations=(
        GovernanceRelation("contains", description="Containment relationship"),
        GovernanceRelation("registers", description="Registration relationship"),
        GovernanceRelation("coordinates", description="Coordination relationship"),
        GovernanceRelation("depends_on", description="Dependency relationship"),
        GovernanceRelation("produces", description="Production relationship"),
        GovernanceRelation("consumes", description="Consumption relationship"),
        GovernanceRelation("next", description="Sequence relationship"),
        GovernanceRelation("triggers", description="Trigger relationship"),
        GovernanceRelation("constrains", description="Constraint relationship"),
        GovernanceRelation("available_in", description="Availability relationship (projection surface scope)"),
        GovernanceRelation("records", description="Recording relationship (governance records execution results)"),
    ),
)
