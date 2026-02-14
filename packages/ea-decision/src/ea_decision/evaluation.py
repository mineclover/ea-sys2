"""Evaluation framework types (N2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class EvaluationDimension:
    """A single axis of evaluation (e.g., cost, performance, risk)."""
    name: str
    description: str
    weight: float = 1.0
    scale: str = "qualitative"  # e.g., "1-5", "USD", "ms"


@dataclass(frozen=True)
class OptionScore:
    """Score of one option on one dimension."""
    option_id: str
    dimension_name: str
    value: float
    rationale: str = ""


@dataclass(frozen=True)
class EvaluationResult:
    """Aggregated evaluation across all dimensions for a set of options."""
    dimensions: tuple[EvaluationDimension, ...] = ()
    scores: tuple[OptionScore, ...] = ()

    def weighted_total(self, option_id: str) -> float:
        weight_map = {d.name: d.weight for d in self.dimensions}
        total = 0.0
        for s in self.scores:
            if s.option_id == option_id:
                total += s.value * weight_map.get(s.dimension_name, 1.0)
        return total
