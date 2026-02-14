from dataclasses import dataclass, field
from typing import Any

from ea_flow.types import FlowStepCategory


@dataclass(frozen=True)
class SchemaDefinition:
    """
    Defines the shape of data used in the flow.
    Can be a reference to a JSON Schema or a Kernel Entity.
    """
    id: str
    name: str
    schema_format: str = "json-schema-2020-12"
    definition: dict[str, Any] = field(default_factory=dict) # The actual schema object

@dataclass(frozen=True)
class StepSchemaUsage:
    """
    Defines how a step uses data schemas.
    """
    input_schema_id: str | None = None
    output_schema_id: str | None = None
    required_fields: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class DataFlowEdge:
    """
    Defines how data moves between steps.
    """
    source_step_id: str
    target_step_id: str
    source_field: str # e.g., "output.userId"
    target_field: str # e.g., "input.id"
    transformation_rule: str | None = None # e.g. "toString()"

@dataclass(frozen=True)
class LogicCondition:
    """
    A specific condition that must be met.
    """
    expression: str  # e.g., "amount >= 10000"
    engine: str = "json-logic" # or "python", "sql", etc.
    parameters: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DataTransformation:
    """
    Defines how data changes shape between steps.
    """
    input_schema: dict[str, Any]  # JSON Schema
    output_schema: dict[str, Any] # JSON Schema
    mapping_rules: dict[str, str] # Field-to-field mapping

@dataclass(frozen=True)
class StepDefinition:
    """
    A single node in the process graph.
    """
    id: str
    name: str
    category: FlowStepCategory
    description: str

    # Logic (For Decision/Gateway steps)
    condition: LogicCondition | None = None

    # Data (For Action/Transform steps)
    transformation: DataTransformation | None = None
    schema_usage: StepSchemaUsage | None = None

    # Routing (Where to go next)
    next_step_ids: list[str] = field(default_factory=list)

    # Error Handling
    on_failure_step_id: str | None = None

@dataclass(frozen=True)
class ProcessSpec:
    """
    The root ontology entity for a Flow/Process.
    Represents the "Execution Spec".
    """
    id: str
    name: str
    version: str
    steps: list[StepDefinition] = field(default_factory=list)
    trigger_event: str = "manual"

    # Data Architecture
    defined_schemas: list[SchemaDefinition] = field(default_factory=list)
    data_flow_edges: list[DataFlowEdge] = field(default_factory=list)

class FlowOntology:
    """
    Registry for Process Specification types.
    """
    @staticmethod
    def describe() -> dict[str, str]:
        return {
            "ProcessSpec": "A complete definition of an executable process.",
            "SchemaDefinition": "Data structure definition (JSON Schema).",
            "DataFlowEdge": "Definition of data movement between steps.",
            "StepSchemaUsage": "Input/Output contract for a step."
        }
