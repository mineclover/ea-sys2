"""Tests for NeedsAnalyzer — S4 Analysis."""

from __future__ import annotations

import pytest

from ea_needs.needs_analyzer import (
    NeedsAnalysisReport,
    NeedsAnalyzer,
    PriorityDistribution,
    StakeholderCoverage,
    StakeholderCoverageGrade,
)
from ea_needs.needs_store import (
    InMemoryNeedStore,
    NeedSnapshotStatus,
    StoredNeedSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    need_id: str = "need-1",
    stakeholder_id: str = "sh-cto",
    status: NeedSnapshotStatus = NeedSnapshotStatus.ADDRESSED,
    priority: str = "high",
    complexity: str = "procedural",
    expressed_at: str = "2025-01-15T10:00:00Z",
    justification_count: int = 2,
    kernel_ref_count: int = 1,
) -> StoredNeedSnapshot:
    return StoredNeedSnapshot(
        storage_id="",
        need_id=need_id,
        lineage_id=need_id,
        stakeholder_id=stakeholder_id,
        status=status,
        priority=priority,
        complexity=complexity,
        expressed_at=expressed_at,
        justification_count=justification_count,
        kernel_ref_count=kernel_ref_count,
    )


def _populated_store() -> InMemoryNeedStore:
    store = InMemoryNeedStore()
    # CTO: 8 needs (6 addressed, 1 withdrawn, 1 expressed)
    for i in range(6):
        store.store(_make_snapshot(
            need_id=f"cto-addr-{i}", stakeholder_id="sh-cto",
            status=NeedSnapshotStatus.ADDRESSED,
            priority="high", justification_count=3,
            kernel_ref_count=2,
            expressed_at=f"2025-01-{10 + i:02d}T00:00:00Z",
        ))
    store.store(_make_snapshot(
        need_id="cto-with", stakeholder_id="sh-cto",
        status=NeedSnapshotStatus.WITHDRAWN,
        priority="low", justification_count=1,
        expressed_at="2025-01-17T00:00:00Z",
    ))
    store.store(_make_snapshot(
        need_id="cto-expr", stakeholder_id="sh-cto",
        status=NeedSnapshotStatus.EXPRESSED,
        priority="medium", justification_count=2,
        expressed_at="2025-01-18T00:00:00Z",
    ))

    # Dev: 3 needs (1 addressed, 2 draft)
    store.store(_make_snapshot(
        need_id="dev-addr", stakeholder_id="sh-dev",
        status=NeedSnapshotStatus.ADDRESSED,
        priority="medium", justification_count=1,
        expressed_at="2025-02-01T00:00:00Z",
    ))
    for i in range(2):
        store.store(_make_snapshot(
            need_id=f"dev-draft-{i}", stakeholder_id="sh-dev",
            status=NeedSnapshotStatus.DRAFT,
            priority="low", justification_count=0,
            expressed_at=f"2025-02-{10 + i:02d}T00:00:00Z",
        ))

    # QA: 2 needs (2 withdrawn)
    for i in range(2):
        store.store(_make_snapshot(
            need_id=f"qa-with-{i}", stakeholder_id="sh-qa",
            status=NeedSnapshotStatus.WITHDRAWN,
            priority="low", justification_count=0,
            expressed_at=f"2025-03-{10 + i:02d}T00:00:00Z",
        ))

    return store


# ── StakeholderCoverage Grade Tests ─────────────────────────────────────

class TestStakeholderCoverageGrade:
    def test_well_covered(self):
        cov = StakeholderCoverage(
            stakeholder_id="sh-1",
            total_needs=10,
            addressed_count=8,
            withdrawn_count=0,
            expressed_count=2,
        )
        assert cov.grade == StakeholderCoverageGrade.WELL_COVERED

    def test_covered(self):
        cov = StakeholderCoverage(
            stakeholder_id="sh-1",
            total_needs=10,
            addressed_count=5,
            withdrawn_count=2,
            expressed_count=3,
        )
        assert cov.grade == StakeholderCoverageGrade.COVERED

    def test_partially_covered(self):
        cov = StakeholderCoverage(
            stakeholder_id="sh-1",
            total_needs=10,
            addressed_count=1,
            withdrawn_count=4,
            expressed_count=3,
            acknowledged_count=1,
            draft_count=1,
        )
        assert cov.grade == StakeholderCoverageGrade.PARTIALLY_COVERED

    def test_underserved(self):
        cov = StakeholderCoverage(
            stakeholder_id="sh-1",
            total_needs=10,
            addressed_count=0,
            withdrawn_count=8,
            draft_count=2,
        )
        assert cov.grade == StakeholderCoverageGrade.UNDERSERVED

    def test_unserved(self):
        cov = StakeholderCoverage(stakeholder_id="sh-1", total_needs=0)
        assert cov.grade == StakeholderCoverageGrade.UNSERVED

    def test_rates(self):
        cov = StakeholderCoverage(
            stakeholder_id="sh-1",
            total_needs=10,
            addressed_count=4,
            withdrawn_count=2,
            expressed_count=2,
            acknowledged_count=1,
            draft_count=1,
        )
        assert cov.addressed_rate == pytest.approx(0.4)
        assert cov.withdrawn_rate == pytest.approx(0.2)
        assert cov.active_rate == pytest.approx(0.7)  # 4+2+1 = 7

    def test_rates_empty(self):
        cov = StakeholderCoverage(stakeholder_id="sh-1", total_needs=0)
        assert cov.addressed_rate == 0.0
        assert cov.withdrawn_rate == 0.0
        assert cov.active_rate == 0.0


# ── PriorityDistribution Tests ─────────────────────────────────────────

class TestPriorityDistribution:
    def test_rates(self):
        dist = PriorityDistribution(
            priority="high",
            total_needs=20,
            addressed_count=15,
            withdrawn_count=3,
        )
        assert dist.addressed_rate == pytest.approx(0.75)
        assert dist.withdrawn_rate == pytest.approx(0.15)

    def test_empty(self):
        dist = PriorityDistribution(priority="low", total_needs=0)
        assert dist.addressed_rate == 0.0


# ── NeedsAnalyzer Tests ────────────────────────────────────────────────

class TestNeedsAnalyzer:
    def test_analyze_stakeholder_coverage(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        coverage = analyzer.analyze_stakeholder_coverage()
        assert len(coverage) == 3

        # CTO should have most needs (sorted by total_needs desc)
        assert coverage[0].stakeholder_id == "sh-cto"
        assert coverage[0].total_needs == 8
        assert coverage[0].addressed_count == 6
        assert coverage[0].withdrawn_count == 1

    def test_analyze_priority_distribution(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        dist = analyzer.analyze_priority_distribution()
        assert len(dist) >= 2

        # Find high priority
        high = next((d for d in dist if d.priority == "high"), None)
        assert high is not None
        assert high.total_needs == 6

    def test_generate_report(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        report = analyzer.generate_report()
        assert report.report_id.startswith("needs-report-")
        assert report.total_needs_analyzed == 13
        assert len(report.stakeholder_coverage) == 3
        assert len(report.priority_distribution) >= 2

    def test_report_health_score(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        report = analyzer.generate_report()
        assert 0.0 <= report.health_score <= 100.0

    def test_report_stale_needs(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        report = analyzer.generate_report()
        # Dev has 2 draft needs
        assert report.stale_needs_count == 2

    def test_report_underserved_stakeholders(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        report = analyzer.generate_report()
        # QA has 100% withdrawn rate → underserved
        assert "sh-qa" in report.underserved_stakeholders

    def test_empty_store(self):
        store = InMemoryNeedStore()
        analyzer = NeedsAnalyzer(store)

        report = analyzer.generate_report()
        assert report.total_needs_analyzed == 0
        assert report.health_score == 0.0
        assert len(report.stakeholder_coverage) == 0

    def test_custom_report_id(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        report = analyzer.generate_report(report_id="custom-id")
        assert report.report_id == "custom-id"

    def test_coverage_time_range(self):
        store = _populated_store()
        analyzer = NeedsAnalyzer(store)

        coverage = analyzer.analyze_stakeholder_coverage()
        cto = next(c for c in coverage if c.stakeholder_id == "sh-cto")
        assert cto.first_need_at <= cto.last_need_at
