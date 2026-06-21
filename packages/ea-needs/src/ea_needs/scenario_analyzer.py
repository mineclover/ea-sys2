"""Scenario Analyzer — S4 Analysis for Scenario Flows.

Analyzes accumulated scenario snapshots to extract use-case coverage,
kernel-ref grounding rates, and scenario completeness insights.

Provides:
- ScenarioCoverage: Per-use-case scenario coverage metrics
- KernelRefCoverage: Kernel reference grounding rate
- ScenarioAnalysisReport: Comprehensive analysis report
- ScenarioAnalyzer: Analysis engine

References:
- ea_needs/needs_analyzer.py: S4 analysis pattern
- ea_needs/scenario_store.py: S3 storage pattern
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_needs.scenario_store import ScenarioStore


# ═══════════════════════════════════════════════════════════════════════════════
# ScenarioCoverage — Per-use-case coverage metrics
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ScenarioCoverage:
    """Per-use-case scenario coverage metrics."""
    use_case_id: str
    total_scenarios: int
    main_count: int
    alternative_count: int
    exception_count: int
    total_steps: int
    kernel_grounded_steps: int


# ═══════════════════════════════════════════════════════════════════════════════
# KernelRefCoverage — Kernel reference grounding rate
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class KernelRefCoverage:
    """Aggregate kernel reference grounding rate."""
    total_steps: int
    grounded_steps: int

    @property
    def coverage_rate(self) -> float:
        if self.total_steps == 0:
            return 0.0
        return self.grounded_steps / self.total_steps


# ═══════════════════════════════════════════════════════════════════════════════
# ScenarioAnalysisReport — S4 comprehensive report
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ScenarioAnalysisReport:
    """S4 comprehensive analysis report for scenario flows."""
    report_id: str
    created_at: str
    total_scenarios_analyzed: int
    use_case_coverage: tuple[ScenarioCoverage, ...]
    kernel_ref_coverage: KernelRefCoverage
    use_cases_without_main: tuple[str, ...]


# ═══════════════════════════════════════════════════════════════════════════════
# ScenarioAnalyzer — Analysis engine
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioAnalyzer:
    """Scenario analysis engine.

    Analyzes ScenarioStore snapshots to extract coverage insights.
    """

    __slots__ = ("_scenario_store",)

    def __init__(self, scenario_store: ScenarioStore) -> None:
        self._scenario_store = scenario_store

    def analyze_coverage(self) -> tuple[ScenarioCoverage, ...]:
        """Analyze scenario coverage per use case."""
        records = self._scenario_store.query()

        uc_data: dict[str, dict] = {}

        for snap in records:
            uid = snap.use_case_id
            if uid not in uc_data:
                uc_data[uid] = {
                    "total": 0,
                    "main": 0,
                    "alternative": 0,
                    "exception": 0,
                    "total_steps": 0,
                    "kernel_grounded_steps": 0,
                }

            data = uc_data[uid]
            data["total"] += 1
            data["total_steps"] += snap.step_count
            data["kernel_grounded_steps"] += snap.kernel_ref_count

            if snap.scenario_type == "main":
                data["main"] += 1
            elif snap.scenario_type == "alternative":
                data["alternative"] += 1
            elif snap.scenario_type == "exception":
                data["exception"] += 1

        results: list[ScenarioCoverage] = []
        for uid, data in uc_data.items():
            results.append(ScenarioCoverage(
                use_case_id=uid,
                total_scenarios=data["total"],
                main_count=data["main"],
                alternative_count=data["alternative"],
                exception_count=data["exception"],
                total_steps=data["total_steps"],
                kernel_grounded_steps=data["kernel_grounded_steps"],
            ))

        return tuple(sorted(results, key=lambda r: -r.total_scenarios))

    def generate_report(
        self,
        report_id: str | None = None,
    ) -> ScenarioAnalysisReport:
        """Generate comprehensive scenario analysis report."""
        if report_id is None:
            report_id = f"scenario-report-{uuid.uuid4().hex[:8]}"

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        coverage = self.analyze_coverage()

        # Aggregate kernel ref coverage
        total_steps = sum(c.total_steps for c in coverage)
        grounded_steps = sum(c.kernel_grounded_steps for c in coverage)
        kernel_ref_coverage = KernelRefCoverage(
            total_steps=total_steps,
            grounded_steps=grounded_steps,
        )

        # Identify use cases without a MAIN scenario
        use_cases_without_main = tuple(
            c.use_case_id for c in coverage if c.main_count == 0
        )

        # Total scenarios analyzed
        total_scenarios = sum(c.total_scenarios for c in coverage)

        return ScenarioAnalysisReport(
            report_id=report_id,
            created_at=now,
            total_scenarios_analyzed=total_scenarios,
            use_case_coverage=coverage,
            kernel_ref_coverage=kernel_ref_coverage,
            use_cases_without_main=use_cases_without_main,
        )
