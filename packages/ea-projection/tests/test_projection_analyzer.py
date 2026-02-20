"""Tests for ProjectionAnalyzer — S4 Analysis."""

from __future__ import annotations

from ea_projection.projection_analyzer import (
    FilterEffectiveness,
    FilterEffectivenessGrade,
    LevelCoverage,
    LevelCoverageGrade,
    ProjectionAnalysisReport,
    ProjectionAnalyzer,
)
from ea_projection.projection_store import (
    InMemoryProjectionStore,
    ProjectionSnapshotStatus,
    StoredProjectionSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    profile_name: str = "ea_sys",
    level: str = "l0",
    lens: str = "panorama",
    node_count: int = 10,
    edge_count: int = 20,
    status: ProjectionSnapshotStatus = ProjectionSnapshotStatus.PROJECTED,
    projected_at: str = "2025-01-15T10:00:00Z",
    filter_node_input: int = 0,
    filter_node_output: int = 0,
    filter_edge_input: int = 0,
    filter_edge_output: int = 0,
) -> StoredProjectionSnapshot:
    return StoredProjectionSnapshot(
        storage_id="",
        profile_name=profile_name,
        level=level,
        lens=lens,
        node_count=node_count,
        edge_count=edge_count,
        status=status,
        projected_at=projected_at,
        filter_node_input=filter_node_input,
        filter_node_output=filter_node_output,
        filter_edge_input=filter_edge_input,
        filter_edge_output=filter_edge_output,
    )


def _populated_store() -> InMemoryProjectionStore:
    """Create store with diverse test data."""
    store = InMemoryProjectionStore()

    # L0: 6 projected, 1 stale
    for i in range(6):
        store.store(_make_snapshot(
            level="l0", node_count=10 + i, edge_count=20 + i * 2,
            projected_at=f"2025-01-{10 + i:02d}T10:00:00Z",
            filter_node_input=50, filter_node_output=10 + i,
            filter_edge_input=100, filter_edge_output=20 + i * 2,
        ))
    store.store(_make_snapshot(
        level="l0", node_count=8, edge_count=15,
        status=ProjectionSnapshotStatus.STALE,
        projected_at="2025-01-20T10:00:00Z",
    ))

    # L1: 3 projected
    for i in range(3):
        store.store(_make_snapshot(
            level="l1", lens="capability",
            node_count=20 + i, edge_count=40 + i,
            projected_at=f"2025-01-{15 + i:02d}T10:00:00Z",
            filter_node_input=80, filter_node_output=20 + i,
        ))

    # L2: 1 stale only
    store.store(_make_snapshot(
        level="l2", lens="interaction",
        node_count=5, edge_count=8,
        status=ProjectionSnapshotStatus.STALE,
        projected_at="2025-02-01T10:00:00Z",
    ))

    return store


# ── LevelCoverage Tests ─────────────────────────────────────────────────

class TestLevelCoverage:
    def test_grade_uncovered(self):
        cov = LevelCoverage(level="l0")
        assert cov.grade == LevelCoverageGrade.UNCOVERED
        assert cov.stale_rate == 0.0
        assert cov.freshness_rate == 0.0

    def test_grade_well_covered(self):
        cov = LevelCoverage(
            level="l0",
            total_projections=10,
            projected_count=10,
            stale_count=0,
        )
        assert cov.grade == LevelCoverageGrade.WELL_COVERED

    def test_grade_covered(self):
        cov = LevelCoverage(
            level="l0",
            total_projections=4,
            projected_count=3,
            stale_count=1,
        )
        assert cov.grade == LevelCoverageGrade.COVERED

    def test_grade_partially_covered(self):
        cov = LevelCoverage(
            level="l0",
            total_projections=2,
            projected_count=2,
            stale_count=0,
        )
        assert cov.grade == LevelCoverageGrade.PARTIALLY_COVERED

    def test_grade_sparse(self):
        cov = LevelCoverage(
            level="l0",
            total_projections=2,
            projected_count=0,
            stale_count=2,
        )
        assert cov.grade == LevelCoverageGrade.SPARSE

    def test_freshness_rate(self):
        cov = LevelCoverage(
            level="l0",
            total_projections=10,
            projected_count=8,
        )
        assert cov.freshness_rate == 0.8

    def test_stale_rate(self):
        cov = LevelCoverage(
            level="l0",
            total_projections=10,
            stale_count=3,
        )
        assert cov.stale_rate == 0.3


# ── FilterEffectiveness Tests ───────────────────────────────────────────

class TestFilterEffectiveness:
    def test_grade_unused(self):
        fe = FilterEffectiveness(level="l0")
        assert fe.grade == FilterEffectivenessGrade.UNUSED

    def test_grade_highly_effective(self):
        fe = FilterEffectiveness(
            level="l0",
            total_projections=10,
            avg_node_reduction_rate=0.7,
            avg_edge_reduction_rate=0.6,
        )
        assert fe.grade == FilterEffectivenessGrade.HIGHLY_EFFECTIVE

    def test_grade_effective(self):
        fe = FilterEffectiveness(
            level="l0",
            total_projections=10,
            avg_node_reduction_rate=0.4,
            avg_edge_reduction_rate=0.35,
        )
        assert fe.grade == FilterEffectivenessGrade.EFFECTIVE

    def test_grade_moderate(self):
        fe = FilterEffectiveness(
            level="l0",
            total_projections=10,
            avg_node_reduction_rate=0.15,
            avg_edge_reduction_rate=0.2,
        )
        assert fe.grade == FilterEffectivenessGrade.MODERATE

    def test_grade_weak(self):
        fe = FilterEffectiveness(
            level="l0",
            total_projections=10,
            avg_node_reduction_rate=0.05,
            avg_edge_reduction_rate=0.03,
        )
        assert fe.grade == FilterEffectivenessGrade.WEAK


# ── ProjectionAnalyzer Tests ────────────────────────────────────────────

class TestProjectionAnalyzer:
    def test_analyze_level_coverage(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        results = analyzer.analyze_level_coverage()
        assert len(results) == 3

        l0 = next(r for r in results if r.level == "l0")
        assert l0.total_projections == 7
        assert l0.projected_count == 6
        assert l0.stale_count == 1

    def test_analyze_level_coverage_time_tracking(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        results = analyzer.analyze_level_coverage()
        l0 = next(r for r in results if r.level == "l0")
        assert l0.first_projected_at != ""
        assert l0.last_projected_at != ""
        assert l0.first_projected_at <= l0.last_projected_at

    def test_analyze_filter_effectiveness(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        results = analyzer.analyze_filter_effectiveness()
        assert len(results) >= 1

        l0_fe = next(r for r in results if r.level == "l0")
        assert l0_fe.total_projections > 0
        assert l0_fe.avg_node_reduction_rate > 0.0

    def test_generate_report(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.report_id.startswith("projection-report-")
        assert report.created_at != ""
        assert report.total_projections_analyzed == 11
        assert len(report.level_coverage) == 3
        assert report.health_score > 0

    def test_generate_report_custom_id(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        report = analyzer.generate_report(report_id="custom-id")
        assert report.report_id == "custom-id"

    def test_generate_report_empty_store(self):
        store = InMemoryProjectionStore()
        analyzer = ProjectionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.total_projections_analyzed == 0
        assert len(report.level_coverage) == 0
        assert report.health_score == 0.0

    def test_report_identifies_sparse_levels(self):
        store = InMemoryProjectionStore()
        # Only stale snapshots for l0
        for i in range(3):
            store.store(_make_snapshot(
                level="l0",
                status=ProjectionSnapshotStatus.STALE,
                projected_at=f"2025-01-{10+i:02d}T10:00:00Z",
            ))

        analyzer = ProjectionAnalyzer(store)
        report = analyzer.generate_report()
        assert "l0" in report.sparse_levels

    def test_report_period_range(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.analysis_period_start != ""
        assert report.analysis_period_end != ""
        assert report.analysis_period_start <= report.analysis_period_end

    def test_stale_projection_count(self):
        store = _populated_store()
        analyzer = ProjectionAnalyzer(store)

        report = analyzer.generate_report()
        assert report.stale_projection_count == 2  # 1 in l0, 1 in l2
