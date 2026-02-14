"""What-If Simulator — Phase 3 Governance (S5 Evolution).

Simulates the impact of rule changes before applying them.
Provides:
- WhatIfSimulator: 규칙 변경 영향 시뮬레이션
- SimulationResult: 시뮬레이션 결과

References:
- governance_lifecycle.toml: Evolution 레이어 (WhatIfSimulator, ProposeEvolution)
- governance_lifecycle.md: S5 Rule Evolution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_kernel.decision_store import DecisionStore
    from ea_kernel.governance_types import StoredDecisionRecord
    from ea_kernel.rule_asset_store import RuleAssetStore
    from ea_kernel.types import RuleCorpusEntry


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Change Types
# ═══════════════════════════════════════════════════════════════════════════════

class ChangeType(str, Enum):
    """시뮬레이션할 변경 유형."""
    ADD_RULE = "add_rule"           # 새 규칙 추가
    REMOVE_RULE = "remove_rule"     # 규칙 제거
    MODIFY_RULE = "modify_rule"     # 규칙 수정
    CHANGE_PRIORITY = "change_priority"  # 우선순위 변경


@dataclass(frozen=True)
class SimulatedChange:
    """시뮬레이션할 변경 사항."""
    change_type: ChangeType
    rule_id: str
    new_entry: RuleCorpusEntry | None = None  # For ADD/MODIFY
    new_priority: int | None = None  # For CHANGE_PRIORITY


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Results
# ═══════════════════════════════════════════════════════════════════════════════

class ImpactLevel(str, Enum):
    """영향 수준."""
    NONE = "none"           # 영향 없음
    LOW = "low"             # 낮은 영향
    MEDIUM = "medium"       # 중간 영향
    HIGH = "high"           # 높은 영향
    CRITICAL = "critical"   # 치명적 영향


@dataclass(frozen=True)
class VerdictChange:
    """판정 변경."""
    triple: tuple[str, str, str]
    original_verdict: bool
    simulated_verdict: bool
    original_winning_rule: str
    simulated_winning_rule: str
    timestamp: str


@dataclass(frozen=True)
class SimulationResult:
    """시뮬레이션 결과.
    
    governance_lifecycle.toml의 ImpactReport(item) 부분 매핑.
    """
    simulation_id: str
    created_at: str
    
    # Changes applied
    changes: tuple[SimulatedChange, ...]
    
    # Analysis
    total_decisions_analyzed: int = 0
    affected_decisions: int = 0
    verdict_changes: tuple[VerdictChange, ...] = ()
    
    # Impact assessment
    impact_level: ImpactLevel = ImpactLevel.NONE
    
    # Summary statistics
    verdicts_flipped_allow_to_deny: int = 0
    verdicts_flipped_deny_to_allow: int = 0
    winning_rule_changes: int = 0
    
    # Affected domains
    affected_domains: tuple[str, ...] = ()
    
    # Recommendations
    risk_factors: tuple[str, ...] = ()
    safe_to_apply: bool = True
    
    @property
    def change_rate(self) -> float:
        """변경 비율."""
        if self.total_decisions_analyzed == 0:
            return 0.0
        return self.affected_decisions / self.total_decisions_analyzed


# ═══════════════════════════════════════════════════════════════════════════════
# What-If Simulator
# ═══════════════════════════════════════════════════════════════════════════════

class WhatIfSimulator:
    """규칙 변경 영향 시뮬레이터.
    
    governance_lifecycle.toml의 WhatIfSimulator(structure) 매핑.
    과거 판단 이력에 규칙 변경을 적용했을 때 결과가 어떻게 달라지는지 시뮬레이션.
    """
    
    __slots__ = ("_decision_store", "_asset_store")
    
    def __init__(
        self,
        decision_store: DecisionStore,
        asset_store: RuleAssetStore | None = None,
    ) -> None:
        """Initialize WhatIfSimulator.
        
        Args:
            decision_store: 과거 판단 이력 조회용
            asset_store: 현재 규칙 상태 조회용 (optional)
        """
        self._decision_store = decision_store
        self._asset_store = asset_store
    
    def simulate(
        self,
        changes: list[SimulatedChange],
        limit: int = 1000,
    ) -> SimulationResult:
        """규칙 변경 시뮬레이션.
        
        과거 판단 이력에 변경 사항을 적용하고 결과 비교.
        
        Args:
            changes: 시뮬레이션할 변경 목록
            limit: 분석할 최대 판단 수
            
        Returns:
            SimulationResult with impact analysis
        """
        import uuid
        from ea_kernel.governance_types import DecisionQueryOptions
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        simulation_id = f"sim-{uuid.uuid4().hex[:8]}"
        
        # Get past decisions
        options = DecisionQueryOptions(limit=limit)
        stored_records = self._decision_store.query(options)
        
        # Build rule modification map
        rule_changes: dict[str, SimulatedChange] = {
            c.rule_id: c for c in changes
        }
        removed_rules: set[str] = {
            c.rule_id for c in changes 
            if c.change_type == ChangeType.REMOVE_RULE
        }
        added_rules: dict[str, SimulatedChange] = {
            c.rule_id: c for c in changes 
            if c.change_type == ChangeType.ADD_RULE
        }
        
        # Analyze each decision
        verdict_changes: list[VerdictChange] = []
        affected_domains: set[str] = set()
        verdicts_allow_to_deny = 0
        verdicts_deny_to_allow = 0
        winning_rule_changes = 0
        
        for stored in stored_records:
            record = stored.record
            if record.judgment is None:
                continue
            
            # Get original winning rule
            original_winner = ""
            for item in stored.evidence_summary:
                if item.is_winner:
                    original_winner = item.rule_id
                    break
            
            # Simulate the change
            simulated_winner, would_change = self._simulate_judgment(
                stored, rule_changes, removed_rules, added_rules,
            )
            
            if would_change:
                # Determine if verdict would flip
                # For simplicity, we assume removing the winning rule 
                # might flip the verdict if no fallback exists
                original_verdict = record.judgment.verdict
                simulated_verdict = original_verdict  # Start with same
                
                # If winning rule is removed, verdict might change
                if original_winner in removed_rules:
                    # This is a simplification - real logic would need 
                    # to re-evaluate with remaining rules
                    simulated_verdict = not original_verdict
                    if original_verdict:
                        verdicts_allow_to_deny += 1
                    else:
                        verdicts_deny_to_allow += 1
                
                if simulated_winner != original_winner:
                    winning_rule_changes += 1
                
                verdict_changes.append(VerdictChange(
                    triple=record.subject_triple,
                    original_verdict=original_verdict,
                    simulated_verdict=simulated_verdict,
                    original_winning_rule=original_winner,
                    simulated_winning_rule=simulated_winner,
                    timestamp=record.timestamp,
                ))
                
                # Track affected domains
                affected_domains.update(record.judgment.domains)
        
        # Calculate impact level
        affected_count = len(verdict_changes)
        total_count = len(stored_records)
        impact_level = self._calculate_impact_level(
            affected_count, 
            total_count,
            verdicts_allow_to_deny,
            verdicts_deny_to_allow,
        )
        
        # Identify risk factors
        risk_factors = self._identify_risk_factors(
            verdict_changes,
            verdicts_allow_to_deny,
            verdicts_deny_to_allow,
            changes,
        )
        
        # Determine if safe to apply
        safe = (
            impact_level not in (ImpactLevel.HIGH, ImpactLevel.CRITICAL) and
            verdicts_allow_to_deny < 10 and
            len(risk_factors) < 3
        )
        
        return SimulationResult(
            simulation_id=simulation_id,
            created_at=now,
            changes=tuple(changes),
            total_decisions_analyzed=total_count,
            affected_decisions=affected_count,
            verdict_changes=tuple(verdict_changes),
            impact_level=impact_level,
            verdicts_flipped_allow_to_deny=verdicts_allow_to_deny,
            verdicts_flipped_deny_to_allow=verdicts_deny_to_allow,
            winning_rule_changes=winning_rule_changes,
            affected_domains=tuple(sorted(affected_domains)),
            risk_factors=tuple(risk_factors),
            safe_to_apply=safe,
        )
    
    def simulate_rule_removal(
        self,
        rule_id: str,
        limit: int = 1000,
    ) -> SimulationResult:
        """단일 규칙 제거 시뮬레이션.
        
        Convenience method for simulating removal of a single rule.
        """
        change = SimulatedChange(
            change_type=ChangeType.REMOVE_RULE,
            rule_id=rule_id,
        )
        return self.simulate([change], limit)
    
    def simulate_priority_change(
        self,
        rule_id: str,
        new_priority: int,
        limit: int = 1000,
    ) -> SimulationResult:
        """규칙 우선순위 변경 시뮬레이션."""
        change = SimulatedChange(
            change_type=ChangeType.CHANGE_PRIORITY,
            rule_id=rule_id,
            new_priority=new_priority,
        )
        return self.simulate([change], limit)
    
    def _simulate_judgment(
        self,
        stored: StoredDecisionRecord,
        rule_changes: dict[str, SimulatedChange],
        removed_rules: set[str],
        added_rules: dict[str, SimulatedChange],
    ) -> tuple[str, bool]:
        """Simulate judgment with rule changes.
        
        Returns:
            (simulated_winning_rule, would_change)
        """
        # Get current evidence
        evidence = stored.evidence_summary
        
        # Check if any evidence involves changed rules
        would_change = False
        original_winner = ""
        simulated_winner = ""
        
        # Find current winner
        winning_priority = -1
        for item in evidence:
            if item.is_winner:
                original_winner = item.rule_id
            
            # Check if this rule is affected
            if item.rule_id in removed_rules:
                would_change = True
            elif item.rule_id in rule_changes:
                change = rule_changes[item.rule_id]
                if change.change_type == ChangeType.CHANGE_PRIORITY:
                    would_change = True
        
        # Simulate new winner (simplified)
        if original_winner in removed_rules:
            # Winner is removed, find next best match
            for item in evidence:
                if item.matched and item.rule_id not in removed_rules:
                    simulated_winner = item.rule_id
                    break
            if not simulated_winner:
                simulated_winner = "none"
        else:
            simulated_winner = original_winner
        
        return simulated_winner, would_change
    
    def _calculate_impact_level(
        self,
        affected_count: int,
        total_count: int,
        allow_to_deny: int,
        deny_to_allow: int,
    ) -> ImpactLevel:
        """Calculate impact level from statistics."""
        if total_count == 0:
            return ImpactLevel.NONE
        
        change_rate = affected_count / total_count
        flip_count = allow_to_deny + deny_to_allow
        
        # Critical if many verdicts flip
        if flip_count > 20 or allow_to_deny > 10:
            return ImpactLevel.CRITICAL
        
        # High if significant percentage affected
        if change_rate > 0.3 or flip_count > 10:
            return ImpactLevel.HIGH
        
        # Medium
        if change_rate > 0.1 or flip_count > 5:
            return ImpactLevel.MEDIUM
        
        # Low
        if affected_count > 0:
            return ImpactLevel.LOW
        
        return ImpactLevel.NONE
    
    def _identify_risk_factors(
        self,
        verdict_changes: list[VerdictChange],
        allow_to_deny: int,
        deny_to_allow: int,
        changes: list[SimulatedChange],
    ) -> list[str]:
        """Identify risk factors from simulation."""
        factors: list[str] = []
        
        # Verdict flips
        if allow_to_deny > 5:
            factors.append(
                f"High number of ALLOW→DENY flips: {allow_to_deny}"
            )
        
        if deny_to_allow > 10:
            factors.append(
                f"Many DENY→ALLOW flips may indicate permissive drift: {deny_to_allow}"
            )
        
        # Multiple removals
        removals = sum(
            1 for c in changes 
            if c.change_type == ChangeType.REMOVE_RULE
        )
        if removals > 3:
            factors.append(
                f"Removing multiple rules ({removals}) increases risk"
            )
        
        # Affected unique triples
        unique_triples = len(set(v.triple for v in verdict_changes))
        if unique_triples > 20:
            factors.append(
                f"Wide impact across {unique_triples} unique relationships"
            )
        
        return factors
