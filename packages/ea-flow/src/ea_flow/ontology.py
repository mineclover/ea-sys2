"""Backward-compatibility shim — canonical module is ea_flow.topology."""

from ea_flow.topology import (  # noqa: F401
    FlowStepCategory,
    SchemaDefinition,
    StepSchemaUsage,
    DataFlowEdge,
    LogicCondition,
    DataTransformation,
    StepDefinition,
    ProcessSpec,
    FlowOntology,
)
