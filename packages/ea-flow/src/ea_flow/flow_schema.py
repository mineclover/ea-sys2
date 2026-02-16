"""Flow-layer schema definition (F2.5 Schema).

Lightweight SchemaPort-compatible schema for flow-layer profile validation.
Follows ea-kernel's KernelSchema pattern but with flow-specific vocabulary.
Named FlowLayerSchema to avoid confusion with schema.py (data SchemaSpec).

Zero internal dependencies — this module defines pure schema vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlowEntity:
    """A flow-layer entity type."""
    name: str
    is_abstract: bool = False
    description: str = ""


@dataclass(frozen=True)
class FlowRelation:
    """A flow-layer relation type."""
    name: str
    description: str = ""


@dataclass(frozen=True)
class FlowLayerSchema:
    """Schema definition for the flow layer.

    Satisfies SchemaPort protocol (entities + relations properties).
    """
    entities: tuple[FlowEntity, ...] = ()
    relations: tuple[FlowRelation, ...] = ()

    def get_entity(self, name: str) -> FlowEntity | None:
        """Find an entity by name."""
        for e in self.entities:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> FlowRelation | None:
        """Find a relation by name."""
        for r in self.relations:
            if r.name == name:
                return r
        return None


# ── Singleton ──────────────────────────────────────────────────

FLOW_SCHEMA = FlowLayerSchema(
    entities=(
        # P1 Specification Plane
        FlowEntity("flow_layer", is_abstract=True, description="Abstract flow modeling boundary"),
        FlowEntity("step_spec", is_abstract=True, description="Abstract step specification contract"),
        FlowEntity("workflow_spec", is_abstract=True, description="Abstract workflow specification contract"),
        FlowEntity("meta_step", description="Reusable logic pattern definition (FlowMetaStep)"),
        FlowEntity("use_case_spec", description="Business process definition with actor and criteria"),
        FlowEntity("execution_context", description="Frozen execution context with variables"),
        FlowEntity("step_result", description="Step result specification with output schema"),
        FlowEntity("generation_rule", description="Rule for generating flow specs from kernel entities"),
        FlowEntity("flow_topology", description="Declarative process structure with steps and transitions"),
        # P2 Coordination Plane
        FlowEntity("process_spec", description="Root process entity with steps and data flow edges"),
        FlowEntity("step_definition", description="Single node in the process graph"),
        FlowEntity("data_flow_edge", description="Data movement definition between steps"),
        FlowEntity("schema_definition", description="Data shape definition with format and content"),
        FlowEntity("logic_condition", description="Conditional expression for step routing"),
        FlowEntity("data_transformation", description="Data shape transformation with mapping rules"),
        FlowEntity("data_contract", description="Producer-consumer schema matching contract"),
        FlowEntity("data_catalog", description="Registry of all data schemas across workflows"),
        # P3 Realization Plane
        FlowEntity("step_implementer", is_abstract=True, description="Abstract step execution interface"),
        FlowEntity("flow_runtime", description="Workflow interpreter with sequential execution"),
        FlowEntity("execution_result", description="Full workflow execution result"),
        FlowEntity("flow_profile", description="Domain-specific meta-step collection"),
    ),
    relations=(
        FlowRelation("contains", description="Namespace or component containment"),
        FlowRelation("next", description="Execution sequence transition"),
        FlowRelation("produces", description="Behavior produces artifacts"),
        FlowRelation("consumes", description="Behavior consumes artifacts"),
        FlowRelation("depends_on", description="Structural dependency"),
        FlowRelation("registers", description="Registry membership"),
        FlowRelation("coordinates", description="Runtime orchestration linkage"),
        FlowRelation("triggers", description="Event-driven execution trigger"),
        FlowRelation("constrains", description="Policy or guard constrains execution"),
        FlowRelation("available_in", description="Context provides access to element"),
    ),
)
