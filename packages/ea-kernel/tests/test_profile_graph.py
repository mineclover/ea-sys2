"""Tests for profile_graph — ProfileTopologyGraph."""

from __future__ import annotations

import pytest
from ea_kernel.profile_graph import ProfileEdge, ProfilePath, ProfileTopologyGraph
from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileRelation, ProfileRule


def _make_profile() -> KernelProfile:
    """Small profile with known topology for deterministic tests."""
    return KernelProfile(
        name="Test",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("Boundary", "package", "App", "Composite"),
            ProfileElement("ServiceA", "structure", "App", "ActiveStructure"),
            ProfileElement("ServiceB", "structure", "App", "ActiveStructure"),
            ProfileElement("PortX", "port", "App", "Interface"),
            ProfileElement("StepOne", "step", "App", "Behavior"),
            ProfileElement("StepTwo", "step", "App", "Behavior"),
            ProfileElement("DataStore", "item", "App", "PassiveStructure"),
        ),
        relations=(
            ProfileRelation("contains", "ownership"),
            ProfileRelation("coordinates", "association"),
            ProfileRelation("next", "succession"),
            ProfileRelation("produces", "flow", direction="out"),
            ProfileRelation("consumes", "flow", direction="in"),
        ),
        validity_rules=(
            # Pattern rules
            ProfileRule(
                id="r-contain-svc",
                source_pattern="@Composite",
                target_pattern="@ActiveStructure",
                relationship_name="contains",
                valid=True, priority=50,
            ),
            ProfileRule(
                id="r-contain-iface",
                source_pattern="@Composite",
                target_pattern="@Interface",
                relationship_name="contains",
                valid=True, priority=50,
            ),
            ProfileRule(
                id="r-step-next",
                source_pattern="@Behavior",
                target_pattern="@Behavior",
                relationship_name="next",
                valid=True, priority=50,
            ),
            ProfileRule(
                id="r-step-produce",
                source_pattern="@Behavior",
                target_pattern="@PassiveStructure",
                relationship_name="produces",
                valid=True, priority=50,
            ),
            # Explicit rules
            ProfileRule(
                id="r-svc-coord",
                source_pattern="ServiceA",
                target_pattern="ServiceB",
                relationship_name="coordinates",
                valid=True, priority=70,
            ),
            ProfileRule(
                id="r-port-coord",
                source_pattern="PortX",
                target_pattern="ServiceA",
                relationship_name="coordinates",
                valid=True, priority=70,
            ),
            ProfileRule(
                id="r-step1-step2",
                source_pattern="StepOne",
                target_pattern="StepTwo",
                relationship_name="next",
                valid=True, priority=70,
            ),
            ProfileRule(
                id="r-step2-data",
                source_pattern="StepTwo",
                target_pattern="DataStore",
                relationship_name="produces",
                valid=True, priority=70,
            ),
            # Deny rule — should be excluded from edges
            ProfileRule(
                id="deny-all-coord",
                source_pattern="*",
                target_pattern="*",
                relationship_name="coordinates",
                valid=False, priority=1,
            ),
        ),
    )


class TestProfileTopologyGraph:
    def test_nodes(self):
        graph = ProfileTopologyGraph(_make_profile())
        assert len(graph.nodes) == 7

    def test_edge_count_positive(self):
        graph = ProfileTopologyGraph(_make_profile())
        assert graph.edge_count > 0

    def test_deny_rules_excluded(self):
        graph = ProfileTopologyGraph(_make_profile())
        # deny-all-coord should not create edges
        for edges in graph._outgoing.values():
            for e in edges:
                assert e.rule_id != "deny-all-coord"

    def test_self_loop_excluded(self):
        graph = ProfileTopologyGraph(_make_profile())
        for edges in graph._outgoing.values():
            for e in edges:
                assert e.source != e.target

    def test_outgoing(self):
        graph = ProfileTopologyGraph(_make_profile())
        edges = graph.outgoing("ServiceA")
        assert len(edges) > 0
        # ServiceA -> ServiceB via coordinates
        coord_edges = graph.outgoing("ServiceA", "coordinates")
        targets = {e.target for e in coord_edges}
        assert "ServiceB" in targets

    def test_incoming(self):
        graph = ProfileTopologyGraph(_make_profile())
        edges = graph.incoming("ServiceA")
        assert len(edges) > 0
        # PortX -> ServiceA
        sources = {e.source for e in edges}
        assert "PortX" in sources

    def test_neighbors(self):
        graph = ProfileTopologyGraph(_make_profile())
        nbrs = graph.neighbors("Boundary")
        # Boundary contains ActiveStructure and Interface elements
        assert "ServiceA" in nbrs
        assert "ServiceB" in nbrs
        assert "PortX" in nbrs

    def test_outgoing_relation_filter(self):
        graph = ProfileTopologyGraph(_make_profile())
        all_edges = graph.outgoing("Boundary")
        contains_only = graph.outgoing("Boundary", "contains")
        assert len(contains_only) <= len(all_edges)
        assert all(e.relation == "contains" for e in contains_only)


class TestReachability:
    def test_basic_reachable(self):
        graph = ProfileTopologyGraph(_make_profile())
        reached = graph.reachable("PortX", max_depth=3)
        assert "ServiceA" in reached
        assert "ServiceB" in reached

    def test_reachable_depth_limit(self):
        graph = ProfileTopologyGraph(_make_profile())
        shallow = graph.reachable("PortX", max_depth=1)
        deep = graph.reachable("PortX", max_depth=5)
        assert len(shallow) <= len(deep)

    def test_reachable_with_relation_filter(self):
        graph = ProfileTopologyGraph(_make_profile())
        coord_only = graph.reachable(
            "PortX", max_depth=3, relation_filter=frozenset(["coordinates"]),
        )
        assert "ServiceA" in coord_only
        assert "ServiceB" in coord_only

    def test_unknown_element_returns_empty(self):
        graph = ProfileTopologyGraph(_make_profile())
        assert graph.reachable("NonExistent") == ()


class TestFindPaths:
    def test_direct_path(self):
        graph = ProfileTopologyGraph(_make_profile())
        paths = graph.find_paths("PortX", "ServiceA")
        assert len(paths) >= 1
        assert any(len(p.edges) == 1 for p in paths)

    def test_multi_hop_path(self):
        graph = ProfileTopologyGraph(_make_profile())
        paths = graph.find_paths("PortX", "ServiceB")
        assert len(paths) >= 1
        # At least one path PortX -> ServiceA -> ServiceB
        assert any(len(p.edges) == 2 for p in paths)

    def test_step_chain_path(self):
        graph = ProfileTopologyGraph(_make_profile())
        paths = graph.find_paths("StepOne", "DataStore")
        assert len(paths) >= 1

    def test_no_path_returns_empty(self):
        graph = ProfileTopologyGraph(_make_profile())
        # DataStore has no outgoing edges to PortX
        paths = graph.find_paths("DataStore", "PortX")
        assert paths == ()

    def test_unknown_element_returns_empty(self):
        graph = ProfileTopologyGraph(_make_profile())
        assert graph.find_paths("Unknown", "ServiceA") == ()
        assert graph.find_paths("ServiceA", "Unknown") == ()

    def test_relation_filter(self):
        graph = ProfileTopologyGraph(_make_profile())
        paths = graph.find_paths(
            "PortX", "ServiceB",
            relation_filter=frozenset(["coordinates"]),
        )
        for p in paths:
            assert all(e.relation == "coordinates" for e in p.edges)


class TestImpactAnalysis:
    def test_outgoing_impact(self):
        graph = ProfileTopologyGraph(_make_profile())
        impact = graph.impact_analysis("PortX", direction="outgoing")
        assert len(impact) > 0
        assert "ServiceA" in impact

    def test_incoming_impact(self):
        graph = ProfileTopologyGraph(_make_profile())
        impact = graph.impact_analysis("ServiceA", direction="incoming")
        assert len(impact) > 0
        assert "PortX" in impact

    def test_both_directions(self):
        graph = ProfileTopologyGraph(_make_profile())
        impact = graph.impact_analysis("ServiceA", direction="both")
        # Outgoing: ServiceB at least; Incoming: PortX, Boundary
        assert len(impact) >= 2


class TestRelationDistribution:
    def test_distribution(self):
        graph = ProfileTopologyGraph(_make_profile())
        dist = graph.relation_distribution()
        assert "contains" in dist
        assert "coordinates" in dist
        assert dist["contains"] > 0


class TestEmptyProfile:
    def test_empty_elements(self):
        profile = KernelProfile(
            name="Empty", version="1.0", kernel_version="2.5.0",
            elements=(), relations=(), validity_rules=(),
        )
        graph = ProfileTopologyGraph(profile)
        assert graph.nodes == ()
        assert graph.edge_count == 0
        assert graph.reachable("anything") == ()

    def test_single_element_no_rules(self):
        profile = KernelProfile(
            name="Single", version="1.0", kernel_version="2.5.0",
            elements=(ProfileElement("Only", "item", "L", "C"),),
            relations=(),
            validity_rules=(),
        )
        graph = ProfileTopologyGraph(profile)
        assert graph.nodes == ("Only",)
        assert graph.edge_count == 0
