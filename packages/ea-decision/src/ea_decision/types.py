"""Unified immutable vocabulary types for the Decision Layer (N1).

Consolidates frozen types from structure.py, ontology.py, and design_thinking.py.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

I18nString = str | dict[str, str]


def _generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now() -> str:
    """Return current timestamp in ISO 8601."""
    return datetime.now(UTC).isoformat() + "Z"


# ---------------------------------------------------------------------------
# From design_thinking.py
# ---------------------------------------------------------------------------

class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"


@dataclass
class Reference:
    """A link to a specific resource in Layer 1 (ea-infra)."""
    uri: str  # file://... or urn:ea:resource:...
    title: str
    citation: str | None = None  # e.g., "Line 10-20"


# ---------------------------------------------------------------------------
# From structure.py
# ---------------------------------------------------------------------------

class DecisionPhase(StrEnum):
    """Phases of the Design Thinking based decision process."""
    DIVERGE = "diverge"    # Generating options based on Intent
    CONVERGE = "converge"  # Narrowing down and selecting a Choice
    UTILIZE = "utilize"    # Applying the Choice to create a Result


@dataclass(frozen=True)
class Intent:
    """The direction or goal of a decision (The 'Why').

    Represents the starting point of the Diverge phase.
    """
    id: str
    description: str
    direction: str  # e.g., "maximize_stability", "explore_new_tech", "refactor_legacy"
    context_refs: list[str]  # References to reports, analysis, external mandates (The Context)


@dataclass(frozen=True)
class ChoiceOption:
    """An available option generated during the Diverge phase (The 'Could Be')."""
    id: str
    intent_id: str
    description: str
    feasibility_score: float  # 0.0 to 1.0
    alignment_score: float    # 0.0 to 1.0 (Alignment with Intent)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Choice:
    """The selected option from the Converge phase (The 'Should Be')."""
    id: str
    intent_id: str
    selected_option_id: str
    rationale: str  # Justification for why this option was chosen
    distance: float  # Conceptual "distance" from intent (Gap analysis)


@dataclass(frozen=True)
class DecisionResult:
    """The final outcome of the Utilize phase (The 'Is')."""
    id: str
    intent_id: str
    choice_id: str
    outcome_artifact: Any  # The actual artifact produced (e.g., a Rule, a Judgment, a Plan)
    timestamp: str  # ISO 8601


# ---------------------------------------------------------------------------
# From ontology.py
# ---------------------------------------------------------------------------

class DecisionType(Enum):
    """
    Classifies the nature of the decision.
    """
    ARCHITECTURE_SELECTION = "architecture_selection"  # Choosing a tech/pattern
    TRADE_OFF_RESOLUTION = "trade_off_resolution"      # Balancing conflicting constraints
    COMPLIANCE_CHECK = "compliance_check"              # Verifying against rules
    RESOURCE_ALLOCATION = "resource_allocation"        # Assigning resources
    STRATEGIC_DIRECTION = "strategic_direction"        # High-level goal setting


class ActivationStatus(Enum):
    """
    The current lifecycle state of a decision.
    """
    DRAFT = "draft"
    ACTIVE = "active"       # Currently in effect
    DEPRECATED = "deprecated" # Still valid but phased out
    SUPERSEDED = "superseded" # Replaced by a newer decision
    REJECTED = "rejected"


@dataclass(frozen=True)
class EvidenceReference:
    """
    A link to Layer 1 resources that support this decision.
    """
    resource_uri: str  # e.g., file://path/to/doc.pdf
    description: str   # How this supports the decision
    relevance_score: float = 1.0


@dataclass(frozen=True)
class EvaluationCriteria:
    """
    A dimension against which options are judged.
    """
    name: str
    description: str
    weight: float = 1.0
    # The 'unit' or 'scale' of measurement (e.g., "1-5", "USD", "ms")
    scale: str = "qualitative"


@dataclass(frozen=True)
class Rationale:
    """
    The reasoning behind a specific score or choice.
    """
    summary: str
    evidence_links: list[EvidenceReference] = field(default_factory=list) # URI to Layer 1 resources
    confidence_score: float = 1.0 # 0.0 to 1.0


@dataclass(frozen=True)
class TopicOption:
    """
    An option available for selection within a DecisionTopic.
    Renamed from ontology.ChoiceOption to avoid collision with structure.ChoiceOption.
    """
    id: str
    name: str
    description: str
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    # Map of Criteria Name -> Score/Value
    scores: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionTopic:
    """
    The root ontology entity for a Decision.
    Represents the "Problem Space" and the "Resolved Path".
    """
    id: str
    title: str
    description: str
    decision_type: DecisionType

    # Time & Status Tracking
    status: ActivationStatus = ActivationStatus.DRAFT
    decision_date: datetime | None = None
    valid_until: datetime | None = None
    superseded_by_id: str | None = None

    # The Context
    criteria: list[EvaluationCriteria] = field(default_factory=list)
    options: list[TopicOption] = field(default_factory=list)

    # The Conclusion
    selected_option_id: str | None = None
    final_rationale: Rationale | None = None

    # L1 Grounding
    supporting_evidence: list[EvidenceReference] = field(default_factory=list)


class DecisionOntology:
    """
    Registry and factory for Decision types.
    """
    @staticmethod
    def describe() -> dict[str, str]:
        return {
            "DecisionTopic": "Represents a single decision point with context, outcome, time, and status.",
            "ActivationStatus": "Lifecycle state (Active, Deprecated, etc.)",
            "EvidenceReference": "Link to L1 supporting materials."
        }
