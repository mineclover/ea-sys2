"""Surface relation profile — formal types for surface/deep edge classification.

Extracted from kernel_service.py surface visibility policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from ea_projection.deds import RELATION_DEPTH_SEMANTIC


@dataclass(frozen=True)
class SurfaceRelationProfile:
    """Classifies relations into surface-visibility axes."""

    structural: tuple[str, ...] = ()
    causal: tuple[str, ...] = ()
    operational: tuple[str, ...] = ()
    self_description: tuple[str, ...] = ()
    inheritance_meta: tuple[str, ...] = ()

    @property
    def groups(self) -> dict[str, tuple[str, ...]]:
        """Return all axes as a dict (group_name → relation tuple)."""
        return {
            "structural": self.structural,
            "causal": self.causal,
            "operational": self.operational,
            "self_description": self.self_description,
            "inheritance_meta": self.inheritance_meta,
        }

    @property
    def surface_relations(self) -> tuple[str, ...]:
        return self.structural + self.causal

    def is_surface_exposed(self, relation: str) -> bool:
        return relation.strip().lower() in self.surface_relations

    def depth_semantic(self, relation: str) -> str:
        """Return DEDS depth semantic for a relation (existence/instance/...)."""
        normalized = relation.strip().lower()
        sem = RELATION_DEPTH_SEMANTIC.get(normalized)
        return str(sem) if sem is not None else "unknown"

    def depth_axis(self, relation: str) -> str:
        normalized = relation.strip().lower()
        if normalized in self.structural:
            return "structural"
        if normalized in self.causal:
            return "causal"
        if normalized in self.operational:
            return "operational"
        if normalized in self.self_description:
            return "self_description"
        if normalized in self.inheritance_meta:
            return "inheritance_meta"
        return "unknown"


DEFAULT_SURFACE_PROFILE = SurfaceRelationProfile(
    structural=("contains", "depends_on", "next"),
    causal=("triggers", "constrains"),
    operational=("produces", "consumes", "coordinates"),
    self_description=("registers", "available_in"),
    inheritance_meta=("specialization", "redefinition", "subsetting", "feature_typing"),
)
