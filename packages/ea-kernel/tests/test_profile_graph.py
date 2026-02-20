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


# ---------------------------------------------------------------------------
# Scope-aware edge expansion
# ---------------------------------------------------------------------------

def _make_scoped_profile() -> KernelProfile:
    """Profile with containment hierarchy for scope testing.

    Hierarchy:
      Container1 contains PortA, PortB
      Container2 contains PortC, PortD
    """
    return KernelProfile(
        name="ScopedTest",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("Container1", "structure", "L", "Composite"),
            ProfileElement("Container2", "structure", "L", "Composite"),
            ProfileElement("PortA", "port", "L", "Interface"),
            ProfileElement("PortB", "port", "L", "Interface"),
            ProfileElement("PortC", "port", "L", "Interface"),
            ProfileElement("PortD", "port", "L", "Interface"),
        ),
        relations=(
            ProfileRelation("contains", "ownership"),
            ProfileRelation("next", "succession"),
        ),
        validity_rules=(
            # Containment rules
            ProfileRule(
                id="s-contain-1a", source_pattern="Container1",
                target_pattern="PortA", relationship_name="contains",
                valid=True, priority=60,
            ),
            ProfileRule(
                id="s-contain-1b", source_pattern="Container1",
                target_pattern="PortB", relationship_name="contains",
                valid=True, priority=60,
            ),
            ProfileRule(
                id="s-contain-2c", source_pattern="Container2",
                target_pattern="PortC", relationship_name="contains",
                valid=True, priority=60,
            ),
            ProfileRule(
                id="s-contain-2d", source_pattern="Container2",
                target_pattern="PortD", relationship_name="contains",
                valid=True, priority=60,
            ),
            # Global scope: all Interface → Interface (Cartesian product)
            ProfileRule(
                id="s-wire-global", source_pattern="@Interface",
                target_pattern="@Interface", relationship_name="next",
                valid=True, priority=50, scope="",
            ),
        ),
    )


class TestScopeGlobal:
    def test_global_scope_cartesian_product(self):
        """scope="" creates all Interface×Interface edges (4×3=12)."""
        profile = _make_scoped_profile()
        graph = ProfileTopologyGraph(profile)
        next_edges = [
            e for src in graph.nodes
            for e in graph.outgoing(src, "next")
        ]
        # 4 ports × 3 other ports = 12 edges
        assert len(next_edges) == 12


class TestScopeSibling:
    def test_sibling_scope_limits_to_same_container(self):
        """scope="sibling" only creates edges between ports in the same container."""
        from dataclasses import replace
        profile = _make_scoped_profile()
        # Replace the global rule with a sibling-scoped one
        new_rules = tuple(
            r for r in profile.validity_rules if r.id != "s-wire-global"
        ) + (
            ProfileRule(
                id="s-wire-sibling", source_pattern="@Interface",
                target_pattern="@Interface", relationship_name="next",
                valid=True, priority=50, scope="sibling",
            ),
        )
        profile = replace(profile, validity_rules=new_rules)
        graph = ProfileTopologyGraph(profile)
        next_edges = [
            e for src in graph.nodes
            for e in graph.outgoing(src, "next")
        ]
        # Container1: PortA↔PortB = 2 edges
        # Container2: PortC↔PortD = 2 edges
        assert len(next_edges) == 4
        # Verify no cross-container edges
        for e in next_edges:
            assert not (e.source.endswith("A") and e.target.endswith("C"))
            assert not (e.source.endswith("C") and e.target.endswith("A"))


class TestScopeSubtree:
    def test_subtree_scope_limits_to_same_root(self):
        """scope="subtree" only creates edges within the same root subtree."""
        from dataclasses import replace
        # Create a profile with two separate roots
        profile = KernelProfile(
            name="SubtreeTest",
            version="1.0",
            kernel_version="2.5.0",
            elements=(
                ProfileElement("Root1", "structure", "L", "Composite"),
                ProfileElement("Root2", "structure", "L", "Composite"),
                ProfileElement("Child1A", "port", "L", "Interface"),
                ProfileElement("Child2A", "port", "L", "Interface"),
            ),
            relations=(
                ProfileRelation("contains", "ownership"),
                ProfileRelation("next", "succession"),
            ),
            validity_rules=(
                ProfileRule(
                    id="c-1a", source_pattern="Root1",
                    target_pattern="Child1A", relationship_name="contains",
                    valid=True, priority=60,
                ),
                ProfileRule(
                    id="c-2a", source_pattern="Root2",
                    target_pattern="Child2A", relationship_name="contains",
                    valid=True, priority=60,
                ),
                ProfileRule(
                    id="wire-subtree", source_pattern="@Interface",
                    target_pattern="@Interface", relationship_name="next",
                    valid=True, priority=50, scope="subtree",
                ),
            ),
        )
        graph = ProfileTopologyGraph(profile)
        next_edges = [
            e for src in graph.nodes
            for e in graph.outgoing(src, "next")
        ]
        # Child1A and Child2A are in different subtrees → no edges
        assert len(next_edges) == 0


class TestContainmentDepths:
    def test_depths_simple_hierarchy(self):
        """Test containment depth calculation."""
        profile = _make_scoped_profile()
        graph = ProfileTopologyGraph(profile)
        depths = graph.containment_depths()
        # Containers are roots (depth 0)
        assert depths["Container1"] == 0
        assert depths["Container2"] == 0
        # Ports are children (depth 1)
        assert depths["PortA"] == 1
        assert depths["PortB"] == 1
        assert depths["PortC"] == 1
        assert depths["PortD"] == 1

    def test_priority_ordering_prevents_spurious_containment(self):
        """Higher-priority instance rules should win over lower-priority category rules.

        Without priority sorting, @Composite→@Behavior (priority 50) would set
        Mid's container to the first Composite it finds. With priority sorting,
        the explicit rule Root→Mid (priority 60) wins.
        """
        profile = KernelProfile(
            name="PriorityTest",
            version="1.0",
            kernel_version="2.5.0",
            elements=(
                ProfileElement("NodeA", "structure", "L", "Composite"),
                ProfileElement("NodeB", "structure", "L", "Composite"),
                ProfileElement("NodeA.logic", "package", "L", "Behavior"),
                ProfileElement("NodeB.logic", "package", "L", "Behavior"),
            ),
            relations=(
                ProfileRelation("contains", "ownership"),
            ),
            validity_rules=(
                # Category-level rule (lower priority) — Cartesian product
                ProfileRule(
                    id="cat-contain", source_pattern="@Composite",
                    target_pattern="@Behavior", relationship_name="contains",
                    valid=True, priority=50,
                ),
                # Instance-level rules (higher priority) — correct mappings
                ProfileRule(
                    id="inst-a-logic", source_pattern="NodeA",
                    target_pattern="NodeA.logic", relationship_name="contains",
                    valid=True, priority=65,
                ),
                ProfileRule(
                    id="inst-b-logic", source_pattern="NodeB",
                    target_pattern="NodeB.logic", relationship_name="contains",
                    valid=True, priority=65,
                ),
            ),
        )
        graph = ProfileTopologyGraph(profile)
        depths = graph.containment_depths()
        # Instance rules should win: each .logic belongs to its own Node
        assert depths["NodeA"] == 0
        assert depths["NodeB"] == 0
        assert depths["NodeA.logic"] == 1
        assert depths["NodeB.logic"] == 1
        # Verify correct parents
        assert graph._container_of["NodeA.logic"] == "NodeA"
        assert graph._container_of["NodeB.logic"] == "NodeB"

    def test_depths_nested(self):
        """3-level nesting: Root → Mid → Leaf."""
        profile = KernelProfile(
            name="Nested",
            version="1.0",
            kernel_version="2.5.0",
            elements=(
                ProfileElement("Root", "structure", "L", "Composite"),
                ProfileElement("Mid", "package", "L", "Behavior"),
                ProfileElement("Leaf", "port", "L", "Interface"),
            ),
            relations=(
                ProfileRelation("contains", "ownership"),
            ),
            validity_rules=(
                ProfileRule(
                    id="c-rm", source_pattern="Root",
                    target_pattern="Mid", relationship_name="contains",
                    valid=True, priority=60,
                ),
                ProfileRule(
                    id="c-ml", source_pattern="Mid",
                    target_pattern="Leaf", relationship_name="contains",
                    valid=True, priority=60,
                ),
            ),
        )
        graph = ProfileTopologyGraph(profile)
        depths = graph.containment_depths()
        assert depths["Root"] == 0
        assert depths["Mid"] == 1
        assert depths["Leaf"] == 2
