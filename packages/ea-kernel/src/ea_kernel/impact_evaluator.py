"""Impact Evaluator — Phase 4 Governance (S6 Propagation).

Evaluates the impact of rule changes on existing decisions.
Provides:
- RuleChangeSet: Corpus 버전 간 규칙 변경 내역
- ImpactReport: 영향 보고서
- ImpactEvaluator: 규칙 변경의 기존 모델 영향 평가

References:
- governance_lifecycle.toml: S6 Propagation 레이어
  - ImpactEvaluator(structure), EvaluateImpact(step)
  - RuleChangeSet(item), ImpactReport(item)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_kernel.decision_store import DecisionStore
    from ea_kernel.governance_types import StoredDecisionRecord
    from ea_kernel.rule_asset_store import RuleAssetStore
    from ea_kernel.types import RuleCorpusEntry


# ═══════════════════════════════════════════════════════════════════════════════
# Rule Change Set — Corpus 버전 간 변경 내역
# ═══════════════════════════════════════════════════════════════════════════════

class RuleChangeAction(str, Enum):
    """규칙 변경 유형."""
    ADDED = "added"           # 새 규칙 추가
    REMOVED = "removed"       # 규칙 제거
    MODIFIED = "modified"     # 규칙 내용 수정
    STATE_CHANGED = "state_changed"  # 생명주기 상태 변경


@dataclass(frozen=True)
class RuleChange:
    """개별 규칙 변경."""
    rule_id: str
    action: RuleChangeAction
    before_entry: RuleCorpusEntry | None = None
    after_entry: RuleCorpusEntry | None = None
    before_state: str = ""
    after_state: str = ""
    description: str = ""


@dataclass(frozen=True)
class RuleChangeSet:
    """규칙 변경 집합.
    
    governance_lifecycle.toml의 RuleChangeSet(item) 매핑.
    두 Corpus 버전 간의 규칙 변경을 표현.
    """
    changeset_id: str
    from_version: str
    to_version: str
    created_at: str
    changes: tuple[RuleChange, ...]
    
    @property
    def added_rules(self) -> tuple[RuleChange, ...]:
        return tuple(c for c in self.changes if c.action == RuleChangeAction.ADDED)
    
    @property
    def removed_rules(self) -> tuple[RuleChange, ...]:
        return tuple(c for c in self.changes if c.action == RuleChangeAction.REMOVED)
    
    @property
    def modified_rules(self) -> tuple[RuleChange, ...]:
        return tuple(c for c in self.changes if c.action == RuleChangeAction.MODIFIED)
    
    @property
    def state_changes(self) -> tuple[RuleChange, ...]:
        return tuple(c for c in self.changes if c.action == RuleChangeAction.STATE_CHANGED)
    
    @property
    def is_empty(self) -> bool:
        return len(self.changes) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Impact Report — 영향 보고서
# ═══════════════════════════════════════════════════════════════════════════════

class ImpactSeverity(str, Enum):
    """영향 심각도."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AffectedDecision:
    """영향 받는 판단."""
    decision_id: str
    triple: tuple[str, str, str]
    original_verdict: bool
    affected_by_rules: tuple[str, ...]  # rule_ids
    potential_verdict_change: bool
    timestamp: str


@dataclass(frozen=True)
class ImpactReport:
    """영향 보고서.
    
    governance_lifecycle.toml의 ImpactReport(item) 매핑.
    규칙 변경이 기존 판단에 미치는 영향 분석.
    """
    report_id: str
    changeset_id: str
    created_at: str
    
    # Analysis scope
    total_decisions_scanned: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""
    
    # Results
    affected_decisions: tuple[AffectedDecision, ...] = ()
    severity: ImpactSeverity = ImpactSeverity.NONE
    
    # Statistics
    decisions_with_verdict_change: int = 0
    decisions_with_rule_involvement: int = 0
    
    # Affected triples breakdown
    unique_triples_affected: int = 0
    affected_domains: tuple[str, ...] = ()
    
    # Risk assessment
    risk_factors: tuple[str, ...] = ()
    recommendation: str = ""
    safe_to_apply: bool = True
    
    @property
    def impact_rate(self) -> float:
        """영향 비율."""
        if self.total_decisions_scanned == 0:
            return 0.0
        return len(self.affected_decisions) / self.total_decisions_scanned


# ═══════════════════════════════════════════════════════════════════════════════
# Impact Evaluator — 영향 평가 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class ImpactEvaluator:
    """규칙 변경의 기존 모델 영향 평가 엔진.
    
    governance_lifecycle.toml의 ImpactEvaluator(structure) 매핑.
    RuleChangeSet을 받아 과거 판단 이력에 대한 영향을 분석.
    """
    
    __slots__ = ("_decision_store", "_asset_store")
    
    def __init__(
        self,
        decision_store: DecisionStore,
        asset_store: RuleAssetStore | None = None,
    ) -> None:
        self._decision_store = decision_store
        self._asset_store = asset_store
    
    def evaluate(
        self,
        changeset: RuleChangeSet,
        limit: int = 1000,
    ) -> ImpactReport:
        """규칙 변경 영향 평가.
        
        governance_lifecycle.toml의 EvaluateImpact(step) 매핑.
        
        Args:
            changeset: 평가할 규칙 변경 집합
            limit: 분석할 최대 판단 수
            
        Returns:
            ImpactReport
        """
        import uuid
        from ea_kernel.governance_types import DecisionQueryOptions
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report_id = f"impact-{uuid.uuid4().hex[:8]}"
        
        if changeset.is_empty:
            return ImpactReport(
                report_id=report_id,
                changeset_id=changeset.changeset_id,
                created_at=now,
                recommendation="No changes to evaluate.",
            )
        
        # Get affected rule IDs
        affected_rule_ids = {c.rule_id for c in changeset.changes}
        removed_rule_ids = {
            c.rule_id for c in changeset.changes 
            if c.action == RuleChangeAction.REMOVED
        }
        
        # Query past decisions
        options = DecisionQueryOptions(limit=limit)
        stored_records = self._decision_store.query(options)
        
        # Analyze
        affected: list[AffectedDecision] = []
        domains_seen: set[str] = set()
        verdict_changes = 0
        rule_involvement = 0
        
        period_start = ""
        period_end = ""
        
        for stored in stored_records:
            record = stored.record
            if record.judgment is None:
                continue
            
            # Track time range
            if not period_start or record.timestamp < period_start:
                period_start = record.timestamp
            if not period_end or record.timestamp > period_end:
                period_end = record.timestamp
            
            # Check if this decision involves any changed rules
            involved_rules: list[str] = []
            has_winner_affected = False
            
            for item in stored.evidence_summary:
                if item.rule_id in affected_rule_ids:
                    involved_rules.append(item.rule_id)
                    if item.is_winner:
                        has_winner_affected = True
            
            if not involved_rules:
                continue
            
            rule_involvement += 1
            
            # Determine if verdict could change
            potential_change = False
            if has_winner_affected:
                # If the winning rule is removed, verdict may change
                winning_rule = next(
                    (item.rule_id for item in stored.evidence_summary 
                     if item.is_winner), 
                    None,
                )
                if winning_rule in removed_rule_ids:
                    potential_change = True
                    verdict_changes += 1
                elif winning_rule in affected_rule_ids:
                    # Modified rule might change verdict
                    potential_change = True
                    verdict_changes += 1
            
            affected.append(AffectedDecision(
                decision_id=record.id,
                triple=record.subject_triple,
                original_verdict=record.judgment.verdict,
                affected_by_rules=tuple(involved_rules),
                potential_verdict_change=potential_change,
                timestamp=record.timestamp,
            ))
            
            domains_seen.update(record.judgment.domains)
        
        # Calculate severity
        severity = self._calculate_severity(
            len(affected),
            len(stored_records),
            verdict_changes,
            changeset,
        )
        
        # Identify risk factors
        risk_factors = self._identify_risks(
            changeset, affected, verdict_changes,
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            severity, changeset, verdict_changes, len(affected),
        )
        
        # Determine safety
        safe = severity not in (ImpactSeverity.HIGH, ImpactSeverity.CRITICAL)
        
        unique_triples = len(set(a.triple for a in affected))
        
        return ImpactReport(
            report_id=report_id,
            changeset_id=changeset.changeset_id,
            created_at=now,
            total_decisions_scanned=len(stored_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            affected_decisions=tuple(affected),
            severity=severity,
            decisions_with_verdict_change=verdict_changes,
            decisions_with_rule_involvement=rule_involvement,
            unique_triples_affected=unique_triples,
            affected_domains=tuple(sorted(domains_seen)),
            risk_factors=tuple(risk_factors),
            recommendation=recommendation,
            safe_to_apply=safe,
        )
    
    def evaluate_changeset_from_versions(
        self,
        from_version: str,
        to_version: str,
        limit: int = 1000,
    ) -> ImpactReport:
        """두 Corpus 버전 간 변경 영향 평가.
        
        RuleAssetStore 기반으로 자동 RuleChangeSet 생성 후 평가.
        """
        if self._asset_store is None:
            raise ValueError("RuleAssetStore is required for version-based evaluation")
        
        changeset = self._build_changeset_from_history(from_version, to_version)
        return self.evaluate(changeset, limit)
    
    def _build_changeset_from_history(
        self,
        from_version: str,
        to_version: str,
    ) -> RuleChangeSet:
        """두 버전 간 변경 집합 생성."""
        import uuid
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        changeset_id = f"cs-{uuid.uuid4().hex[:8]}"
        
        # For now, return empty changeset
        # Full implementation would diff two corpus versions
        return RuleChangeSet(
            changeset_id=changeset_id,
            from_version=from_version,
            to_version=to_version,
            created_at=now,
            changes=(),
        )
    
    def _calculate_severity(
        self,
        affected_count: int,
        total_count: int,
        verdict_changes: int,
        changeset: RuleChangeSet,
    ) -> ImpactSeverity:
        """영향 심각도 계산."""
        if total_count == 0 or affected_count == 0:
            return ImpactSeverity.NONE
        
        rate = affected_count / total_count
        
        if verdict_changes > 20 or rate > 0.5:
            return ImpactSeverity.CRITICAL
        if verdict_changes > 10 or rate > 0.3:
            return ImpactSeverity.HIGH
        if verdict_changes > 5 or rate > 0.1:
            return ImpactSeverity.MEDIUM
        if affected_count > 0:
            return ImpactSeverity.LOW
        return ImpactSeverity.NONE
    
    def _identify_risks(
        self,
        changeset: RuleChangeSet,
        affected: list[AffectedDecision],
        verdict_changes: int,
    ) -> list[str]:
        """위험 요소 식별."""
        risks: list[str] = []
        
        if len(changeset.removed_rules) > 3:
            risks.append(
                f"Multiple rules removed ({len(changeset.removed_rules)})"
            )
        
        if verdict_changes > 5:
            risks.append(
                f"High number of potential verdict changes ({verdict_changes})"
            )
        
        # Check for cascading effects
        triples_with_changes = [a for a in affected if a.potential_verdict_change]
        if len(triples_with_changes) > 10:
            risks.append(
                f"Wide cascade: {len(triples_with_changes)} triples may flip"
            )
        
        return risks
    
    def _generate_recommendation(
        self,
        severity: ImpactSeverity,
        changeset: RuleChangeSet,
        verdict_changes: int,
        affected_count: int,
    ) -> str:
        """추천 사항 생성."""
        if severity == ImpactSeverity.NONE:
            return "No impact detected. Safe to apply changes."
        
        if severity == ImpactSeverity.LOW:
            return (
                f"Low impact: {affected_count} decisions involved. "
                "Changes can be applied with standard review."
            )
        
        if severity == ImpactSeverity.MEDIUM:
            return (
                f"Medium impact: {verdict_changes} potential verdict changes. "
                "Recommend stakeholder review before applying."
            )
        
        if severity == ImpactSeverity.HIGH:
            return (
                f"High impact: {verdict_changes} verdict changes across "
                f"{affected_count} decisions. Phased rollout recommended."
            )
        
        return (
            f"Critical impact: {verdict_changes} verdict changes. "
            "Do NOT apply without thorough review and approval. "
            "Consider breaking changes into smaller increments."
        )
