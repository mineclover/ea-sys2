"""Flow Propagation Engine — S6 Propagation for Flow Layer.

Evaluates the impact of workflow/step changes on existing execution records.
Provides:
- WorkflowChangeSet: 워크플로 변경 집합
- FlowPropagationReport: 영향 보고서
- FlowPropagationEngine: 워크플로 변경의 기존 실행 기록 영향 평가

References:
- ea_kernel/impact_evaluator.py: S6 Propagation 패턴
- ea_flow/execution_store.py: S3 Store
- ea_flow/flow_analyzer.py: S4 Analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_flow.execution_store import ExecutionStore


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Change Set — 워크플로 변경 내역
# ═══════════════════════════════════════════════════════════════════════════════

class WorkflowChangeAction(StrEnum):
    """워크플로 변경 유형."""
    STEP_ADDED = "step_added"
    STEP_REMOVED = "step_removed"
    STEP_MODIFIED = "step_modified"
    TOPOLOGY_CHANGED = "topology_changed"


@dataclass(frozen=True)
class WorkflowChange:
    """개별 워크플로 변경."""
    workflow_name: str
    action: WorkflowChangeAction
    step_name: str = ""
    before_state: str = ""
    after_state: str = ""
    description: str = ""


@dataclass(frozen=True)
class WorkflowChangeSet:
    """워크플로 변경 집합."""
    changeset_id: str
    from_version: str
    to_version: str
    created_at: str
    changes: tuple[WorkflowChange, ...]

    @property
    def step_removals(self) -> tuple[WorkflowChange, ...]:
        return tuple(c for c in self.changes if c.action == WorkflowChangeAction.STEP_REMOVED)

    @property
    def step_modifications(self) -> tuple[WorkflowChange, ...]:
        return tuple(c for c in self.changes if c.action == WorkflowChangeAction.STEP_MODIFIED)

    @property
    def topology_changes(self) -> tuple[WorkflowChange, ...]:
        return tuple(c for c in self.changes if c.action == WorkflowChangeAction.TOPOLOGY_CHANGED)

    @property
    def is_empty(self) -> bool:
        return len(self.changes) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Propagation Report — 영향 보고서
# ═══════════════════════════════════════════════════════════════════════════════

class PropagationSeverity(StrEnum):
    """영향 심각도."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AffectedExecutionRecord:
    """영향 받는 실행 기록."""
    storage_id: str
    workflow_name: str
    affected_steps: tuple[str, ...]
    original_success: bool
    affected_by_changes: tuple[str, ...]
    potential_outcome_change: bool
    timestamp: str


@dataclass(frozen=True)
class FlowPropagationReport:
    """플로 전파 영향 보고서."""
    report_id: str
    changeset_id: str
    created_at: str

    # Analysis scope
    total_executions_scanned: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Results
    affected_executions: tuple[AffectedExecutionRecord, ...] = ()
    severity: PropagationSeverity = PropagationSeverity.NONE

    # Statistics
    executions_with_outcome_change: int = 0
    executions_with_step_involvement: int = 0
    unique_workflows_affected: int = 0
    affected_steps: tuple[str, ...] = ()

    # Risk assessment
    risk_factors: tuple[str, ...] = ()
    recommendation: str = ""
    safe_to_apply: bool = True

    @property
    def impact_rate(self) -> float:
        if self.total_executions_scanned == 0:
            return 0.0
        return len(self.affected_executions) / self.total_executions_scanned


# ═══════════════════════════════════════════════════════════════════════════════
# Flow Propagation Engine — 영향 평가 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class FlowPropagationEngine:
    """워크플로 변경의 기존 실행 기록 영향 평가 엔진.

    WorkflowChangeSet을 받아 과거 실행 기록에 대한 영향을 분석.
    """

    __slots__ = ("_execution_store",)

    def __init__(self, execution_store: ExecutionStore) -> None:
        self._execution_store = execution_store

    def evaluate(
        self,
        changeset: WorkflowChangeSet,
        limit: int = 1000,
    ) -> FlowPropagationReport:
        """워크플로 변경 영향 평가."""
        import uuid

        from ea_flow.execution_store import ExecutionQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report_id = f"flow-prop-{uuid.uuid4().hex[:8]}"

        if changeset.is_empty:
            return FlowPropagationReport(
                report_id=report_id,
                changeset_id=changeset.changeset_id,
                created_at=now,
                recommendation="No changes to evaluate.",
            )

        affected_workflows = {c.workflow_name for c in changeset.changes}
        removed_steps = {
            (c.workflow_name, c.step_name)
            for c in changeset.changes
            if c.action == WorkflowChangeAction.STEP_REMOVED
        }
        changed_steps = {
            (c.workflow_name, c.step_name)
            for c in changeset.changes
            if c.step_name
        }

        options = ExecutionQueryOptions(limit=limit)
        stored_records = self._execution_store.query(options)

        affected: list[AffectedExecutionRecord] = []
        workflows_seen: set[str] = set()
        all_affected_steps: set[str] = set()
        outcome_changes = 0
        step_involvement = 0

        period_start = ""
        period_end = ""

        for rec in stored_records:
            if not period_start or rec.executed_at < period_start:
                period_start = rec.executed_at
            if not period_end or rec.executed_at > period_end:
                period_end = rec.executed_at

            if rec.workflow_name not in affected_workflows:
                continue

            involved_steps: list[str] = []
            for sr in rec.step_results:
                if (rec.workflow_name, sr.step_name) in changed_steps:
                    involved_steps.append(sr.step_name)

            # Also check topology changes affecting the whole workflow
            has_topology_change = any(
                c.workflow_name == rec.workflow_name
                and c.action == WorkflowChangeAction.TOPOLOGY_CHANGED
                for c in changeset.changes
            )

            if not involved_steps and not has_topology_change:
                continue

            step_involvement += 1

            potential_change = False
            if has_topology_change:
                potential_change = True
            elif any(
                (rec.workflow_name, s) in removed_steps
                for s in involved_steps
            ):
                potential_change = True

            if potential_change:
                outcome_changes += 1

            change_ids = tuple(
                c.step_name or c.workflow_name
                for c in changeset.changes
                if c.workflow_name == rec.workflow_name
            )

            affected.append(AffectedExecutionRecord(
                storage_id=rec.storage_id,
                workflow_name=rec.workflow_name,
                affected_steps=tuple(involved_steps),
                original_success=rec.success,
                affected_by_changes=change_ids,
                potential_outcome_change=potential_change,
                timestamp=rec.executed_at,
            ))

            workflows_seen.add(rec.workflow_name)
            all_affected_steps.update(involved_steps)

        severity = self._calculate_severity(
            len(affected), len(stored_records), outcome_changes, changeset,
        )
        risk_factors = self._identify_risks(changeset, affected, outcome_changes)
        recommendation = self._generate_recommendation(
            severity, changeset, outcome_changes, len(affected),
        )
        safe = severity not in (PropagationSeverity.HIGH, PropagationSeverity.CRITICAL)

        return FlowPropagationReport(
            report_id=report_id,
            changeset_id=changeset.changeset_id,
            created_at=now,
            total_executions_scanned=len(stored_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            affected_executions=tuple(affected),
            severity=severity,
            executions_with_outcome_change=outcome_changes,
            executions_with_step_involvement=step_involvement,
            unique_workflows_affected=len(workflows_seen),
            affected_steps=tuple(sorted(all_affected_steps)),
            risk_factors=tuple(risk_factors),
            recommendation=recommendation,
            safe_to_apply=safe,
        )

    def _calculate_severity(
        self,
        affected_count: int,
        total_count: int,
        outcome_changes: int,
        changeset: WorkflowChangeSet,
    ) -> PropagationSeverity:
        if total_count == 0 or affected_count == 0:
            return PropagationSeverity.NONE

        rate = affected_count / total_count

        if outcome_changes > 20 or rate > 0.5:
            return PropagationSeverity.CRITICAL
        if outcome_changes > 10 or rate > 0.3:
            return PropagationSeverity.HIGH
        if outcome_changes > 5 or rate > 0.1:
            return PropagationSeverity.MEDIUM
        if affected_count > 0:
            return PropagationSeverity.LOW
        return PropagationSeverity.NONE

    def _identify_risks(
        self,
        changeset: WorkflowChangeSet,
        affected: list[AffectedExecutionRecord],
        outcome_changes: int,
    ) -> list[str]:
        risks: list[str] = []

        if len(changeset.step_removals) > 3:
            risks.append(
                f"Multiple steps removed ({len(changeset.step_removals)})"
            )

        if outcome_changes > 5:
            risks.append(
                f"High number of potential outcome changes ({outcome_changes})"
            )

        if len(changeset.topology_changes) > 0:
            risks.append(
                f"Topology restructuring affects {len(changeset.topology_changes)} workflows"
            )

        return risks

    def _generate_recommendation(
        self,
        severity: PropagationSeverity,
        changeset: WorkflowChangeSet,
        outcome_changes: int,
        affected_count: int,
    ) -> str:
        if severity == PropagationSeverity.NONE:
            return "No impact detected. Safe to apply workflow changes."

        if severity == PropagationSeverity.LOW:
            return (
                f"Low impact: {affected_count} executions involved. "
                "Changes can be applied with standard review."
            )

        if severity == PropagationSeverity.MEDIUM:
            return (
                f"Medium impact: {outcome_changes} potential outcome changes. "
                "Recommend stakeholder review before applying."
            )

        if severity == PropagationSeverity.HIGH:
            return (
                f"High impact: {outcome_changes} outcome changes across "
                f"{affected_count} executions. Phased rollout recommended."
            )

        return (
            f"Critical impact: {outcome_changes} outcome changes. "
            "Do NOT apply without thorough review and approval. "
            "Consider breaking changes into smaller increments."
        )
