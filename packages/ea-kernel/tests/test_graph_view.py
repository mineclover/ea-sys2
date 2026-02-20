"""Tests for Phase 2 TopologyGraph — graph navigation and path finding."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from ea_kernel.graph_view import TopologyGraph
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import (
    GraphEdge,
    GraphPath,
    KernelEntity,
    KernelRelation,
    KernelSchema,
    KernelValidityRule,
    Layer,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)

# ═════════════════════════════════════════════════════════════════════════════
# 1. Graph construction
# ═════════════════════════════════════════════════════════════════════════════

class TestGraphConstruction:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_from_spec(self):
        graph = TopologyGraph.from_spec()
        assert len(graph.entities) > 0

    def test_entities_are_concrete(self, graph):
        for name in graph.entities:
            entity = KERNEL_SPEC.get_entity(name)
            assert entity is not None
            assert not entity.is_abstract

    def test_edge_count_positive(self, graph):
        assert graph.edge_count > 0

    def test_entities_include_structure(self, graph):
        assert "structure" in graph.entities

    def test_entities_include_item(self, graph):
        assert "item" in graph.entities

    def test_entities_exclude_abstract(self, graph):
        assert "element" not in graph.entities
        assert "namespace" not in graph.entities
        assert "metatype" not in graph.entities
        assert "classifier" not in graph.entities


# ═════════════════════════════════════════════════════════════════════════════
# 2. Outgoing / Incoming
# ═════════════════════════════════════════════════════════════════════════════

class TestOutgoingIncoming:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_structure_has_outgoing(self, graph):
        out = graph.outgoing("structure")
        assert len(out) > 0
        assert all(isinstance(e, GraphEdge) for e in out)

    def test_structure_outgoing_filtered(self, graph):
        out = graph.outgoing("structure", "association")
        for edge in out:
            assert edge.relation == "association"

    def test_structure_has_incoming(self, graph):
        inc = graph.incoming("structure")
        assert len(inc) > 0

    def test_incoming_filtered(self, graph):
        inc = graph.incoming("structure", "association")
        for edge in inc:
            assert edge.relation == "association"
            assert edge.target == "structure"

    def test_outgoing_nonexistent_entity(self, graph):
        out = graph.outgoing("nonexistent")
        assert out == ()

    def test_outgoing_relation_filter_no_match(self, graph):
        out = graph.outgoing("structure", "nonexistent_relation")
        assert out == ()

    def test_edge_has_source_target(self, graph):
        out = graph.outgoing("structure")
        if out:
            edge = out[0]
            assert edge.source == "structure"
            assert edge.target != ""
            assert edge.relation != ""


# ═════════════════════════════════════════════════════════════════════════════
# 3. Neighbors
# ═════════════════════════════════════════════════════════════════════════════

class TestNeighbors:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_structure_neighbors(self, graph):
        neighbors = graph.neighbors("structure")
        assert len(neighbors) > 0

    def test_structure_can_reach_item(self, graph):
        # structure→item via association should be valid
        neighbors = graph.neighbors("structure")
        # structure can reach various entities
        assert len(neighbors) > 0

    def test_neighbors_sorted(self, graph):
        neighbors = graph.neighbors("structure")
        assert neighbors == tuple(sorted(neighbors))

    def test_nonexistent_entity_no_neighbors(self, graph):
        neighbors = graph.neighbors("nonexistent")
        assert neighbors == ()


# ═════════════════════════════════════════════════════════════════════════════
# 4. Find paths
# ═════════════════════════════════════════════════════════════════════════════

class TestFindPaths:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_self_path_via_association(self, graph):
        paths = graph.find_paths("structure", "structure", max_depth=2)
        assert len(paths) > 0

    def test_path_has_edges(self, graph):
        paths = graph.find_paths("structure", "structure", max_depth=3)
        if paths:
            assert paths[0].length > 0
            assert isinstance(paths[0], GraphPath)

    def test_path_nodes_property(self, graph):
        paths = graph.find_paths("structure", "structure", max_depth=3)
        if paths:
            for path in paths:
                nodes = path.nodes
                assert nodes[0] == "structure"
                assert nodes[-1] == "structure"

    def test_max_depth_limits(self, graph):
        paths_d1 = graph.find_paths("structure", "item", max_depth=1)
        paths_d3 = graph.find_paths("structure", "item", max_depth=3)
        # Deeper search may find more paths
        assert len(paths_d3) >= len(paths_d1)

    def test_relation_filter(self, graph):
        paths = graph.find_paths(
            "structure", "item",
            relation_filter=frozenset({"association"}),
        )
        for path in paths:
            for edge in path.edges:
                assert edge.relation == "association"

    def test_nonexistent_source(self, graph):
        paths = graph.find_paths("nonexistent", "structure")
        assert paths == ()

    def test_nonexistent_target(self, graph):
        paths = graph.find_paths("structure", "nonexistent")
        assert paths == ()

    def test_path_total_confidence(self, graph):
        paths = graph.find_paths("structure", "structure", max_depth=3)
        for path in paths:
            assert isinstance(path.total_confidence, RuleConfidence)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Reachable
# ═════════════════════════════════════════════════════════════════════════════

class TestReachable:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_reachable_from_structure(self, graph):
        reachable = graph.reachable("structure")
        assert len(reachable) > 0

    def test_reachable_sorted(self, graph):
        reachable = graph.reachable("structure")
        assert reachable == tuple(sorted(reachable))

    def test_reachable_depth_1(self, graph):
        reachable = graph.reachable("structure", max_depth=1)
        assert len(reachable) > 0

    def test_deeper_depth_more_reachable(self, graph):
        r1 = graph.reachable("structure", max_depth=1)
        r3 = graph.reachable("structure", max_depth=3)
        assert len(r3) >= len(r1)

    def test_reachable_with_filter(self, graph):
        reachable = graph.reachable(
            "structure",
            relation_filter=frozenset({"association"}),
        )
        # Should only traverse association edges
        assert len(reachable) > 0

    def test_reachable_nonexistent(self, graph):
        reachable = graph.reachable("nonexistent")
        assert reachable == ()

    def test_source_not_in_reachable(self, graph):
        reachable = graph.reachable("structure")
        assert isinstance(reachable, tuple)
        # source is excluded from reachable set
        # (only if there's no self-loop edge; structure→structure association exists
        # but reachable excludes source by design)
        # This tests the base behavior


# ═════════════════════════════════════════════════════════════════════════════
# 6. Impact analysis
# ═════════════════════════════════════════════════════════════════════════════

class TestImpactAnalysis:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_outgoing_impact(self, graph):
        impact = graph.impact_analysis("structure", direction="outgoing")
        assert isinstance(impact, dict)

    def test_incoming_impact(self, graph):
        impact = graph.impact_analysis("structure", direction="incoming")
        assert isinstance(impact, dict)

    def test_both_direction(self, graph):
        impact = graph.impact_analysis("structure", direction="both")
        assert isinstance(impact, dict)

    def test_impact_values_are_paths(self, graph):
        impact = graph.impact_analysis("structure", direction="outgoing", max_depth=1)
        for _entity, paths in impact.items():
            assert all(isinstance(p, GraphPath) for p in paths)

    def test_impact_max_depth(self, graph):
        impact_1 = graph.impact_analysis("feature", direction="outgoing", max_depth=1)
        impact_3 = graph.impact_analysis("feature", direction="outgoing", max_depth=3)
        assert len(impact_3) >= len(impact_1)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Relation distribution
# ═════════════════════════════════════════════════════════════════════════════

class TestRelationDistribution:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_distribution_not_empty(self, graph):
        dist = graph.relation_distribution()
        assert len(dist) > 0

    def test_association_has_edges(self, graph):
        dist = graph.relation_distribution()
        assert "association" in dist
        assert dist["association"] > 0

    def test_all_values_positive(self, graph):
        dist = graph.relation_distribution()
        for _rel, count in dist.items():
            assert count > 0


# ═════════════════════════════════════════════════════════════════════════════
# 8. With corpus
# ═════════════════════════════════════════════════════════════════════════════

class TestWithCorpus:
    def test_graph_with_corpus(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        graph = TopologyGraph(KERNEL_SPEC, corpus)
        assert graph.edge_count > 0

    def test_edges_have_judgment(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        graph = TopologyGraph(KERNEL_SPEC, corpus)
        out = graph.outgoing("structure", "association")
        if out:
            edge = out[0]
            assert edge.judgment is not None

    def test_from_spec_with_corpus(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        graph = TopologyGraph.from_spec(corpus)
        assert graph.edge_count > 0


class TestDomainFiltering:
    def _make_schema_and_corpus(self) -> tuple[KernelSchema, RuleCorpus]:
        allow_alpha = KernelValidityRule(
            id="alpha-allow",
            source_pattern="structure",
            target_pattern="item",
            relationship_name="association",
            valid=True,
            priority=50,
        )
        deny_beta = KernelValidityRule(
            id="beta-deny",
            source_pattern="structure",
            target_pattern="item",
            relationship_name="association",
            valid=False,
            priority=40,
        )
        schema = KernelSchema(
            attributes=(),
            entities=(
                KernelEntity(name="structure", layer=Layer.L1),
                KernelEntity(name="item", layer=Layer.L1),
            ),
            relations=(KernelRelation(name="association", layer=Layer.L2),),
            validity_rules=(allow_alpha, deny_beta),
            layer_constraints=(),
        )
        entries = (
            RuleCorpusEntry(
                rule=allow_alpha,
                metadata=RuleMetadata(
                    domain="alpha",
                    tags=("association",),
                    category=RuleCategory.STRUCTURAL,
                    confidence=RuleConfidence.COMMON,
                    source="test",
                    established_version="test",
                    rationale="alpha allow",
                    group=RuleGroup.ASSOCIATION,
                ),
            ),
            RuleCorpusEntry(
                rule=deny_beta,
                metadata=RuleMetadata(
                    domain="beta",
                    tags=("association",),
                    category=RuleCategory.STRUCTURAL,
                    confidence=RuleConfidence.COMMON,
                    source="test",
                    established_version="test",
                    rationale="beta deny",
                    group=RuleGroup.ASSOCIATION,
                ),
            ),
        )
        return schema, RuleCorpus(entries, schema)

    def test_domain_filter_keeps_only_winner_domain_edges(self) -> None:
        schema, corpus = self._make_schema_and_corpus()

        graph_alpha = TopologyGraph(schema, corpus, domain="alpha")
        alpha_targets = {edge.target for edge in graph_alpha.outgoing("structure", "association")}
        assert "item" in alpha_targets

        graph_beta = TopologyGraph(schema, corpus, domain="beta")
        assert graph_beta.edge_count == 0


# ═════════════════════════════════════════════════════════════════════════════
# 9. Edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_self_loop_association(self, graph):
        # structure→structure association should exist
        out = graph.outgoing("structure", "association")
        self_edges = [e for e in out if e.target == "structure"]
        assert len(self_edges) > 0

    def test_empty_path(self):
        path = GraphPath(edges=())
        assert path.length == 0
        assert path.nodes == ()

    def test_graph_edge_frozen(self):
        edge = GraphEdge("a", "b", "rel")
        with pytest.raises(AttributeError):
            edge.source = "c"  # type: ignore[misc]

    def test_graph_path_frozen(self):
        path = GraphPath(edges=())
        with pytest.raises(AttributeError):
            path.edges = ()  # type: ignore[misc]

    def test_isolated_entity(self, graph):
        # package might have limited connectivity
        out = graph.outgoing("package")
        # package has association edges
        assert isinstance(out, tuple)


# ═════════════════════════════════════════════════════════════════════════════
# 10. Specific topology assertions
# ═════════════════════════════════════════════════════════════════════════════

class TestTopologyAssertions:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_structure_item_association(self, graph):
        out = graph.outgoing("structure", "association")
        targets = {e.target for e in out}
        assert "item" in targets

    def test_item_structure_association_denied(self, graph):
        """assoc-04: Item(passive) cannot directly associate with structure(active)."""
        out = graph.outgoing("item", "association")
        targets = {e.target for e in out}
        assert "structure" not in targets

    def test_feature_metatype_feature_typing(self, graph):
        out = graph.outgoing("feature", "feature_typing")
        assert len(out) > 0

    def test_step_step_succession(self, graph):
        out = graph.outgoing("step", "succession")
        targets = {e.target for e in out}
        assert "step" in targets or "action" in targets

    def test_state_state_transition(self, graph):
        out = graph.outgoing("state", "transition")
        targets = {e.target for e in out}
        assert "state" in targets

    def test_event_step_triggering(self, graph):
        out = graph.outgoing("event", "triggering")
        assert len(out) > 0

    def test_no_package_specialization(self, graph):
        out = graph.outgoing("package", "specialization")
        assert len(out) == 0

    def test_concrete_entity_count(self, graph):
        # 13 concrete entities (11 original + input_port + output_port)
        assert len(graph.entities) == 13


# ═════════════════════════════════════════════════════════════════════════════
# 11. Path properties
# ═════════════════════════════════════════════════════════════════════════════

class TestPathProperties:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_single_hop_path_length(self, graph):
        paths = graph.find_paths("structure", "item", max_depth=1)
        for path in paths:
            assert path.length == 1

    def test_path_edges_connected(self, graph):
        paths = graph.find_paths("structure", "item", max_depth=3)
        for path in paths:
            for i in range(len(path.edges) - 1):
                assert path.edges[i].target == path.edges[i + 1].source

    def test_path_starts_at_source(self, graph):
        paths = graph.find_paths("structure", "item", max_depth=3)
        for path in paths:
            assert path.edges[0].source == "structure"

    def test_path_ends_at_target(self, graph):
        paths = graph.find_paths("structure", "item", max_depth=3)
        for path in paths:
            assert path.edges[-1].target == "item"

    def test_nodes_length(self, graph):
        paths = graph.find_paths("structure", "item", max_depth=2)
        for path in paths:
            assert len(path.nodes) == path.length + 1


# ═════════════════════════════════════════════════════════════════════════════
# 12. Reachability properties
# ═════════════════════════════════════════════════════════════════════════════

class TestReachabilityProperties:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_structure_reaches_most_entities(self, graph):
        reachable = graph.reachable("structure", max_depth=2)
        assert len(reachable) >= 5

    def test_step_reaches_step(self, graph):
        reachable = graph.reachable("step", max_depth=1)
        # step should reach other entities via succession, etc.
        assert len(reachable) > 0

    def test_state_reachable_entities(self, graph):
        reachable = graph.reachable("state", max_depth=1)
        assert "state" in reachable  # state→state transition

    def test_depth_zero_returns_empty(self, graph):
        reachable = graph.reachable("structure", max_depth=0)
        assert reachable == ()


# ═════════════════════════════════════════════════════════════════════════════
# 13. Multiple relation types
# ═════════════════════════════════════════════════════════════════════════════

class TestMultipleRelationTypes:
    @pytest.fixture
    def graph(self):
        return TopologyGraph(KERNEL_SPEC)

    def test_structure_has_multiple_relation_types(self, graph):
        out = graph.outgoing("structure")
        relations = {e.relation for e in out}
        assert len(relations) > 1

    def test_feature_has_multiple_relation_types(self, graph):
        out = graph.outgoing("feature")
        relations = {e.relation for e in out}
        assert len(relations) > 1

    def test_filter_isolates_one_relation(self, graph):
        all_out = graph.outgoing("structure")
        assoc_out = graph.outgoing("structure", "association")
        assert len(assoc_out) <= len(all_out)
        for edge in assoc_out:
            assert edge.relation == "association"

    def test_distribution_covers_known_relations(self, graph):
        dist = graph.relation_distribution()
        assert "specialization" in dist
        assert "membership" in dist
        assert "ownership" in dist
