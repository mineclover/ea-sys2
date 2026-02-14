"""Backward-compatibility shim — canonical module is ea_flow.spec."""

from ea_flow.spec import (  # noqa: F401
    I18nString,
    ExecutionContext,
    StepResultSpec,
    FlowMetaStep,
    StepSpec,
    KernelGroundedStepSpec,
    WorkflowSpec,
    UseCaseSpec,
    FlowGenerationRule,
    FlowTopology,
)
