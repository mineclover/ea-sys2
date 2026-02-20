"""Tests for filter/ — projection filter engine."""

from ea_projection.filter import apply_projection_filters, edge_surface_exposed
from ea_projection.tier.resolver import TIER_DEFINITIONS_FALLBACK


def _make_topology(nodes, edges):
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


class TestApplyProjectionFilters:

    def test_filter_by_allowed_relations(self):
        topo = _make_topology(
            nodes=[
                {"name": "A", "category": "Composite"},
                {"name": "B", "category": "Composite"},
            ],
            edges=[
                {"source": "A", "target": "B", "relation": "contains"},
                {"source": "A", "target": "B", "relation": "produces"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=("contains",),
            allowed_categories=None,
            max_edges=None,
        )
        assert result["edge_count"] == 1
        assert result["edges"][0]["relation"] == "contains"

    def test_filter_by_allowed_categories(self):
        topo = _make_topology(
            nodes=[
                {"name": "A", "category": "Page"},
                {"name": "B", "category": "Behavior"},
                {"name": "C", "category": "Page"},
            ],
            edges=[
                {"source": "A", "target": "C", "relation": "contains"},
                {"source": "A", "target": "B", "relation": "contains"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=("Page",),
            max_edges=None,
        )
        assert result["node_count"] == 2
        assert all(n["category"] == "Page" for n in result["nodes"])

    def test_filter_by_tier(self):
        topo = _make_topology(
            nodes=[
                {"name": "LoginPage", "category": "Page"},
                {"name": "HandleLogin", "category": "Behavior"},
            ],
            edges=[
                {"source": "LoginPage", "target": "HandleLogin", "relation": "triggers"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=None,
            tier="ui",
            tier_definitions=TIER_DEFINITIONS_FALLBACK,
        )
        # Only LoginPage matches ui tier; HandleLogin is function tier
        # Edge between them is filtered since HandleLogin isn't in candidate set
        assert result["node_count"] == 0  # no edges means no connected nodes

    def test_filter_edge_budget(self):
        topo = _make_topology(
            nodes=[{"name": f"N{i}", "category": "Composite"} for i in range(10)],
            edges=[
                {"source": f"N{i}", "target": f"N{i+1}", "relation": "contains", "priority": 50}
                for i in range(9)
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=5,
        )
        assert result["edge_count"] == 5
        assert result["edge_truncated"] is True

    def test_filter_preserve_nodes(self):
        topo = _make_topology(
            nodes=[
                {"name": "A", "category": "Composite"},
                {"name": "B", "category": "Composite"},
            ],
            edges=[
                {"source": "A", "target": "B", "relation": "contains"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=("Page",),  # Neither A nor B match
            max_edges=None,
            preserve_nodes={"A", "B"},
        )
        # Preserve overrides category filter
        assert result["edge_count"] == 1
        assert result["node_count"] == 2

    def test_projection_filter_metadata(self):
        topo = _make_topology(
            nodes=[{"name": "A", "category": "Page"}],
            edges=[],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=None,
        )
        assert "projection_filter" in result
        pf = result["projection_filter"]
        assert "stages" in pf
        assert "drop_reasons" in pf
        assert "preserve" in pf


class TestContainmentDepthFilter:

    def test_max_containment_depth_0_filters_deep_nodes(self):
        topo = _make_topology(
            nodes=[
                {"name": "Root", "category": "Composite", "containment_depth": 0},
                {"name": "Child", "category": "Composite", "containment_depth": 1},
                {"name": "Grandchild", "category": "Composite", "containment_depth": 2},
            ],
            edges=[
                {"source": "Root", "target": "Child", "relation": "contains"},
                {"source": "Child", "target": "Grandchild", "relation": "contains"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=None,
            max_containment_depth=0,
        )
        # Only Root survives, but with no connected edges it may not appear
        # Actually: Root→Child edge is filtered because Child is depth 1
        assert result["node_count"] == 0  # no edges → no connected nodes
        pf = result["projection_filter"]
        assert pf["drop_reasons"]["node_depth_filtered"] == 2

    def test_max_containment_depth_1_includes_children(self):
        topo = _make_topology(
            nodes=[
                {"name": "Root", "category": "Composite", "containment_depth": 0},
                {"name": "Child", "category": "Composite", "containment_depth": 1},
                {"name": "Grandchild", "category": "Composite", "containment_depth": 2},
            ],
            edges=[
                {"source": "Root", "target": "Child", "relation": "contains"},
                {"source": "Child", "target": "Grandchild", "relation": "contains"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=None,
            max_containment_depth=1,
        )
        # Root and Child survive; Grandchild filtered
        assert result["edge_count"] == 1
        assert result["node_count"] == 2
        pf = result["projection_filter"]
        assert pf["drop_reasons"]["node_depth_filtered"] == 1

    def test_max_containment_depth_none_passes_all(self):
        topo = _make_topology(
            nodes=[
                {"name": "Root", "category": "Composite", "containment_depth": 0},
                {"name": "Deep", "category": "Composite", "containment_depth": 5},
            ],
            edges=[
                {"source": "Root", "target": "Deep", "relation": "contains"},
            ],
        )
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=None,
            max_containment_depth=None,
        )
        assert result["edge_count"] == 1
        assert result["node_count"] == 2
        pf = result["projection_filter"]
        assert pf["drop_reasons"]["node_depth_filtered"] == 0

    def test_drop_reasons_include_node_depth_filtered(self):
        topo = _make_topology(nodes=[], edges=[])
        result = apply_projection_filters(
            topology=topo,
            allowed_relations=None,
            allowed_categories=None,
            max_edges=None,
        )
        assert "node_depth_filtered" in result["projection_filter"]["drop_reasons"]


class TestEdgeSurfaceExposed:

    def test_surface_relations(self):
        assert edge_surface_exposed("contains") is True
        assert edge_surface_exposed("depends_on") is True
        assert edge_surface_exposed("next") is True
        assert edge_surface_exposed("triggers") is True
        assert edge_surface_exposed("constrains") is True

    def test_deep_relations(self):
        assert edge_surface_exposed("produces") is False
        assert edge_surface_exposed("consumes") is False
        assert edge_surface_exposed("registers") is False
