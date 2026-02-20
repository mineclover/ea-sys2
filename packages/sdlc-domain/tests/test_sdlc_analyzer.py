"""Tests for SDLCAnalyzer — S4 Analysis in SDLC domain."""

from __future__ import annotations

import pytest
from sdlc_domain.sdlc_analyzer import SDLCAnalyzer
from sdlc_domain.sdlc_store import InMemorySDLCStore, StoredSDLCSnapshot


def _make_snapshot(
    snapshot_id: str,
    lineage_id: str,
    profile_id: str,
    status: str,
    recorded_at: str,
    element: str,
) -> StoredSDLCSnapshot:
    return StoredSDLCSnapshot(
        storage_id="",
        snapshot_id=snapshot_id,
        lineage_id=lineage_id,
        profile_id=profile_id,
        status=status,
        recorded_at=recorded_at,
        owner="team-sdlc",
        metadata=(("element", element),),
    )


def _store_lineage(
    store: InMemorySDLCStore,
    *,
    profile_id: str,
    lineage_id: str,
    statuses: tuple[str, ...],
    start_day: int,
    element: str,
) -> None:
    for index, status in enumerate(statuses, start=1):
        day = start_day + index - 1
        store.store(
            _make_snapshot(
                snapshot_id=f"{lineage_id}-{index}",
                lineage_id=lineage_id,
                profile_id=profile_id,
                status=status,
                recorded_at=f"2025-01-{day:02d}T00:00:00Z",
                element=element,
            )
        )


def _populated_store() -> InMemorySDLCStore:
    store = InMemorySDLCStore()

    # requirements: 3 lineages, 2 fully completed (CLOSED)
    _store_lineage(
        store,
        profile_id="requirements",
        lineage_id="req-1",
        statuses=("BACKLOG", "GROOMED", "SPRINT", "IN_PROGRESS", "REVIEW", "DONE", "CLOSED"),
        start_day=1,
        element="UserStory",
    )
    _store_lineage(
        store,
        profile_id="requirements",
        lineage_id="req-2",
        statuses=("BACKLOG", "GROOMED", "SPRINT"),
        start_day=2,
        element="TechnicalDebt",
    )
    _store_lineage(
        store,
        profile_id="requirements",
        lineage_id="req-3",
        statuses=("BACKLOG", "GROOMED", "SPRINT", "IN_PROGRESS", "REVIEW", "DONE", "CLOSED"),
        start_day=3,
        element="BugReport",
    )

    # pipeline: 3 lineages, 2 latest in PRODUCTION, 1 latest in ROLLED_BACK
    _store_lineage(
        store,
        profile_id="pipeline",
        lineage_id="pipe-1",
        statuses=("QUEUED", "BUILDING", "TESTING", "STAGING", "PRODUCTION"),
        start_day=10,
        element="BuildStep",
    )
    _store_lineage(
        store,
        profile_id="pipeline",
        lineage_id="pipe-2",
        statuses=("QUEUED", "BUILDING", "TESTING", "STAGING", "PRODUCTION", "ROLLED_BACK"),
        start_day=12,
        element="DeployTarget",
    )
    _store_lineage(
        store,
        profile_id="pipeline",
        lineage_id="pipe-3",
        statuses=("QUEUED", "BUILDING", "TESTING", "STAGING", "PRODUCTION"),
        start_day=14,
        element="TestSuite",
    )

    # arch-decision: 3 ADR lineages with different progress depths
    _store_lineage(
        store,
        profile_id="arch-decision",
        lineage_id="adr-1",
        statuses=("PROPOSED", "REVIEW", "ACCEPTED"),
        start_day=20,
        element="ArchDecisionRecord",
    )
    _store_lineage(
        store,
        profile_id="arch-decision",
        lineage_id="adr-2",
        statuses=("PROPOSED", "REVIEW"),
        start_day=22,
        element="DesignReviewItem",
    )
    _store_lineage(
        store,
        profile_id="arch-decision",
        lineage_id="adr-3",
        statuses=("PROPOSED", "REVIEW", "ACCEPTED", "SUPERSEDED"),
        start_day=22,
        element="TechRadarEntry",
    )

    return store


def test_profile_dimensions_come_from_profile_elements() -> None:
    analyzer = SDLCAnalyzer(InMemorySDLCStore())
    dimensions = {dimension.profile_id: dimension for dimension in analyzer.profile_dimensions()}

    assert set(dimensions) == {"arch-decision", "pipeline", "requirements"}

    requirements = dimensions["requirements"]
    assert "UserStory" in requirements.passive_elements
    assert "AcceptanceCriteria" in requirements.passive_elements
    assert "CLOSED" in requirements.state_tokens

    pipeline = dimensions["pipeline"]
    assert "BuildStep" in pipeline.behavior_elements
    assert "TestSuite" in pipeline.behavior_elements
    assert "PRODUCTION" in pipeline.success_states

    arch_decision = dimensions["arch-decision"]
    assert "ArchDecisionRecord" in arch_decision.passive_elements
    assert "TechRadarEntry" in arch_decision.passive_elements
    # State alias extraction from ArchDecisionStatus* elements
    assert "PROPOSED" in arch_decision.state_tokens
    assert "REVIEW" in arch_decision.state_tokens


def test_generate_report_from_sdlc_snapshots() -> None:
    store = _populated_store()
    analyzer = SDLCAnalyzer(store)

    report = analyzer.generate_report()

    assert report.report_id.startswith("sdlc-report-")
    assert report.created_at != ""
    assert report.total_snapshots_analyzed == 42
    assert report.analysis_period_start == "2025-01-01T00:00:00Z"
    assert report.analysis_period_end == "2025-01-25T00:00:00Z"

    # requirements closed throughput: 2 CLOSED snapshots across 8-day window
    assert report.requirements_throughput == pytest.approx(2 / 8)
    # 2/3 latest pipeline lineages are in inferred success state (PRODUCTION)
    assert report.pipeline_success_rate == pytest.approx(2 / 3)
    # arch-decision latest depth: (ACCEPTED=2, REVIEW=1, SUPERSEDED=3) / max_depth(4)
    assert report.adr_effectiveness == pytest.approx(0.5)

    by_profile = {metric.profile_id: metric for metric in report.profile_metrics}
    assert by_profile["requirements"].completed_snapshots == 2
    assert by_profile["pipeline"].success_rate == pytest.approx(2 / 3)
    assert by_profile["arch-decision"].avg_state_progress == pytest.approx(0.5)
    assert by_profile["requirements"].dimension_coverage > 0.0
    assert by_profile["pipeline"].dimension_coverage > 0.0
    assert by_profile["arch-decision"].dimension_coverage > 0.0


def test_generate_report_empty_store() -> None:
    analyzer = SDLCAnalyzer(InMemorySDLCStore())
    report = analyzer.generate_report(report_id="empty-sdlc")

    assert report.report_id == "empty-sdlc"
    assert report.total_snapshots_analyzed == 0
    assert report.requirements_throughput == 0.0
    assert report.pipeline_success_rate == 0.0
    assert report.adr_effectiveness == 0.0
    assert report.health_score == 0.0
