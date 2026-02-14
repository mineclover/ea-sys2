"""Governance Lifecycle types — Phase 1 Foundation.

Common types for the Governance Lifecycle system:
- RuleProvenance: 규칙 출처 정보
- RuleLifecycle: 규칙 생명주기 상태
- RuleAsset: 규칙 + 메타데이터 + 출처 + 생명주기를 묶은 자산 단위
- StoredDecisionRecord: 영속화된 판단 기록
- CorpusVersionInfo: Corpus 버전 정보
- JudgmentStatistics: triple별 판단 통계

References:
- governance_lifecycle.toml: Recording 레이어 (DecisionStore, DecisionRecord, JudgmentStat)
- governance_lifecycle.md: S3 Decision Recording
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleMetadata,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Lifecycle States — TOML의 LifecycleState 4종 매핑
# ═══════════════════════════════════════════════════════════════════════════════

class RuleLifecycleState(str, Enum):
    """규칙 생명주기 상태.
    
    governance_lifecycle.toml의 RuleDraft/RuleReview/RuleApproved/RuleDeprecated 매핑.
    """
    DRAFT = "draft"           # 초안 — 판단에 사용되지 않음
    REVIEW = "review"         # 검토 중 — 판단에 사용되지 않음
    APPROVED = "approved"     # 승인됨 — 활성 판단에 사용
    DEPRECATED = "deprecated" # 폐기됨 — 새 판단에 미사용, 이력 유지


# Valid state transitions (source → allowed targets)
VALID_TRANSITIONS: dict[RuleLifecycleState, tuple[RuleLifecycleState, ...]] = {
    RuleLifecycleState.DRAFT: (RuleLifecycleState.REVIEW,),
    RuleLifecycleState.REVIEW: (RuleLifecycleState.APPROVED, RuleLifecycleState.DRAFT),
    RuleLifecycleState.APPROVED: (RuleLifecycleState.DEPRECATED,),
    RuleLifecycleState.DEPRECATED: (),  # 최종 상태, 복원 불가
}


def is_valid_transition(
    from_state: RuleLifecycleState, to_state: RuleLifecycleState
) -> bool:
    """규칙 생명주기 상태 전이가 유효한지 검사."""
    return to_state in VALID_TRANSITIONS.get(from_state, ())


# ═══════════════════════════════════════════════════════════════════════════════
# Trigger Events — TOML의 TriggerEvent 3종 매핑
# ═══════════════════════════════════════════════════════════════════════════════

class TriggerEventType(str, Enum):
    """규칙 생명주기 트리거 이벤트.
    
    governance_lifecycle.toml의 RuleSubmitted/RuleApprovedEvent/CorpusUpdated 매핑.
    """
    RULE_SUBMITTED = "rule_submitted"      # 규칙 초안 제출 → DRAFT → REVIEW
    RULE_APPROVED = "rule_approved"        # 규칙 승인 완료 → Corpus 갱신 트리거
    CORPUS_UPDATED = "corpus_updated"      # Corpus 버전 갱신 → 영향 평가 트리거


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Provenance — 규칙 출처 정보
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuleProvenance:
    """규칙 출처 정보.
    
    규칙이 어디서 왔는지 추적:
    - author: 작성자 식별자
    - source_type: 출처 유형 (kernel, profile, empirical, manual)
    - source_reference: 원본 참조 (파일 경로, 커밋 해시 등)
    - created_at: 최초 생성 시점
    - updated_at: 마지막 수정 시점
    - version: 규칙 버전 (동일 ID로 수정됨에 따라 증가)
    """
    author: str
    source_type: str  # kernel | profile | empirical | manual
    source_reference: str = ""
    decision_ref: str = ""  # Link to ea-decision Intent/Choice
    created_at: str = ""  # ISO 8601
    updated_at: str = ""  # ISO 8601
    version: int = 1
    
    def __post_init__(self) -> None:
        if not self.created_at:
            now = _utc_now_iso()
            object.__setattr__(self, "created_at", now)
        if not self.updated_at:
            object.__setattr__(self, "updated_at", self.created_at)


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Lifecycle — 규칙 생명주기 상태 컨테이너
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuleLifecycle:
    """규칙 생명주기 정보.
    
    상태 전이 이력 포함:
    - current_state: 현재 상태
    - state_history: (timestamp, from_state, to_state, actor, reason) 튜플 리스트
    """
    current_state: RuleLifecycleState = RuleLifecycleState.DRAFT
    state_history: tuple[tuple[str, str, str, str, str], ...] = ()
    
    def transition(
        self,
        to_state: RuleLifecycleState,
        actor: str,
        reason: str = "",
    ) -> RuleLifecycle:
        """새 상태로 전이하고 새 RuleLifecycle 반환.
        
        Raises:
            ValueError: 무효한 상태 전이
        """
        if not is_valid_transition(self.current_state, to_state):
            msg = f"Invalid transition: {self.current_state.value} → {to_state.value}"
            raise ValueError(msg)
        
        timestamp = _utc_now_iso()
        entry = (timestamp, self.current_state.value, to_state.value, actor, reason)
        
        return RuleLifecycle(
            current_state=to_state,
            state_history=(*self.state_history, entry),
        )
    
    @property
    def is_active(self) -> bool:
        """판단에 사용 가능한 상태인지."""
        return self.current_state == RuleLifecycleState.APPROVED


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Asset — 규칙 자산 (규칙 + 메타데이터 + 출처 + 생명주기)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RuleAsset:
    """규칙 자산 — 규칙 + 메타데이터 + 출처 + 생명주기를 묶은 자산 단위.
    
    governance_lifecycle.toml의 RuleAsset(item) 매핑.
    RuleCorpusEntry를 확장하여 출처 및 생명주기 정보 추가.
    """
    entry: RuleCorpusEntry  # 기존 규칙 + 메타데이터
    provenance: RuleProvenance
    lifecycle: RuleLifecycle = field(default_factory=RuleLifecycle)
    
    @property
    def rule(self) -> KernelValidityRule:
        return self.entry.rule
    
    @property
    def metadata(self) -> RuleMetadata:
        return self.entry.metadata
    
    @property
    def id(self) -> str:
        return self.entry.rule.id
    
    @property
    def is_active(self) -> bool:
        return self.lifecycle.is_active
    
    def with_lifecycle(self, lifecycle: RuleLifecycle) -> RuleAsset:
        """새 생명주기로 RuleAsset 반환."""
        return RuleAsset(
            entry=self.entry,
            provenance=self.provenance,
            lifecycle=lifecycle,
        )
    
    def with_provenance(self, provenance: RuleProvenance) -> RuleAsset:
        """새 출처로 RuleAsset 반환."""
        return RuleAsset(
            entry=self.entry,
            provenance=provenance,
            lifecycle=self.lifecycle,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Evidence Summary — 분석용 증거 요약 (full RuleCorpusEntry 없이 분석 가능)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EvidenceSummaryItem:
    """요약된 증거 항목.
    
    Full RuleCorpusEntry 없이도 분석이 가능한 최소 정보.
    """
    rule_id: str
    domain: str
    matched: bool
    is_winner: bool


# ═══════════════════════════════════════════════════════════════════════════════
# Stored Decision Record — 영속화된 판단 기록 (S3 Recording)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StoredDecisionRecord:
    """영속화된 판단 기록.
    
    DecisionRecord에 저장소 메타데이터 추가:
    - storage_id: 저장소 내부 ID (auto-increment 또는 UUID)
    - corpus_version_id: 판단 시점의 Corpus 버전
    - stored_at: 저장 시각
    - evidence_summary: 분석용 증거 요약 (full evidence 없이도 분석 가능)
    """
    record: DecisionRecord
    storage_id: str
    corpus_version_id: str = ""
    stored_at: str = ""  # ISO 8601
    evidence_summary: tuple[EvidenceSummaryItem, ...] = ()
    
    def __post_init__(self) -> None:
        if not self.stored_at:
            now = _utc_now_iso()
            object.__setattr__(self, "stored_at", now)
    
    @property
    def triple(self) -> tuple[str, str, str]:
        return self.record.subject_triple


# ═══════════════════════════════════════════════════════════════════════════════
# Corpus Version Info — Corpus 버전 정보
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CorpusVersionInfo:
    """Corpus 버전 정보.
    
    governance_lifecycle.toml의 CorpusVersion(item) 매핑.
    특정 시점의 RuleCorpus 스냅샷 식별자.
    """
    version_id: str
    corpus_name: str  # e.g., "kernel", "GovernanceLifecycle"
    rule_count: int
    created_at: str = ""  # ISO 8601
    parent_version_id: str = ""  # 이전 버전 (변경 추적용)
    description: str = ""
    rule_ids: tuple[str, ...] = ()  # 포함된 규칙 ID 목록
    
    def __post_init__(self) -> None:
        if not self.created_at:
            now = _utc_now_iso()
            object.__setattr__(self, "created_at", now)


# ═══════════════════════════════════════════════════════════════════════════════
# Judgment Statistics — triple별 판단 통계 (S3 Recording)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class JudgmentStatistics:
    """Triple별 판단 통계.
    
    governance_lifecycle.toml의 JudgmentStat(item) 매핑.
    특정 triple에 대한 판단 이력 집계.
    """
    source: str
    target: str
    relation: str
    total_judgments: int = 0
    allow_count: int = 0
    deny_count: int = 0
    override_count: int = 0
    avg_confidence: float = 0.0  # RuleConfidence 매핑된 수치 평균
    last_judgment_at: str = ""
    dominant_domains: tuple[str, ...] = ()  # 가장 빈번한 도메인
    
    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.relation)
    
    @property
    def allow_rate(self) -> float:
        if self.total_judgments == 0:
            return 0.0
        return self.allow_count / self.total_judgments
    
    @property
    def override_rate(self) -> float:
        if self.total_judgments == 0:
            return 0.0
        return self.override_count / self.total_judgments
    
    def with_judgment(
        self,
        verdict: bool,
        confidence: RuleConfidence,
        domains: tuple[str, ...],
        is_override: bool = False,
    ) -> JudgmentStatistics:
        """새 판단으로 통계 업데이트."""
        confidence_value = {
            RuleConfidence.UNIVERSAL: 1.0,
            RuleConfidence.COMMON: 0.75,
            RuleConfidence.CONTEXTUAL: 0.5,
            RuleConfidence.EMPIRICAL: 0.25,
        }.get(confidence, 0.5)
        
        new_total = self.total_judgments + 1
        new_avg = (
            (self.avg_confidence * self.total_judgments + confidence_value) 
            / new_total
        )
        
        # 도메인 빈도 업데이트 (간단한 구현: 최신 도메인 유지)
        domain_set = set(self.dominant_domains) | set(domains)
        
        return JudgmentStatistics(
            source=self.source,
            target=self.target,
            relation=self.relation,
            total_judgments=new_total,
            allow_count=self.allow_count + (1 if verdict else 0),
            deny_count=self.deny_count + (0 if verdict else 1),
            override_count=self.override_count + (1 if is_override else 0),
            avg_confidence=new_avg,
            last_judgment_at=_utc_now_iso(),
            dominant_domains=tuple(sorted(domain_set)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Store Query Options — 저장소 조회 옵션
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DecisionQueryOptions:
    """DecisionStore 조회 옵션."""
    triple: tuple[str, str, str] | None = None
    actor_prefix: str | None = None  # "human:" or "ai:"
    decision_type: str | None = None  # "accept", "override", "create", "delete"
    start_time: str | None = None  # ISO 8601
    end_time: str | None = None  # ISO 8601
    corpus_version_id: str | None = None
    limit: int = 100
    offset: int = 0


@dataclass(frozen=True)
class VersionQueryOptions:
    """CorpusVersionStore 조회 옵션."""
    corpus_name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    limit: int = 100
    offset: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# S2/S4 Results — 판단 및 분석 결과
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EnhancedJudgment:
    """S2: Enhanced Judgment result."""
    judgment: JudgmentReport
    metadata: dict[str, Any] = field(default_factory=dict)
    
@dataclass(frozen=True)
class AnalysisReport:
    """S4: Analysis Report."""
    generated_at: str
    total_decisions: int
    conflict_rate: float
    coverage_stats: dict[str, Any]
    recommendations: tuple[Any, ...] = ()
