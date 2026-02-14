"""
Decision Layer for EA System.

This package implements the decision-making layer based on Design Thinking principles:

- N1 Vocabulary: Immutable types (types.py — Intent, Choice, DecisionResult, etc.)
- N2 Process: Topic aggregate root (topic.py — Diverge→Converge→Plan→Action)
- N3 Integration: Kernel bridge and persistence (kernel_bridge.py, repository.py)

Patterns live in pattern.py (DecisionPattern, PatternSchema).
Lifecycle state machine in lifecycle.py.
"""

__version__ = "0.1.0"
