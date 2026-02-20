"""Projection Simulator — S5 Evolution What-If for Projection Layer.

Simulates the impact of policy/level changes on existing projections.
Provides:
- PolicyChangeType: 변경 유형
- PolicyChange: 시뮬레이션할 변경 사항
- ProjectionSimulationResult: 시뮬레이션 결과
- ProjectionSimulator: 시뮬레이션 엔진

References:
- ea_needs/needs_simulator.py: S5 시뮬레이션 패턴
- ea_decision/decision_simulator.py: S5 도메인 번역 패턴
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_projection.projection_store import ProjectionStore


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Change Types
# ═══════════════════════════════════════════════════════════════════════════════

class PolicyChangeType(StrEnum):
    """시뮬레이션할 변경 유형."""
    REMOVE_LEVEL = "remove_level"
    CHANGE_MAX_EDGES = "change_max_edges"
    REMOVE_CATEGORY = "remove_category"
    CHANGE_LENS = "change_lens"


@dataclass(frozen=True)
class PolicyChange:
    """시뮬레이션할 변경 사항."""
    change_type: PolicyChangeType
    target_value: str
    new_value: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Results
# ═══════════════════════════════════════════════════════════════════════════════

class ImpactLevel(StrEnum):
    """영향 수준."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AffectedProjection:
    """영향 받는 프로젝션."""
    storage_id: str
    profile_name: str
    level: str
    lens: str
    node_count: int
    edge_count: int
    impact_description: str


@dataclass(frozen=True)
class ProjectionSimulationResult:
    """프로젝션 변경 시뮬레이션 결과."""
    simulation_id: str
    created_at: str

    # Changes applied
    changes: tuple[PolicyChange, ...]

    # Analysis
    total_projections_analyzed: int = 0
    affected_projections: int = 0
    affected_projection_details: tuple[AffectedProjection, ...] = ()

    # Impact assessment
    impact_level: ImpactLevel = ImpactLevel.NONE

    # Summary
    invalidated_projections: int = 0
    edge_budget_violations: int = 0

    # Recommendations
    risk_factors: tuple[str, ...] = ()
    safe_to_apply: bool = True

    @property
    def change_rate(self) -> float:
        if self.total_projections_analyzed == 0:
            return 0.0
        return self.affected_projections / self.total_projections_analyzed


# ═══════════════════════════════════════════════════════════════════════════════
# Projection Simulator
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionSimulator:
    """프로젝션 정책 변경 영향 시뮬레이터.

    과거 프로젝션 이력에 정책 변경을 적용했을 때 결과가 어떻게 달라지는지 시뮬레이션.
    """

    __slots__ = ("_projection_store",)

    def __init__(self, projection_store: ProjectionStore) -> None:
        self._projection_store = projection_store

    def simulate(
        self,
        changes: list[PolicyChange],
        limit: int = 1000,
    ) -> ProjectionSimulationResult:
        """프로젝션 정책 변경 시뮬레이션.

        Args:
            changes: 시뮬레이션할 변경 목록
            limit: 분석할 최대 프로젝션 수

        Returns:
            ProjectionSimulationResult with impact analysis
        """
        from ea_projection.projection_store import ProjectionQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        simulation_id = f"sim-{uuid.uuid4().hex[:8]}"

        options = ProjectionQueryOptions(limit=limit)
        records = self._projection_store.query(options)

        # Build change maps
        removed_levels: set[str] = {
            c.target_value for c in changes
            if c.change_type == PolicyChangeType.REMOVE_LEVEL
        }
        edge_budget_changes: dict[str, int] = {}
        for c in changes:
            if c.change_type == PolicyChangeType.CHANGE_MAX_EDGES:
                try:
                    edge_budget_changes[c.target_value] = int(c.new_value)
                except (ValueError, TypeError):
                    pass
        removed_categories: set[str] = {
            c.target_value for c in changes
            if c.change_type == PolicyChangeType.REMOVE_CATEGORY
        }
        lens_changes: dict[str, str] = {
            c.target_value: c.new_value
            for c in changes
            if c.change_type == PolicyChangeType.CHANGE_LENS
        }

        # Analyze each projection
        affected_details: list[AffectedProjection] = []
        invalidated = 0
        edge_violations = 0

        for snap in records:
            # Check if level is being removed
            if snap.level in removed_levels:
                invalidated += 1
                affected_details.append(AffectedProjection(
                    storage_id=snap.storage_id,
                    profile_name=snap.profile_name,
                    level=snap.level,
                    lens=snap.lens,
                    node_count=snap.node_count,
                    edge_count=snap.edge_count,
                    impact_description=(
                        f"Projection level '{snap.level}' would be removed"
                    ),
                ))
                continue

            # Check if edge budget is being reduced below current count
            if snap.level in edge_budget_changes:
                new_budget = edge_budget_changes[snap.level]
                if snap.edge_count > new_budget:
                    edge_violations += 1
                    affected_details.append(AffectedProjection(
                        storage_id=snap.storage_id,
                        profile_name=snap.profile_name,
                        level=snap.level,
                        lens=snap.lens,
                        node_count=snap.node_count,
                        edge_count=snap.edge_count,
                        impact_description=(
                            f"Edge count {snap.edge_count} exceeds "
                            f"new budget {new_budget}"
                        ),
                    ))
                    continue

            # Check if lens is being changed
            if snap.level in lens_changes:
                new_lens = lens_changes[snap.level]
                if snap.lens != new_lens:
                    affected_details.append(AffectedProjection(
                        storage_id=snap.storage_id,
                        profile_name=snap.profile_name,
                        level=snap.level,
                        lens=snap.lens,
                        node_count=snap.node_count,
                        edge_count=snap.edge_count,
                        impact_description=(
                            f"Lens change: {snap.lens} -> {new_lens}"
                        ),
                    ))

        # Calculate impact level
        affected_count = len(affected_details)
        total_count = len(records)
        impact_level = self._calculate_impact_level(
            affected_count, total_count, invalidated,
        )

        # Identify risk factors
        risk_factors = self._identify_risk_factors(
            invalidated, edge_violations, changes,
        )

        safe = (
            impact_level not in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)
            and invalidated < 10
            and len(risk_factors) < 3
        )

        return ProjectionSimulationResult(
            simulation_id=simulation_id,
            created_at=now,
            changes=tuple(changes),
            total_projections_analyzed=total_count,
            affected_projections=affected_count,
            affected_projection_details=tuple(affected_details),
            impact_level=impact_level,
            invalidated_projections=invalidated,
            edge_budget_violations=edge_violations,
            risk_factors=tuple(risk_factors),
            safe_to_apply=safe,
        )

    def simulate_level_removal(
        self,
        level: str,
        limit: int = 1000,
    ) -> ProjectionSimulationResult:
        """단일 레벨 제거 시뮬레이션."""
        change = PolicyChange(
            change_type=PolicyChangeType.REMOVE_LEVEL,
            target_value=level,
        )
        return self.simulate([change], limit)

    def _calculate_impact_level(
        self,
        affected_count: int,
        total_count: int,
        invalidated: int,
    ) -> ImpactLevel:
        if total_count == 0:
            return ImpactLevel.NONE

        change_rate = affected_count / total_count

        if invalidated > 20 or change_rate > 0.5:
            return ImpactLevel.CRITICAL
        if invalidated > 10 or change_rate > 0.3:
            return ImpactLevel.HIGH
        if invalidated > 5 or change_rate > 0.1:
            return ImpactLevel.MEDIUM
        if affected_count > 0:
            return ImpactLevel.LOW

        return ImpactLevel.NONE

    def _identify_risk_factors(
        self,
        invalidated: int,
        edge_violations: int,
        changes: list[PolicyChange],
    ) -> list[str]:
        factors: list[str] = []

        if invalidated > 5:
            factors.append(
                f"High number of invalidated projections: {invalidated}"
            )

        if edge_violations > 10:
            factors.append(
                f"Many edge budget violations: {edge_violations}"
            )

        removals = sum(
            1 for c in changes
            if c.change_type == PolicyChangeType.REMOVE_LEVEL
        )
        if removals > 2:
            factors.append(
                f"Removing multiple levels ({removals}) increases risk"
            )

        return factors
