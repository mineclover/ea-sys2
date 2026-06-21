"""Tests for ScenarioAnalyzer — S4 Analysis for Scenario Flows."""

from __future__ import annotations

import pytest

from ea_needs.scenario_analyzer import (
    KernelRefCoverage,
    ScenarioAnalyzer,
)
from ea_needs.scenario_store import (
    InMemoryScenarioStore,
    StoredScenarioSnapshot,
)


def _make_snapshot(
    scenario_id: str = "sc-001",
    use_case_id: str = "uc-001",
    scenario_type: str = "main",
    step_count: int = 3,
    kernel_ref_count: int = 2,
    version: int = 1,
) -> StoredScenarioSnapshot:
    return StoredScenarioSnapshot(
        storage_id="",
        scenario_id=scenario_id,
        use_case_id=use_case_id,
        scenario_type=scenario_type,
        step_count=step_count,
        kernel_ref_count=kernel_ref_count,
        version=version,
        stored_at="",
    )


class TestScenarioAnalyzer:
    """Tests for ScenarioAnalyzer."""

    def test_analyze_coverage_with_main(self) -> None:
        """AC-25: Coverage analysis with MAIN scenario present."""
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-main", scenario_type="main", step_count=3, kernel_ref_count=2))
        store.store(_make_snapshot(scenario_id="sc-alt", scenario_type="alternative", step_count=2, kernel_ref_count=1))
        store.store(_make_snapshot(scenario_id="sc-exc", scenario_type="exception", step_count=1, kernel_ref_count=0))

        analyzer = ScenarioAnalyzer(store)
        coverage = analyzer.analyze_coverage()

        assert len(coverage) == 1
        cov = coverage[0]
        assert cov.use_case_id == "uc-001"
        assert cov.total_scenarios == 3
        assert cov.main_count == 1
        assert cov.alternative_count == 1
        assert cov.exception_count == 1
        assert cov.total_steps == 6
        assert cov.kernel_grounded_steps == 3

    def test_analyze_coverage_without_main(self) -> None:
        """AC-25: Coverage analysis without MAIN scenario."""
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-alt", scenario_type="alternative"))

        analyzer = ScenarioAnalyzer(store)
        coverage = analyzer.analyze_coverage()

        assert len(coverage) == 1
        assert coverage[0].main_count == 0

    def test_analyze_coverage_multiple_use_cases(self) -> None:
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(use_case_id="uc-001", scenario_id="sc-001"))
        store.store(_make_snapshot(use_case_id="uc-002", scenario_id="sc-002"))
        store.store(_make_snapshot(use_case_id="uc-002", scenario_id="sc-003", scenario_type="alternative"))

        analyzer = ScenarioAnalyzer(store)
        coverage = analyzer.analyze_coverage()

        assert len(coverage) == 2
        # Sorted by total_scenarios descending
        assert coverage[0].use_case_id == "uc-002"
        assert coverage[0].total_scenarios == 2
        assert coverage[1].use_case_id == "uc-001"
        assert coverage[1].total_scenarios == 1

    def test_kernel_ref_coverage_rate(self) -> None:
        """Test kernel_ref_coverage rate calculation."""
        cov = KernelRefCoverage(total_steps=10, grounded_steps=8)
        assert cov.coverage_rate == 0.8

    def test_kernel_ref_coverage_rate_zero_steps(self) -> None:
        cov = KernelRefCoverage(total_steps=0, grounded_steps=0)
        assert cov.coverage_rate == 0.0

    def test_generate_report_aggregation(self) -> None:
        """Test generate_report aggregation."""
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(use_case_id="uc-001", scenario_id="sc-main", scenario_type="main", step_count=4, kernel_ref_count=3))
        store.store(_make_snapshot(use_case_id="uc-001", scenario_id="sc-alt", scenario_type="alternative", step_count=2, kernel_ref_count=1))
        store.store(_make_snapshot(use_case_id="uc-002", scenario_id="sc-alt2", scenario_type="alternative", step_count=3, kernel_ref_count=0))

        analyzer = ScenarioAnalyzer(store)
        report = analyzer.generate_report()

        assert report.report_id.startswith("scenario-report-")
        assert report.created_at != ""
        assert report.total_scenarios_analyzed == 3
        assert len(report.use_case_coverage) == 2
        assert report.kernel_ref_coverage.total_steps == 9
        assert report.kernel_ref_coverage.grounded_steps == 4
        assert report.kernel_ref_coverage.coverage_rate == pytest.approx(4 / 9)

        # uc-002 has no main scenario
        assert "uc-002" in report.use_cases_without_main
        assert "uc-001" not in report.use_cases_without_main

    def test_generate_report_empty_store(self) -> None:
        store = InMemoryScenarioStore()
        analyzer = ScenarioAnalyzer(store)
        report = analyzer.generate_report()

        assert report.total_scenarios_analyzed == 0
        assert len(report.use_case_coverage) == 0
        assert report.kernel_ref_coverage.coverage_rate == 0.0
        assert len(report.use_cases_without_main) == 0

    def test_generate_report_custom_id(self) -> None:
        store = InMemoryScenarioStore()
        analyzer = ScenarioAnalyzer(store)
        report = analyzer.generate_report(report_id="custom-report-id")
        assert report.report_id == "custom-report-id"
