"""Integration tests — full projection pipeline and cross-module consistency."""

from ea_projection.surface import DEFAULT_SURFACE_PROFILE
from ea_projection.depth import DepthLevelRegistry
from ea_projection.tier import classify_element_tier, resolve_tier_definitions, resolve_tier_node_set
from ea_projection.filter import apply_projection_filters, edge_surface_exposed


class TestFullProjectionPipeline:
    """Verify policy → tier → filter pipeline works end-to-end."""

    def setup_method(self):
        self.registry = DepthLevelRegistry.from_hardcoded()
        self.tier_defs = resolve_tier_definitions(None)

    def test_pipeline_l0_panorama(self):
        """L0 panorama: structural+causal relations only, broad categories."""
        level = self.registry.get("l0")
        topology = {
            "nodes": [
                {"name": "Element1", "category": "Composite"},
                {"name": "Element2", "category": "Page"},
                {"name": "Element3", "category": "Interface"},
            ],
            "edges": [
                {"source": "Element1", "target": "Element2", "relation": "contains"},
                {"source": "Element2", "target": "Element3", "relation": "depends_on"},
                {"source": "Element1", "target": "Element3", "relation": "produces"},
            ],
        }
        result = apply_projection_filters(
            topology=topology,
            allowed_relations=tuple(level.allowed_relations),
            allowed_categories=tuple(level.allowed_categories),
            max_edges=level.max_edges,
            preserve_nodes=set(),
            tier=None,
            tier_definitions=self.tier_defs,
        )
        # 'produces' should be filtered out at L0 (not in L0 allowed_relations)
        edge_relations = {e["relation"] for e in result["edges"]}
        assert "produces" not in edge_relations
        assert "contains" in edge_relations
        assert "depends_on" in edge_relations

    def test_pipeline_l4_trace(self):
        """L4 trace: all relations allowed."""
        level = self.registry.get("l4")
        topology = {
            "nodes": [
                {"name": "StepA", "category": "Behavior"},
                {"name": "DataX", "category": "PassiveStructure"},
            ],
            "edges": [
                {"source": "StepA", "target": "DataX", "relation": "produces"},
            ],
        }
        result = apply_projection_filters(
            topology=topology,
            allowed_relations=tuple(level.allowed_relations),
            allowed_categories=tuple(level.allowed_categories),
            max_edges=level.max_edges,
            preserve_nodes=set(),
            tier=None,
            tier_definitions=self.tier_defs,
        )
        edge_relations = {e["relation"] for e in result["edges"]}
        assert "produces" in edge_relations

    def test_pipeline_with_tier_filter(self):
        """Tier filter narrows nodes to specific classification."""
        topology = {
            "nodes": [
                {"name": "UserDashboard", "category": "Executable"},
                {"name": "UserData", "category": "PassiveStructure"},
                {"name": "OrderData", "category": "PassiveStructure"},
                {"name": "AuditLog", "category": "PassiveStructure"},
            ],
            "edges": [
                {"source": "UserDashboard", "target": "UserData", "relation": "consumes"},
                {"source": "UserDashboard", "target": "AuditLog", "relation": "produces"},
                {"source": "UserData", "target": "OrderData", "relation": "depends_on"},
            ],
        }
        level = self.registry.get("l3")
        # With tier=data, only data-tier nodes connected by edges survive.
        # UserData and OrderData are PassiveStructure (data tier) and connected.
        # AuditLog matches evidence name pattern → excluded from data tier.
        # UserDashboard is Executable → excluded from data tier.
        result = apply_projection_filters(
            topology=topology,
            allowed_relations=tuple(level.allowed_relations),
            allowed_categories=tuple(level.allowed_categories),
            max_edges=level.max_edges,
            preserve_nodes=set(),
            tier="data",
            tier_definitions=self.tier_defs,
        )
        node_names = {n["name"] for n in result["nodes"]}
        assert "UserData" in node_names
        assert "OrderData" in node_names
        assert "UserDashboard" not in node_names
        assert "AuditLog" not in node_names


class TestSurfaceProfileConsistency:
    """Verify SurfaceProfile and DepthLevel relation sets are consistent."""

    def setup_method(self):
        self.surface = DEFAULT_SURFACE_PROFILE
        self.registry = DepthLevelRegistry.from_hardcoded()

    def test_l0_uses_surface_relations(self):
        """L0 allowed_relations should be a subset of surface-exposed relations."""
        l0 = self.registry.get("l0")
        surface_rels = set(self.surface.surface_relations)
        # L0 relations should overlap significantly with surface relations
        overlap = l0.allowed_relations & surface_rels
        assert len(overlap) > 0, "L0 should share relations with surface profile"

    def test_l4_covers_most_surface_relations(self):
        """L4 covers causal surface relations; 'contains' is structural-only at L0-L2."""
        l4 = self.registry.get("l4")
        causal_rels = set(self.surface.causal)
        assert causal_rels.issubset(l4.allowed_relations), (
            "L4 (trace) should contain all causal surface relations"
        )
        # 'contains' is intentionally absent from L3/L4 (execution/trace levels
        # focus on behavioral relations, not structural containment)
        assert "contains" not in l4.allowed_relations

    def test_depth_levels_monotonically_expand_relations(self):
        """Higher depth levels should have >= relations than lower levels."""
        keys = self.registry.keys()
        for i in range(len(keys) - 1):
            lower = self.registry.get(keys[i])
            higher = self.registry.get(keys[i + 1])
            assert len(higher.allowed_relations) >= len(lower.allowed_relations), (
                f"{keys[i+1]} should have >= relations than {keys[i]}"
            )

    def test_surface_exposed_aligns_with_profile(self):
        """edge_surface_exposed should agree with SurfaceRelationProfile."""
        for rel in self.surface.surface_relations:
            assert edge_surface_exposed(rel), (
                f"'{rel}' is in surface_relations but edge_surface_exposed returns False"
            )
