"""Test suite for ea_decision.types module.

Tests:
- Enum membership and values
- Frozen dataclass creation and immutability
- Default field values
- Helper functions (_generate_id, _now)
- Mutable vs frozen dataclasses
- DecisionTopic with complex defaults
- DecisionOntology.describe()
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from ea_decision.types import (
    ActivationStatus,
    Choice,
    ChoiceOption,
    DecisionOntology,
    DecisionPhase,
    DecisionResult,
    DecisionStatus,
    DecisionTopic,
    DecisionType,
    EvaluationCriteria,
    EvidenceReference,
    I18nString,
    Intent,
    Rationale,
    Reference,
    TopicOption,
    _generate_id,
    _now,
)


class TestHelperFunctions:
    """Test helper functions for ID generation and timestamps."""

    def test_generate_id_has_prefix(self) -> None:
        """Test that _generate_id produces IDs with the correct prefix."""
        result = _generate_id("test")
        assert result.startswith("test-")

    def test_generate_id_is_unique(self) -> None:
        """Test that _generate_id produces unique IDs."""
        id1 = _generate_id("prefix")
        id2 = _generate_id("prefix")
        assert id1 != id2

    def test_generate_id_has_8_char_suffix(self) -> None:
        """Test that _generate_id produces IDs with 8-character hex suffix."""
        result = _generate_id("test")
        suffix = result.split("-", 1)[1]
        assert len(suffix) == 8
        # Verify it's valid hex
        int(suffix, 16)

    def test_now_returns_iso8601_with_z_suffix(self) -> None:
        """Test that _now returns ISO 8601 timestamp ending with 'Z'."""
        result = _now()
        assert result.endswith("Z")

    def test_now_can_be_parsed_as_datetime(self) -> None:
        """Test that _now returns a parseable ISO 8601 timestamp."""
        result = _now()
        # Remove trailing 'Z' and parse
        parsed = datetime.fromisoformat(result.rstrip("Z"))
        assert parsed.tzinfo == UTC


class TestI18nString:
    """Test I18nString type alias."""

    def test_i18n_string_accepts_str(self) -> None:
        """Test that I18nString can be a plain string."""
        value: I18nString = "Hello"
        assert isinstance(value, str)

    def test_i18n_string_accepts_dict(self) -> None:
        """Test that I18nString can be a dictionary."""
        value: I18nString = {"en": "Hello", "ko": "안녕하세요"}
        assert isinstance(value, dict)


class TestDecisionStatusEnum:
    """Test DecisionStatus StrEnum."""

    def test_all_members_present(self) -> None:
        """Test that all expected members are present."""
        expected = {"PROPOSED", "ACCEPTED", "REJECTED", "DEPRECATED"}
        actual = {member.name for member in DecisionStatus}
        assert actual == expected

    def test_member_values(self) -> None:
        """Test that member values match expected strings."""
        assert DecisionStatus.PROPOSED == "proposed"
        assert DecisionStatus.ACCEPTED == "accepted"
        assert DecisionStatus.REJECTED == "rejected"
        assert DecisionStatus.DEPRECATED == "deprecated"


class TestDecisionPhaseEnum:
    """Test DecisionPhase StrEnum."""

    def test_all_members_present(self) -> None:
        """Test that all expected members are present."""
        expected = {"DIVERGE", "CONVERGE", "UTILIZE"}
        actual = {member.name for member in DecisionPhase}
        assert actual == expected

    def test_member_values(self) -> None:
        """Test that member values match expected strings."""
        assert DecisionPhase.DIVERGE == "diverge"
        assert DecisionPhase.CONVERGE == "converge"
        assert DecisionPhase.UTILIZE == "utilize"


class TestDecisionTypeEnum:
    """Test DecisionType Enum."""

    def test_all_members_present(self) -> None:
        """Test that all expected members are present."""
        expected = {
            "ARCHITECTURE_SELECTION",
            "TRADE_OFF_RESOLUTION",
            "COMPLIANCE_CHECK",
            "RESOURCE_ALLOCATION",
            "STRATEGIC_DIRECTION",
        }
        actual = {member.name for member in DecisionType}
        assert actual == expected

    def test_member_values(self) -> None:
        """Test that member values match expected strings."""
        assert DecisionType.ARCHITECTURE_SELECTION.value == "architecture_selection"
        assert DecisionType.TRADE_OFF_RESOLUTION.value == "trade_off_resolution"
        assert DecisionType.COMPLIANCE_CHECK.value == "compliance_check"
        assert DecisionType.RESOURCE_ALLOCATION.value == "resource_allocation"
        assert DecisionType.STRATEGIC_DIRECTION.value == "strategic_direction"


class TestActivationStatusEnum:
    """Test ActivationStatus Enum."""

    def test_all_members_present(self) -> None:
        """Test that all expected members are present."""
        expected = {"DRAFT", "ACTIVE", "DEPRECATED", "SUPERSEDED", "REJECTED"}
        actual = {member.name for member in ActivationStatus}
        assert actual == expected

    def test_member_values(self) -> None:
        """Test that member values match expected strings."""
        assert ActivationStatus.DRAFT.value == "draft"
        assert ActivationStatus.ACTIVE.value == "active"
        assert ActivationStatus.DEPRECATED.value == "deprecated"
        assert ActivationStatus.SUPERSEDED.value == "superseded"
        assert ActivationStatus.REJECTED.value == "rejected"


class TestIntent:
    """Test Intent frozen dataclass."""

    def test_create_intent(self) -> None:
        """Test creating an Intent instance."""
        intent = Intent(
            id="int-001",
            description="Improve system performance",
            direction="maximize_efficiency",
            context_refs=["ctx-001", "ctx-002"],
        )
        assert intent.id == "int-001"
        assert intent.description == "Improve system performance"
        assert intent.direction == "maximize_efficiency"
        assert intent.context_refs == ["ctx-001", "ctx-002"]

    def test_intent_is_frozen(self) -> None:
        """Test that Intent is immutable."""
        intent = Intent(
            id="int-001",
            description="Test",
            direction="test_direction",
            context_refs=[],
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            intent.id = "int-002"  # type: ignore


class TestChoiceOption:
    """Test ChoiceOption frozen dataclass."""

    def test_create_choice_option(self) -> None:
        """Test creating a ChoiceOption instance."""
        option = ChoiceOption(
            id="opt-001",
            intent_id="int-001",
            description="Option A",
            feasibility_score=0.8,
            alignment_score=0.9,
        )
        assert option.id == "opt-001"
        assert option.intent_id == "int-001"
        assert option.description == "Option A"
        assert option.feasibility_score == 0.8
        assert option.alignment_score == 0.9
        assert option.metadata == {}

    def test_choice_option_with_metadata(self) -> None:
        """Test creating a ChoiceOption with metadata."""
        metadata = {"cost": 1000, "team": "backend"}
        option = ChoiceOption(
            id="opt-001",
            intent_id="int-001",
            description="Option A",
            feasibility_score=0.8,
            alignment_score=0.9,
            metadata=metadata,
        )
        assert option.metadata == metadata

    def test_choice_option_is_frozen(self) -> None:
        """Test that ChoiceOption is immutable."""
        option = ChoiceOption(
            id="opt-001",
            intent_id="int-001",
            description="Test",
            feasibility_score=0.5,
            alignment_score=0.5,
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            option.feasibility_score = 0.9  # type: ignore


class TestChoice:
    """Test Choice frozen dataclass."""

    def test_create_choice(self) -> None:
        """Test creating a Choice instance."""
        choice = Choice(
            id="choice-001",
            intent_id="int-001",
            selected_option_id="opt-001",
            rationale="Best balance of cost and performance",
            distance=0.2,
        )
        assert choice.id == "choice-001"
        assert choice.intent_id == "int-001"
        assert choice.selected_option_id == "opt-001"
        assert choice.rationale == "Best balance of cost and performance"
        assert choice.distance == 0.2

    def test_choice_is_frozen(self) -> None:
        """Test that Choice is immutable."""
        choice = Choice(
            id="choice-001",
            intent_id="int-001",
            selected_option_id="opt-001",
            rationale="Test",
            distance=0.1,
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            choice.distance = 0.5  # type: ignore


class TestDecisionResult:
    """Test DecisionResult frozen dataclass."""

    def test_create_decision_result(self) -> None:
        """Test creating a DecisionResult instance."""
        result = DecisionResult(
            id="res-001",
            intent_id="int-001",
            choice_id="choice-001",
            outcome_artifact={"type": "rule", "rule_id": "rule-123"},
            timestamp="2026-02-16T10:00:00Z",
        )
        assert result.id == "res-001"
        assert result.intent_id == "int-001"
        assert result.choice_id == "choice-001"
        assert result.outcome_artifact == {"type": "rule", "rule_id": "rule-123"}
        assert result.timestamp == "2026-02-16T10:00:00Z"

    def test_decision_result_is_frozen(self) -> None:
        """Test that DecisionResult is immutable."""
        result = DecisionResult(
            id="res-001",
            intent_id="int-001",
            choice_id="choice-001",
            outcome_artifact=None,
            timestamp="2026-02-16T10:00:00Z",
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            result.timestamp = "2026-02-17T10:00:00Z"  # type: ignore


class TestEvidenceReference:
    """Test EvidenceReference frozen dataclass."""

    def test_create_evidence_reference(self) -> None:
        """Test creating an EvidenceReference with default relevance_score."""
        evidence = EvidenceReference(
            resource_uri="file://docs/design.md",
            description="Design document",
        )
        assert evidence.resource_uri == "file://docs/design.md"
        assert evidence.description == "Design document"
        assert evidence.relevance_score == 1.0

    def test_evidence_reference_with_custom_score(self) -> None:
        """Test creating an EvidenceReference with custom relevance_score."""
        evidence = EvidenceReference(
            resource_uri="file://docs/design.md",
            description="Design document",
            relevance_score=0.75,
        )
        assert evidence.relevance_score == 0.75

    def test_evidence_reference_is_frozen(self) -> None:
        """Test that EvidenceReference is immutable."""
        evidence = EvidenceReference(
            resource_uri="file://test",
            description="Test",
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            evidence.relevance_score = 0.5  # type: ignore


class TestEvaluationCriteria:
    """Test EvaluationCriteria frozen dataclass."""

    def test_create_evaluation_criteria_with_defaults(self) -> None:
        """Test creating an EvaluationCriteria with default values."""
        criteria = EvaluationCriteria(
            name="Performance",
            description="System response time",
        )
        assert criteria.name == "Performance"
        assert criteria.description == "System response time"
        assert criteria.weight == 1.0
        assert criteria.scale == "qualitative"

    def test_evaluation_criteria_with_custom_values(self) -> None:
        """Test creating an EvaluationCriteria with custom values."""
        criteria = EvaluationCriteria(
            name="Cost",
            description="Implementation cost",
            weight=2.0,
            scale="USD",
        )
        assert criteria.weight == 2.0
        assert criteria.scale == "USD"

    def test_evaluation_criteria_is_frozen(self) -> None:
        """Test that EvaluationCriteria is immutable."""
        criteria = EvaluationCriteria(
            name="Test",
            description="Test description",
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            criteria.weight = 3.0  # type: ignore


class TestRationale:
    """Test Rationale frozen dataclass."""

    def test_create_rationale_with_defaults(self) -> None:
        """Test creating a Rationale with default values."""
        rationale = Rationale(
            summary="This option provides the best value",
        )
        assert rationale.summary == "This option provides the best value"
        assert rationale.evidence_links == []
        assert rationale.confidence_score == 1.0

    def test_rationale_with_evidence(self) -> None:
        """Test creating a Rationale with evidence links."""
        evidence = EvidenceReference(
            resource_uri="file://proof.pdf",
            description="Supporting proof",
        )
        rationale = Rationale(
            summary="Justified by evidence",
            evidence_links=[evidence],
            confidence_score=0.9,
        )
        assert len(rationale.evidence_links) == 1
        assert rationale.evidence_links[0] == evidence
        assert rationale.confidence_score == 0.9

    def test_rationale_is_frozen(self) -> None:
        """Test that Rationale is immutable."""
        rationale = Rationale(summary="Test")
        with pytest.raises((FrozenInstanceError, AttributeError)):
            rationale.confidence_score = 0.5  # type: ignore


class TestTopicOption:
    """Test TopicOption frozen dataclass."""

    def test_create_topic_option_with_defaults(self) -> None:
        """Test creating a TopicOption with default values."""
        option = TopicOption(
            id="top-opt-001",
            name="Option A",
            description="First option",
        )
        assert option.id == "top-opt-001"
        assert option.name == "Option A"
        assert option.description == "First option"
        assert option.pros == []
        assert option.cons == []
        assert option.scores == {}

    def test_topic_option_with_full_data(self) -> None:
        """Test creating a TopicOption with all fields populated."""
        option = TopicOption(
            id="top-opt-001",
            name="Option A",
            description="First option",
            pros=["Fast", "Cheap"],
            cons=["Complex"],
            scores={"Performance": 0.9, "Cost": 0.7},
        )
        assert option.pros == ["Fast", "Cheap"]
        assert option.cons == ["Complex"]
        assert option.scores == {"Performance": 0.9, "Cost": 0.7}

    def test_topic_option_is_frozen(self) -> None:
        """Test that TopicOption is immutable."""
        option = TopicOption(
            id="top-opt-001",
            name="Test",
            description="Test",
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            option.name = "Changed"  # type: ignore


class TestDecisionTopic:
    """Test DecisionTopic frozen dataclass."""

    def test_create_decision_topic_minimal(self) -> None:
        """Test creating a DecisionTopic with minimal required fields."""
        topic = DecisionTopic(
            id="topic-001",
            title="Choose Database",
            description="Select database technology",
            decision_type=DecisionType.ARCHITECTURE_SELECTION,
        )
        assert topic.id == "topic-001"
        assert topic.title == "Choose Database"
        assert topic.description == "Select database technology"
        assert topic.decision_type == DecisionType.ARCHITECTURE_SELECTION
        assert topic.status == ActivationStatus.DRAFT
        assert topic.decision_date is None
        assert topic.valid_until is None
        assert topic.superseded_by_id is None
        assert topic.criteria == []
        assert topic.options == []
        assert topic.selected_option_id is None
        assert topic.final_rationale is None
        assert topic.supporting_evidence == []

    def test_decision_topic_with_complex_fields(self) -> None:
        """Test creating a DecisionTopic with all fields populated."""
        criteria = EvaluationCriteria(name="Cost", description="Total cost")
        option = TopicOption(id="opt-1", name="PostgreSQL", description="Relational DB")
        evidence = EvidenceReference(
            resource_uri="file://bench.pdf",
            description="Benchmark results",
        )
        rationale = Rationale(summary="Best for our use case")
        decision_date = datetime(2026, 2, 15, tzinfo=UTC)
        valid_until = datetime(2027, 2, 15, tzinfo=UTC)

        topic = DecisionTopic(
            id="topic-001",
            title="Choose Database",
            description="Select database technology",
            decision_type=DecisionType.ARCHITECTURE_SELECTION,
            status=ActivationStatus.ACTIVE,
            decision_date=decision_date,
            valid_until=valid_until,
            superseded_by_id="topic-002",
            criteria=[criteria],
            options=[option],
            selected_option_id="opt-1",
            final_rationale=rationale,
            supporting_evidence=[evidence],
        )

        assert topic.status == ActivationStatus.ACTIVE
        assert topic.decision_date == decision_date
        assert topic.valid_until == valid_until
        assert topic.superseded_by_id == "topic-002"
        assert len(topic.criteria) == 1
        assert len(topic.options) == 1
        assert topic.selected_option_id == "opt-1"
        assert topic.final_rationale == rationale
        assert len(topic.supporting_evidence) == 1

    def test_decision_topic_is_frozen(self) -> None:
        """Test that DecisionTopic is immutable."""
        topic = DecisionTopic(
            id="topic-001",
            title="Test",
            description="Test",
            decision_type=DecisionType.ARCHITECTURE_SELECTION,
        )
        with pytest.raises((FrozenInstanceError, AttributeError)):
            topic.status = ActivationStatus.ACTIVE  # type: ignore


class TestReference:
    """Test Reference dataclass (mutable)."""

    def test_create_reference(self) -> None:
        """Test creating a Reference instance."""
        ref = Reference(
            uri="file://docs/spec.md",
            title="Specification Document",
        )
        assert ref.uri == "file://docs/spec.md"
        assert ref.title == "Specification Document"
        assert ref.citation is None

    def test_reference_with_citation(self) -> None:
        """Test creating a Reference with citation."""
        ref = Reference(
            uri="file://docs/spec.md",
            title="Specification Document",
            citation="Line 10-20",
        )
        assert ref.citation == "Line 10-20"

    def test_reference_is_mutable(self) -> None:
        """Test that Reference is mutable (not frozen)."""
        ref = Reference(uri="file://test", title="Test")
        # Should not raise - Reference is mutable
        ref.citation = "Updated citation"
        assert ref.citation == "Updated citation"

    def test_reference_can_modify_uri(self) -> None:
        """Test that Reference uri can be modified."""
        ref = Reference(uri="file://original", title="Test")
        ref.uri = "file://updated"
        assert ref.uri == "file://updated"


class TestDecisionOntology:
    """Test DecisionOntology class."""

    def test_describe_returns_dict(self) -> None:
        """Test that describe() returns a dictionary."""
        result = DecisionOntology.describe()
        assert isinstance(result, dict)

    def test_describe_has_expected_keys(self) -> None:
        """Test that describe() contains expected keys."""
        result = DecisionOntology.describe()
        expected_keys = {"DecisionTopic", "ActivationStatus", "EvidenceReference"}
        assert set(result.keys()) == expected_keys

    def test_describe_has_non_empty_descriptions(self) -> None:
        """Test that describe() values are non-empty strings."""
        result = DecisionOntology.describe()
        for key, value in result.items():
            assert isinstance(value, str)
            assert len(value) > 0

    def test_describe_content(self) -> None:
        """Test that describe() contains expected content."""
        result = DecisionOntology.describe()
        assert "decision point" in result["DecisionTopic"].lower()
        assert "lifecycle" in result["ActivationStatus"].lower()
        assert "l1" in result["EvidenceReference"].lower() or "supporting" in result["EvidenceReference"].lower()
