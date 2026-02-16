"""Flow Simulator — S5 Evolution What-If for Flow Layer.

Simulates the impact of topology changes (step add/remove/reorder) on past executions.
Provides:
- TopologyChangeType: 변경 유형
- TopologyChange: 시뮬레이션할 변경 사항
- TopologySimulationResult: 시뮬레이션 결과
- FlowSimulator: 시뮬레이션 엔진

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
    from ea_flow.execution_store import ExecutionStore


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Change Types
# ═══════════════════════════════════════════════════════════════════════════════

class TopologyChangeType(StrEnum):
    """시뮬레이션할 변경 유형."""
    ADD_STEP = "add_step"
    REMOVE_STEP = "remove_step"
    REORDER_STEP = "reorder_step"


@dataclass(frozen=True)
class TopologyChange:
    """시뮬레이션할 변경 사항."""
    change_type: TopologyChangeType
    step_name: str
    workflow_name: str = ""
    new_position: int = -1  # For REORDER_STEP


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
class AffectedExecution:
    """영향 받는 실행 기록."""
    execution_id: str
    workflow_name: str
    original_success: bool
    impact_description: str


@dataclass(frozen=True)
class TopologySimulationResult:
    """토폴로지 변경 시뮬레이션 결과."""
    simulation_id: str
    created_at: str

    # Changes applied
    changes: tuple[TopologyChange, ...]

    # Analysis
    total_executions_analyzed: int = 0
    affected_executions: int = 0
    affected_execution_details: tuple[AffectedExecution, ...] = ()

    # Impact assessment
    impact_level: ImpactLevel = ImpactLevel.NONE

    # Summary
    broken_workflows: int = 0
    step_dependency_violations: int = 0

    # Recommendations
    risk_factors: tuple[str, ...] = ()
    safe_to_apply: bool = True

    @property
    def change_rate(self) -> float:
        if self.total_executions_analyzed == 0:
            return 0.0
        return self.affected_executions / self.total_executions_analyzed


# ═══════════════════════════════════════════════════════════════════════════════
# Flow Simulator
# ═══════════════════════════════════════════════════════════════════════════════

class FlowSimulator:
    """토폴로지 변경 영향 시뮬레이터.

    과거 실행 이력에 토폴로지 변경을 적용했을 때 결과가 어떻게 달라지는지 시뮬레이션.
    """

    __slots__ = ("_execution_store",)

    def __init__(self, execution_store: ExecutionStore) -> None:
        self._execution_store = execution_store

    def simulate(
        self,
        changes: list[TopologyChange],
        limit: int = 1000,
    ) -> TopologySimulationResult:
        """토폴로지 변경 시뮬레이션.

        Args:
            changes: 시뮬레이션할 변경 목록
            limit: 분석할 최대 실행 수

        Returns:
            TopologySimulationResult with impact analysis
        """
        from ea_flow.execution_store import ExecutionQueryOptions

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        simulation_id = f"sim-{uuid.uuid4().hex[:8]}"

        options = ExecutionQueryOptions(limit=limit)
        records = self._execution_store.query(options)

        # Build change maps
        removed_steps: dict[str, set[str]] = {}
        for c in changes:
            if c.change_type == TopologyChangeType.REMOVE_STEP:
                removed_steps.setdefault(c.workflow_name, set()).add(c.step_name)

        reordered_steps: dict[str, list[TopologyChange]] = {}
        for c in changes:
            if c.change_type == TopologyChangeType.REORDER_STEP:
                reordered_steps.setdefault(c.workflow_name, []).append(c)

        # Analyze each execution
        affected_details: list[AffectedExecution] = []
        broken_wfs: set[str] = set()
        dependency_violations = 0

        for rec in records:
            step_names = {sr.step_name for sr in rec.step_results}

            # Check removed steps
            wf_removed = removed_steps.get(rec.workflow_name, set())
            # Also check steps removed without workflow scope
            global_removed = removed_steps.get("", set())
            all_removed = wf_removed | global_removed

            affected_steps = step_names & all_removed
            if affected_steps:
                for step in affected_steps:
                    # Check if removing this step would break a successful workflow
                    was_accepted = any(
                        sr.accepted for sr in rec.step_results
                        if sr.step_name == step
                    )
                    if was_accepted and rec.success:
                        broken_wfs.add(rec.workflow_name)

                affected_details.append(AffectedExecution(
                    execution_id=rec.execution_id or rec.storage_id,
                    workflow_name=rec.workflow_name,
                    original_success=rec.success,
                    impact_description=(
                        f"Steps removed: {', '.join(sorted(affected_steps))}"
                    ),
                ))
                continue

            # Check reordered steps
            wf_reordered = reordered_steps.get(rec.workflow_name, [])
            if wf_reordered:
                reordered_names = {c.step_name for c in wf_reordered}
                if step_names & reordered_names:
                    dependency_violations += 1
                    affected_details.append(AffectedExecution(
                        execution_id=rec.execution_id or rec.storage_id,
                        workflow_name=rec.workflow_name,
                        original_success=rec.success,
                        impact_description=(
                            f"Step order changed for: "
                            f"{', '.join(sorted(step_names & reordered_names))}"
                        ),
                    ))

        # Calculate impact level
        affected_count = len(affected_details)
        total_count = len(records)
        impact_level = self._calculate_impact_level(
            affected_count, total_count, len(broken_wfs),
        )

        # Identify risk factors
        risk_factors = self._identify_risk_factors(
            len(broken_wfs), dependency_violations, changes,
        )

        safe = (
            impact_level not in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)
            and len(broken_wfs) < 5
            and len(risk_factors) < 3
        )

        return TopologySimulationResult(
            simulation_id=simulation_id,
            created_at=now,
            changes=tuple(changes),
            total_executions_analyzed=total_count,
            affected_executions=affected_count,
            affected_execution_details=tuple(affected_details),
            impact_level=impact_level,
            broken_workflows=len(broken_wfs),
            step_dependency_violations=dependency_violations,
            risk_factors=tuple(risk_factors),
            safe_to_apply=safe,
        )

    def simulate_step_removal(
        self,
        step_name: str,
        workflow_name: str = "",
        limit: int = 1000,
    ) -> TopologySimulationResult:
        """단일 스텝 제거 시뮬레이션."""
        change = TopologyChange(
            change_type=TopologyChangeType.REMOVE_STEP,
            step_name=step_name,
            workflow_name=workflow_name,
        )
        return self.simulate([change], limit)

    def _calculate_impact_level(
        self,
        affected_count: int,
        total_count: int,
        broken_workflows: int,
    ) -> ImpactLevel:
        if total_count == 0:
            return ImpactLevel.NONE

        change_rate = affected_count / total_count

        if broken_workflows > 5 or change_rate > 0.5:
            return ImpactLevel.CRITICAL
        if broken_workflows > 2 or change_rate > 0.3:
            return ImpactLevel.HIGH
        if broken_workflows > 0 or change_rate > 0.1:
            return ImpactLevel.MEDIUM
        if affected_count > 0:
            return ImpactLevel.LOW

        return ImpactLevel.NONE

    def _identify_risk_factors(
        self,
        broken_workflows: int,
        dependency_violations: int,
        changes: list[TopologyChange],
    ) -> list[str]:
        factors: list[str] = []

        if broken_workflows > 2:
            factors.append(
                f"Would break {broken_workflows} previously successful workflows"
            )

        if dependency_violations > 5:
            factors.append(
                f"Many step dependency violations: {dependency_violations}"
            )

        removals = sum(
            1 for c in changes
            if c.change_type == TopologyChangeType.REMOVE_STEP
        )
        if removals > 3:
            factors.append(
                f"Removing multiple steps ({removals}) increases risk"
            )

        return factors
