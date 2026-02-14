"""Design Thinking Process Data Model.

This module defines the artifacts used in the "Diverge-Converge-Decide" workflow.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from ea_decision.pattern import DecisionComplexity, DecisionPattern
from ea_decision.types import (
    DecisionStatus,
    I18nString,
    Reference,
    _generate_id,
    _now,
)


def _as_text(value: I18nString) -> str:
    if isinstance(value, str):
        return value
    return value.get("en") or next(iter(value.values()), "")


@dataclass
class ResearchNote:
    """Raw data, references, findings gathered during the Diverge phase."""
    content: str  # Markdown content
    source_url: str | None = None
    references: list[Reference] = field(default_factory=list)
    author: str = "unknown"
    created_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: _generate_id("note"))


@dataclass
class Question:
    """A specific inquiry made during the process."""
    text: str
    asked_by: str
    created_at: str = field(default_factory=_now)
    answer: str | None = None
    answered_by: str | None = None
    answered_at: str | None = None
    id: str = field(default_factory=lambda: _generate_id("q"))

    def reply(self, answer_text: str, responder: str) -> None:
        self.answer = answer_text
        self.answered_by = responder
        self.answered_at = _now()


@dataclass
class Evaluation:
    """Pros/cons analysis of an option."""
    pros: list[str]
    cons: list[str]
    score: int = 0  # 0-10 scale
    comment: str = ""


@dataclass
class Option:
    """A candidate solution path."""
    title: str
    description: str
    evaluation: Evaluation | None = None
    created_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: _generate_id("opt"))


@dataclass
class ModelingAction:
    """A specific planned change to the ea-kernel model."""
    action_type: str  # e.g., "create_rule", "define_entity"
    target: str       # e.g., "rule:no-db-access"
    description: I18nString
    status: str = "pending"  # pending, completed
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class DesignDecision:
    """The final finalized decision."""
    selected_option_id: str
    rationale: str
    pattern_name: str | None = None  # Link to DecisionPattern
    complexity: DecisionComplexity = DecisionComplexity.TRIVIAL
    impact_analysis: str = ""  # Summary of expected impact
    status: DecisionStatus = DecisionStatus.PROPOSED
    approver: str | None = None
    approved_at: str | None = None
    id: str = field(default_factory=lambda: _generate_id("decision"))

    def approve(self, approver: str) -> None:
        self.status = DecisionStatus.ACCEPTED
        self.approver = approver
        self.approved_at = _now()


@dataclass
class DesignReport:
    """
    The formal output of the Design Thinking process.
    It serves as the 'Plan' that aggregates the Decision and defines Modeling Actions.
    """
    title: I18nString
    summary: I18nString  # Executive summary of the plan

    # The 'Why' & 'What'
    decision: DesignDecision

    # The 'How' (Execution Plan)
    modeling_actions: list[ModelingAction] = field(default_factory=list)

    # References to grounded evidence (IDs)
    key_evidence_refs: list[str] = field(default_factory=list)

    # Execution Status
    executed_at: str | None = None
    execution_log: list[str] = field(default_factory=list)
    transaction_id: str | None = None

    created_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: _generate_id("report"))

    def add_action(
        self,
        action_type: str,
        target: str,
        description: I18nString,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.modeling_actions.append(ModelingAction(action_type, target, description, payload=(payload or {})))

@dataclass
class Topic:
    """Grouping container for a specific design problem."""
    title: I18nString
    description: I18nString  # The "Intent" or "Problem Statement"

    # Diverge
    research_notes: list[ResearchNote] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)

    # Decide / Plan
    report: DesignReport | None = None
    report_history: list[DesignReport] = field(default_factory=list)

    # Metadata
    pattern_name: str | None = None
    status: str = "active"  # active, completed, archived
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: _generate_id("topic"))

    def apply_pattern(self, pattern: DecisionPattern) -> None:
        """Apply a cognitive reasoning pattern to this topic."""
        self.pattern_name = _as_text(pattern.name)
        self.updated_at = _now()

        # Auto-populate inquiries
        for q_text in pattern.inquiry_template:
            q_value = _as_text(q_text)
            # Avoid duplicate questions
            if not any(q.text == q_value for q in self.questions):
                self.ask(q_value, asked_by="system:pattern")

        # Add research notes about verification heuristics
        if pattern.verification_heuristics:
            heuristics_content = "### Verification Heuristics\n" + "\n".join(
                f"- {_as_text(heuristic)}" for heuristic in pattern.verification_heuristics
            )
            self.add_research(heuristics_content, author="system:pattern")

    def get_timeline(self) -> list[dict[str, Any]]:
        """Returns a chronological list of all events in the topic."""
        events: list[dict[str, Any]] = []

        for r in self.research_notes:
            events.append({"type": "research", "date": r.created_at, "item": r})

        for q in self.questions:
            events.append({"type": "question", "date": q.created_at, "item": q})
            if q.answered_at:
                events.append({"type": "answer", "date": q.answered_at, "item": q, "detail": q.answer})

        for o in self.options:
            events.append({"type": "option_created", "date": o.created_at, "item": o})
            if o.evaluation:
                events.append({"type": "option_evaluated", "date": o.created_at, "item": o, "detail": o.evaluation})

        if self.report:
            events.append({"type": "report_finalized", "date": self.report.created_at, "item": self.report})
            if self.report.decision.approved_at:
                events.append({"type": "decision_approved", "date": self.report.decision.approved_at, "item": self.report.decision})

        for historical_report in self.report_history:
            events.append({"type": "report_deprecated", "date": historical_report.created_at, "item": historical_report})

        # Sort by date
        return sorted(events, key=lambda x: x["date"])

    def add_research(self, content: str, source: str | None = None, author: str = "unknown") -> None:
        self.research_notes.append(ResearchNote(content=content, source_url=source, author=author))
        self.updated_at = _now()

    def ask(self, text: str, asked_by: str) -> None:
        self.questions.append(Question(text, asked_by))
        self.updated_at = _now()

    def add_option(self, title: str, description: str) -> None:
        self.options.append(Option(title, description))
        self.updated_at = _now()

    def finalize_plan(self, title: str, summary: str, selected_option_id: str, rationale: str) -> DesignReport:
        """Creates the formal Design Report (Plan) based on the process."""
        # Archive existing report if any
        if self.report:
            self.report.decision.status = DecisionStatus.DEPRECATED
            self.report_history.append(self.report)

        # Verify option exists
        if not any(o.id == selected_option_id for o in self.options):
            raise ValueError(f"Option {selected_option_id} not found in topic {self.id}")

        decision = DesignDecision(selected_option_id=selected_option_id, rationale=rationale)
        self.report = DesignReport(title=title, summary=summary, decision=decision)
        self.status = "completed"
        self.updated_at = _now()
        return self.report

    def revise_report(self) -> None:
        """Re-opens the topic for further discussion, archiving the current report."""
        if self.report:
            self.report.decision.status = DecisionStatus.DEPRECATED
            self.report_history.append(self.report)
            self.report = None

        self.status = "active"
        self.updated_at = _now()

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> Topic:
        data = json.loads(json_str)
        # Reconstruct structured objects
        topic = cls(
            title=data['title'],
            description=data['description'],
            status=data.get('status', 'active'),
            created_at=data.get('created_at', ""),
            updated_at=data.get('updated_at', ""),
            id=data.get('id', "")
        )

        # Hydrate lists
        for r in data.get('research_notes', []):
            refs_data = r.pop('references', [])
            note = ResearchNote(**r)
            for ref in refs_data:
                note.references.append(Reference(**ref))
            topic.research_notes.append(note)

        for q in data.get('questions', []):
            q_obj = Question(**q)
            topic.questions.append(q_obj)

        for o in data.get('options', []):
            eval_data = o.pop('evaluation', None)
            opt = Option(**o)
            if eval_data:
                opt.evaluation = Evaluation(**eval_data)
            topic.options.append(opt)

        if data.get('report'):
            rep_data = data['report']
            dec_data = rep_data.pop('decision')
            actions_data = rep_data.pop('modeling_actions', [])

            report = DesignReport(decision=DesignDecision(**dec_data), **rep_data)
            for act in actions_data:
                report.modeling_actions.append(ModelingAction(**act))

            topic.report = report

        # Hydrate history
        for h_data in data.get('report_history', []):
             dec_data = h_data.pop('decision')
             actions_data = h_data.pop('modeling_actions', [])
             report = DesignReport(decision=DesignDecision(**dec_data), **h_data)

             for act in actions_data:
                report.modeling_actions.append(ModelingAction(**act))
             topic.report_history.append(report)

        return topic
