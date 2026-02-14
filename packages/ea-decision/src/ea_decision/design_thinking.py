"""Backward-compatibility shim — canonical modules are ea_decision.topic and ea_decision.types."""

from ea_decision.pattern import DecisionComplexity, DecisionPattern  # noqa: F401
from ea_decision.topic import (  # noqa: F401
    DesignDecision,
    DesignReport,
    Evaluation,
    ModelingAction,
    Option,
    Question,
    ResearchNote,
    Topic,
)
from ea_decision.types import (  # noqa: F401
    DecisionStatus,
    I18nString,
    Reference,
    _generate_id,
    _now,
)
