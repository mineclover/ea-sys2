"""Tests for deds.py — DEDS 7-component vocabulary constants."""

from ea_projection.deds import (
    DepthSemantic,
    GateType,
    DEPTH_LEVEL_SEMANTIC,
    DEPTH_LEVEL_ENTRY_QUESTION,
    DEPTH_LEVEL_ENTRY_INTENT,
    RELATION_DEPTH_SEMANTIC,
    GATE_NAME_PATTERNS,
    GATE_CATEGORIES,
)


class TestDEDSEnums:

    def test_depth_semantic_values(self):
        assert set(DepthSemantic) == {
            "existence", "instance", "configuration", "execution", "trace",
        }

    def test_gate_type_values(self):
        assert set(GateType) == {
            "quality", "lifecycle", "approval", "evidence", "promotion",
        }

    def test_depth_semantic_is_str(self):
        assert isinstance(DepthSemantic.EXISTENCE, str)
        assert DepthSemantic.EXISTENCE == "existence"

    def test_gate_type_is_str(self):
        assert isinstance(GateType.QUALITY, str)
        assert GateType.QUALITY == "quality"


class TestDepthLevelMappings:

    def test_depth_level_semantic_completeness(self):
        expected_keys = {"l0", "l1", "l2", "l3", "l4"}
        assert set(DEPTH_LEVEL_SEMANTIC.keys()) == expected_keys

    def test_depth_level_entry_question_completeness(self):
        expected_keys = {"l0", "l1", "l2", "l3", "l4"}
        assert set(DEPTH_LEVEL_ENTRY_QUESTION.keys()) == expected_keys
        for q in DEPTH_LEVEL_ENTRY_QUESTION.values():
            assert len(q) > 0
            assert q.endswith("?")

    def test_depth_level_entry_intent_completeness(self):
        expected_keys = {"l0", "l1", "l2", "l3", "l4"}
        assert set(DEPTH_LEVEL_ENTRY_INTENT.keys()) == expected_keys
        for intent in DEPTH_LEVEL_ENTRY_INTENT.values():
            assert len(intent) > 0


class TestRelationDepthSemantic:

    def test_14_relations_covered(self):
        assert len(RELATION_DEPTH_SEMANTIC) == 14

    def test_structural_relations_existence(self):
        assert RELATION_DEPTH_SEMANTIC["contains"] == DepthSemantic.EXISTENCE
        assert RELATION_DEPTH_SEMANTIC["depends_on"] == DepthSemantic.EXISTENCE

    def test_causal_relations_execution(self):
        assert RELATION_DEPTH_SEMANTIC["triggers"] == DepthSemantic.EXECUTION
        assert RELATION_DEPTH_SEMANTIC["constrains"] == DepthSemantic.EXECUTION

    def test_operational_relations(self):
        assert RELATION_DEPTH_SEMANTIC["produces"] == DepthSemantic.TRACE
        assert RELATION_DEPTH_SEMANTIC["consumes"] == DepthSemantic.TRACE
        assert RELATION_DEPTH_SEMANTIC["coordinates"] == DepthSemantic.CONFIGURATION

    def test_self_description_relations_instance(self):
        assert RELATION_DEPTH_SEMANTIC["registers"] == DepthSemantic.INSTANCE
        assert RELATION_DEPTH_SEMANTIC["available_in"] == DepthSemantic.INSTANCE


class TestGatePatterns:

    def test_gate_name_patterns_mapping(self):
        assert GATE_NAME_PATTERNS["quality"] == GateType.QUALITY
        assert GATE_NAME_PATTERNS["approval"] == GateType.APPROVAL
        assert GATE_NAME_PATTERNS["promotion"] == GateType.PROMOTION

    def test_gate_categories(self):
        assert "Assessment" in GATE_CATEGORIES
        assert "Governance" in GATE_CATEGORIES
