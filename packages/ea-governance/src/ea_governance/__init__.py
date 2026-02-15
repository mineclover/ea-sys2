"""
Governance System Integration.

This package provides the unified facade `GovernanceContainer` that orchestrates:
1. ea-kernel (Core Structure)
2. ea-decision (Intent & Choice)
3. ea-flow (Execution & Automation)
4. ea-needs DB persistence adapters (storage ownership)
5. ea-kernel governance snapshots (storage ownership)

Schema & Profile:
- GovernanceSchema: SchemaPort-compatible governance vocabulary (governance_schema.py)
- governance_condition_registry: Kernel defaults + governance conditions (condition_registry.py)
- load_governance_profile: TOML profile loading with validation (profile_bridge.py)

Service Layer:
- governance_service: Pure functions for governance-specific queries (list_managed_layers, etc.)

Ops Modules (internal, used by facade):
- decision_trace_ops: Decision trace read/write
- kernel_model_ops: Model registration/validation/activation
- kernel_rule_ops: Rule lifecycle + evaluation + snapshots
- needs_ops: Needs catalog CRUD
"""

__version__ = "0.1.0"
