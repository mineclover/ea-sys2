"""Tests for projection_ext.py — FlowProjectionExtension."""

from ea_flow.projection_ext import FlowProjectionExtension
from ea_projection.ext import ProjectionExtension


class TestFlowProjectionExtension:

    def setup_method(self):
        self.ext = FlowProjectionExtension()

    def test_layer_key(self):
        assert self.ext.layer_key == "flow"

    def test_extension_protocol_compliance(self):
        assert isinstance(self.ext, ProjectionExtension)

    def test_enrich_nodes_adds_pipeline_order(self):
        nodes = [
            {"name": "ContextIngestStep", "category": "Behavior", "description": "Step 1"},
            {"name": "NormalizeNeedStep", "category": "Behavior", "description": "Step 2"},
            {"name": "UnrelatedElement", "category": "Composite", "description": "Not a step"},
        ]
        enriched = self.ext.enrich_nodes(nodes, "l3", None)
        assert enriched[0]["pipeline_order"] == 1
        assert enriched[1]["pipeline_order"] == 2
        assert "pipeline_order" not in enriched[2]

    def test_enrich_nodes_skips_low_levels(self):
        nodes = [{"name": "ContextIngestStep", "category": "Behavior", "description": ""}]
        enriched = self.ext.enrich_nodes(nodes, "l0", None)
        assert "pipeline_order" not in enriched[0]

    def test_enrich_nodes_adds_plane(self):
        nodes = [
            {"name": "FlowSpecPlane", "category": "Composite", "description": "P1 Specification plane."},
            {"name": "FlowCoordPlane", "category": "Composite", "description": "P2 Coordination plane."},
            {"name": "FlowRealPlane", "category": "Composite", "description": "P3 Realization plane."},
        ]
        enriched = self.ext.enrich_nodes(nodes, "l3", None)
        assert enriched[0]["plane"] == "P1"
        assert enriched[1]["plane"] == "P2"
        assert enriched[2]["plane"] == "P3"

    def test_enrich_edges_adds_pipeline_order(self):
        nodes = [
            {"name": "ContextIngestStep"},
            {"name": "NormalizeNeedStep"},
        ]
        edges = [
            {"source": "ContextIngestStep", "target": "NormalizeNeedStep", "relation": "next"},
        ]
        enriched = self.ext.enrich_edges(edges, nodes, "l3")
        assert enriched[0]["pipeline_order"] == (1, 2)

    def test_enrich_edges_adds_data_schema(self):
        nodes = [{"name": "A"}, {"name": "B"}]
        edges = [
            {"source": "A", "target": "B", "relation": "produces"},
        ]
        enriched = self.ext.enrich_edges(edges, nodes, "l4")
        assert enriched[0]["data_schema"] == "A:produces:B"

    def test_supplementary_edges_data_flow(self):
        nodes = [
            {"name": "ExecuteKernelAction", "category": "Executable"},
            {"name": "ContextIngestStep", "category": "Behavior"},
            {"name": "NormalizeNeedStep", "category": "Behavior"},
        ]
        edges = self.ext.supplementary_edges(nodes, "l4", None)
        assert len(edges) == 2
        # Should be ordered by pipeline_order
        assert edges[0]["source"] == "ContextIngestStep"
        assert edges[0]["target"] == "NormalizeNeedStep"
        assert edges[1]["source"] == "NormalizeNeedStep"
        assert edges[1]["target"] == "ExecuteKernelAction"

    def test_supplementary_edges_empty_at_l0(self):
        nodes = [{"name": "ContextIngestStep"}]
        edges = self.ext.supplementary_edges(nodes, "l0", None)
        assert edges == []

    def test_classify_tier_data(self):
        assert self.ext.classify_tier("UserData", "PassiveStructure", None) == "data"

    def test_classify_tier_evidence(self):
        assert self.ext.classify_tier("AuditLog", "PassiveStructure", None) == "evidence"

    def test_classify_tier_decision(self):
        assert self.ext.classify_tier("FlowDecisionPoint", "Assessment", None) == "decision"

    def test_classify_tier_function_p1(self):
        meta = {"description": "P1 Specification plane container."}
        assert self.ext.classify_tier("FlowSpecPlane", "Composite", meta) == "function"

    def test_classify_tier_none_for_unmatched(self):
        assert self.ext.classify_tier("RandomElement", "Unknown", None) is None
