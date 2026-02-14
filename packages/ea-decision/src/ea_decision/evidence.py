"""Structured evidence types (N1+N2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ea_decision.types import _generate_id, _now


class EvidenceType(StrEnum):
    DOCUMENT = "document"
    DATA = "data"
    EXPERT_OPINION = "expert_opinion"
    BENCHMARK = "benchmark"
    REGULATION = "regulation"


@dataclass(frozen=True)
class Evidence:
    """A single piece of structured evidence."""
    id: str
    type: EvidenceType
    uri: str
    title: str
    description: str = ""
    relevance_score: float = 1.0
    collected_at: str = field(default_factory=_now)


@dataclass(frozen=True)
class EvidenceCollection:
    """Immutable collection of evidence items."""
    id: str = field(default_factory=lambda: _generate_id("evset"))
    items: tuple[Evidence, ...] = ()

    def add(self, evidence: Evidence) -> EvidenceCollection:
        """Return a new collection with the evidence appended."""
        return EvidenceCollection(id=self.id, items=self.items + (evidence,))
