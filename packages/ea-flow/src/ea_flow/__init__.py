"""
Execution Layer for EA System.

This package implements the 3-plane execution model:
- P1 Specification: Declarative definitions (spec.py — StepSpec, WorkflowSpec)
- P2 Coordination: Execution graph (topology.py — ProcessSpec, DataFlowEdge)
- P3 Realization: Runtime interpretation/planning (runtime.py — FlowRuntime, StepImplementer)

Shared types live in types.py (I18nString, FlowStepCategory).
"""

__version__ = "0.1.0"
