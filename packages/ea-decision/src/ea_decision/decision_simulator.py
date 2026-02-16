"""Decision Simulator — S5 Evolution What-If for Decision Layer.

Simulates the impact of pattern changes (add/remove/modify) on past decisions.
Provides:
- PatternChangeType: 변경 유형
- PatternChange: 시뮬레이션할 변경 사항
- PatternSimulationResult: 시뮬레이션 결과
- DecisionSimulator: 시뮬레이션 엔진

References:
- ea_kernel/what_if_simulator.py: S5 시뮬레이션 패턴
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_decision.topic_store import TopicStore


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Change Types
# ═══════════════════════════════════════════════════════════════════════════════

class PatternChangeType(StrEnum):
    """시뮬레이션할 변경 유형."""
    ADD_PATTERN = "add_pattern"
    REMOVE_PATTERN = "remove_pattern"
    MODIFY_COMPLEXITY = "modify_complexity"


@dataclass(frozen=True)
class PatternChange:
    """시뮬레이션할 변경 사항."""
    change_type: PatternChangeType
    pattern_name: str
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
class AffectedDecision:
    """영향 받는 의사결정."""
    topic_id: str
    pattern_name: str
    original_status: str
    impact_description: str


@dataclass(frozen=True)
class PatternSimulationResult:
    """패턴 변경 시뮬레이션 결과."""
    simulation_id: str
    created_at: str

    # Changes applied
    changes: tuple[PatternChange, ...]

    # Analysis
    total_decisions_analyzed: int = 0
    affected_decisions: int = 0
    affected_decision_details: tuple[AffectedDecision, ...] = ()

    # Impact assessment
    impact_level: ImpactLevel = ImpactLevel.NONE

    # Summary
    orphaned_decisions: int = 0
    complexity_mismatches: int = 0

    # Recommendations
    risk_factors: tuple[str, ...] = ()
    safe_to_apply: bool = True

    @property
    def change_rate(self) -> float:
        if self.total_decisions_analyzed == 0:
            return 0.0
        return self.affected_decisions / self.total_decisions_analyzed


# ═══════════════════════════════════════════════════════════════════════════════
# Decision Simulator
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionSimulator:
    """패턴 변경 영향 시뮬레이터.

    과거 의사결정 이력에 패턴 변경을 적용했을 때 결과가 어떻게 달라지는지 시뮬레이션.
    """

    __slots__ = ("_topic_store",)

    def __init__(self, topic_store: TopicStore) -> None:
        self._topic_store = topic_store

    def simulate(
        self,
        changes: list[PatternChange],
        limit: int = 1000,
    ) -> PatternSimulationResult:
        """패턴 변경 시뮬레이션.

        Args:
            changes: 시뮬레이션할 변경 목록
            limit: 분석할 최대 의사결정 수

        Returns:
            PatternSimulationResult with impact analysis
        """
        from ea_decision.topic_store import DecisionQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        simulation_id = f"sim-{uuid.uuid4().hex[:8]}"

        options = DecisionQueryOptions(limit=limit)
        records = self._topic_store.query(options)

        # Build change maps
        removed_patterns: set[str] = {
            c.pattern_name for c in changes
            if c.change_type == PatternChangeType.REMOVE_PATTERN
        }
        complexity_changes: dict[str, str] = {
            c.pattern_name: c.new_complexity
            for c in changes
            if c.change_type == PatternChangeType.MODIFY_COMPLEXITY
        }

        # Analyze each decision
        affected_details: list[AffectedDecision] = []
        orphaned = 0
        complexity_mismatches = 0

        for snap in records:
            # Check if pattern is being removed
            if snap.pattern_name in removed_patterns:
                orphaned += 1
                affected_details.append(AffectedDecision(
                    topic_id=snap.topic_id,
                    pattern_name=snap.pattern_name,
                    original_status=snap.status.value,
                    impact_description=(
                        f"Decision would lose pattern '{snap.pattern_name}'"
                    ),
                ))
                continue

            # Check if complexity is changing
            if snap.pattern_name in complexity_changes:
                new_complexity = complexity_changes[snap.pattern_name]
                if snap.complexity != new_complexity:
                    complexity_mismatches += 1
                    affected_details.append(AffectedDecision(
                        topic_id=snap.topic_id,
                        pattern_name=snap.pattern_name,
                        original_status=snap.status.value,
                        impact_description=(
                            f"Complexity change: {snap.complexity} -> {new_complexity}"
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

        return PatternSimulationResult(
            simulation_id=simulation_id,
            created_at=now,
            changes=tuple(changes),
            total_decisions_analyzed=total_count,
            affected_decisions=affected_count,
            affected_decision_details=tuple(affected_details),
            impact_level=impact_level,
            orphaned_decisions=orphaned,
            complexity_mismatches=complexity_mismatches,
            risk_factors=tuple(risk_factors),
            safe_to_apply=safe,
        )

    def simulate_pattern_removal(
        self,
        pattern_name: str,
        limit: int = 1000,
    ) -> PatternSimulationResult:
        """단일 패턴 제거 시뮬레이션."""
        change = PatternChange(
            change_type=PatternChangeType.REMOVE_PATTERN,
            pattern_name=pattern_name,
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
        changes: list[PatternChange],
    ) -> list[str]:
        factors: list[str] = []

        if orphaned > 5:
            factors.append(
                f"High number of orphaned decisions: {orphaned}"
            )

        if complexity_mismatches > 10:
            factors.append(
                f"Many complexity mismatches: {complexity_mismatches}"
            )

        removals = sum(
            1 for c in changes
            if c.change_type == PatternChangeType.REMOVE_PATTERN
        )
        if removals > 3:
            factors.append(
                f"Removing multiple patterns ({removals}) increases risk"
            )

        return factors
