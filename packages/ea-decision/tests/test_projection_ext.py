"""Tests for projection_ext.py — DecisionProjectionExtension."""

from ea_decision.projection_ext import DecisionProjectionExtension
from ea_projection.ext import ProjectionExtension


class TestDecisionProjectionExtension:

    def setup_method(self):
        self.ext = DecisionProjectionExtension()

    def test_layer_key(self):
        assert self.ext.layer_key == "decision"

    def test_extension_protocol_compliance(self):
        assert isinstance(self.ext, ProjectionExtension)

    # ── enrich_nodes ──────────────────────────────────────────

    def test_enrich_nodes_adds_decision_phase(self):
        nodes = [
            {"name": "CaptureDecisionContextStep", "category": "Behavior", "description": ""},
            {"name": "EvaluateOptionGraphStep", "category": "Behavior", "description": ""},
            {"name": "FinalizeDecisionStep", "category": "Behavior", "description": ""},
        ]
        enriched = self.ext.enrich_nodes(nodes, "l3", None)
        assert enriched[0]["decision_phase"] == "diverge"
        assert enriched[1]["decision_phase"] == "converge"
        assert enriched[2]["decision_phase"] == "utilize"

    def test_enrich_nodes_adds_gate_type(self):
        nodes = [
            {"name": "QualityGateCheck", "category": "Assessment", "description": ""},
            {"name": "PromotionGate", "category": "Governance", "description": ""},
        ]
        enriched = self.ext.enrich_nodes(nodes, "l3", None)
        assert enriched[0]["decision_gate"] is True
        assert enriched[0]["gate_type"] == "quality"
        assert enriched[1]["decision_gate"] is True
        assert enriched[1]["gate_type"] == "promotion"

    def test_enrich_nodes_skips_low_levels(self):
        nodes = [{"name": "CaptureDecisionContextStep", "category": "Behavior", "description": ""}]
        enriched = self.ext.enrich_nodes(nodes, "l0", None)
        assert "decision_phase" not in enriched[0]

    def test_enrich_nodes_no_phase_for_unmatched(self):
        nodes = [{"name": "RandomElement", "category": "Composite", "description": ""}]
        enriched = self.ext.enrich_nodes(nodes, "l3", None)
        assert "decision_phase" not in enriched[0]

    # ── enrich_edges ──────────────────────────────────────────

    def test_enrich_edges_phase_transition(self):
        nodes = [
            {"name": "DivergeStep", "decision_phase": "diverge"},
            {"name": "ConvergeStep", "decision_phase": "converge"},
        ]
        edges = [
            {"source": "DivergeStep", "target": "ConvergeStep", "relation": "next"},
        ]
        enriched = self.ext.enrich_edges(edges, nodes, "l3")
        assert enriched[0]["phase_transition"] == "diverge->converge"

    def test_enrich_edges_gate_constraint(self):
        nodes = [
            {"name": "QualityGate", "decision_gate": True},
            {"name": "FinalizeStep"},
        ]
        edges = [
            {"source": "QualityGate", "target": "FinalizeStep", "relation": "constrains"},
        ]
        enriched = self.ext.enrich_edges(edges, nodes, "l3")
        assert enriched[0]["gate_constraint"] is True

    def test_enrich_edges_skips_low_levels(self):
        nodes = [
            {"name": "DivergeStep", "decision_phase": "diverge"},
            {"name": "ConvergeStep", "decision_phase": "converge"},
        ]
        edges = [
            {"source": "DivergeStep", "target": "ConvergeStep", "relation": "next"},
        ]
        enriched = self.ext.enrich_edges(edges, nodes, "l0")
        assert "phase_transition" not in enriched[0]

    # ── supplementary_edges ───────────────────────────────────

    def test_supplementary_edges_phase_sequence(self):
        nodes = [
            {"name": "DivergeStep", "category": "Behavior", "decision_phase": "diverge"},
            {"name": "ConvergeStep", "category": "Behavior", "decision_phase": "converge"},
            {"name": "UtilizeStep", "category": "Behavior", "decision_phase": "utilize"},
        ]
        edges = self.ext.supplementary_edges(nodes, "l4", None)
        phase_edges = [e for e in edges if "phase_transition" in e]
        assert len(phase_edges) == 2
        assert phase_edges[0]["phase_transition"] == "diverge->converge"
        assert phase_edges[1]["phase_transition"] == "converge->utilize"

    def test_supplementary_edges_evidence_justification(self):
        nodes = [
            {"name": "EvidenceRecord", "category": "PassiveStructure"},
            {"name": "DecisionCriteriaModel", "category": "Assessment"},
        ]
        edges = self.ext.supplementary_edges(nodes, "l4", None)
        justification_edges = [e for e in edges if e.get("evidence_justification")]
        assert len(justification_edges) == 1
        assert justification_edges[0]["source"] == "EvidenceRecord"
        assert justification_edges[0]["target"] == "DecisionCriteriaModel"

    def test_supplementary_edges_empty_at_l0(self):
        nodes = [{"name": "DivergeStep", "category": "Behavior", "decision_phase": "diverge"}]
        edges = self.ext.supplementary_edges(nodes, "l0", None)
        assert edges == []

    # ── classify_tier ─────────────────────────────────────────

    def test_classify_tier_evidence(self):
        assert self.ext.classify_tier("EvidenceRecord", "PassiveStructure", None) == "evidence"

    def test_classify_tier_decision(self):
        assert self.ext.classify_tier("DecisionCriteriaModel", "Assessment", None) == "decision"
        assert self.ext.classify_tier("DecisionTraceGoal", "Goal", None) == "decision"

    def test_classify_tier_none_for_unmatched(self):
        assert self.ext.classify_tier("RandomElement", "Composite", None) is None
