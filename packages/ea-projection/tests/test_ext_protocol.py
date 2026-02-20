"""Tests for ext/ — ProjectionExtension protocol structural subtyping."""

from typing import Any

from ea_projection.ext import ProjectionExtension


class _MockExtension:
    """Satisfies ProjectionExtension via structural subtyping."""

    @property
    def layer_key(self) -> str:
        return "mock"

    def enrich_nodes(self, nodes: list[dict[str, Any]], level: str, tier: str | None) -> list[dict[str, Any]]:
        return nodes

    def enrich_edges(self, edges: list[dict[str, Any]], nodes: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
        return edges

    def supplementary_edges(self, nodes: list[dict[str, Any]], level: str, tier: str | None) -> list[dict[str, Any]]:
        return []

    def classify_tier(self, name: str, category: str, metadata: dict[str, Any] | None) -> str | None:
        return None


class TestProjectionExtensionProtocol:

    def test_structural_subtyping(self):
        ext = _MockExtension()
        assert isinstance(ext, ProjectionExtension)

    def test_layer_key(self):
        ext = _MockExtension()
        assert ext.layer_key == "mock"

    def test_enrich_nodes_passthrough(self):
        ext = _MockExtension()
        nodes = [{"name": "A"}]
        result = ext.enrich_nodes(nodes, "l0", None)
        assert result == nodes

    def test_supplementary_edges_empty(self):
        ext = _MockExtension()
        result = ext.supplementary_edges([], "l0", None)
        assert result == []

    def test_classify_tier_none(self):
        ext = _MockExtension()
        assert ext.classify_tier("test", "Page", None) is None
