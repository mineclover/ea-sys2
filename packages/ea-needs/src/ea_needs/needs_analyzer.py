"""Needs Analyzer — S4 Analysis for Needs Layer.

Analyzes accumulated need snapshots to extract stakeholder coverage,
priority distribution, and resolution throughput insights.
Provides:
- StakeholderCoverageGrade: 이해관계자 커버리지 등급
- StakeholderCoverage: 이해관계자별 니즈 해결 효과성
- PriorityDistribution: 우선순위별 분포 분석
- NeedsAnalysisReport: 종합 분석 보고서

References:
- ea_kernel/evidence_analyzer.py: S4 분석 패턴
- ea_decision/decision_analyzer.py: S4 도메인 번역 패턴
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
# StakeholderCoverage — 이해관계자별 커버리지 측정
# ═══════════════════════════════════════════════════════════════════════════════

class StakeholderCoverageGrade(StrEnum):
    """이해관계자 커버리지 등급."""
    WELL_COVERED = "well_covered"
    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    UNDERSERVED = "underserved"
    UNSERVED = "unserved"


@dataclass(frozen=True)
class StakeholderCoverage:
    """이해관계자별 니즈 해결 효과성."""
    stakeholder_id: str

    # Volume metrics
    total_needs: int = 0
    addressed_count: int = 0
    withdrawn_count: int = 0
    acknowledged_count: int = 0
    expressed_count: int = 0
    draft_count: int = 0

    # Quality metrics
    avg_justification_count: float = 0.0
    avg_kernel_ref_count: float = 0.0

    # Time-based
    first_need_at: str = ""
    last_need_at: str = ""

    @property
    def addressed_rate(self) -> float:
        if self.total_needs == 0:
            return 0.0
        return self.addressed_count / self.total_needs

    @property
    def withdrawn_rate(self) -> float:
        if self.total_needs == 0:
            return 0.0
        return self.withdrawn_count / self.total_needs

    @property
    def active_rate(self) -> float:
        """Fraction of needs that are active (not withdrawn/draft)."""
        if self.total_needs == 0:
            return 0.0
        active = self.expressed_count + self.acknowledged_count + self.addressed_count
        return active / self.total_needs

    @property
    def grade(self) -> StakeholderCoverageGrade:
        if self.total_needs == 0:
            return StakeholderCoverageGrade.UNSERVED

        if self.addressed_rate > 0.7 and self.withdrawn_rate < 0.1:
            return StakeholderCoverageGrade.WELL_COVERED

        if self.addressed_rate > 0.4 and self.withdrawn_rate < 0.3:
            return StakeholderCoverageGrade.COVERED

        if self.active_rate > 0.3:
            return StakeholderCoverageGrade.PARTIALLY_COVERED

        return StakeholderCoverageGrade.UNDERSERVED


# ═══════════════════════════════════════════════════════════════════════════════
# PriorityDistribution — 우선순위별 분포
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PriorityDistribution:
    """우선순위별 니즈 분포 분석."""
    priority: str

    total_needs: int = 0
    addressed_count: int = 0
    withdrawn_count: int = 0

    @property
    def addressed_rate(self) -> float:
        if self.total_needs == 0:
            return 0.0
        return self.addressed_count / self.total_needs

    @property
    def withdrawn_rate(self) -> float:
        if self.total_needs == 0:
            return 0.0
        return self.withdrawn_count / self.total_needs


# ═══════════════════════════════════════════════════════════════════════════════
# NeedsAnalysisReport — S4 종합 산출물
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class NeedsAnalysisReport:
    """S4 종합 분석 보고서."""
    report_id: str
    created_at: str

    # Summary
    total_needs_analyzed: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Component reports
    stakeholder_coverage: tuple[StakeholderCoverage, ...] = ()
    priority_distribution: tuple[PriorityDistribution, ...] = ()

    # Aggregate insights
    unserved_stakeholders: tuple[str, ...] = ()
    underserved_stakeholders: tuple[str, ...] = ()
    stale_needs_count: int = 0

    @property
    def health_score(self) -> float:
        """Overall needs health score (0-100)."""
        if not self.stakeholder_coverage:
            return 0.0

        total_stakeholders = len(self.stakeholder_coverage)
        unserved_count = len(self.unserved_stakeholders)
        underserved_count = len(self.underserved_stakeholders)

        problem_count = unserved_count + underserved_count
        healthy_ratio = (
            1 - (problem_count / total_stakeholders)
            if total_stakeholders > 0 else 0
        )

        # Factor in average addressed rate
        avg_addressed = 0.0
        active_stakeholders = [
            s for s in self.stakeholder_coverage
            if s.total_needs > 0
        ]
        if active_stakeholders:
            avg_addressed = sum(
                s.addressed_rate for s in active_stakeholders
            ) / len(active_stakeholders)

        return max(0.0, min(
            100.0,
            (healthy_ratio * 0.6 + avg_addressed * 0.4) * 100,
        ))


# ═══════════════════════════════════════════════════════════════════════════════
# NeedsAnalyzer — 분석 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class NeedsAnalyzer:
    """니즈 분석 엔진.

    NeedStore의 니즈 이력을 분석하여 인사이트 추출.
    """

    __slots__ = ("_need_store",)

    def __init__(self, need_store: NeedStore) -> None:
        self._need_store = need_store

    def analyze_stakeholder_coverage(
        self,
    ) -> tuple[StakeholderCoverage, ...]:
        """Analyze needs coverage per stakeholder."""
        from ea_needs.needs_store import NeedSnapshotStatus

        records = self._need_store.query()

        stakeholder_data: dict[str, dict] = {}

        for snap in records:
            sid = snap.stakeholder_id
            if sid not in stakeholder_data:
                stakeholder_data[sid] = {
                    "total": 0,
                    "addressed": 0,
                    "withdrawn": 0,
                    "acknowledged": 0,
                    "expressed": 0,
                    "draft": 0,
                    "justification_counts": [],
                    "kernel_ref_counts": [],
                    "first_need_at": snap.expressed_at,
                    "last_need_at": snap.expressed_at,
                }

            data = stakeholder_data[sid]
            data["total"] += 1
            data["justification_counts"].append(snap.justification_count)
            data["kernel_ref_counts"].append(snap.kernel_ref_count)

            if snap.expressed_at:
                if data["last_need_at"]:
                    data["last_need_at"] = max(
                        data["last_need_at"], snap.expressed_at,
                    )
                else:
                    data["last_need_at"] = snap.expressed_at
                if data["first_need_at"]:
                    data["first_need_at"] = min(
                        data["first_need_at"], snap.expressed_at,
                    )
                else:
                    data["first_need_at"] = snap.expressed_at

            if snap.status == NeedSnapshotStatus.ADDRESSED:
                data["addressed"] += 1
            elif snap.status == NeedSnapshotStatus.WITHDRAWN:
                data["withdrawn"] += 1
            elif snap.status == NeedSnapshotStatus.ACKNOWLEDGED:
                data["acknowledged"] += 1
            elif snap.status == NeedSnapshotStatus.EXPRESSED:
                data["expressed"] += 1
            elif snap.status == NeedSnapshotStatus.DRAFT:
                data["draft"] += 1

        results: list[StakeholderCoverage] = []
        for sid, data in stakeholder_data.items():
            j_counts = data["justification_counts"]
            k_counts = data["kernel_ref_counts"]
            avg_j = sum(j_counts) / len(j_counts) if j_counts else 0.0
            avg_k = sum(k_counts) / len(k_counts) if k_counts else 0.0

            results.append(StakeholderCoverage(
                stakeholder_id=sid,
                total_needs=data["total"],
                addressed_count=data["addressed"],
                withdrawn_count=data["withdrawn"],
                acknowledged_count=data["acknowledged"],
                expressed_count=data["expressed"],
                draft_count=data["draft"],
                avg_justification_count=avg_j,
                avg_kernel_ref_count=avg_k,
                first_need_at=data["first_need_at"],
                last_need_at=data["last_need_at"],
            ))

        return tuple(sorted(results, key=lambda r: -r.total_needs))

    def analyze_priority_distribution(
        self,
    ) -> tuple[PriorityDistribution, ...]:
        """Analyze needs distribution by priority."""
        from ea_needs.needs_store import NeedSnapshotStatus

        records = self._need_store.query()

        priority_data: dict[str, dict] = {}

        for snap in records:
            p = snap.priority
            if p not in priority_data:
                priority_data[p] = {
                    "total": 0,
                    "addressed": 0,
                    "withdrawn": 0,
                }

            data = priority_data[p]
            data["total"] += 1

            if snap.status == NeedSnapshotStatus.ADDRESSED:
                data["addressed"] += 1
            elif snap.status == NeedSnapshotStatus.WITHDRAWN:
                data["withdrawn"] += 1

        results: list[PriorityDistribution] = []
        for priority, data in priority_data.items():
            results.append(PriorityDistribution(
                priority=priority,
                total_needs=data["total"],
                addressed_count=data["addressed"],
                withdrawn_count=data["withdrawn"],
            ))

        return tuple(sorted(results, key=lambda r: -r.total_needs))

    def generate_report(
        self,
        report_id: str | None = None,
    ) -> NeedsAnalysisReport:
        """Generate comprehensive analysis report."""
        if report_id is None:
            report_id = f"needs-report-{uuid.uuid4().hex[:8]}"

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        coverage = self.analyze_stakeholder_coverage()
        distribution = self.analyze_priority_distribution()

        # Compute aggregate insights
        unserved = tuple(
            s.stakeholder_id for s in coverage
            if s.grade == StakeholderCoverageGrade.UNSERVED
        )
        underserved = tuple(
            s.stakeholder_id for s in coverage
            if s.grade == StakeholderCoverageGrade.UNDERSERVED
        )

        # Count stale needs (draft status)
        stale_count = sum(s.draft_count for s in coverage)

        # Get time range
        all_records = self._need_store.query()
        period_start = ""
        period_end = ""
        if all_records:
            timestamps = [
                r.expressed_at for r in all_records if r.expressed_at
            ]
            if timestamps:
                period_start = min(timestamps)
                period_end = max(timestamps)

        return NeedsAnalysisReport(
            report_id=report_id,
            created_at=now,
            total_needs_analyzed=len(all_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            stakeholder_coverage=coverage,
            priority_distribution=distribution,
            unserved_stakeholders=unserved,
            underserved_stakeholders=underserved,
            stale_needs_count=stale_count,
        )
