"""Decision Analyzer — S4 Analysis for Decision Layer.

Analyzes accumulated decision snapshots to extract pattern effectiveness,
evaluation consistency, and throughput insights.
Provides:
- PatternEffectivenessGrade: 패턴 실효성 등급
- PatternEffectiveness: 패턴별 acceptance_rate, revision_rate, avg_time_to_decision
- EvaluationConsistency: 점수-결과 상관관계
- DecisionAnalysisReport: 종합 분석 보고서

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
    from ea_decision.topic_store import TopicStore


# ═══════════════════════════════════════════════════════════════════════════════
# PatternEffectiveness — 패턴별 실효성 측정
# ═══════════════════════════════════════════════════════════════════════════════

class PatternEffectivenessGrade(StrEnum):
    """패턴 실효성 등급."""
    HIGHLY_EFFECTIVE = "highly_effective"
    EFFECTIVE = "effective"
    MARGINALLY_EFFECTIVE = "marginally_effective"
    INEFFECTIVE = "ineffective"
    UNUSED = "unused"


@dataclass(frozen=True)
class PatternEffectiveness:
    """패턴별 실효성 측정."""
    pattern_name: str
    complexity: str = ""

    # Usage metrics
    total_decisions: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    deprecated_count: int = 0

    # Quality metrics
    avg_evaluation_score: float = 0.0
    avg_option_count: float = 0.0

    # Cross-layer execution feedback
    execution_linked_count: int = 0
    execution_success_count: int = 0

    # Time-based
    first_used_at: str = ""
    last_used_at: str = ""

    @property
    def acceptance_rate(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.accepted_count / self.total_decisions

    @property
    def rejection_rate(self) -> float:
        if self.total_decisions == 0:
            return 0.0
        return self.rejected_count / self.total_decisions

    @property
    def revision_rate(self) -> float:
        """Deprecated/superseded decisions as fraction of total."""
        if self.total_decisions == 0:
            return 0.0
        return self.deprecated_count / self.total_decisions

    @property
    def execution_success_rate(self) -> float:
        """Success rate of linked executions."""
        if self.execution_linked_count == 0:
            return 0.0
        return self.execution_success_count / self.execution_linked_count

    @property
    def grade(self) -> PatternEffectivenessGrade:
        if self.total_decisions == 0:
            return PatternEffectivenessGrade.UNUSED

        if self.acceptance_rate > 0.8 and self.avg_evaluation_score > 0.7:
            return PatternEffectivenessGrade.HIGHLY_EFFECTIVE

        if self.acceptance_rate > 0.5 and self.avg_evaluation_score > 0.4:
            return PatternEffectivenessGrade.EFFECTIVE

        if self.total_decisions < 5:
            return PatternEffectivenessGrade.MARGINALLY_EFFECTIVE

        return PatternEffectivenessGrade.INEFFECTIVE


# ═══════════════════════════════════════════════════════════════════════════════
# EvaluationConsistency — 점수-결과 상관관계
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvaluationConsistency:
    """평가 점수와 결과 간 일관성 분석."""
    pattern_name: str

    # Consistency metrics
    high_score_accepted: int = 0    # score > 0.7 AND accepted
    high_score_rejected: int = 0    # score > 0.7 AND rejected
    low_score_accepted: int = 0     # score <= 0.3 AND accepted
    low_score_rejected: int = 0     # score <= 0.3 AND rejected
    total_analyzed: int = 0

    @property
    def consistency_score(self) -> float:
        """How well evaluation scores predict outcomes (0-1)."""
        if self.total_analyzed == 0:
            return 0.0
        consistent = self.high_score_accepted + self.low_score_rejected
        return consistent / self.total_analyzed


# ═══════════════════════════════════════════════════════════════════════════════
# DecisionAnalysisReport — S4 종합 산출물
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DecisionAnalysisReport:
    """S4 종합 분석 보고서."""
    report_id: str
    created_at: str

    # Summary
    total_decisions_analyzed: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Component reports
    pattern_effectiveness: tuple[PatternEffectiveness, ...] = ()
    evaluation_consistency: tuple[EvaluationConsistency, ...] = ()

    # Aggregate insights
    unused_patterns: tuple[str, ...] = ()
    patterns_for_promotion: tuple[str, ...] = ()
    patterns_for_deprecation: tuple[str, ...] = ()

    @property
    def health_score(self) -> float:
        """Overall decision health score (0-100)."""
        if not self.pattern_effectiveness:
            return 0.0

        total_patterns = len(self.pattern_effectiveness)
        unused_count = len(self.unused_patterns)
        ineffective_count = sum(
            1 for p in self.pattern_effectiveness
            if p.grade == PatternEffectivenessGrade.INEFFECTIVE
        )

        problem_count = unused_count + ineffective_count
        healthy_ratio = 1 - (problem_count / total_patterns) if total_patterns > 0 else 0

        # Factor in average acceptance rate
        avg_acceptance = 0.0
        active_patterns = [
            p for p in self.pattern_effectiveness
            if p.total_decisions > 0
        ]
        if active_patterns:
            avg_acceptance = sum(
                p.acceptance_rate for p in active_patterns
            ) / len(active_patterns)

        return max(0.0, min(100.0, (healthy_ratio * 0.6 + avg_acceptance * 0.4) * 100))


# ═══════════════════════════════════════════════════════════════════════════════
# DecisionAnalyzer — 분석 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionAnalyzer:
    """의사결정 분석 엔진.

    TopicStore의 의사결정 이력을 분석하여 인사이트 추출.
    """

    __slots__ = ("_topic_store",)

    def __init__(self, topic_store: TopicStore) -> None:
        self._topic_store = topic_store

    def analyze_pattern_effectiveness(self) -> tuple[PatternEffectiveness, ...]:
        """Analyze effectiveness of all decision patterns."""
        from ea_decision.topic_store import DecisionSnapshotStatus

        records = self._topic_store.query()

        pattern_data: dict[str, dict] = {}

        for snap in records:
            name = snap.pattern_name
            if name not in pattern_data:
                pattern_data[name] = {
                    "complexity": snap.complexity,
                    "total": 0,
                    "accepted": 0,
                    "rejected": 0,
                    "deprecated": 0,
                    "scores": [],
                    "option_counts": [],
                    "first_used_at": snap.decided_at,
                    "last_used_at": snap.decided_at,
                    "execution_linked": 0,
                    "execution_success": 0,
                }

            data = pattern_data[name]
            data["total"] += 1
            data["scores"].append(snap.evaluation_score)
            data["option_counts"].append(snap.option_count)
            data["last_used_at"] = max(data["last_used_at"], snap.decided_at)
            data["first_used_at"] = min(data["first_used_at"], snap.decided_at)

            if snap.status == DecisionSnapshotStatus.ACCEPTED:
                data["accepted"] += 1
            elif snap.status == DecisionSnapshotStatus.REJECTED:
                data["rejected"] += 1
            elif snap.status in (
                DecisionSnapshotStatus.DEPRECATED,
                DecisionSnapshotStatus.SUPERSEDED,
            ):
                data["deprecated"] += 1

            # Cross-layer execution feedback
            if snap.execution_success is not None:
                data["execution_linked"] += 1
                if snap.execution_success:
                    data["execution_success"] += 1

        results: list[PatternEffectiveness] = []
        for name, data in pattern_data.items():
            scores = data["scores"]
            options = data["option_counts"]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            avg_options = sum(options) / len(options) if options else 0.0

            results.append(PatternEffectiveness(
                pattern_name=name,
                complexity=data["complexity"],
                total_decisions=data["total"],
                accepted_count=data["accepted"],
                rejected_count=data["rejected"],
                deprecated_count=data["deprecated"],
                avg_evaluation_score=avg_score,
                avg_option_count=avg_options,
                execution_linked_count=data["execution_linked"],
                execution_success_count=data["execution_success"],
                first_used_at=data["first_used_at"],
                last_used_at=data["last_used_at"],
            ))

        return tuple(sorted(results, key=lambda r: -r.total_decisions))

    def analyze_evaluation_consistency(self) -> tuple[EvaluationConsistency, ...]:
        """Analyze correlation between evaluation scores and outcomes."""
        from ea_decision.topic_store import DecisionSnapshotStatus

        records = self._topic_store.query()

        pattern_data: dict[str, dict] = {}

        for snap in records:
            name = snap.pattern_name
            if name not in pattern_data:
                pattern_data[name] = {
                    "high_score_accepted": 0,
                    "high_score_rejected": 0,
                    "low_score_accepted": 0,
                    "low_score_rejected": 0,
                    "total": 0,
                }

            data = pattern_data[name]
            is_accepted = snap.status == DecisionSnapshotStatus.ACCEPTED
            is_rejected = snap.status == DecisionSnapshotStatus.REJECTED

            if not (is_accepted or is_rejected):
                continue

            data["total"] += 1

            if snap.evaluation_score > 0.7:
                if is_accepted:
                    data["high_score_accepted"] += 1
                else:
                    data["high_score_rejected"] += 1
            elif snap.evaluation_score <= 0.3:
                if is_accepted:
                    data["low_score_accepted"] += 1
                else:
                    data["low_score_rejected"] += 1

        results: list[EvaluationConsistency] = []
        for name, data in pattern_data.items():
            results.append(EvaluationConsistency(
                pattern_name=name,
                high_score_accepted=data["high_score_accepted"],
                high_score_rejected=data["high_score_rejected"],
                low_score_accepted=data["low_score_accepted"],
                low_score_rejected=data["low_score_rejected"],
                total_analyzed=data["total"],
            ))

        return tuple(sorted(results, key=lambda r: -r.total_analyzed))

    def generate_report(
        self,
        report_id: str | None = None,
    ) -> DecisionAnalysisReport:
        """Generate comprehensive analysis report."""
        if report_id is None:
            report_id = f"decision-report-{uuid.uuid4().hex[:8]}"

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        effectiveness = self.analyze_pattern_effectiveness()
        consistency = self.analyze_evaluation_consistency()

        # Compute aggregate insights
        unused = tuple(
            p.pattern_name for p in effectiveness
            if p.grade == PatternEffectivenessGrade.UNUSED
        )
        for_promotion = tuple(
            p.pattern_name for p in effectiveness
            if p.grade == PatternEffectivenessGrade.HIGHLY_EFFECTIVE
        )[:5]
        for_deprecation = tuple(
            p.pattern_name for p in effectiveness
            if p.grade in (
                PatternEffectivenessGrade.INEFFECTIVE,
                PatternEffectivenessGrade.UNUSED,
            )
        )[:5]

        # Get time range
        all_records = self._topic_store.query()
        period_start = ""
        period_end = ""
        if all_records:
            timestamps = [r.decided_at for r in all_records]
            period_start = min(timestamps)
            period_end = max(timestamps)

        return DecisionAnalysisReport(
            report_id=report_id,
            created_at=now,
            total_decisions_analyzed=len(all_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            pattern_effectiveness=effectiveness,
            evaluation_consistency=consistency,
            unused_patterns=unused,
            patterns_for_promotion=for_promotion,
            patterns_for_deprecation=for_deprecation,
        )
