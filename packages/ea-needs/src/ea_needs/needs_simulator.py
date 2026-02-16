"""Needs Simulator — S5 Evolution What-If for Needs Layer.

Simulates the impact of stakeholder/need changes on existing needs.
Provides:
- NeedChangeType: 변경 유형
- NeedChange: 시뮬레이션할 변경 사항
- NeedSimulationResult: 시뮬레이션 결과
- NeedsSimulator: 시뮬레이션 엔진

References:
- ea_kernel/what_if_simulator.py: S5 시뮬레이션 패턴
- ea_decision/decision_simulator.py: S5 도메인 번역 패턴
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_needs.needs_store import NeedStore


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Change Types
# ═══════════════════════════════════════════════════════════════════════════════

class NeedChangeType(StrEnum):
    """시뮬레이션할 변경 유형."""
    REMOVE_STAKEHOLDER = "remove_stakeholder"
    WITHDRAW_BY_PRIORITY = "withdraw_by_priority"
    CHANGE_COMPLEXITY = "change_complexity"
    REMOVE_USE_CASE = "remove_use_case"


@dataclass(frozen=True)
class NeedChange:
    """시뮬레이션할 변경 사항."""
    change_type: NeedChangeType
    target_value: str
    new_complexity: str = ""


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
class AffectedNeed:
    """영향 받는 니즈."""
    need_id: str
    stakeholder_id: str
    original_status: str
    priority: str
    impact_description: str


@dataclass(frozen=True)
class NeedSimulationResult:
    """니즈 변경 시뮬레이션 결과."""
    simulation_id: str
    created_at: str

    # Changes applied
    changes: tuple[NeedChange, ...]

    # Analysis
    total_needs_analyzed: int = 0
    affected_needs: int = 0
    affected_need_details: tuple[AffectedNeed, ...] = ()

    # Impact assessment
    impact_level: ImpactLevel = ImpactLevel.NONE

    # Summary
    orphaned_needs: int = 0
    complexity_mismatches: int = 0

    # Recommendations
    risk_factors: tuple[str, ...] = ()
    safe_to_apply: bool = True

    @property
    def change_rate(self) -> float:
        if self.total_needs_analyzed == 0:
            return 0.0
        return self.affected_needs / self.total_needs_analyzed


# ═══════════════════════════════════════════════════════════════════════════════
# Needs Simulator
# ═══════════════════════════════════════════════════════════════════════════════

class NeedsSimulator:
    """니즈 변경 영향 시뮬레이터.

    과거 니즈 이력에 변경을 적용했을 때 결과가 어떻게 달라지는지 시뮬레이션.
    """

    __slots__ = ("_need_store",)

    def __init__(self, need_store: NeedStore) -> None:
        self._need_store = need_store

    def simulate(
        self,
        changes: list[NeedChange],
        limit: int = 1000,
    ) -> NeedSimulationResult:
        """니즈 변경 시뮬레이션.

        Args:
            changes: 시뮬레이션할 변경 목록
            limit: 분석할 최대 니즈 수

        Returns:
            NeedSimulationResult with impact analysis
        """
        from ea_needs.needs_store import NeedQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        simulation_id = f"sim-{uuid.uuid4().hex[:8]}"

        options = NeedQueryOptions(limit=limit)
        records = self._need_store.query(options)

        # Build change maps
        removed_stakeholders: set[str] = {
            c.target_value for c in changes
            if c.change_type == NeedChangeType.REMOVE_STAKEHOLDER
        }
        withdrawn_priorities: set[str] = {
            c.target_value for c in changes
            if c.change_type == NeedChangeType.WITHDRAW_BY_PRIORITY
        }
        complexity_changes: dict[str, str] = {
            c.target_value: c.new_complexity
            for c in changes
            if c.change_type == NeedChangeType.CHANGE_COMPLEXITY
        }
        removed_use_cases: set[str] = {
            c.target_value for c in changes
            if c.change_type == NeedChangeType.REMOVE_USE_CASE
        }

        # Analyze each need
        affected_details: list[AffectedNeed] = []
        orphaned = 0
        complexity_mismatches = 0

        for snap in records:
            # Check if stakeholder is being removed
            if snap.stakeholder_id in removed_stakeholders:
                orphaned += 1
                affected_details.append(AffectedNeed(
                    need_id=snap.need_id,
                    stakeholder_id=snap.stakeholder_id,
                    original_status=snap.status.value,
                    priority=snap.priority,
                    impact_description=(
                        f"Need would lose stakeholder "
                        f"'{snap.stakeholder_id}'"
                    ),
                ))
                continue

            # Check if priority is being withdrawn
            if snap.priority in withdrawn_priorities:
                affected_details.append(AffectedNeed(
                    need_id=snap.need_id,
                    stakeholder_id=snap.stakeholder_id,
                    original_status=snap.status.value,
                    priority=snap.priority,
                    impact_description=(
                        f"Need with priority '{snap.priority}' "
                        f"would be withdrawn"
                    ),
                ))
                continue

            # Check if use case is being removed
            if snap.use_case_id and snap.use_case_id in removed_use_cases:
                affected_details.append(AffectedNeed(
                    need_id=snap.need_id,
                    stakeholder_id=snap.stakeholder_id,
                    original_status=snap.status.value,
                    priority=snap.priority,
                    impact_description=(
                        f"Need would lose use case "
                        f"'{snap.use_case_id}'"
                    ),
                ))
                continue

            # Check if complexity is changing
            if snap.complexity in complexity_changes:
                new_complexity = complexity_changes[snap.complexity]
                if snap.complexity != new_complexity:
                    complexity_mismatches += 1
                    affected_details.append(AffectedNeed(
                        need_id=snap.need_id,
                        stakeholder_id=snap.stakeholder_id,
                        original_status=snap.status.value,
                        priority=snap.priority,
                        impact_description=(
                            f"Complexity change: "
                            f"{snap.complexity} -> {new_complexity}"
                        ),
                    ))

        # Calculate impact level
        affected_count = len(affected_details)
        total_count = len(records)
        impact_level = self._calculate_impact_level(
            affected_count, total_count, orphaned,
        )

        # Identify risk factors
        risk_factors = self._identify_risk_factors(
            orphaned, complexity_mismatches, changes,
        )

        safe = (
            impact_level not in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)
            and orphaned < 10
            and len(risk_factors) < 3
        )

        return NeedSimulationResult(
            simulation_id=simulation_id,
            created_at=now,
            changes=tuple(changes),
            total_needs_analyzed=total_count,
            affected_needs=affected_count,
            affected_need_details=tuple(affected_details),
            impact_level=impact_level,
            orphaned_needs=orphaned,
            complexity_mismatches=complexity_mismatches,
            risk_factors=tuple(risk_factors),
            safe_to_apply=safe,
        )

    def simulate_stakeholder_removal(
        self,
        stakeholder_id: str,
        limit: int = 1000,
    ) -> NeedSimulationResult:
        """단일 이해관계자 제거 시뮬레이션."""
        change = NeedChange(
            change_type=NeedChangeType.REMOVE_STAKEHOLDER,
            target_value=stakeholder_id,
        )
        return self.simulate([change], limit)

    def _calculate_impact_level(
        self,
        affected_count: int,
        total_count: int,
        orphaned: int,
    ) -> ImpactLevel:
        if total_count == 0:
            return ImpactLevel.NONE

        change_rate = affected_count / total_count

        if orphaned > 20 or change_rate > 0.5:
            return ImpactLevel.CRITICAL
        if orphaned > 10 or change_rate > 0.3:
            return ImpactLevel.HIGH
        if orphaned > 5 or change_rate > 0.1:
            return ImpactLevel.MEDIUM
        if affected_count > 0:
            return ImpactLevel.LOW

        return ImpactLevel.NONE

    def _identify_risk_factors(
        self,
        orphaned: int,
        complexity_mismatches: int,
        changes: list[NeedChange],
    ) -> list[str]:
        factors: list[str] = []

        if orphaned > 5:
            factors.append(
                f"High number of orphaned needs: {orphaned}"
            )

        if complexity_mismatches > 10:
            factors.append(
                f"Many complexity mismatches: {complexity_mismatches}"
            )

        removals = sum(
            1 for c in changes
            if c.change_type == NeedChangeType.REMOVE_STAKEHOLDER
        )
        if removals > 3:
            factors.append(
                f"Removing multiple stakeholders ({removals}) increases risk"
            )

        return factors
