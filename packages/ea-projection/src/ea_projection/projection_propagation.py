"""Projection Propagation Engine — S6 Propagation for Projection Layer.

Evaluates the impact of level/filter/lens changes on existing projection snapshots.
Provides:
- ProjectionChangeSet: 프로젝션 변경 집합
- ProjectionPropagationReport: 영향 보고서
- ProjectionPropagationEngine: 프로젝션 변경의 기존 스냅샷 영향 평가

References:
- ea_kernel/impact_evaluator.py: S6 Propagation 패턴
- ea_projection/projection_store.py: S3 Store
- ea_projection/projection_analyzer.py: S4 Analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_projection.projection_store import ProjectionStore


# ═══════════════════════════════════════════════════════════════════════════════
# Projection Change Set — 프로젝션 변경 내역
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionChangeAction(StrEnum):
    """프로젝션 변경 유형."""
    LEVEL_ADDED = "level_added"
    LEVEL_REMOVED = "level_removed"
    FILTER_CHANGED = "filter_changed"
    LENS_CHANGED = "lens_changed"


@dataclass(frozen=True)
class ProjectionChange:
    """개별 프로젝션 변경."""
    change_id: str
    action: ProjectionChangeAction
    level: str = ""
    lens: str = ""
    before_state: str = ""
    after_state: str = ""
    description: str = ""


@dataclass(frozen=True)
class ProjectionChangeSet:
    """프로젝션 변경 집합."""
    changeset_id: str
    from_version: str
    to_version: str
    created_at: str
    changes: tuple[ProjectionChange, ...]

    @property
    def level_removals(self) -> tuple[ProjectionChange, ...]:
        return tuple(
            c for c in self.changes
            if c.action == ProjectionChangeAction.LEVEL_REMOVED
        )

    @property
    def filter_changes(self) -> tuple[ProjectionChange, ...]:
        return tuple(
            c for c in self.changes
            if c.action == ProjectionChangeAction.FILTER_CHANGED
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
class AffectedProjectionSnapshot:
    """영향 받는 프로젝션 스냅샷."""
    storage_id: str
    profile_name: str
    level: str
    lens: str
    original_status: str
    affected_by_changes: tuple[str, ...]
    potential_staleness: bool
    timestamp: str


@dataclass(frozen=True)
class ProjectionPropagationReport:
    """프로젝션 전파 영향 보고서."""
    report_id: str
    changeset_id: str
    created_at: str

    # Analysis scope
    total_projections_scanned: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Results
    affected_projections: tuple[AffectedProjectionSnapshot, ...] = ()
    severity: PropagationSeverity = PropagationSeverity.NONE

    # Statistics
    projections_becoming_stale: int = 0
    projections_with_level_involvement: int = 0
    unique_levels_affected: int = 0
    affected_lenses: tuple[str, ...] = ()

    # Risk assessment
    risk_factors: tuple[str, ...] = ()
    recommendation: str = ""
    safe_to_apply: bool = True

    @property
    def impact_rate(self) -> float:
        if self.total_projections_scanned == 0:
            return 0.0
        return len(self.affected_projections) / self.total_projections_scanned


# ═══════════════════════════════════════════════════════════════════════════════
# Projection Propagation Engine — 영향 평가 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionPropagationEngine:
    """프로젝션 변경의 기존 스냅샷 영향 평가 엔진.

    ProjectionChangeSet을 받아 과거 프로젝션 스냅샷에 대한 영향을 분석.
    """

    __slots__ = ("_projection_store",)

    def __init__(self, projection_store: ProjectionStore) -> None:
        self._projection_store = projection_store

    def evaluate(
        self,
        changeset: ProjectionChangeSet,
        limit: int = 1000,
    ) -> ProjectionPropagationReport:
        """프로젝션 변경 영향 평가."""
        import uuid

        from ea_projection.projection_store import ProjectionQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report_id = f"proj-prop-{uuid.uuid4().hex[:8]}"

        if changeset.is_empty:
            return ProjectionPropagationReport(
                report_id=report_id,
                changeset_id=changeset.changeset_id,
                created_at=now,
                recommendation="No changes to evaluate.",
            )

        removed_levels = {
            c.level for c in changeset.changes
            if c.action == ProjectionChangeAction.LEVEL_REMOVED
        }
        changed_levels = {
            c.level for c in changeset.changes if c.level
        }
        changed_lenses = {
            c.lens for c in changeset.changes if c.lens
        }

        options = ProjectionQueryOptions(limit=limit)
        stored_records = self._projection_store.query(options)

        affected: list[AffectedProjectionSnapshot] = []
        levels_seen: set[str] = set()
        lenses_seen: set[str] = set()
        staleness_count = 0
        level_involvement = 0

        period_start = ""
        period_end = ""

        for snap in stored_records:
            ts = snap.projected_at or snap.stored_at
            if ts:
                if not period_start or ts < period_start:
                    period_start = ts
                if not period_end or ts > period_end:
                    period_end = ts

            involved = False
            involved_change_ids: list[str] = []

            if snap.level in changed_levels:
                involved = True
                involved_change_ids.extend(
                    c.change_id for c in changeset.changes
                    if c.level == snap.level
                )

            if snap.lens in changed_lenses:
                involved = True
                involved_change_ids.extend(
                    c.change_id for c in changeset.changes
                    if c.lens == snap.lens
                )

            if not involved:
                continue

            level_involvement += 1

            potential_stale = (
                snap.level in removed_levels
                or any(
                    c.action == ProjectionChangeAction.FILTER_CHANGED
                    and c.level == snap.level
                    for c in changeset.changes
                )
            )

            if potential_stale:
                staleness_count += 1

            affected.append(AffectedProjectionSnapshot(
                storage_id=snap.storage_id,
                profile_name=snap.profile_name,
                level=snap.level,
                lens=snap.lens,
                original_status=snap.status.value,
                affected_by_changes=tuple(involved_change_ids),
                potential_staleness=potential_stale,
                timestamp=ts,
            ))

            levels_seen.add(snap.level)
            lenses_seen.add(snap.lens)

        severity = self._calculate_severity(
            len(affected), len(stored_records), staleness_count, changeset,
        )
        risk_factors = self._identify_risks(changeset, affected, staleness_count)
        recommendation = self._generate_recommendation(
            severity, changeset, staleness_count, len(affected),
        )
        safe = severity not in (PropagationSeverity.HIGH, PropagationSeverity.CRITICAL)

        return ProjectionPropagationReport(
            report_id=report_id,
            changeset_id=changeset.changeset_id,
            created_at=now,
            total_projections_scanned=len(stored_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            affected_projections=tuple(affected),
            severity=severity,
            projections_becoming_stale=staleness_count,
            projections_with_level_involvement=level_involvement,
            unique_levels_affected=len(levels_seen),
            affected_lenses=tuple(sorted(lenses_seen)),
            risk_factors=tuple(risk_factors),
            recommendation=recommendation,
            safe_to_apply=safe,
        )

    def _calculate_severity(
        self,
        affected_count: int,
        total_count: int,
        staleness_count: int,
        changeset: ProjectionChangeSet,
    ) -> PropagationSeverity:
        if total_count == 0 or affected_count == 0:
            return PropagationSeverity.NONE

        rate = affected_count / total_count

        if staleness_count > 20 or rate > 0.5:
            return PropagationSeverity.CRITICAL
        if staleness_count > 10 or rate > 0.3:
            return PropagationSeverity.HIGH
        if staleness_count > 5 or rate > 0.1:
            return PropagationSeverity.MEDIUM
        if affected_count > 0:
            return PropagationSeverity.LOW
        return PropagationSeverity.NONE

    def _identify_risks(
        self,
        changeset: ProjectionChangeSet,
        affected: list[AffectedProjectionSnapshot],
        staleness_count: int,
    ) -> list[str]:
        risks: list[str] = []

        if len(changeset.level_removals) > 2:
            risks.append(
                f"Multiple levels removed ({len(changeset.level_removals)})"
            )

        if staleness_count > 5:
            risks.append(
                f"High number of projections becoming stale ({staleness_count})"
            )

        stale_items = [a for a in affected if a.potential_staleness]
        if len(stale_items) > 10:
            risks.append(
                f"Wide cascade: {len(stale_items)} projections may become stale"
            )

        return risks

    def _generate_recommendation(
        self,
        severity: PropagationSeverity,
        changeset: ProjectionChangeSet,
        staleness_count: int,
        affected_count: int,
    ) -> str:
        if severity == PropagationSeverity.NONE:
            return "No impact detected. Safe to apply projection changes."

        if severity == PropagationSeverity.LOW:
            return (
                f"Low impact: {affected_count} projections involved. "
                "Changes can be applied with standard review."
            )

        if severity == PropagationSeverity.MEDIUM:
            return (
                f"Medium impact: {staleness_count} projections becoming stale. "
                "Recommend re-projection after applying changes."
            )

        if severity == PropagationSeverity.HIGH:
            return (
                f"High impact: {staleness_count} stale projections across "
                f"{affected_count} snapshots. Phased rollout recommended."
            )

        return (
            f"Critical impact: {staleness_count} projections becoming stale. "
            "Do NOT apply without thorough review and approval. "
            "Consider breaking changes into smaller increments."
        )
