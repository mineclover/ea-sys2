"""Projection Analyzer — S4 Analysis for Projection Layer.

Analyzes accumulated projection snapshots to extract level coverage,
filter effectiveness, and projection stability insights.
Provides:
- LevelCoverageGrade: 레벨별 커버리지 등급
- LevelCoverage: 레벨별 프로젝션 품질 측정
- FilterEffectiveness: 필터 효과성 분석
- ProjectionAnalysisReport: 종합 분석 보고서

References:
- ea_needs/needs_analyzer.py: S4 분석 패턴
- ea_decision/decision_analyzer.py: S4 도메인 번역 패턴
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
# LevelCoverage — 레벨별 커버리지 측정
# ═══════════════════════════════════════════════════════════════════════════════

class LevelCoverageGrade(StrEnum):
    """레벨 커버리지 등급."""
    WELL_COVERED = "well_covered"
    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    SPARSE = "sparse"
    UNCOVERED = "uncovered"


@dataclass(frozen=True)
class LevelCoverage:
    """레벨별 프로젝션 품질 측정."""
    level: str

    # Volume metrics
    total_projections: int = 0
    projected_count: int = 0
    stale_count: int = 0
    archived_count: int = 0

    # Size metrics
    avg_node_count: float = 0.0
    avg_edge_count: float = 0.0
    max_node_count: int = 0
    max_edge_count: int = 0

    # Filter metrics
    avg_filter_reduction_rate: float = 0.0

    # Time-based
    first_projected_at: str = ""
    last_projected_at: str = ""

    @property
    def stale_rate(self) -> float:
        if self.total_projections == 0:
            return 0.0
        return self.stale_count / self.total_projections

    @property
    def freshness_rate(self) -> float:
        if self.total_projections == 0:
            return 0.0
        return self.projected_count / self.total_projections

    @property
    def grade(self) -> LevelCoverageGrade:
        if self.total_projections == 0:
            return LevelCoverageGrade.UNCOVERED

        if self.total_projections >= 5 and self.stale_rate < 0.1:
            return LevelCoverageGrade.WELL_COVERED

        if self.total_projections >= 3 and self.stale_rate < 0.3:
            return LevelCoverageGrade.COVERED

        if self.total_projections >= 1 and self.stale_rate < 0.5:
            return LevelCoverageGrade.PARTIALLY_COVERED

        return LevelCoverageGrade.SPARSE


# ═══════════════════════════════════════════════════════════════════════════════
# FilterEffectiveness — 필터 효과성
# ═══════════════════════════════════════════════════════════════════════════════

class FilterEffectivenessGrade(StrEnum):
    """필터 효과성 등급."""
    HIGHLY_EFFECTIVE = "highly_effective"
    EFFECTIVE = "effective"
    MODERATE = "moderate"
    WEAK = "weak"
    UNUSED = "unused"


@dataclass(frozen=True)
class FilterEffectiveness:
    """프로젝션 필터 효과성 분석."""
    level: str

    total_projections: int = 0
    avg_node_reduction_rate: float = 0.0
    avg_edge_reduction_rate: float = 0.0

    @property
    def grade(self) -> FilterEffectivenessGrade:
        if self.total_projections == 0:
            return FilterEffectivenessGrade.UNUSED

        avg_reduction = (
            self.avg_node_reduction_rate + self.avg_edge_reduction_rate
        ) / 2

        if avg_reduction > 0.5:
            return FilterEffectivenessGrade.HIGHLY_EFFECTIVE
        if avg_reduction > 0.3:
            return FilterEffectivenessGrade.EFFECTIVE
        if avg_reduction > 0.1:
            return FilterEffectivenessGrade.MODERATE
        return FilterEffectivenessGrade.WEAK


# ═══════════════════════════════════════════════════════════════════════════════
# ProjectionAnalysisReport — S4 종합 산출물
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ProjectionAnalysisReport:
    """S4 종합 분석 보고서."""
    report_id: str
    created_at: str

    # Summary
    total_projections_analyzed: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Component reports
    level_coverage: tuple[LevelCoverage, ...] = ()
    filter_effectiveness: tuple[FilterEffectiveness, ...] = ()

    # Aggregate insights
    uncovered_levels: tuple[str, ...] = ()
    sparse_levels: tuple[str, ...] = ()
    stale_projection_count: int = 0

    @property
    def health_score(self) -> float:
        """Overall projection health score (0-100)."""
        if not self.level_coverage:
            return 0.0

        total_levels = len(self.level_coverage)
        uncovered_count = len(self.uncovered_levels)
        sparse_count = len(self.sparse_levels)

        problem_count = uncovered_count + sparse_count
        healthy_ratio = (
            1 - (problem_count / total_levels)
            if total_levels > 0 else 0
        )

        # Factor in average freshness rate
        avg_freshness = 0.0
        active_levels = [
            lc for lc in self.level_coverage
            if lc.total_projections > 0
        ]
        if active_levels:
            avg_freshness = sum(
                lc.freshness_rate for lc in active_levels
            ) / len(active_levels)

        return max(0.0, min(
            100.0,
            (healthy_ratio * 0.6 + avg_freshness * 0.4) * 100,
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# ProjectionAnalyzer — 분석 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class ProjectionAnalyzer:
    """프로젝션 분석 엔진.

    ProjectionStore의 프로젝션 이력을 분석하여 인사이트 추출.
    """

    __slots__ = ("_projection_store",)

    def __init__(self, projection_store: ProjectionStore) -> None:
        self._projection_store = projection_store

    def analyze_level_coverage(
        self,
    ) -> tuple[LevelCoverage, ...]:
        """Analyze projection coverage per level."""
        from ea_projection.projection_store import ProjectionSnapshotStatus

        records = self._projection_store.query()

        level_data: dict[str, dict] = {}

        for snap in records:
            lvl = snap.level
            if lvl not in level_data:
                level_data[lvl] = {
                    "total": 0,
                    "projected": 0,
                    "stale": 0,
                    "archived": 0,
                    "node_counts": [],
                    "edge_counts": [],
                    "filter_reduction_rates": [],
                    "first_projected_at": snap.projected_at,
                    "last_projected_at": snap.projected_at,
                }

            data = level_data[lvl]
            data["total"] += 1
            data["node_counts"].append(snap.node_count)
            data["edge_counts"].append(snap.edge_count)

            # Calculate filter reduction rate
            if snap.filter_node_input > 0:
                node_reduction = 1 - (snap.filter_node_output / snap.filter_node_input)
                data["filter_reduction_rates"].append(node_reduction)

            if snap.projected_at:
                if data["last_projected_at"]:
                    data["last_projected_at"] = max(
                        data["last_projected_at"], snap.projected_at,
                    )
                else:
                    data["last_projected_at"] = snap.projected_at
                if data["first_projected_at"]:
                    data["first_projected_at"] = min(
                        data["first_projected_at"], snap.projected_at,
                    )
                else:
                    data["first_projected_at"] = snap.projected_at

            if snap.status == ProjectionSnapshotStatus.PROJECTED:
                data["projected"] += 1
            elif snap.status == ProjectionSnapshotStatus.STALE:
                data["stale"] += 1
            elif snap.status == ProjectionSnapshotStatus.ARCHIVED:
                data["archived"] += 1

        results: list[LevelCoverage] = []
        for lvl, data in level_data.items():
            nc = data["node_counts"]
            ec = data["edge_counts"]
            fr = data["filter_reduction_rates"]

            results.append(LevelCoverage(
                level=lvl,
                total_projections=data["total"],
                projected_count=data["projected"],
                stale_count=data["stale"],
                archived_count=data["archived"],
                avg_node_count=sum(nc) / len(nc) if nc else 0.0,
                avg_edge_count=sum(ec) / len(ec) if ec else 0.0,
                max_node_count=max(nc) if nc else 0,
                max_edge_count=max(ec) if ec else 0,
                avg_filter_reduction_rate=sum(fr) / len(fr) if fr else 0.0,
                first_projected_at=data["first_projected_at"],
                last_projected_at=data["last_projected_at"],
            ))

        return tuple(sorted(results, key=lambda r: r.level))

    def analyze_filter_effectiveness(
        self,
    ) -> tuple[FilterEffectiveness, ...]:
        """Analyze filter effectiveness per level."""
        records = self._projection_store.query()

        level_data: dict[str, dict] = {}

        for snap in records:
            lvl = snap.level
            if lvl not in level_data:
                level_data[lvl] = {
                    "total": 0,
                    "node_reductions": [],
                    "edge_reductions": [],
                }

            data = level_data[lvl]
            data["total"] += 1

            if snap.filter_node_input > 0:
                node_reduction = 1 - (snap.filter_node_output / snap.filter_node_input)
                data["node_reductions"].append(node_reduction)

            if snap.filter_edge_input > 0:
                edge_reduction = 1 - (snap.filter_edge_output / snap.filter_edge_input)
                data["edge_reductions"].append(edge_reduction)

        results: list[FilterEffectiveness] = []
        for lvl, data in level_data.items():
            nr = data["node_reductions"]
            er = data["edge_reductions"]

            results.append(FilterEffectiveness(
                level=lvl,
                total_projections=data["total"],
                avg_node_reduction_rate=sum(nr) / len(nr) if nr else 0.0,
                avg_edge_reduction_rate=sum(er) / len(er) if er else 0.0,
            ))

        return tuple(sorted(results, key=lambda r: r.level))

    def generate_report(
        self,
        report_id: str | None = None,
    ) -> ProjectionAnalysisReport:
        """Generate comprehensive analysis report."""
        if report_id is None:
            report_id = f"projection-report-{uuid.uuid4().hex[:8]}"

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        coverage = self.analyze_level_coverage()
        effectiveness = self.analyze_filter_effectiveness()

        # Compute aggregate insights
        uncovered = tuple(
            lc.level for lc in coverage
            if lc.grade == LevelCoverageGrade.UNCOVERED
        )
        sparse = tuple(
            lc.level for lc in coverage
            if lc.grade == LevelCoverageGrade.SPARSE
        )

        stale_count = sum(lc.stale_count for lc in coverage)

        # Get time range
        all_records = self._projection_store.query()
        period_start = ""
        period_end = ""
        if all_records:
            timestamps = [
                r.projected_at for r in all_records if r.projected_at
            ]
            if timestamps:
                period_start = min(timestamps)
                period_end = max(timestamps)

        return ProjectionAnalysisReport(
            report_id=report_id,
            created_at=now,
            total_projections_analyzed=len(all_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            level_coverage=coverage,
            filter_effectiveness=effectiveness,
            uncovered_levels=uncovered,
            sparse_levels=sparse,
            stale_projection_count=stale_count,
        )
