"""Cross-Layer Governance Lifecycle — S4/S5/S6 Feedback Loop.

Integrates Analysis (S4), Evolution (S5), and Propagation (S6) modules
from Kernel, Decision, Needs, and Flow layers into unified governance
coordination.

Transitions governance from recording-only to active feedback:
- S4: Accept analysis reports from each layer, record as governance snapshots
- S5: Auto-generate promotion/deprecation proposals from analysis results
- S6: Pre-evaluate propagation impact before applying changes

References:
- ea_kernel/evidence_analyzer.py, promotion_engine.py, impact_evaluator.py
- ea_decision/decision_analyzer.py, pattern_promotion.py, decision_propagation.py
- ea_needs/needs_analyzer.py, needs_promotion.py, needs_propagation.py
- ea_flow/flow_analyzer.py, workflow_promotion.py, flow_propagation.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Types
# ═══════════════════════════════════════════════════════════════════════════════

class FeedbackLayer(StrEnum):
    """Layers that participate in the governance feedback loop."""
    KERNEL = "kernel"
    DECISION = "decision"
    NEEDS = "needs"
    FLOW = "flow"


class FeedbackPhase(StrEnum):
    """Phase within the governance feedback cycle."""
    ANALYSIS = "analysis"       # S4: measure effectiveness
    PROPOSAL = "proposal"       # S5: generate change proposals
    IMPACT = "impact"           # S6: evaluate propagation risk
    APPLIED = "applied"         # Change applied after impact check


@dataclass(frozen=True)
class FeedbackCycleResult:
    """Result of a complete S4→S5→S6 feedback cycle for one layer."""
    cycle_id: str
    layer: str
    analysis_snapshot_id: str
    proposals_generated: int
    proposals_auto_approved: int
    impact_safe: bool
    impact_severity: str
    transaction_ids: tuple[str, ...]
    created_at: str


# ═══════════════════════════════════════════════════════════════════════════════
# LifecycleOps — Cross-Layer Feedback Coordinator
# ═══════════════════════════════════════════════════════════════════════════════

class LifecycleOps:
    """Cross-layer governance lifecycle: Analysis -> Evolution -> Propagation.

    Accepts analysis reports and propagation assessments from each layer,
    records them as governance snapshots, auto-generates proposals, and
    evaluates propagation risk before applying changes.
    """

    __slots__ = ("_execution_service", "_layer_stores")

    def __init__(
        self,
        execution_service: Any,
        layer_stores: dict[str, Any],
    ) -> None:
        self._execution_service = execution_service
        self._layer_stores = layer_stores

    # ── S4: Analysis Report Publishing ────────────────────────────────────

    def publish_kernel_analysis(
        self,
        report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, str]:
        """Record kernel evidence analysis report as governance snapshot.

        Accepts an AnalysisReport from ea_kernel.evidence_analyzer.
        Returns dict with report_id, snapshot_id, transaction_id.
        """
        report_payload = {
            "report_id": report.report_id,
            "created_at": report.created_at,
            "total_rules_analyzed": report.total_rules_analyzed,
            "analysis_period_start": report.analysis_period_start,
            "analysis_period_end": report.analysis_period_end,
            "rule_count": len(report.rule_effectiveness),
            "conflict_count": len(report.conflict_hotspots),
        }
        return self._publish_analysis(
            layer="kernel",
            report_id=report.report_id,
            report_payload=report_payload,
            actor=actor,
        )

    def publish_decision_analysis(
        self,
        report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, str]:
        """Record decision pattern analysis report as governance snapshot.

        Accepts a DecisionAnalysisReport from ea_decision.decision_analyzer.
        """
        report_payload = {
            "report_id": report.report_id,
            "created_at": report.created_at,
            "total_decisions_analyzed": report.total_decisions_analyzed,
            "analysis_period_start": report.analysis_period_start,
            "analysis_period_end": report.analysis_period_end,
            "pattern_count": len(report.pattern_effectiveness),
            "consistency_count": len(report.evaluation_consistency),
        }
        return self._publish_analysis(
            layer="decision",
            report_id=report.report_id,
            report_payload=report_payload,
            actor=actor,
        )

    def publish_flow_analysis(
        self,
        report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, str]:
        """Record flow step analysis report as governance snapshot.

        Accepts a FlowAnalysisReport from ea_flow.flow_analyzer.
        """
        report_payload = {
            "report_id": report.report_id,
            "created_at": report.created_at,
            "total_executions_analyzed": report.total_executions_analyzed,
            "analysis_period_start": report.analysis_period_start,
            "analysis_period_end": report.analysis_period_end,
            "step_count": len(report.step_effectiveness),
            "bottleneck_count": len(report.bottleneck_hotspots),
        }
        return self._publish_analysis(
            layer="flow",
            report_id=report.report_id,
            report_payload=report_payload,
            actor=actor,
        )

    def _publish_analysis(
        self,
        *,
        layer: str,
        report_id: str,
        report_payload: dict[str, Any],
        actor: str,
    ) -> dict[str, str]:
        """Generic analysis report publishing with transaction."""
        tx = self._execution_service.tx_manager.begin_transaction(
            f"{layer}_analysis_{report_id}",
            tx_type=f"{layer}_analysis_report",
            payload={"layer": layer, "actor": actor, "report_id": report_id},
        )
        try:
            store = self._layer_stores.get(layer)
            snapshot_id = ""
            if store is not None:
                snapshot_id = f"{layer}_analysis_{report_id}"
                store.save_payload(snapshot_id, report_payload)

            self._execution_service.tx_manager.add_event(
                tx.id,
                f"{layer}_analysis_published",
                f"{layer.capitalize()} analysis report {report_id} published.",
                payload=report_payload,
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "report_id": report_id,
            "snapshot_id": snapshot_id,
            "transaction_id": tx.id,
        }

    # ── S5: Proposal Auto-Generation ─────────────────────────────────────

    def generate_kernel_proposals(
        self,
        analysis_report: Any,
        *,
        promotion_criteria: Any | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Auto-generate kernel rule promotion/deprecation proposals from analysis.

        Uses PromotionCriteria from ea_kernel.promotion_engine to evaluate
        each rule's effectiveness and generate proposals.
        """
        from ea_kernel.promotion_engine import PromotionCriteria

        criteria = promotion_criteria or PromotionCriteria()
        proposals: list[dict[str, Any]] = []

        for effectiveness in analysis_report.rule_effectiveness:
            grade = effectiveness.grade.value
            if grade in ("dead", "shadowed", "ineffective"):
                proposals.append({
                    "type": "deprecate",
                    "target": effectiveness.rule_id,
                    "reason": f"Auto-detected {grade} rule (grade={grade})",
                    "grade": grade,
                })
            elif grade == "highly_effective":
                can_promote, reasons = criteria.evaluate(
                    effectiveness, effectiveness.first_eval_at,
                )
                if can_promote:
                    proposals.append({
                        "type": "promote",
                        "target": effectiveness.rule_id,
                        "reason": "; ".join(reasons),
                        "grade": grade,
                    })

        return self._record_proposals(
            layer="kernel",
            report_id=analysis_report.report_id,
            proposals=proposals,
            actor=actor,
        )

    def generate_decision_proposals(
        self,
        analysis_report: Any,
        *,
        promotion_criteria: Any | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Auto-generate decision pattern proposals from analysis."""
        from ea_decision.pattern_promotion import PatternPromotionCriteria

        criteria = promotion_criteria or PatternPromotionCriteria()
        proposals: list[dict[str, Any]] = []

        for effectiveness in analysis_report.pattern_effectiveness:
            grade = effectiveness.grade.value
            if grade in ("unused", "ineffective"):
                proposals.append({
                    "type": "deprecate",
                    "target": effectiveness.pattern_name,
                    "reason": f"Auto-detected {grade} pattern (grade={grade})",
                    "grade": grade,
                })
            elif grade == "highly_effective":
                can_promote, reasons = criteria.evaluate(effectiveness)
                if can_promote:
                    proposals.append({
                        "type": "promote",
                        "target": effectiveness.pattern_name,
                        "reason": "; ".join(reasons),
                        "grade": grade,
                    })

        return self._record_proposals(
            layer="decision",
            report_id=analysis_report.report_id,
            proposals=proposals,
            actor=actor,
        )

    def generate_flow_proposals(
        self,
        analysis_report: Any,
        *,
        promotion_criteria: Any | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Auto-generate flow workflow proposals from analysis."""
        from ea_flow.workflow_promotion import WorkflowPromotionCriteria

        criteria = promotion_criteria or WorkflowPromotionCriteria()
        proposals: list[dict[str, Any]] = []

        for effectiveness in analysis_report.step_effectiveness:
            grade = effectiveness.grade.value
            if grade in ("broken", "unused"):
                proposals.append({
                    "type": "deprecate",
                    "target": effectiveness.step_name,
                    "reason": f"Auto-detected {grade} step (grade={grade})",
                    "grade": grade,
                })
            elif grade == "highly_reliable":
                can_promote, reasons = criteria.evaluate(effectiveness)
                if can_promote:
                    proposals.append({
                        "type": "promote",
                        "target": effectiveness.step_name,
                        "reason": "; ".join(reasons),
                        "grade": grade,
                    })

        return self._record_proposals(
            layer="flow",
            report_id=analysis_report.report_id,
            proposals=proposals,
            actor=actor,
        )

    def generate_needs_proposals(
        self,
        analysis_report: Any,
        *,
        promotion_criteria: Any | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Auto-generate needs change proposals from analysis."""
        from ea_needs.needs_promotion import NeedPromotionCriteria

        criteria = promotion_criteria or NeedPromotionCriteria()
        proposals: list[dict[str, Any]] = []

        for coverage in analysis_report.stakeholder_coverage:
            grade = coverage.grade.value
            if grade in ("unserved",):
                proposals.append({
                    "type": "create",
                    "target": coverage.stakeholder_id,
                    "reason": "Unserved stakeholder needs attention",
                    "grade": grade,
                })
            elif grade == "well_covered":
                can_promote, reasons = criteria.evaluate(coverage)
                if can_promote:
                    proposals.append({
                        "type": "promote",
                        "target": coverage.stakeholder_id,
                        "reason": "; ".join(reasons),
                        "grade": grade,
                    })

        return self._record_proposals(
            layer="needs",
            report_id=analysis_report.report_id,
            proposals=proposals,
            actor=actor,
        )

    def _record_proposals(
        self,
        *,
        layer: str,
        report_id: str,
        proposals: list[dict[str, Any]],
        actor: str,
    ) -> dict[str, Any]:
        """Record generated proposals with transaction."""
        tx = self._execution_service.tx_manager.begin_transaction(
            f"{layer}_proposals_{report_id}",
            tx_type=f"{layer}_proposal_generation",
            payload={"layer": layer, "actor": actor, "report_id": report_id},
        )
        try:
            store = self._layer_stores.get(layer)
            if store is not None:
                snapshot_id = f"{layer}_proposals_{report_id}"
                store.save_payload(snapshot_id, {
                    "report_id": report_id,
                    "proposals": proposals,
                    "generated_at": _now(),
                })

            self._execution_service.tx_manager.add_event(
                tx.id,
                f"{layer}_proposals_generated",
                f"Generated {len(proposals)} {layer} proposals from analysis {report_id}.",
                payload={
                    "proposal_count": len(proposals),
                    "deprecate_count": sum(1 for p in proposals if p["type"] == "deprecate"),
                    "promote_count": sum(1 for p in proposals if p["type"] == "promote"),
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "layer": layer,
            "report_id": report_id,
            "proposals": proposals,
            "total": len(proposals),
            "transaction_id": tx.id,
        }

    # ── S6: Propagation Impact Evaluation ─────────────────────────────────

    def evaluate_kernel_impact(
        self,
        impact_report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Record kernel propagation impact assessment.

        Accepts an ImpactReport from ea_kernel.impact_evaluator.
        """
        return self._record_impact(
            layer="kernel",
            report_id=impact_report.report_id,
            severity=impact_report.severity.value,
            safe_to_apply=impact_report.safe_to_apply,
            affected_count=len(impact_report.affected_decisions),
            total_scanned=impact_report.total_decisions_scanned,
            recommendation=impact_report.recommendation,
            risk_factors=list(impact_report.risk_factors),
            actor=actor,
        )

    def evaluate_decision_impact(
        self,
        propagation_report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Record decision propagation impact assessment.

        Accepts a DecisionPropagationReport from ea_decision.decision_propagation.
        """
        return self._record_impact(
            layer="decision",
            report_id=propagation_report.report_id,
            severity=propagation_report.severity.value,
            safe_to_apply=propagation_report.safe_to_apply,
            affected_count=len(propagation_report.affected_decisions),
            total_scanned=propagation_report.total_decisions_scanned,
            recommendation=propagation_report.recommendation,
            risk_factors=list(propagation_report.risk_factors),
            actor=actor,
        )

    def evaluate_needs_impact(
        self,
        propagation_report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Record needs propagation impact assessment.

        Accepts a NeedsPropagationReport from ea_needs.needs_propagation.
        """
        return self._record_impact(
            layer="needs",
            report_id=propagation_report.report_id,
            severity=propagation_report.severity.value,
            safe_to_apply=propagation_report.safe_to_apply,
            affected_count=len(propagation_report.affected_needs),
            total_scanned=propagation_report.total_needs_scanned,
            recommendation=propagation_report.recommendation,
            risk_factors=list(propagation_report.risk_factors),
            actor=actor,
        )

    def evaluate_flow_impact(
        self,
        propagation_report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Record flow propagation impact assessment.

        Accepts a FlowPropagationReport from ea_flow.flow_propagation.
        """
        return self._record_impact(
            layer="flow",
            report_id=propagation_report.report_id,
            severity=propagation_report.severity.value,
            safe_to_apply=propagation_report.safe_to_apply,
            affected_count=len(propagation_report.affected_executions),
            total_scanned=propagation_report.total_executions_scanned,
            recommendation=propagation_report.recommendation,
            risk_factors=list(propagation_report.risk_factors),
            actor=actor,
        )

    def _record_impact(
        self,
        *,
        layer: str,
        report_id: str,
        severity: str,
        safe_to_apply: bool,
        affected_count: int,
        total_scanned: int,
        recommendation: str,
        risk_factors: list[str],
        actor: str,
    ) -> dict[str, Any]:
        """Generic propagation impact recording with transaction."""
        impact_payload = {
            "report_id": report_id,
            "severity": severity,
            "safe_to_apply": safe_to_apply,
            "affected_count": affected_count,
            "total_scanned": total_scanned,
            "impact_rate": affected_count / max(total_scanned, 1),
            "recommendation": recommendation,
            "risk_factors": risk_factors,
            "evaluated_at": _now(),
        }

        tx = self._execution_service.tx_manager.begin_transaction(
            f"{layer}_impact_{report_id}",
            tx_type=f"{layer}_impact_evaluation",
            payload={"layer": layer, "actor": actor, "report_id": report_id},
        )
        try:
            store = self._layer_stores.get(layer)
            if store is not None:
                snapshot_id = f"{layer}_impact_{report_id}"
                store.save_payload(snapshot_id, impact_payload)

            self._execution_service.tx_manager.add_event(
                tx.id,
                f"{layer}_impact_evaluated",
                f"{layer.capitalize()} impact: severity={severity}, "
                f"safe={safe_to_apply}, affected={affected_count}/{total_scanned}.",
                payload=impact_payload,
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "layer": layer,
            "report_id": report_id,
            "severity": severity,
            "safe_to_apply": safe_to_apply,
            "affected_count": affected_count,
            "total_scanned": total_scanned,
            "recommendation": recommendation,
            "transaction_id": tx.id,
        }

    # ── Unified Feedback Cycle ────────────────────────────────────────────

    def get_latest_analysis(self, layer: str) -> dict[str, Any] | None:
        """Retrieve the most recent analysis snapshot for a layer."""
        store = self._layer_stores.get(layer)
        if store is None:
            return None

        snapshots = [
            s for s in store.list_snapshots()
            if s.model_id.startswith(f"{layer}_analysis_")
        ]
        if not snapshots:
            return None
        return snapshots[-1].payload

    def get_latest_proposals(self, layer: str) -> dict[str, Any] | None:
        """Retrieve the most recent proposals snapshot for a layer."""
        store = self._layer_stores.get(layer)
        if store is None:
            return None

        snapshots = [
            s for s in store.list_snapshots()
            if s.model_id.startswith(f"{layer}_proposals_")
        ]
        if not snapshots:
            return None
        return snapshots[-1].payload

    def get_latest_impact(self, layer: str) -> dict[str, Any] | None:
        """Retrieve the most recent impact assessment for a layer."""
        store = self._layer_stores.get(layer)
        if store is None:
            return None

        snapshots = [
            s for s in store.list_snapshots()
            if s.model_id.startswith(f"{layer}_impact_")
        ]
        if not snapshots:
            return None
        return snapshots[-1].payload

    def lifecycle_summary(self) -> dict[str, Any]:
        """Summary of latest feedback cycle state across all layers."""
        summary: dict[str, Any] = {}
        for layer in ("kernel", "decision", "needs", "flow"):
            analysis = self.get_latest_analysis(layer)
            proposals = self.get_latest_proposals(layer)
            impact = self.get_latest_impact(layer)
            summary[layer] = {
                "has_analysis": analysis is not None,
                "has_proposals": proposals is not None,
                "has_impact": impact is not None,
                "proposal_count": len(proposals.get("proposals", [])) if proposals else 0,
                "impact_safe": impact.get("safe_to_apply") if impact else None,
                "impact_severity": impact.get("severity") if impact else None,
            }
        return summary


def _now() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
