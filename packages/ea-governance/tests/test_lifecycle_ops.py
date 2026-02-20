"""Tests for LifecycleOps — S4/S5/S6 cross-layer feedback loop."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from ea_governance.facade import GovernanceContainer
from ea_kernel.types import KernelSchema


# ── Fake analysis/propagation report fixtures ─────────────────────────


@dataclass(frozen=True)
class FakeRuleEffectiveness:
    rule_id: str
    grade: Any
    first_eval_at: str = "2025-01-01T00:00:00Z"
    total_evaluations: int = 100
    match_count: int = 50
    win_count: int = 30


@dataclass(frozen=True)
class FakeConflictHotspot:
    pass


@dataclass(frozen=True)
class FakeUsageProfile:
    pass


@dataclass(frozen=True)
class FakeKernelAnalysisReport:
    report_id: str
    created_at: str
    total_rules_analyzed: int
    analysis_period_start: str
    analysis_period_end: str
    rule_effectiveness: tuple[FakeRuleEffectiveness, ...] = ()
    conflict_hotspots: tuple[FakeConflictHotspot, ...] = ()
    usage_profile: tuple[FakeUsageProfile, ...] = ()


@dataclass(frozen=True)
class FakePatternEffectiveness:
    pattern_name: str
    grade: Any
    complexity: str = "trivial"
    total_decisions: int = 50
    accepted_count: int = 40
    rejected_count: int = 5
    deprecated_count: int = 5
    avg_evaluation_score: float = 0.8
    avg_option_count: float = 3.0
    execution_linked_count: int = 0
    execution_success_count: int = 0


@dataclass(frozen=True)
class FakeEvaluationConsistency:
    pattern_name: str
    high_score_accepted: int = 10
    high_score_rejected: int = 1
    low_score_accepted: int = 1
    low_score_rejected: int = 8
    total_analyzed: int = 20


@dataclass(frozen=True)
class FakeDecisionAnalysisReport:
    report_id: str
    created_at: str
    total_decisions_analyzed: int
    analysis_period_start: str
    analysis_period_end: str
    pattern_effectiveness: tuple[FakePatternEffectiveness, ...] = ()
    evaluation_consistency: tuple[FakeEvaluationConsistency, ...] = ()


@dataclass(frozen=True)
class FakeStepEffectiveness:
    step_name: str
    grade: Any
    kernel_anchor: str = "ea:kernel:entity:element"
    total_executions: int = 100
    success_count: int = 90
    failure_count: int = 10
    rollback_trigger_count: int = 2
    decision_linked_count: int = 0
    decision_accepted_count: int = 0


@dataclass(frozen=True)
class FakeBottleneckHotspot:
    pass


@dataclass(frozen=True)
class FakeFlowAnalysisReport:
    report_id: str
    created_at: str
    total_executions_analyzed: int
    analysis_period_start: str
    analysis_period_end: str
    step_effectiveness: tuple[FakeStepEffectiveness, ...] = ()
    bottleneck_hotspots: tuple[FakeBottleneckHotspot, ...] = ()


@dataclass(frozen=True)
class FakeImpactReport:
    report_id: str
    severity: Any
    safe_to_apply: bool
    affected_decisions: tuple[Any, ...] = ()
    total_decisions_scanned: int = 100
    recommendation: str = "proceed"
    risk_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeDecisionPropReport:
    report_id: str
    severity: Any
    safe_to_apply: bool
    affected_decisions: tuple[Any, ...] = ()
    total_decisions_scanned: int = 50
    recommendation: str = "proceed"
    risk_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeNeedsPropReport:
    report_id: str
    severity: Any
    safe_to_apply: bool
    affected_needs: tuple[Any, ...] = ()
    total_needs_scanned: int = 30
    recommendation: str = "proceed"
    risk_factors: tuple[str, ...] = ()


@dataclass(frozen=True)
class FakeFlowPropReport:
    report_id: str
    severity: Any
    safe_to_apply: bool
    affected_executions: tuple[Any, ...] = ()
    total_executions_scanned: int = 80
    recommendation: str = "proceed"
    risk_factors: tuple[str, ...] = ()


class FakeGrade:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeSeverity:
    def __init__(self, value: str) -> None:
        self.value = value


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def governance():
    with tempfile.TemporaryDirectory() as tmpdir:
        schema = KernelSchema(attributes=(), entities=(), relations=())
        yield GovernanceContainer(Path(tmpdir), schema)


# ── S4: Analysis Publishing ───────────────────────────────────────────


class TestPublishAnalysis:

    def test_publish_kernel_analysis(self, governance):
        report = FakeKernelAnalysisReport(
            report_id="kernel-rpt-001",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=50,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            rule_effectiveness=(
                FakeRuleEffectiveness("rule-1", FakeGrade("effective")),
            ),
        )
        result = governance.publish_kernel_analysis(report)

        assert result["report_id"] == "kernel-rpt-001"
        assert result["transaction_id"] != ""
        assert result["snapshot_id"] == "kernel_analysis_kernel-rpt-001"

    def test_publish_decision_analysis(self, governance):
        report = FakeDecisionAnalysisReport(
            report_id="decision-rpt-001",
            created_at="2025-01-15T10:00:00Z",
            total_decisions_analyzed=100,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            pattern_effectiveness=(
                FakePatternEffectiveness("TradeOff", FakeGrade("effective")),
            ),
        )
        result = governance.publish_decision_analysis(report)

        assert result["report_id"] == "decision-rpt-001"
        assert result["transaction_id"] != ""

    def test_publish_flow_analysis(self, governance):
        report = FakeFlowAnalysisReport(
            report_id="flow-rpt-001",
            created_at="2025-01-15T10:00:00Z",
            total_executions_analyzed=200,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
        )
        result = governance.publish_flow_analysis(report)

        assert result["report_id"] == "flow-rpt-001"
        assert result["transaction_id"] != ""

    def test_analysis_persisted_in_layer_store(self, governance):
        report = FakeKernelAnalysisReport(
            report_id="kernel-rpt-persist",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=10,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
        )
        governance.publish_kernel_analysis(report)

        snapshot = governance.get_layer_snapshot("kernel", "kernel_analysis_kernel-rpt-persist")
        assert snapshot is not None
        assert snapshot["report_id"] == "kernel-rpt-persist"
        assert snapshot["total_rules_analyzed"] == 10


# ── S5: Proposal Generation ──────────────────────────────────────────


class TestProposalGeneration:

    def test_generate_kernel_proposals_deprecate(self, governance):
        report = FakeKernelAnalysisReport(
            report_id="kernel-rpt-002",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=3,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            rule_effectiveness=(
                FakeRuleEffectiveness("rule-dead", FakeGrade("dead")),
                FakeRuleEffectiveness("rule-ok", FakeGrade("effective")),
                FakeRuleEffectiveness("rule-shadow", FakeGrade("shadowed")),
            ),
        )
        result = governance.generate_kernel_proposals(report)

        assert result["layer"] == "kernel"
        assert result["total"] == 2  # dead + shadowed
        types = {p["type"] for p in result["proposals"]}
        assert "deprecate" in types
        targets = {p["target"] for p in result["proposals"]}
        assert "rule-dead" in targets
        assert "rule-shadow" in targets
        assert "rule-ok" not in targets

    def test_generate_decision_proposals_deprecate(self, governance):
        report = FakeDecisionAnalysisReport(
            report_id="decision-rpt-002",
            created_at="2025-01-15T10:00:00Z",
            total_decisions_analyzed=100,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            pattern_effectiveness=(
                FakePatternEffectiveness("UnusedPat", FakeGrade("unused")),
                FakePatternEffectiveness("GoodPat", FakeGrade("effective")),
            ),
        )
        result = governance.generate_decision_proposals(report)

        assert result["total"] == 1
        assert result["proposals"][0]["target"] == "UnusedPat"
        assert result["proposals"][0]["type"] == "deprecate"

    def test_generate_flow_proposals_deprecate(self, governance):
        report = FakeFlowAnalysisReport(
            report_id="flow-rpt-002",
            created_at="2025-01-15T10:00:00Z",
            total_executions_analyzed=200,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            step_effectiveness=(
                FakeStepEffectiveness("BrokenStep", FakeGrade("broken")),
                FakeStepEffectiveness("GoodStep", FakeGrade("reliable")),
            ),
        )
        result = governance.generate_flow_proposals(report)

        assert result["total"] == 1
        assert result["proposals"][0]["target"] == "BrokenStep"

    def test_generate_no_proposals_for_healthy(self, governance):
        report = FakeKernelAnalysisReport(
            report_id="kernel-rpt-healthy",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=2,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            rule_effectiveness=(
                FakeRuleEffectiveness("rule-ok", FakeGrade("effective")),
                FakeRuleEffectiveness("rule-marginal", FakeGrade("marginally_effective")),
            ),
        )
        result = governance.generate_kernel_proposals(report)

        assert result["total"] == 0
        assert result["proposals"] == []

    def test_proposals_persisted_in_layer_store(self, governance):
        report = FakeKernelAnalysisReport(
            report_id="kernel-rpt-persist-prop",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=1,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            rule_effectiveness=(
                FakeRuleEffectiveness("rule-dead", FakeGrade("dead")),
            ),
        )
        governance.generate_kernel_proposals(report)

        snapshot = governance.get_layer_snapshot(
            "kernel", "kernel_proposals_kernel-rpt-persist-prop",
        )
        assert snapshot is not None
        assert len(snapshot["proposals"]) == 1


# ── S6: Impact Evaluation ────────────────────────────────────────────


class TestImpactEvaluation:

    def test_evaluate_kernel_impact(self, governance):
        report = FakeImpactReport(
            report_id="impact-kernel-001",
            severity=FakeSeverity("low"),
            safe_to_apply=True,
            total_decisions_scanned=100,
            recommendation="proceed with caution",
        )
        result = governance.evaluate_kernel_impact(report)

        assert result["layer"] == "kernel"
        assert result["severity"] == "low"
        assert result["safe_to_apply"] is True
        assert result["recommendation"] == "proceed with caution"
        assert result["transaction_id"] != ""

    def test_evaluate_decision_impact(self, governance):
        report = FakeDecisionPropReport(
            report_id="impact-decision-001",
            severity=FakeSeverity("medium"),
            safe_to_apply=False,
            recommendation="review required",
            risk_factors=("pattern dependency",),
        )
        result = governance.evaluate_decision_impact(report)

        assert result["severity"] == "medium"
        assert result["safe_to_apply"] is False

    def test_evaluate_needs_impact(self, governance):
        report = FakeNeedsPropReport(
            report_id="impact-needs-001",
            severity=FakeSeverity("none"),
            safe_to_apply=True,
        )
        result = governance.evaluate_needs_impact(report)

        assert result["layer"] == "needs"
        assert result["safe_to_apply"] is True

    def test_evaluate_flow_impact(self, governance):
        report = FakeFlowPropReport(
            report_id="impact-flow-001",
            severity=FakeSeverity("high"),
            safe_to_apply=False,
            affected_executions=("exec-1", "exec-2"),
            total_executions_scanned=80,
            recommendation="halt",
        )
        result = governance.evaluate_flow_impact(report)

        assert result["layer"] == "flow"
        assert result["severity"] == "high"
        assert result["affected_count"] == 2
        assert result["total_scanned"] == 80

    def test_impact_persisted_in_layer_store(self, governance):
        report = FakeImpactReport(
            report_id="impact-persist-001",
            severity=FakeSeverity("critical"),
            safe_to_apply=False,
            total_decisions_scanned=200,
        )
        governance.evaluate_kernel_impact(report)

        snapshot = governance.get_layer_snapshot("kernel", "kernel_impact_impact-persist-001")
        assert snapshot is not None
        assert snapshot["severity"] == "critical"
        assert snapshot["safe_to_apply"] is False


# ── Lifecycle Summary ─────────────────────────────────────────────────


class TestLifecycleSummary:

    def test_empty_summary(self, governance):
        summary = governance.lifecycle_summary()

        assert "kernel" in summary
        assert "decision" in summary
        assert "needs" in summary
        assert "flow" in summary

        for layer_data in summary.values():
            assert layer_data["has_analysis"] is False
            assert layer_data["has_proposals"] is False
            assert layer_data["has_impact"] is False

    def test_summary_after_analysis(self, governance):
        report = FakeKernelAnalysisReport(
            report_id="kernel-sum-001",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=10,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
        )
        governance.publish_kernel_analysis(report)

        summary = governance.lifecycle_summary()
        assert summary["kernel"]["has_analysis"] is True
        assert summary["decision"]["has_analysis"] is False

    def test_summary_after_full_cycle(self, governance):
        # S4: publish analysis
        analysis = FakeKernelAnalysisReport(
            report_id="kernel-cycle-001",
            created_at="2025-01-15T10:00:00Z",
            total_rules_analyzed=1,
            analysis_period_start="2025-01-01T00:00:00Z",
            analysis_period_end="2025-01-15T00:00:00Z",
            rule_effectiveness=(
                FakeRuleEffectiveness("rule-dead", FakeGrade("dead")),
            ),
        )
        governance.publish_kernel_analysis(analysis)

        # S5: generate proposals
        governance.generate_kernel_proposals(analysis)

        # S6: evaluate impact
        impact = FakeImpactReport(
            report_id="impact-cycle-001",
            severity=FakeSeverity("low"),
            safe_to_apply=True,
        )
        governance.evaluate_kernel_impact(impact)

        summary = governance.lifecycle_summary()
        assert summary["kernel"]["has_analysis"] is True
        assert summary["kernel"]["has_proposals"] is True
        assert summary["kernel"]["proposal_count"] == 1
        assert summary["kernel"]["has_impact"] is True
        assert summary["kernel"]["impact_safe"] is True
        assert summary["kernel"]["impact_severity"] == "low"
