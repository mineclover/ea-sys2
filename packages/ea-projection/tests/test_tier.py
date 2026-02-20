"""Tests for tier/ — classification and resolution."""

from ea_projection.tier import classify_element_tier, resolve_tier_node_set, resolve_tier_definitions
from ea_projection.tier.resolver import TIER_DEFINITIONS_FALLBACK, TIER_NAMES


class TestClassifyElementTier:

    def test_classify_ui_tier(self):
        assert classify_element_tier("LoginPage", "Page", TIER_DEFINITIONS_FALLBACK) == "ui"
        assert classify_element_tier("SearchInterface", "Interface", TIER_DEFINITIONS_FALLBACK) == "ui"
        assert classify_element_tier("UserContext", "Context", TIER_DEFINITIONS_FALLBACK) == "ui"

    def test_classify_function_tier(self):
        assert classify_element_tier("HandleLogin", "Behavior", TIER_DEFINITIONS_FALLBACK) == "function"
        assert classify_element_tier("RunValidation", "Executable", TIER_DEFINITIONS_FALLBACK) == "function"
        assert classify_element_tier("PolicyEngine", "Governance", TIER_DEFINITIONS_FALLBACK) == "function"

    def test_classify_data_excludes_evidence(self):
        assert classify_element_tier("UserData", "PassiveStructure", TIER_DEFINITIONS_FALLBACK) == "data"
        assert classify_element_tier("ConfigModel", "Composite", TIER_DEFINITIONS_FALLBACK) == "data"
        # Evidence names in PassiveStructure should NOT match data tier
        assert classify_element_tier("AuditRecord", "PassiveStructure", TIER_DEFINITIONS_FALLBACK) != "data"

    def test_classify_evidence_by_name_pattern(self):
        assert classify_element_tier("EvidenceLog", "PassiveStructure", TIER_DEFINITIONS_FALLBACK) == "evidence"
        assert classify_element_tier("ProvenanceTrail", "PassiveStructure", TIER_DEFINITIONS_FALLBACK) == "evidence"
        assert classify_element_tier("RationaleDoc", "PassiveStructure", TIER_DEFINITIONS_FALLBACK) == "evidence"
        assert classify_element_tier("AuditRecord", "PassiveStructure", TIER_DEFINITIONS_FALLBACK) == "evidence"

    def test_classify_decision_tier(self):
        assert classify_element_tier("RiskAssessment", "Assessment", TIER_DEFINITIONS_FALLBACK) == "decision"
        assert classify_element_tier("BusinessGoal", "Goal", TIER_DEFINITIONS_FALLBACK) == "decision"

    def test_classify_unknown_category(self):
        assert classify_element_tier("Unknown", "NonExistent", TIER_DEFINITIONS_FALLBACK) is None


class TestResolveTierNodeSet:

    def test_filters_correctly(self):
        nodes = [
            {"name": "LoginPage", "category": "Page"},
            {"name": "HandleLogin", "category": "Behavior"},
            {"name": "UserData", "category": "PassiveStructure"},
        ]
        matched, classification = resolve_tier_node_set(nodes, "ui", TIER_DEFINITIONS_FALLBACK)
        assert matched == {"LoginPage"}
        assert classification["LoginPage"] == "ui"
        assert classification["HandleLogin"] == "function"
        assert classification["UserData"] == "data"

    def test_empty_nodes(self):
        matched, classification = resolve_tier_node_set([], "ui", TIER_DEFINITIONS_FALLBACK)
        assert matched == set()
        assert classification == {}


class TestResolveTierDefinitions:

    def test_fallback(self):
        result = resolve_tier_definitions(None)
        assert "ui" in result
        assert "function" in result
        assert "evidence" in result

    def test_from_policy(self):
        loader = {
            "status": "ok",
            "document": {
                "m2": {
                    "tiers": {
                        "definitions": {
                            "custom": {
                                "categories": ["Custom"],
                                "name_patterns": [],
                                "transitions": [],
                            }
                        }
                    }
                }
            },
        }
        result = resolve_tier_definitions(loader)
        assert "custom" in result
        assert result["custom"]["categories"] == ["Custom"]

    def test_tier_names_constant(self):
        assert TIER_NAMES == ("ui", "function", "data", "decision", "evidence")
