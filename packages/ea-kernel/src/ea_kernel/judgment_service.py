"""Judgment Service — Phase 4 Governance (S2 Judgment 보강).

RuleCorpus.judge()를 래핑하여 Governance 루프에 연결.
Provides:
- ReferenceStats: 유사 판단 통계
- JudgmentService: Governance-aware 판단 실행 서비스

References:
- governance_lifecycle.toml: S2 Judgment 레이어
  - JudgmentEngine(structure), ExecuteJudgment(step)
  - ReferenceStats(item), JudgmentReport(item)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_kernel.decision_store import DecisionStore
    from ea_kernel.governance_types import (
        EvidenceSummaryItem,
        JudgmentStatistics,
        StoredDecisionRecord,
    )
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.types import DecisionRecord, JudgmentReport


# ═══════════════════════════════════════════════════════════════════════════════
# Reference Stats — 유사 판단 통계
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ReferenceStats:
    """유사 판단 통계.
    
    governance_lifecycle.toml의 ReferenceStats(item) 매핑.
    현재 판단의 맥락에서 과거 유사 판단 통계를 첨부.
    """
    # For the current triple
    total_past_judgments: int = 0
    allow_count: int = 0
    deny_count: int = 0
    override_count: int = 0
    
    # Consistency
    consistency_rate: float = 0.0  # 같은 verdict 비율
    
    # Time info
    first_judgment_at: str = ""
    last_judgment_at: str = ""
    
    # Relation-level stats
    relation_total_judgments: int = 0
    relation_allow_rate: float = 0.0
    
    @property
    def is_novel(self) -> bool:
        """이전에 판단된 적 없는 새로운 관계인지."""
        return self.total_past_judgments == 0
    
    @property
    def consensus_verdict(self) -> bool | None:
        """과거 판단의 합의 verdict. 합의 없으면 None."""
        if self.total_past_judgments == 0:
            return None
        if self.consistency_rate >= 0.8:
            return self.allow_count > self.deny_count
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Enhanced Judgment Result
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EnhancedJudgment:
    """Governance-enhanced 판단 결과.
    
    JudgmentReport + ReferenceStats + 자동 기록.
    """
    judgment: JudgmentReport
    reference_stats: ReferenceStats
    stored_record: StoredDecisionRecord | None = None
    
    @property
    def verdict(self) -> bool:
        return self.judgment.verdict
    
    @property
    def is_consistent(self) -> bool:
        """과거 판단과 일관적인지."""
        if self.reference_stats.is_novel:
            return True  # 첫 판단은 항상 일관적
        consensus = self.reference_stats.consensus_verdict
        if consensus is None:
            return True  # 합의 없으면 일관적으로 간주
        return self.verdict == consensus
    
    @property
    def confidence_boost(self) -> float:
        """참조 통계 기반 신뢰도 보정.
        
        -0.2 ~ +0.2 범위. 과거 판단과 일관적이면 양수.
        """
        if self.reference_stats.is_novel:
            return 0.0
        
        if self.is_consistent:
            return min(0.2, self.reference_stats.consistency_rate * 0.2)
        else:
            return max(-0.2, -(1 - self.reference_stats.consistency_rate) * 0.2)


# ═══════════════════════════════════════════════════════════════════════════════
# Judgment Service — Governance-aware 판단 서비스
# ═══════════════════════════════════════════════════════════════════════════════

class JudgmentService:
    """Governance-aware 판단 실행 서비스.
    
    governance_lifecycle.toml의 JudgmentEngine(structure) 매핑.
    RuleCorpus.judge()를 래핑하여:
    1. 판단 실행 (S2: ExecuteJudgment)
    2. 레퍼런스 통계 첨부 (ReferenceStats)
    3. 판단 자동 기록 (S3: RecordDecision)
    
    이를 통해 S2→S3 자동 연결 달성.
    """
    
    __slots__ = ("_corpus", "_decision_store", "_auto_record", "_default_actor")
    
    def __init__(
        self,
        corpus: RuleCorpus,
        decision_store: DecisionStore | None = None,
        auto_record: bool = True,
        default_actor: str = "system:judgment_service",
    ) -> None:
        """Initialize JudgmentService.
        
        Args:
            corpus: RuleCorpus for judgment execution
            decision_store: Optional DecisionStore for recording + stats
            auto_record: 판단 후 자동으로 DecisionStore에 기록할지
            default_actor: 기본 actor 이름
        """
        self._corpus = corpus
        self._decision_store = decision_store
        self._auto_record = auto_record
        self._default_actor = default_actor
    
    def judge(
        self,
        source: str,
        target: str,
        relation: str,
        actor: str | None = None,
        context: tuple[tuple[str, str], ...] = (),
    ) -> EnhancedJudgment:
        """Governance-enhanced 판단 실행.
        
        Args:
            source: 소스 엔티티
            target: 타겟 엔티티
            relation: 관계 이름
            actor: 판단 수행자 (None이면 default_actor)
            context: 추가 컨텍스트
            
        Returns:
            EnhancedJudgment (judgment + reference_stats + stored_record)
        """
        # S2: Execute judgment
        judgment = self._corpus.judge(source, target, relation)
        
        # Build reference stats from past decisions
        ref_stats = self._build_reference_stats(source, target, relation)
        
        # S3: Auto-record if enabled
        stored = None
        if self._auto_record and self._decision_store is not None:
            stored = self._record_decision(
                source, target, relation,
                judgment, 
                actor or self._default_actor,
                context,
            )
        
        return EnhancedJudgment(
            judgment=judgment,
            reference_stats=ref_stats,
            stored_record=stored,
        )
    
    def get_reference_stats(
        self,
        source: str,
        target: str,
        relation: str,
    ) -> ReferenceStats:
        """특정 triple에 대한 레퍼런스 통계 조회."""
        return self._build_reference_stats(source, target, relation)
    
    def _build_reference_stats(
        self,
        source: str,
        target: str,
        relation: str,
    ) -> ReferenceStats:
        """과거 판단 이력에서 레퍼런스 통계 생성."""
        if self._decision_store is None:
            return ReferenceStats()
        
        triple = (source, target, relation)
        
        # Get statistics for this triple
        stats = self._decision_store.statistics_for(source, target, relation)
        
        if stats.total_judgments == 0:
            # No past judgments — check relation-level stats
            rel_stats = self._get_relation_stats(relation)
            return ReferenceStats(
                relation_total_judgments=rel_stats[0],
                relation_allow_rate=rel_stats[1],
            )
        
        total = stats.total_judgments
        allow = stats.allow_count
        deny = stats.deny_count
        override = stats.override_count
        
        # Calculate consistency
        if total > 0:
            majority = max(allow, deny)
            consistency = majority / total
        else:
            consistency = 0.0
        
        # Get relation-level stats
        rel_total, rel_allow_rate = self._get_relation_stats(relation)
        
        return ReferenceStats(
            total_past_judgments=total,
            allow_count=allow,
            deny_count=deny,
            override_count=override,
            consistency_rate=consistency,
            first_judgment_at="",  # Not tracked by JudgmentStatistics
            last_judgment_at=stats.last_judgment_at,
            relation_total_judgments=rel_total,
            relation_allow_rate=rel_allow_rate,
        )
    
    def _get_relation_stats(self, relation: str) -> tuple[int, float]:
        """관계 유형 전체 통계 조회.
        
        Returns:
            (total_judgments, allow_rate)
        """
        if self._decision_store is None:
            return (0, 0.0)
        
        all_stats = self._decision_store.all_statistics()
        
        rel_total = 0
        rel_allow = 0
        
        for stat in all_stats:
            if stat.triple[2] == relation:
                rel_total += stat.total_judgments
                rel_allow += stat.allow_count
        
        rate = rel_allow / rel_total if rel_total > 0 else 0.0
        return (rel_total, rate)
    
    def _record_decision(
        self,
        source: str,
        target: str,
        relation: str,
        judgment: JudgmentReport,
        actor: str,
        context: tuple[tuple[str, str], ...],
    ) -> StoredDecisionRecord:
        """판단 결과를 DecisionStore에 기록."""
        import uuid
        from datetime import datetime, UTC
        from ea_kernel.types import DecisionRecord
        
        now = datetime.now(UTC).isoformat() + "Z"
        record = DecisionRecord(
            id=f"jdg-{uuid.uuid4().hex[:8]}",
            timestamp=now,
            actor=actor,
            decision_type="validate",
            subject_triple=(source, target, relation),
            judgment=judgment,
            context=context,
        )
        
        return self._decision_store.store(record)
