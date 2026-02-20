"""Decision Propagation Engine — S6 Propagation for Decision Layer.

Evaluates the impact of pattern changes on existing decision snapshots.
Provides:
- PatternChangeSet: 패턴 변경 집합
- DecisionPropagationReport: 영향 보고서
- DecisionPropagationEngine: 패턴 변경의 기존 의사결정 영향 평가

References:
- ea_kernel/impact_evaluator.py: S6 Propagation 패턴
- ea_decision/topic_store.py: S3 Store
- ea_decision/decision_analyzer.py: S4 Analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_decision.topic_store import TopicStore


# ═══════════════════════════════════════════════════════════════════════════════
# Pattern Change Set — 패턴 변경 내역
# ═══════════════════════════════════════════════════════════════════════════════

class PatternChangeAction(StrEnum):
    """패턴 변경 유형."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    EFFECTIVENESS_CHANGED = "effectiveness_changed"


@dataclass(frozen=True)
class PatternChange:
    """개별 패턴 변경."""
    pattern_name: str
    action: PatternChangeAction
    before_grade: str = ""
    after_grade: str = ""
    description: str = ""


@dataclass(frozen=True)
class PatternChangeSet:
    """패턴 변경 집합."""
    changeset_id: str
    from_version: str
    to_version: str
    created_at: str
    changes: tuple[PatternChange, ...]

    @property
    def added_patterns(self) -> tuple[PatternChange, ...]:
        return tuple(c for c in self.changes if c.action == PatternChangeAction.ADDED)

    @property
    def removed_patterns(self) -> tuple[PatternChange, ...]:
        return tuple(c for c in self.changes if c.action == PatternChangeAction.REMOVED)

    @property
    def modified_patterns(self) -> tuple[PatternChange, ...]:
        return tuple(c for c in self.changes if c.action == PatternChangeAction.MODIFIED)

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
class AffectedDecisionSnapshot:
    """영향 받는 의사결정 스냅샷."""
    storage_id: str
    topic_id: str
    pattern_name: str
    original_status: str
    affected_by_patterns: tuple[str, ...]
    potential_status_change: bool
    timestamp: str


@dataclass(frozen=True)
class DecisionPropagationReport:
    """의사결정 전파 영향 보고서."""
    report_id: str
    changeset_id: str
    created_at: str

    # Analysis scope
    total_decisions_scanned: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Results
    affected_decisions: tuple[AffectedDecisionSnapshot, ...] = ()
    severity: PropagationSeverity = PropagationSeverity.NONE

    # Statistics
    decisions_with_status_change: int = 0
    decisions_with_pattern_involvement: int = 0
    unique_patterns_affected: int = 0
    affected_complexities: tuple[str, ...] = ()

    # Risk assessment
    risk_factors: tuple[str, ...] = ()
    recommendation: str = ""
    safe_to_apply: bool = True

    @property
    def impact_rate(self) -> float:
        if self.total_decisions_scanned == 0:
            return 0.0
        return len(self.affected_decisions) / self.total_decisions_scanned


# ═══════════════════════════════════════════════════════════════════════════════
# Decision Propagation Engine — 영향 평가 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionPropagationEngine:
    """패턴 변경의 기존 의사결정 영향 평가 엔진.

    PatternChangeSet을 받아 과거 의사결정 스냅샷에 대한 영향을 분석.
    """

    __slots__ = ("_topic_store",)

    def __init__(self, topic_store: TopicStore) -> None:
        self._topic_store = topic_store

    def evaluate(
        self,
        changeset: PatternChangeSet,
        limit: int = 1000,
    ) -> DecisionPropagationReport:
        """패턴 변경 영향 평가."""
        import uuid

        from ea_decision.topic_store import DecisionQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report_id = f"decision-prop-{uuid.uuid4().hex[:8]}"

        if changeset.is_empty:
            return DecisionPropagationReport(
                report_id=report_id,
                changeset_id=changeset.changeset_id,
                created_at=now,
                recommendation="No changes to evaluate.",
            )

        affected_pattern_names = {c.pattern_name for c in changeset.changes}
        removed_pattern_names = {
            c.pattern_name for c in changeset.changes
            if c.action == PatternChangeAction.REMOVED
        }

        options = DecisionQueryOptions(limit=limit)
        stored_records = self._topic_store.query(options)

        affected: list[AffectedDecisionSnapshot] = []
        complexities_seen: set[str] = set()
        status_changes = 0
        pattern_involvement = 0

        period_start = ""
        period_end = ""

        for snap in stored_records:
            if not period_start or snap.decided_at < period_start:
                period_start = snap.decided_at
            if not period_end or snap.decided_at > period_end:
                period_end = snap.decided_at

            if snap.pattern_name not in affected_pattern_names:
                continue

            pattern_involvement += 1

            potential_change = snap.pattern_name in removed_pattern_names

            if potential_change:
                status_changes += 1

            affected.append(AffectedDecisionSnapshot(
                storage_id=snap.storage_id,
                topic_id=snap.topic_id,
                pattern_name=snap.pattern_name,
                original_status=snap.status.value,
                affected_by_patterns=(snap.pattern_name,),
                potential_status_change=potential_change,
                timestamp=snap.decided_at,
            ))

            complexities_seen.add(snap.complexity)

        severity = self._calculate_severity(
            len(affected), len(stored_records), status_changes, changeset,
        )
        risk_factors = self._identify_risks(changeset, affected, status_changes)
        recommendation = self._generate_recommendation(
            severity, changeset, status_changes, len(affected),
        )
        safe = severity not in (PropagationSeverity.HIGH, PropagationSeverity.CRITICAL)

        return DecisionPropagationReport(
            report_id=report_id,
            changeset_id=changeset.changeset_id,
            created_at=now,
            total_decisions_scanned=len(stored_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            affected_decisions=tuple(affected),
            severity=severity,
            decisions_with_status_change=status_changes,
            decisions_with_pattern_involvement=pattern_involvement,
            unique_patterns_affected=len(affected_pattern_names & {a.pattern_name for a in affected}),
            affected_complexities=tuple(sorted(complexities_seen)),
            risk_factors=tuple(risk_factors),
            recommendation=recommendation,
            safe_to_apply=safe,
        )

    def _calculate_severity(
        self,
        affected_count: int,
        total_count: int,
        status_changes: int,
        changeset: PatternChangeSet,
    ) -> PropagationSeverity:
        if total_count == 0 or affected_count == 0:
            return PropagationSeverity.NONE

        rate = affected_count / total_count

        if status_changes > 20 or rate > 0.5:
            return PropagationSeverity.CRITICAL
        if status_changes > 10 or rate > 0.3:
            return PropagationSeverity.HIGH
        if status_changes > 5 or rate > 0.1:
            return PropagationSeverity.MEDIUM
        if affected_count > 0:
            return PropagationSeverity.LOW
        return PropagationSeverity.NONE

    def _identify_risks(
        self,
        changeset: PatternChangeSet,
        affected: list[AffectedDecisionSnapshot],
        status_changes: int,
    ) -> list[str]:
        risks: list[str] = []

        if len(changeset.removed_patterns) > 3:
            risks.append(
                f"Multiple patterns removed ({len(changeset.removed_patterns)})"
            )

        if status_changes > 5:
            risks.append(
                f"High number of potential status changes ({status_changes})"
            )

        patterns_with_changes = [a for a in affected if a.potential_status_change]
        if len(patterns_with_changes) > 10:
            risks.append(
                f"Wide cascade: {len(patterns_with_changes)} decisions may be invalidated"
            )

        return risks

    def _generate_recommendation(
        self,
        severity: PropagationSeverity,
        changeset: PatternChangeSet,
        status_changes: int,
        affected_count: int,
    ) -> str:
        if severity == PropagationSeverity.NONE:
            return "No impact detected. Safe to apply pattern changes."

        if severity == PropagationSeverity.LOW:
            return (
                f"Low impact: {affected_count} decisions involved. "
                "Changes can be applied with standard review."
            )

        if severity == PropagationSeverity.MEDIUM:
            return (
                f"Medium impact: {status_changes} potential status changes. "
                "Recommend stakeholder review before applying."
            )

        if severity == PropagationSeverity.HIGH:
            return (
                f"High impact: {status_changes} status changes across "
                f"{affected_count} decisions. Phased rollout recommended."
            )

        return (
            f"Critical impact: {status_changes} status changes. "
            "Do NOT apply without thorough review and approval. "
            "Consider breaking changes into smaller increments."
        )
