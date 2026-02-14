"""Backward-compatibility shim — canonical module is ea_flow.topology."""

from ea_flow.topology import (  # noqa: F401
    DataFlowEdge,
    DataTransformation,
    FlowOntology,
    LogicCondition,
    ProcessSpec,
    SchemaDefinition,
    StepDefinition,
    StepSchemaUsage,
)
from ea_flow.types import FlowStepCategory  # noqa: F401
