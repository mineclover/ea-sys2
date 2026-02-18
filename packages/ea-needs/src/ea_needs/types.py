"""Immutable vocabulary types for the Needs Layer (N1).

Frozen types representing stakeholder needs before decision-making.
Zero internal dependencies — this module is pure vocabulary.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

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
# Enums
# ---------------------------------------------------------------------------

class JustificationType(StrEnum):
    """Why the stakeholder has this need."""
    BECAUSE = "because"             # causal: "...because X is true"
    IN_ORDER_TO = "in_order_to"     # teleological: "...in order to achieve X"


class NeedPriority(StrEnum):
    """Urgency / importance of a need."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NeedStatus(StrEnum):
    """Lifecycle state of a need.

    Transitions:
        DRAFT -> EXPRESSED -> ACKNOWLEDGED -> ADDRESSED
                           \\               \\
                         WITHDRAWN        WITHDRAWN
    """
    DRAFT = "draft"
    EXPRESSED = "expressed"
    ACKNOWLEDGED = "acknowledged"
    ADDRESSED = "addressed"
    WITHDRAWN = "withdrawn"


class NeedKernelChangePhase(StrEnum):
    """Kernel reflection phase driven by this need."""
    PLANNED = "planned"
    APPLIED = "applied"
    SUPERSEDED = "superseded"
    ROLLED_BACK = "rolled_back"


class NeedRelationType(StrEnum):
    """Directed relationship between two needs."""
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"
    SUPPORTS = "supports"
    REFINES = "refines"
    SUPERSEDES = "supersedes"


class NeedCauseType(StrEnum):
    """Root cause domains that can generate a need."""
    EMOTIONAL = "emotional"
    SITUATIONAL = "situational"
    PHYSICAL = "physical"
    LOGICAL = "logical"
    MENTAL = "mental"
    PHILOSOPHICAL = "philosophical"


class NeedPurpose(StrEnum):
    """Canonical purpose taxonomy for stakeholder needs."""
    SAFETY = "safety"
    EFFICIENCY = "efficiency"
    USABILITY = "usability"
    COMPLIANCE = "compliance"
    GROWTH = "growth"
    TRUST = "trust"
    UNSPECIFIED = "unspecified"


class NeedResolutionComplexity(StrEnum):
    """Expected complexity of need resolution process."""
    SIMPLE = "simple"
    PROCEDURAL = "procedural"
    COMPLEX = "complex"


class NeedProcessStage(StrEnum):
    """Canonical process stages for need modeling units."""
    IDENTIFY = "identify"
    QUERY = "query"
    MODEL_DETAIL = "model_detail"


# ---------------------------------------------------------------------------
# Frozen value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stakeholder:
    """The subject who has the need.

    Example: Stakeholder(name="CTO", role="executive", context="cloud migration initiative")
    """
    id: str
    name: str
    role: str
    context: str = ""


@dataclass(frozen=True)
class Desire:
    """What the stakeholder wants — the action, subject, and optional target.

    Examples:
        Desire(action="migrate", subject="payment system", target="cloud")
        Desire(action="reduce", subject="deployment time")
    """
    action: str
    subject: str
    target: str | None = None


@dataclass(frozen=True)
class Justification:
    """Why the stakeholder has this desire.

    Examples:
        Justification(type=JustificationType.BECAUSE, description="current system has frequent outages")
        Justification(type=JustificationType.IN_ORDER_TO, description="achieve 99.99% availability")
    """
    type: JustificationType
    description: str


@dataclass(frozen=True)
class UseCase:
    """Use-case vocabulary captured by the needs layer."""
    id: str
    title: str
    actor: str
    situation: str
    purpose: str
    outcome: str = ""
    tags: list[str] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class NeedProcessUnit:
    """Modeling unit for need processes (identify/query/model detail)."""
    id: str
    need_id: str
    stage: NeedProcessStage
    label: str
    description: str = ""
    sequence: int = 0
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class NeedStatement:
    """A complete, immutable expression of a stakeholder need.

    Combines: Stakeholder(id) + Desire + Justifications + metadata.
    This is the frozen record — once expressed, it does not change.
    """
    stakeholder_id: str
    desire: Desire
    justifications: list[Justification] = field(default_factory=list)
    kernel_refs: list[str] = field(default_factory=list)  # ea-kernel entity IDs
    tags: list[str] = field(default_factory=list)
    use_case_id: str | None = None
    purpose: NeedPurpose = NeedPurpose.UNSPECIFIED
    cause_types: list[NeedCauseType] = field(default_factory=list)
    complexity: NeedResolutionComplexity = NeedResolutionComplexity.PROCEDURAL
    expressed_at: str = field(default_factory=_now)
