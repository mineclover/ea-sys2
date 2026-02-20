"""Needs Propagation Engine — S6 Propagation for Needs Layer.

Evaluates the impact of stakeholder/priority changes on existing need snapshots.
Provides:
- NeedsChangeSet: 니즈 변경 집합
- NeedsPropagationReport: 영향 보고서
- NeedsPropagationEngine: 니즈 변경의 기존 스냅샷 영향 평가

References:
- ea_kernel/impact_evaluator.py: S6 Propagation 패턴
- ea_needs/needs_store.py: S3 Store
- ea_needs/needs_analyzer.py: S4 Analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_needs.needs_store import NeedStore


# ═══════════════════════════════════════════════════════════════════════════════
# Needs Change Set — 니즈 변경 내역
# ═══════════════════════════════════════════════════════════════════════════════

class NeedsChangeAction(StrEnum):
    """니즈 변경 유형."""
    STAKEHOLDER_ADDED = "stakeholder_added"
    STAKEHOLDER_REMOVED = "stakeholder_removed"
    PRIORITY_CHANGED = "priority_changed"
    STATUS_CHANGED = "status_changed"


@dataclass(frozen=True)
class NeedsChange:
    """개별 니즈 변경."""
    change_id: str
    action: NeedsChangeAction
    stakeholder_id: str = ""
    priority: str = ""
    before_state: str = ""
    after_state: str = ""
    description: str = ""


@dataclass(frozen=True)
class NeedsChangeSet:
    """니즈 변경 집합."""
    changeset_id: str
    from_version: str
    to_version: str
    created_at: str
    changes: tuple[NeedsChange, ...]

    @property
    def stakeholder_removals(self) -> tuple[NeedsChange, ...]:
        return tuple(
            c for c in self.changes
            if c.action == NeedsChangeAction.STAKEHOLDER_REMOVED
        )

    @property
    def priority_changes(self) -> tuple[NeedsChange, ...]:
        return tuple(
            c for c in self.changes
            if c.action == NeedsChangeAction.PRIORITY_CHANGED
        )

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
class AffectedNeedSnapshot:
    """영향 받는 니즈 스냅샷."""
    storage_id: str
    need_id: str
    stakeholder_id: str
    original_status: str
    original_priority: str
    affected_by_changes: tuple[str, ...]
    potential_status_change: bool
    timestamp: str


@dataclass(frozen=True)
class NeedsPropagationReport:
    """니즈 전파 영향 보고서."""
    report_id: str
    changeset_id: str
    created_at: str

    # Analysis scope
    total_needs_scanned: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Results
    affected_needs: tuple[AffectedNeedSnapshot, ...] = ()
    severity: PropagationSeverity = PropagationSeverity.NONE

    # Statistics
    needs_with_status_change: int = 0
    needs_with_stakeholder_involvement: int = 0
    unique_stakeholders_affected: int = 0
    affected_priorities: tuple[str, ...] = ()

    # Risk assessment
    risk_factors: tuple[str, ...] = ()
    recommendation: str = ""
    safe_to_apply: bool = True

    @property
    def impact_rate(self) -> float:
        if self.total_needs_scanned == 0:
            return 0.0
        return len(self.affected_needs) / self.total_needs_scanned


# ═══════════════════════════════════════════════════════════════════════════════
# Needs Propagation Engine — 영향 평가 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class NeedsPropagationEngine:
    """니즈 변경의 기존 스냅샷 영향 평가 엔진.

    NeedsChangeSet을 받아 과거 니즈 스냅샷에 대한 영향을 분석.
    """

    __slots__ = ("_need_store",)

    def __init__(self, need_store: NeedStore) -> None:
        self._need_store = need_store

    def evaluate(
        self,
        changeset: NeedsChangeSet,
        limit: int = 1000,
    ) -> NeedsPropagationReport:
        """니즈 변경 영향 평가."""
        import uuid

        from ea_needs.needs_store import NeedQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report_id = f"needs-prop-{uuid.uuid4().hex[:8]}"

        if changeset.is_empty:
            return NeedsPropagationReport(
                report_id=report_id,
                changeset_id=changeset.changeset_id,
                created_at=now,
                recommendation="No changes to evaluate.",
            )

        removed_stakeholders = {
            c.stakeholder_id for c in changeset.changes
            if c.action == NeedsChangeAction.STAKEHOLDER_REMOVED
        }
        changed_stakeholders = {
            c.stakeholder_id for c in changeset.changes
            if c.stakeholder_id
        }
        changed_priorities = {
            c.priority for c in changeset.changes
            if c.action == NeedsChangeAction.PRIORITY_CHANGED and c.priority
        }

        options = NeedQueryOptions(limit=limit)
        stored_records = self._need_store.query(options)

        affected: list[AffectedNeedSnapshot] = []
        stakeholders_seen: set[str] = set()
        priorities_seen: set[str] = set()
        status_changes = 0
        stakeholder_involvement = 0

        period_start = ""
        period_end = ""

        for snap in stored_records:
            ts = snap.expressed_at or snap.stored_at
            if ts:
                if not period_start or ts < period_start:
                    period_start = ts
                if not period_end or ts > period_end:
                    period_end = ts

            involved = False
            involved_change_ids: list[str] = []

            # Check stakeholder involvement
            if snap.stakeholder_id in changed_stakeholders:
                involved = True
                involved_change_ids.extend(
                    c.change_id for c in changeset.changes
                    if c.stakeholder_id == snap.stakeholder_id
                )

            # Check priority involvement
            if snap.priority in changed_priorities:
                involved = True
                involved_change_ids.extend(
                    c.change_id for c in changeset.changes
                    if c.action == NeedsChangeAction.PRIORITY_CHANGED
                    and c.priority == snap.priority
                )

            if not involved:
                continue

            stakeholder_involvement += 1

            potential_change = snap.stakeholder_id in removed_stakeholders

            if potential_change:
                status_changes += 1

            affected.append(AffectedNeedSnapshot(
                storage_id=snap.storage_id,
                need_id=snap.need_id,
                stakeholder_id=snap.stakeholder_id,
                original_status=snap.status.value,
                original_priority=snap.priority,
                affected_by_changes=tuple(involved_change_ids),
                potential_status_change=potential_change,
                timestamp=ts,
            ))

            stakeholders_seen.add(snap.stakeholder_id)
            priorities_seen.add(snap.priority)

        severity = self._calculate_severity(
            len(affected), len(stored_records), status_changes, changeset,
        )
        risk_factors = self._identify_risks(changeset, affected, status_changes)
        recommendation = self._generate_recommendation(
            severity, changeset, status_changes, len(affected),
        )
        safe = severity not in (PropagationSeverity.HIGH, PropagationSeverity.CRITICAL)

        return NeedsPropagationReport(
            report_id=report_id,
            changeset_id=changeset.changeset_id,
            created_at=now,
            total_needs_scanned=len(stored_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            affected_needs=tuple(affected),
            severity=severity,
            needs_with_status_change=status_changes,
            needs_with_stakeholder_involvement=stakeholder_involvement,
            unique_stakeholders_affected=len(stakeholders_seen),
            affected_priorities=tuple(sorted(priorities_seen)),
            risk_factors=tuple(risk_factors),
            recommendation=recommendation,
            safe_to_apply=safe,
        )

    def _calculate_severity(
        self,
        affected_count: int,
        total_count: int,
        status_changes: int,
        changeset: NeedsChangeSet,
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
        changeset: NeedsChangeSet,
        affected: list[AffectedNeedSnapshot],
        status_changes: int,
    ) -> list[str]:
        risks: list[str] = []

        if len(changeset.stakeholder_removals) > 2:
            risks.append(
                f"Multiple stakeholders removed ({len(changeset.stakeholder_removals)})"
            )

        if status_changes > 5:
            risks.append(
                f"High number of potential status changes ({status_changes})"
            )

        orphaned = [a for a in affected if a.potential_status_change]
        if len(orphaned) > 10:
            risks.append(
                f"Wide cascade: {len(orphaned)} needs may be orphaned"
            )

        return risks

    def _generate_recommendation(
        self,
        severity: PropagationSeverity,
        changeset: NeedsChangeSet,
        status_changes: int,
        affected_count: int,
    ) -> str:
        if severity == PropagationSeverity.NONE:
            return "No impact detected. Safe to apply needs changes."

        if severity == PropagationSeverity.LOW:
            return (
                f"Low impact: {affected_count} needs involved. "
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
                f"{affected_count} needs. Phased rollout recommended."
            )

        return (
            f"Critical impact: {status_changes} status changes. "
            "Do NOT apply without thorough review and approval. "
            "Consider breaking changes into smaller increments."
        )
