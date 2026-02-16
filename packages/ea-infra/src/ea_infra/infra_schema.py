"""Infra-layer schema definition (I2.5 Schema).

Lightweight SchemaPort-compatible schema for infra-layer profile validation.
Follows ea-kernel's KernelSchema pattern but with infra-specific vocabulary.

Zero internal dependencies — this module defines pure schema vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InfraEntity:
    """An infra-layer entity type."""
    name: str
    is_abstract: bool = False
    description: str = ""


@dataclass(frozen=True)
class InfraRelation:
    """An infra-layer relation type."""
    name: str
    description: str = ""


@dataclass(frozen=True)
class InfraSchema:
    """Schema definition for the infra layer.

    Satisfies SchemaPort protocol (entities + relations properties).
    """
    entities: tuple[InfraEntity, ...] = ()
    relations: tuple[InfraRelation, ...] = ()

    def get_entity(self, name: str) -> InfraEntity | None:
        """Find an entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> InfraRelation | None:
        """Find a relation by name."""
        for r in self.relations:
            if r.name == name:
                return r
        return None


# ── Singleton ──────────────────────────────────────────────────

INFRA_SCHEMA = InfraSchema(
    entities=(
        # Core infrastructure
        InfraEntity("infra_layer", is_abstract=True, description="Abstract infrastructure row-data design boundary"),
        InfraEntity("data_platform_service", description="Primary service controlling row-data contracts and physical data access"),
        InfraEntity("storage_lifecycle_service", description="Handles schema lifecycle, migration, and retention routines"),
        # Ports
        InfraEntity("storage_port", description="Row-data storage port for persistence"),
        InfraEntity("event_storage_port", description="Append-only port for immutable event/audit writes"),
        InfraEntity("model_port", description="6x6 contract port for layer model interface"),
        # Stores
        InfraEntity("version_store", description="Row-oriented version table for layer model payloads"),
        InfraEntity("validation_store", description="Row-oriented validation run table with diagnostics"),
        InfraEntity("evidence_store", description="Row-oriented evidence/audit table for execution feedback"),
        InfraEntity("context_store", description="Contextual data store for domain-specific needs"),
        InfraEntity("execution_log", description="Execution log schema for flow runtime"),
        InfraEntity("checkpoint_store", description="Checkpoint/snapshot store for flow state"),
        # Policies and schemas
        InfraEntity("storage_policy", description="Row lifecycle, retention, and partition policy constraints"),
        InfraEntity("data_schema", description="Data shape definition for cross-layer integration"),
        InfraEntity("data_migration", description="Schema migration definition for version transitions"),
        InfraEntity("index_strategy", description="Index strategy for data access optimization"),
        InfraEntity("retention_policy", description="Data retention and archival policy"),
    ),
    relations=(
        InfraRelation("contains", description="Namespace or component containment"),
        InfraRelation("registers", description="Registry membership between components and ports"),
        InfraRelation("coordinates", description="Runtime orchestration or collaboration linkage"),
        InfraRelation("depends_on", description="Structural dependency on data or policies"),
        InfraRelation("produces", description="Behavior produces artifacts"),
        InfraRelation("consumes", description="Behavior consumes artifacts"),
        InfraRelation("next", description="Execution sequence transition"),
        InfraRelation("triggers", description="Event-driven execution trigger"),
        InfraRelation("constrains", description="Policy or guard constrains execution"),
        InfraRelation("available_in", description="Context provides access to element"),
    ),
)
