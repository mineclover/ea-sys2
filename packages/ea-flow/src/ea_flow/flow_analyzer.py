"""Flow Analyzer — S4 Analysis for Flow Layer.

Analyzes accumulated execution records to extract step effectiveness,
bottleneck detection, and throughput insights.
Provides:
- StepEffectivenessGrade: 스텝 실효성 등급
- StepEffectiveness: 스텝별 success_rate, rollback_trigger_rate
- BottleneckHotspot: 반복 실패 스텝 + downstream_impact
- FlowAnalysisReport: 종합 분석 보고서

References:
- ea_kernel/evidence_analyzer.py: S4 분석 패턴
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
# StepEffectiveness — 스텝별 실효성 측정
# ═══════════════════════════════════════════════════════════════════════════════

class StepEffectivenessGrade(StrEnum):
    """스텝 실효성 등급."""
    HIGHLY_RELIABLE = "highly_reliable"
    RELIABLE = "reliable"
    FRAGILE = "fragile"
    BROKEN = "broken"
    UNUSED = "unused"


@dataclass(frozen=True)
class StepEffectiveness:
    """스텝별 실효성 측정."""
    step_name: str
    kernel_anchor: str = ""

    # Execution metrics
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Impact metrics
    rollback_trigger_count: int = 0

    # Time-based
    first_seen_at: str = ""
    last_seen_at: str = ""

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.success_count / self.total_executions

    @property
    def failure_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.failure_count / self.total_executions

    @property
    def rollback_trigger_rate(self) -> float:
        """How often this step causes a workflow rollback."""
        if self.total_executions == 0:
            return 0.0
        return self.rollback_trigger_count / self.total_executions

    @property
    def grade(self) -> StepEffectivenessGrade:
        if self.total_executions == 0:
            return StepEffectivenessGrade.UNUSED

        if self.success_rate > 0.95:
            return StepEffectivenessGrade.HIGHLY_RELIABLE

        if self.success_rate > 0.7:
            return StepEffectivenessGrade.RELIABLE

        if self.success_rate > 0.3:
            return StepEffectivenessGrade.FRAGILE

        return StepEffectivenessGrade.BROKEN


# ═══════════════════════════════════════════════════════════════════════════════
# BottleneckHotspot — 반복 실패 스텝 탐지
# ═══════════════════════════════════════════════════════════════════════════════

class BottleneckSeverity(StrEnum):
    """병목 심각도."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class BottleneckHotspot:
    """반복 실패 스텝 + downstream 영향."""
    step_name: str
    workflow_name: str

    # Failure metrics
    failure_count: int = 0
    rollback_trigger_count: int = 0

    # Downstream impact
    downstream_steps_blocked: int = 0

    # Time-based
    first_failure_at: str = ""
    last_failure_at: str = ""

    @property
    def severity(self) -> BottleneckSeverity:
        if self.failure_count >= 10 or self.rollback_trigger_count >= 5:
            return BottleneckSeverity.CRITICAL
        if self.failure_count >= 5 or self.rollback_trigger_count >= 3:
            return BottleneckSeverity.HIGH
        if self.failure_count >= 2:
            return BottleneckSeverity.MEDIUM
        return BottleneckSeverity.LOW


# ═══════════════════════════════════════════════════════════════════════════════
# FlowAnalysisReport — S4 종합 산출물
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FlowAnalysisReport:
    """S4 종합 분석 보고서."""
    report_id: str
    created_at: str

    # Summary
    total_executions_analyzed: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Component reports
    step_effectiveness: tuple[StepEffectiveness, ...] = ()
    bottleneck_hotspots: tuple[BottleneckHotspot, ...] = ()

    # Aggregate insights
    broken_steps: tuple[str, ...] = ()
    fragile_steps: tuple[str, ...] = ()
    unused_steps: tuple[str, ...] = ()

    @property
    def health_score(self) -> float:
        """Overall flow health score (0-100)."""
        if not self.step_effectiveness:
            return 0.0

        total_steps = len(self.step_effectiveness)
        broken_count = len(self.broken_steps)
        fragile_count = len(self.fragile_steps)

        problem_count = broken_count + fragile_count * 0.5
        healthy_ratio = 1 - (problem_count / total_steps) if total_steps > 0 else 0

        # Factor in bottleneck severity
        critical_hotspots = len([
            h for h in self.bottleneck_hotspots
            if h.severity in (BottleneckSeverity.CRITICAL, BottleneckSeverity.HIGH)
        ])
        bottleneck_penalty = min(0.3, critical_hotspots * 0.05)

        return max(0.0, min(100.0, (healthy_ratio - bottleneck_penalty) * 100))


# ═══════════════════════════════════════════════════════════════════════════════
# FlowAnalyzer — 분석 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class FlowAnalyzer:
    """플로 분석 엔진.

    ExecutionStore의 실행 이력을 분석하여 인사이트 추출.
    """

    __slots__ = ("_execution_store",)

    def __init__(self, execution_store: ExecutionStore) -> None:
        self._execution_store = execution_store

    def analyze_step_effectiveness(self) -> tuple[StepEffectiveness, ...]:
        """Analyze effectiveness of all steps across workflows."""
        records = self._execution_store.query()

        step_data: dict[str, dict] = {}

        for rec in records:
            for sr in rec.step_results:
                name = sr.step_name
                if name not in step_data:
                    step_data[name] = {
                        "kernel_anchor": sr.kernel_anchor,
                        "total": 0,
                        "success": 0,
                        "failure": 0,
                        "rollback_trigger": 0,
                        "first_seen_at": rec.executed_at,
                        "last_seen_at": rec.executed_at,
                    }

                data = step_data[name]
                data["total"] += 1
                data["last_seen_at"] = max(data["last_seen_at"], rec.executed_at)
                data["first_seen_at"] = min(data["first_seen_at"], rec.executed_at)

                if sr.accepted:
                    data["success"] += 1
                else:
                    data["failure"] += 1
                    # If this step caused the workflow failure
                    if rec.failed_step == name and rec.rollback_occurred:
                        data["rollback_trigger"] += 1

        results: list[StepEffectiveness] = []
        for name, data in step_data.items():
            results.append(StepEffectiveness(
                step_name=name,
                kernel_anchor=data["kernel_anchor"],
                total_executions=data["total"],
                success_count=data["success"],
                failure_count=data["failure"],
                rollback_trigger_count=data["rollback_trigger"],
                first_seen_at=data["first_seen_at"],
                last_seen_at=data["last_seen_at"],
            ))

        return tuple(sorted(results, key=lambda r: -r.total_executions))

    def detect_bottleneck_hotspots(
        self,
        min_failures: int = 2,
    ) -> tuple[BottleneckHotspot, ...]:
        """Detect steps with repeated failures that block downstream execution."""
        records = self._execution_store.query()

        hotspot_data: dict[tuple[str, str], dict] = {}

        for rec in records:
            if not rec.failed_step:
                continue

            key = (rec.failed_step, rec.workflow_name)
            if key not in hotspot_data:
                hotspot_data[key] = {
                    "failure_count": 0,
                    "rollback_trigger_count": 0,
                    "first_failure_at": rec.executed_at,
                    "last_failure_at": rec.executed_at,
                    "downstream_blocked": 0,
                }

            data = hotspot_data[key]
            data["failure_count"] += 1
            data["last_failure_at"] = max(data["last_failure_at"], rec.executed_at)
            data["first_failure_at"] = min(data["first_failure_at"], rec.executed_at)

            if rec.rollback_occurred:
                data["rollback_trigger_count"] += 1

            # Downstream impact: steps that didn't get to run
            data["downstream_blocked"] = max(
                data["downstream_blocked"],
                rec.total_steps - rec.completed_steps - 1,
            )

        results: list[BottleneckHotspot] = []
        for (step_name, wf_name), data in hotspot_data.items():
            if data["failure_count"] >= min_failures:
                results.append(BottleneckHotspot(
                    step_name=step_name,
                    workflow_name=wf_name,
                    failure_count=data["failure_count"],
                    rollback_trigger_count=data["rollback_trigger_count"],
                    downstream_steps_blocked=data["downstream_blocked"],
                    first_failure_at=data["first_failure_at"],
                    last_failure_at=data["last_failure_at"],
                ))

        return tuple(sorted(results, key=lambda h: -h.failure_count))

    def generate_report(
        self,
        report_id: str | None = None,
    ) -> FlowAnalysisReport:
        """Generate comprehensive analysis report."""
        if report_id is None:
            report_id = f"flow-report-{uuid.uuid4().hex[:8]}"

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        effectiveness = self.analyze_step_effectiveness()
        hotspots = self.detect_bottleneck_hotspots(min_failures=2)

        # Compute aggregate insights
        broken = tuple(
            s.step_name for s in effectiveness
            if s.grade == StepEffectivenessGrade.BROKEN
        )
        fragile = tuple(
            s.step_name for s in effectiveness
            if s.grade == StepEffectivenessGrade.FRAGILE
        )
        unused = tuple(
            s.step_name for s in effectiveness
            if s.grade == StepEffectivenessGrade.UNUSED
        )

        # Get time range
        all_records = self._execution_store.query()
        period_start = ""
        period_end = ""
        if all_records:
            timestamps = [r.executed_at for r in all_records]
            period_start = min(timestamps)
            period_end = max(timestamps)

        return FlowAnalysisReport(
            report_id=report_id,
            created_at=now,
            total_executions_analyzed=len(all_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            step_effectiveness=effectiveness,
            bottleneck_hotspots=hotspots,
            broken_steps=broken,
            fragile_steps=fragile,
            unused_steps=unused,
        )
