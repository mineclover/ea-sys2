"""Backward-compatibility shim — canonical modules are ea_decision.topic and ea_decision.types."""

from ea_decision.types import (  # noqa: F401
    DecisionStatus,
    Reference,
    I18nString,
    _generate_id,
    _now,
)
from ea_decision.topic import (  # noqa: F401
    ResearchNote,
    Question,
    Evaluation,
    Option,
    ModelingAction,
    DesignDecision,
    DesignReport,
    Topic,
)
from ea_decision.pattern import DecisionComplexity, DecisionPattern  # noqa: F401
