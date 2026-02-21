"""SLO target evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SLOComparison(StrEnum):
    """Comparison operator for SLO objective evaluation."""

    GTE = "gte"
    LTE = "lte"


@dataclass(frozen=True)
class SLOTarget:
    """Service level objective definition."""

    name: str
    objective: float
    comparison: SLOComparison = SLOComparison.GTE


@dataclass(frozen=True)
class SLOEvaluation:
    """Result of evaluating a measured value against an SLO target."""

    target: SLOTarget
    current_value: float
    breached: bool
    margin: float


def evaluate_slo(current_value: float, target: SLOTarget) -> SLOEvaluation:
    """Evaluate whether the SLO target is breached."""

    if target.comparison == SLOComparison.GTE:
        margin = current_value - target.objective
        breached = margin < 0
    else:
        margin = target.objective - current_value
        breached = margin < 0

    return SLOEvaluation(
        target=target,
        current_value=current_value,
        breached=breached,
        margin=margin,
    )


def to_slo_breached_event_payload(
    service_id: str,
    evaluation: SLOEvaluation,
    trace_id: str,
    lineage_id: str,
) -> dict[str, Any]:
    """Convert SLO evaluation into a service ops event payload shape."""

    return {
        "trace_id": trace_id,
        "lineage_id": lineage_id,
        "service_id": service_id,
        "slo_name": evaluation.target.name,
        "current_value": evaluation.current_value,
        "target_value": evaluation.target.objective,
        "comparison": evaluation.target.comparison.value,
        "breached": evaluation.breached,
    }
