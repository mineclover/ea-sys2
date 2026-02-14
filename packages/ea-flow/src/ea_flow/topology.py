from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union
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
    definition: Dict[str, Any] = field(default_factory=dict) # The actual schema object

@dataclass(frozen=True)
class StepSchemaUsage:
    """
    Defines how a step uses data schemas.
    """
    input_schema_id: Optional[str] = None
    output_schema_id: Optional[str] = None
    required_fields: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class DataFlowEdge:
    """
    Defines how data moves between steps.
    """
    source_step_id: str
    target_step_id: str
    source_field: str # e.g., "output.userId"
    target_field: str # e.g., "input.id"
    transformation_rule: Optional[str] = None # e.g. "toString()"

@dataclass(frozen=True)
class LogicCondition:
    """
    A specific condition that must be met.
    """
    expression: str  # e.g., "amount >= 10000"
    engine: str = "json-logic" # or "python", "sql", etc.
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class DataTransformation:
    """
    Defines how data changes shape between steps.
    """
    input_schema: Dict[str, Any]  # JSON Schema
    output_schema: Dict[str, Any] # JSON Schema
    mapping_rules: Dict[str, str] # Field-to-field mapping

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
    condition: Optional[LogicCondition] = None

    # Data (For Action/Transform steps)
    transformation: Optional[DataTransformation] = None
    schema_usage: Optional[StepSchemaUsage] = None

    # Routing (Where to go next)
    next_step_ids: List[str] = field(default_factory=list)

    # Error Handling
    on_failure_step_id: Optional[str] = None

@dataclass(frozen=True)
class ProcessSpec:
    """
    The root ontology entity for a Flow/Process.
    Represents the "Execution Spec".
    """
    id: str
    name: str
    version: str
    steps: List[StepDefinition] = field(default_factory=list)
    trigger_event: str = "manual"

    # Data Architecture
    defined_schemas: List[SchemaDefinition] = field(default_factory=list)
    data_flow_edges: List[DataFlowEdge] = field(default_factory=list)

class FlowOntology:
    """
    Registry for Process Specification types.
    """
    @staticmethod
    def describe() -> Dict[str, str]:
        return {
            "ProcessSpec": "A complete definition of an executable process.",
            "SchemaDefinition": "Data structure definition (JSON Schema).",
            "DataFlowEdge": "Definition of data movement between steps.",
            "StepSchemaUsage": "Input/Output contract for a step."
        }
