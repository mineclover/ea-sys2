"""Tests for ea-decision topic.py module.

Tests the Design Thinking process artifacts: ResearchNote, Question, Option,
DesignDecision, DesignReport, and the Topic aggregate root.
"""

from __future__ import annotations

import json

import pytest

from ea_decision.pattern import DecisionComplexity, DecisionPattern
from ea_decision.topic import (
    DesignDecision,
    DesignReport,
    Evaluation,
    ModelingAction,
    Option,
    Question,
    ResearchNote,
    Topic,
    _as_text,
)
from ea_decision.types import DecisionStatus, Reference


class TestAsText:
    """Tests for _as_text helper function."""

    def test_as_text_with_string(self):
        assert _as_text("hello") == "hello"

    def test_as_text_with_dict_en(self):
        assert _as_text({"en": "hello", "ko": "안녕"}) == "hello"

    def test_as_text_with_dict_no_en(self):
        assert _as_text({"ko": "안녕", "ja": "こんにちは"}) == "안녕"

    def test_as_text_with_empty_dict(self):
        assert _as_text({}) == ""


class TestResearchNote:
    """Tests for ResearchNote dataclass."""

    def test_create_with_defaults(self):
        note = ResearchNote(content="Some findings")
        assert note.content == "Some findings"
        assert note.source_url is None
        assert note.references == []
        assert note.author == "unknown"
        assert note.created_at.endswith("Z")
        assert note.id.startswith("note-")

    def test_create_with_references(self):
        refs = [
            Reference(uri="file://doc.pdf", title="Document", citation="p.5"),
            Reference(uri="urn:ea:resource:123", title="Resource 123"),
        ]
        note = ResearchNote(
            content="Findings",
            source_url="https://example.com",
            references=refs,
            author="alice",
        )
        assert note.references == refs
        assert note.source_url == "https://example.com"
        assert note.author == "alice"


class TestQuestion:
    """Tests for Question dataclass."""

    def test_create_question(self):
        q = Question(text="What is the goal?", asked_by="bob")
        assert q.text == "What is the goal?"
        assert q.asked_by == "bob"
        assert q.answer is None
        assert q.answered_by is None
        assert q.answered_at is None
        assert q.created_at.endswith("Z")
        assert q.id.startswith("q-")

    def test_reply(self):
        q = Question(text="What is the goal?", asked_by="bob")
        original_created = q.created_at

        q.reply("The goal is to improve performance", "alice")

        assert q.answer == "The goal is to improve performance"
        assert q.answered_by == "alice"
        assert q.answered_at.endswith("Z")
        assert q.answered_at > original_created
        assert q.created_at == original_created  # Should not change


class TestEvaluation:
    """Tests for Evaluation dataclass."""

    def test_create_evaluation(self):
        eval_ = Evaluation(
            pros=["Fast", "Easy to implement"],
            cons=["Not scalable"],
            score=7,
            comment="Good for MVP",
        )
        assert eval_.pros == ["Fast", "Easy to implement"]
        assert eval_.cons == ["Not scalable"]
        assert eval_.score == 7
        assert eval_.comment == "Good for MVP"

    def test_evaluation_defaults(self):
        eval_ = Evaluation(pros=["Pro 1"], cons=["Con 1"])
        assert eval_.score == 0
        assert eval_.comment == ""


class TestOption:
    """Tests for Option dataclass."""

    def test_create_option_without_evaluation(self):
        opt = Option(title="Option A", description="Use library X")
        assert opt.title == "Option A"
        assert opt.description == "Use library X"
        assert opt.evaluation is None
        assert opt.created_at.endswith("Z")
        assert opt.id.startswith("opt-")

    def test_create_option_with_evaluation(self):
        eval_ = Evaluation(pros=["Fast"], cons=["Risky"], score=6)
        opt = Option(title="Option B", description="Build from scratch", evaluation=eval_)
        assert opt.evaluation == eval_
        assert opt.evaluation.score == 6


class TestModelingAction:
    """Tests for ModelingAction dataclass."""

    def test_create_modeling_action(self):
        action = ModelingAction(
            action_type="create_rule",
            target="rule:no-db-access",
            description="Create database access rule",
        )
        assert action.action_type == "create_rule"
        assert action.target == "rule:no-db-access"
        assert action.description == "Create database access rule"
        assert action.status == "pending"
        assert action.payload == {}

    def test_create_with_payload(self):
        action = ModelingAction(
            action_type="define_entity",
            target="entity:User",
            description={"en": "Define User entity"},
            status="completed",
            payload={"schema": {"name": "string"}},
        )
        assert action.status == "completed"
        assert action.payload == {"schema": {"name": "string"}}


class TestDesignDecision:
    """Tests for DesignDecision dataclass."""

    def test_create_design_decision(self):
        decision = DesignDecision(
            selected_option_id="opt-abc123",
            rationale="Best balance of speed and cost",
            pattern_name="TradeOffResolution",
            complexity=DecisionComplexity.STRUCTURAL,
            impact_analysis="Medium impact on database layer",
        )
        assert decision.selected_option_id == "opt-abc123"
        assert decision.rationale == "Best balance of speed and cost"
        assert decision.pattern_name == "TradeOffResolution"
        assert decision.complexity == DecisionComplexity.STRUCTURAL
        assert decision.impact_analysis == "Medium impact on database layer"
        assert decision.status == DecisionStatus.PROPOSED
        assert decision.approver is None
        assert decision.approved_at is None
        assert decision.id.startswith("decision-")

    def test_approve_decision(self):
        decision = DesignDecision(
            selected_option_id="opt-abc123",
            rationale="Good choice",
        )
        original_status = decision.status

        decision.approve("charlie")

        assert decision.status == DecisionStatus.ACCEPTED
        assert decision.approver == "charlie"
        assert decision.approved_at.endswith("Z")
        assert original_status == DecisionStatus.PROPOSED


class TestDesignReport:
    """Tests for DesignReport dataclass."""

    def test_create_design_report(self):
        decision = DesignDecision(
            selected_option_id="opt-xyz",
            rationale="It works",
        )
        report = DesignReport(
            title="Database Migration Plan",
            summary="Plan to migrate to PostgreSQL",
            decision=decision,
        )
        assert report.title == "Database Migration Plan"
        assert report.summary == "Plan to migrate to PostgreSQL"
        assert report.decision == decision
        assert report.modeling_actions == []
        assert report.key_evidence_refs == []
        assert report.executed_at is None
        assert report.execution_log == []
        assert report.transaction_id is None
        assert report.created_at.endswith("Z")
        assert report.id.startswith("report-")

    def test_add_action(self):
        decision = DesignDecision(selected_option_id="opt-1", rationale="Test")
        report = DesignReport(title="Plan", summary="Summary", decision=decision)

        report.add_action(
            action_type="create_rule",
            target="rule:auth",
            description="Add authentication rule",
        )

        assert len(report.modeling_actions) == 1
        action = report.modeling_actions[0]
        assert action.action_type == "create_rule"
        assert action.target == "rule:auth"
        assert action.description == "Add authentication rule"
        assert action.payload == {}

    def test_add_action_with_payload(self):
        decision = DesignDecision(selected_option_id="opt-1", rationale="Test")
        report = DesignReport(title="Plan", summary="Summary", decision=decision)

        report.add_action(
            action_type="define_entity",
            target="entity:Product",
            description={"en": "Define Product", "ko": "제품 정의"},
            payload={"fields": ["name", "price"]},
        )

        assert len(report.modeling_actions) == 1
        action = report.modeling_actions[0]
        assert action.payload == {"fields": ["name", "price"]}


class TestTopic:
    """Tests for Topic aggregate root."""

    def test_create_topic(self):
        topic = Topic(
            title="Database Selection",
            description="Choose between PostgreSQL and MongoDB",
        )
        assert topic.title == "Database Selection"
        assert topic.description == "Choose between PostgreSQL and MongoDB"
        assert topic.research_notes == []
        assert topic.questions == []
        assert topic.options == []
        assert topic.report is None
        assert topic.report_history == []
        assert topic.pattern_name is None
        assert topic.status == "active"
        assert topic.created_at.endswith("Z")
        assert topic.updated_at.endswith("Z")
        assert topic.id.startswith("topic-")

    def test_add_research(self):
        topic = Topic(title="Test", description="Test topic")
        original_updated = topic.updated_at

        topic.add_research(
            content="PostgreSQL has good ACID support",
            source="https://postgresql.org/docs",
            author="alice",
        )

        assert len(topic.research_notes) == 1
        note = topic.research_notes[0]
        assert note.content == "PostgreSQL has good ACID support"
        assert note.source_url == "https://postgresql.org/docs"
        assert note.author == "alice"
        assert topic.updated_at > original_updated

    def test_add_research_defaults(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_research("Some findings")

        note = topic.research_notes[0]
        assert note.source_url is None
        assert note.author == "unknown"

    def test_ask(self):
        topic = Topic(title="Test", description="Test topic")
        original_updated = topic.updated_at

        topic.ask("What are the performance requirements?", "bob")

        assert len(topic.questions) == 1
        q = topic.questions[0]
        assert q.text == "What are the performance requirements?"
        assert q.asked_by == "bob"
        assert topic.updated_at > original_updated

    def test_add_option(self):
        topic = Topic(title="Test", description="Test topic")
        original_updated = topic.updated_at

        topic.add_option("PostgreSQL", "Relational database with strong ACID")

        assert len(topic.options) == 1
        opt = topic.options[0]
        assert opt.title == "PostgreSQL"
        assert opt.description == "Relational database with strong ACID"
        assert topic.updated_at > original_updated

    def test_finalize_plan_success(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        topic.add_option("Option B", "Description B")
        option_id = topic.options[0].id

        report = topic.finalize_plan(
            title="Final Plan",
            summary="We chose Option A",
            selected_option_id=option_id,
            rationale="It's the best fit",
        )

        assert topic.report == report
        assert topic.status == "completed"
        assert report.title == "Final Plan"
        assert report.summary == "We chose Option A"
        assert report.decision.selected_option_id == option_id
        assert report.decision.rationale == "It's the best fit"
        assert len(topic.report_history) == 0

    def test_finalize_plan_invalid_option(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")

        with pytest.raises(ValueError, match="Option nonexistent not found in topic"):
            topic.finalize_plan(
                title="Plan",
                summary="Summary",
                selected_option_id="nonexistent",
                rationale="Reason",
            )

    def test_finalize_plan_archives_existing_report(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        topic.add_option("Option B", "Description B")
        option_a_id = topic.options[0].id
        option_b_id = topic.options[1].id

        # First plan
        report1 = topic.finalize_plan(
            title="Plan v1",
            summary="First plan",
            selected_option_id=option_a_id,
            rationale="Initial choice",
        )

        # Second plan
        report2 = topic.finalize_plan(
            title="Plan v2",
            summary="Second plan",
            selected_option_id=option_b_id,
            rationale="Changed our mind",
        )

        assert topic.report == report2
        assert len(topic.report_history) == 1
        assert topic.report_history[0] == report1
        assert report1.decision.status == DecisionStatus.DEPRECATED
        assert report2.decision.status == DecisionStatus.PROPOSED

    def test_revise_report(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        option_id = topic.options[0].id

        # Create a report
        report = topic.finalize_plan(
            title="Plan",
            summary="Summary",
            selected_option_id=option_id,
            rationale="Reason",
        )
        assert topic.status == "completed"

        # Revise it
        topic.revise_report()

        assert topic.report is None
        assert topic.status == "active"
        assert len(topic.report_history) == 1
        assert topic.report_history[0] == report
        assert report.decision.status == DecisionStatus.DEPRECATED

    def test_revise_report_when_no_report(self):
        topic = Topic(title="Test", description="Test topic")
        topic.revise_report()  # Should not raise

        assert topic.report is None
        assert topic.status == "active"
        assert len(topic.report_history) == 0

    def test_apply_pattern(self):
        pattern = DecisionPattern(
            name="TradeOffResolution",
            description="Resolve conflicting constraints",
            complexity=DecisionComplexity.STRUCTURAL,
            governed_rule_group="core_constraints",
            required_intent_tags=("trade-off", "constraint"),
            inquiry_template=(
                "What are the competing constraints?",
                "What is the cost of each option?",
            ),
            verification_heuristics=(
                "Verify all constraints are documented",
                "Check that trade-offs are quantified",
            ),
        )

        topic = Topic(title="Test", description="Test topic")
        topic.apply_pattern(pattern)

        assert topic.pattern_name == "TradeOffResolution"
        assert len(topic.questions) == 2
        assert topic.questions[0].text == "What are the competing constraints?"
        assert topic.questions[0].asked_by == "system:pattern"
        assert topic.questions[1].text == "What is the cost of each option?"
        assert len(topic.research_notes) == 1
        assert "Verification Heuristics" in topic.research_notes[0].content
        assert "Verify all constraints are documented" in topic.research_notes[0].content
        assert topic.research_notes[0].author == "system:pattern"

    def test_apply_pattern_avoids_duplicate_questions(self):
        pattern = DecisionPattern(
            name="Test Pattern",
            description="Test",
            complexity=DecisionComplexity.TRIVIAL,
            inquiry_template=("What is the goal?", "What are the constraints?"),
        )

        topic = Topic(title="Test", description="Test topic")
        topic.ask("What is the goal?", "human")
        topic.apply_pattern(pattern)

        # Should only add the new question, not duplicate
        assert len(topic.questions) == 2
        assert topic.questions[0].text == "What is the goal?"
        assert topic.questions[0].asked_by == "human"
        assert topic.questions[1].text == "What are the constraints?"
        assert topic.questions[1].asked_by == "system:pattern"

    def test_apply_pattern_with_i18n(self):
        pattern = DecisionPattern(
            name={"en": "Pattern Name", "ko": "패턴 이름"},
            description="Test",
            complexity=DecisionComplexity.TRIVIAL,
            inquiry_template=({"en": "What is X?", "ko": "X는 무엇인가?"},),
            verification_heuristics=({"en": "Check Y", "ko": "Y 확인"},),
        )

        topic = Topic(title="Test", description="Test topic")
        topic.apply_pattern(pattern)

        assert topic.pattern_name == "Pattern Name"
        assert topic.questions[0].text == "What is X?"
        assert "Check Y" in topic.research_notes[0].content

    def test_get_timeline_empty(self):
        topic = Topic(title="Test", description="Test topic")
        timeline = topic.get_timeline()
        assert timeline == []

    def test_get_timeline_chronological_order(self):
        topic = Topic(title="Test", description="Test topic")

        # Add items in a specific order
        topic.add_research("Research 1", author="alice")
        topic.ask("Question 1", "bob")
        topic.add_option("Option 1", "Description 1")
        topic.questions[0].reply("Answer 1", "charlie")

        timeline = topic.get_timeline()

        # Should be sorted chronologically
        assert len(timeline) >= 4
        types = [event["type"] for event in timeline]
        assert "research" in types
        assert "question" in types
        assert "option_created" in types
        assert "answer" in types

        # Verify chronological ordering
        dates = [event["date"] for event in timeline]
        assert dates == sorted(dates)

    def test_get_timeline_with_report(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        option_id = topic.options[0].id

        topic.finalize_plan(
            title="Plan",
            summary="Summary",
            selected_option_id=option_id,
            rationale="Reason",
        )

        timeline = topic.get_timeline()
        types = [event["type"] for event in timeline]

        assert "option_created" in types
        assert "report_finalized" in types

    def test_get_timeline_with_approved_decision(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        option_id = topic.options[0].id

        topic.finalize_plan(
            title="Plan",
            summary="Summary",
            selected_option_id=option_id,
            rationale="Reason",
        )
        topic.report.decision.approve("manager")

        timeline = topic.get_timeline()
        types = [event["type"] for event in timeline]

        assert "decision_approved" in types

    def test_get_timeline_with_option_evaluation(self):
        topic = Topic(title="Test", description="Test topic")
        eval_ = Evaluation(pros=["Pro"], cons=["Con"], score=5)
        opt = Option(title="Option A", description="Desc", evaluation=eval_)
        topic.options.append(opt)

        timeline = topic.get_timeline()
        types = [event["type"] for event in timeline]

        assert "option_created" in types
        assert "option_evaluated" in types

    def test_get_timeline_with_report_history(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        topic.add_option("Option B", "Description B")
        option_a_id = topic.options[0].id
        option_b_id = topic.options[1].id

        # First plan
        topic.finalize_plan(
            title="Plan v1",
            summary="First plan",
            selected_option_id=option_a_id,
            rationale="Initial",
        )

        # Second plan
        topic.finalize_plan(
            title="Plan v2",
            summary="Second plan",
            selected_option_id=option_b_id,
            rationale="Revised",
        )

        timeline = topic.get_timeline()
        types = [event["type"] for event in timeline]

        # Only the current report is shown as "report_finalized"
        # Historical reports are shown as "report_deprecated"
        assert types.count("report_finalized") == 1
        assert types.count("report_deprecated") == 1
        assert "report_deprecated" in types

    def test_to_json_from_json_round_trip(self):
        # Create a complex topic
        topic = Topic(
            title="Database Selection",
            description="Choose a database",
            status="active",
        )

        # Add research with references
        refs = [Reference(uri="file://doc.pdf", title="Doc", citation="p.1")]
        topic.research_notes.append(
            ResearchNote(content="Research", source_url="http://example.com", references=refs, author="alice")
        )

        # Add question with answer
        topic.ask("What is the goal?", "bob")
        topic.questions[0].reply("To be fast", "charlie")

        # Add option with evaluation
        eval_ = Evaluation(pros=["Fast"], cons=["Expensive"], score=7, comment="Good")
        topic.add_option("PostgreSQL", "Relational DB")
        topic.options[0].evaluation = eval_

        # Add report with modeling actions
        option_id = topic.options[0].id
        topic.finalize_plan(
            title="Final Decision",
            summary="We chose PostgreSQL",
            selected_option_id=option_id,
            rationale="Best fit",
        )
        topic.report.add_action(
            action_type="create_rule",
            target="rule:db",
            description="Database rule",
            payload={"schema": "public"},
        )

        # Serialize
        json_str = topic.to_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["title"] == "Database Selection"

        # Deserialize
        topic2 = Topic.from_json(json_str)

        # Verify structure
        assert topic2.title == topic.title
        assert topic2.description == topic.description
        assert topic2.status == topic.status
        assert topic2.id == topic.id

        # Verify research notes
        assert len(topic2.research_notes) == 1
        note = topic2.research_notes[0]
        assert note.content == "Research"
        assert note.source_url == "http://example.com"
        assert note.author == "alice"
        assert len(note.references) == 1
        assert note.references[0].uri == "file://doc.pdf"

        # Verify questions
        assert len(topic2.questions) == 1
        q = topic2.questions[0]
        assert q.text == "What is the goal?"
        assert q.asked_by == "bob"
        assert q.answer == "To be fast"
        assert q.answered_by == "charlie"

        # Verify options
        assert len(topic2.options) == 1
        opt = topic2.options[0]
        assert opt.title == "PostgreSQL"
        assert opt.evaluation is not None
        assert opt.evaluation.score == 7
        assert opt.evaluation.pros == ["Fast"]

        # Verify report
        assert topic2.report is not None
        assert topic2.report.title == "Final Decision"
        assert topic2.report.decision.selected_option_id == option_id
        assert len(topic2.report.modeling_actions) == 1
        action = topic2.report.modeling_actions[0]
        assert action.action_type == "create_rule"
        assert action.payload == {"schema": "public"}

    def test_from_json_with_report_history(self):
        topic = Topic(title="Test", description="Test topic")
        topic.add_option("Option A", "Description A")
        topic.add_option("Option B", "Description B")
        option_a_id = topic.options[0].id
        option_b_id = topic.options[1].id

        # Create history
        topic.finalize_plan("Plan v1", "First", option_a_id, "Initial")
        topic.finalize_plan("Plan v2", "Second", option_b_id, "Revised")

        json_str = topic.to_json()
        topic2 = Topic.from_json(json_str)

        assert len(topic2.report_history) == 1
        assert topic2.report_history[0].title == "Plan v1"
        assert topic2.report.title == "Plan v2"

    def test_to_json_minimal_topic(self):
        topic = Topic(title="Minimal", description="Minimal topic")
        json_str = topic.to_json()
        topic2 = Topic.from_json(json_str)

        assert topic2.title == "Minimal"
        assert topic2.description == "Minimal topic"
        assert topic2.research_notes == []
        assert topic2.questions == []
        assert topic2.options == []
        assert topic2.report is None
        assert topic2.report_history == []
