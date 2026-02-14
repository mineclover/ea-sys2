"""Backward-compatibility shim — canonical module is ea_flow.spec."""

from ea_flow.spec import (  # noqa: F401
    ExecutionContext,
    FlowGenerationRule,
    FlowMetaStep,
    FlowTopology,
    KernelGroundedStepSpec,
    StepResultSpec,
    StepSpec,
    UseCaseSpec,
    WorkflowSpec,
)
from ea_flow.types import I18nString  # noqa: F401
