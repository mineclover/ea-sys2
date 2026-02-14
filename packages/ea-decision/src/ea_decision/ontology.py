"""Backward-compatibility shim — canonical module is ea_decision.types."""

from ea_decision.types import (  # noqa: F401
    DecisionType,
    ActivationStatus,
    EvidenceReference,
    EvaluationCriteria,
    Rationale,
    TopicOption as ChoiceOption,
    DecisionTopic,
    DecisionOntology,
)
