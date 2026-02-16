"""Tests for ea_decision.pattern module."""

import pytest
from dataclasses import FrozenInstanceError

from ea_decision.pattern import (
    DecisionComplexity,
    DecisionPattern,
    HeuristicRule,
    PatternSchema,
    PatternType,
    Phase,
)


class TestDecisionComplexity:
    """Test DecisionComplexity enum."""

    def test_enum_values(self):
        assert DecisionComplexity.TRIVIAL == "trivial"
        assert DecisionComplexity.STRUCTURAL == "structural"
        assert DecisionComplexity.STRATEGIC == "strategic"

    def test_enum_count(self):
        assert len(DecisionComplexity) == 3


class TestDecisionPattern:
    """Test DecisionPattern frozen dataclass."""

    def test_creation_minimal(self):
        p = DecisionPattern(
            name="TestPattern",
            description="A test pattern",
            complexity=DecisionComplexity.TRIVIAL,
        )
        assert p.name == "TestPattern"
        assert p.description == "A test pattern"
        assert p.complexity == DecisionComplexity.TRIVIAL
        assert p.governed_rule_group is None
        assert p.required_intent_tags == ()
        assert p.inquiry_template == ()
        assert p.verification_heuristics == ()
        assert p.outcome_anchors == {}

    def test_creation_full(self):
        p = DecisionPattern(
            name={"en": "FullPattern", "ko": "전체패턴"},
            description="Fully specified pattern",
            complexity=DecisionComplexity.STRATEGIC,
            governed_rule_group="rule-group-1",
            required_intent_tags=("refine", "select"),
            inquiry_template=("Question 1?", "Question 2?"),
            verification_heuristics=("Check A", "Check B"),
            outcome_anchors={"success": "All aligned", "failure": "Mismatch"},
        )
        assert p.governed_rule_group == "rule-group-1"
        assert p.required_intent_tags == ("refine", "select")
        assert len(p.inquiry_template) == 2
        assert len(p.verification_heuristics) == 2
        assert p.outcome_anchors["success"] == "All aligned"

    def test_frozen(self):
        p = DecisionPattern(
            name="Frozen",
            description="Cannot mutate",
            complexity=DecisionComplexity.TRIVIAL,
        )
        with pytest.raises(FrozenInstanceError):
            p.name = "Changed"

    def test_matches_intent_all_present(self):
        p = DecisionPattern(
            name="Intent",
            description="desc",
            complexity=DecisionComplexity.STRUCTURAL,
            required_intent_tags=("refine", "select"),
        )
        assert p.matches_intent(("refine", "select", "extra")) is True

    def test_matches_intent_missing_tag(self):
        p = DecisionPattern(
            name="Intent",
            description="desc",
            complexity=DecisionComplexity.STRUCTURAL,
            required_intent_tags=("refine", "select"),
        )
        assert p.matches_intent(("refine",)) is False

    def test_matches_intent_empty_required(self):
        p = DecisionPattern(
            name="Intent",
            description="desc",
            complexity=DecisionComplexity.TRIVIAL,
        )
        assert p.matches_intent(("any", "tags")) is True

    def test_matches_intent_empty_input(self):
        p = DecisionPattern(
            name="Intent",
            description="desc",
            complexity=DecisionComplexity.TRIVIAL,
            required_intent_tags=("required",),
        )
        assert p.matches_intent(()) is False

    def test_i18n_name(self):
        p = DecisionPattern(
            name={"en": "English", "ko": "한국어"},
            description="desc",
            complexity=DecisionComplexity.TRIVIAL,
        )
        assert p.name["en"] == "English"
        assert p.name["ko"] == "한국어"


class TestPatternType:
    """Test PatternType enum."""

    def test_enum_values(self):
        assert PatternType.TRADE_OFF == "trade_off"
        assert PatternType.COMPLIANCE == "compliance"
        assert PatternType.ARCHITECTURE == "architecture"
        assert PatternType.PROCESS == "process"

    def test_enum_count(self):
        assert len(PatternType) == 4


class TestHeuristicRule:
    """Test HeuristicRule dataclass."""

    def test_creation_minimal(self):
        h = HeuristicRule(description="Check consistency")
        assert h.description == "Check consistency"
        assert h.severity == "info"
        assert h.check_function is None

    def test_creation_full(self):
        h = HeuristicRule(
            description="Critical check",
            severity="critical",
            check_function="validate_compliance",
        )
        assert h.severity == "critical"
        assert h.check_function == "validate_compliance"

    def test_mutable(self):
        h = HeuristicRule(description="Mutable")
        h.severity = "warning"
        assert h.severity == "warning"


class TestPhase:
    """Test Phase dataclass."""

    def test_creation_minimal(self):
        p = Phase(name="Research", description="Gather information")
        assert p.name == "Research"
        assert p.description == "Gather information"
        assert p.required_artifacts == []

    def test_creation_with_artifacts(self):
        p = Phase(
            name="Options",
            description="Generate options",
            required_artifacts=["ResearchNote", "Option"],
        )
        assert len(p.required_artifacts) == 2
        assert "ResearchNote" in p.required_artifacts


class TestPatternSchema:
    """Test PatternSchema dataclass."""

    def test_creation_minimal(self):
        ps = PatternSchema(
            name="TradeOff",
            type=PatternType.TRADE_OFF,
            description="Compare A vs B",
            phases=[Phase(name="Research", description="Gather data")],
        )
        assert ps.name == "TradeOff"
        assert ps.type == PatternType.TRADE_OFF
        assert len(ps.phases) == 1
        assert ps.heuristics == []
        assert ps.inquiry_template == []

    def test_creation_full(self):
        ps = PatternSchema(
            name="Compliance",
            type=PatternType.COMPLIANCE,
            description="Align with regulation",
            phases=[
                Phase(name="Research", description="Study regulation"),
                Phase(name="Options", description="Generate alternatives"),
                Phase(name="RFC", description="Request for comments"),
            ],
            heuristics=[
                HeuristicRule(description="Must cite regulation", severity="critical"),
            ],
            inquiry_template=["Which regulation applies?", "What are exceptions?"],
        )
        assert len(ps.phases) == 3
        assert len(ps.heuristics) == 1
        assert len(ps.inquiry_template) == 2
        assert ps.heuristics[0].severity == "critical"
