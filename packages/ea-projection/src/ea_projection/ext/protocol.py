"""ProjectionExtension protocol — structural subtyping for domain enrichment.

Layers (flow, decision, needs, etc.) implement this protocol to inject
domain-specific metadata into projection views.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProjectionExtension(Protocol):
    """Protocol for domain-specific projection enrichment."""

    @property
    def layer_key(self) -> str:
        """Layer identifier (e.g., 'flow', 'decision')."""
        ...

    def enrich_nodes(
        self,
        nodes: list[dict[str, Any]],
        level: str,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Add domain metadata to nodes. Returns enriched node list."""
        ...

    def enrich_edges(
        self,
        edges: list[dict[str, Any]],
        nodes: list[dict[str, Any]],
        level: str,
    ) -> list[dict[str, Any]]:
        """Enrich edge semantics. Returns enriched edge list."""
        ...

    def supplementary_edges(
        self,
        nodes: list[dict[str, Any]],
        level: str,
        tier: str | None,
    ) -> list[dict[str, Any]]:
        """Generate implicit edges from domain rules. Returns new edges."""
        ...

    def classify_tier(
        self,
        name: str,
        category: str,
        metadata: dict[str, Any] | None,
    ) -> str | None:
        """Domain-specific tier override. Returns tier name or None."""
        ...
