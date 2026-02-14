"""Evidence Analyzer — Phase 2 Insight (S4 Analysis).

Analyzes accumulated decision records to extract patterns and insights.
Provides:
- RuleEffectiveness: 규칙별 실효성 측정 (eval/win/override/shadow)
- ConflictHotspot: 반복적 충돌 지점 탐지
- UsageProfile: 프로파일 사용 통계 (reference grade 판정)
- AnalysisReport: S4 종합 산출물

References:
- governance_lifecycle.toml: Analysis 레이어 (EvidenceAnalyzer, RuleEffectiveness, etc.)
- governance_lifecycle.md: S4 Evidence Analysis

Dependencies:
- Phase 1: DecisionStore (판단 이력 읽기)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ea_kernel.corpus_version_store import CorpusVersionStore
    from ea_kernel.decision_store import DecisionStore


# ═══════════════════════════════════════════════════════════════════════════════
# RuleEffectiveness — 규칙별 실효성 측정
# ═══════════════════════════════════════════════════════════════════════════════

class EffectivenessGrade(StrEnum):
    """규칙 실효성 등급.

    Based on evaluation and win metrics.
    """
    HIGHLY_EFFECTIVE = "highly_effective"  # High eval + high win rate
    EFFECTIVE = "effective"                 # Moderate eval + reasonable win rate
    MARGINALLY_EFFECTIVE = "marginally_effective"  # Low usage but wins when used
    INEFFECTIVE = "ineffective"            # Rarely wins, often overridden
    DEAD = "dead"                          # Never evaluated
    SHADOWED = "shadowed"                  # Always overridden by higher priority


@dataclass(frozen=True)
class RuleEffectiveness:
    """규칙별 실효성 측정.

    governance_lifecycle.toml의 RuleEffectiveness(item) 매핑.
    """
    rule_id: str
    domain: str

    # Evaluation metrics
    total_evaluations: int = 0      # How many times this rule was checked
    match_count: int = 0            # How many times pattern matched
    win_count: int = 0              # How many times was the deciding rule

    # Override metrics
    override_count: int = 0         # How many times verdict was overridden
    shadow_count: int = 0           # How many times shadowed by higher priority

    # Time-based metrics
    first_eval_at: str = ""
    last_eval_at: str = ""

    # Calculated properties
    @property
    def match_rate(self) -> float:
        """Pattern match rate."""
        if self.total_evaluations == 0:
            return 0.0
        return self.match_count / self.total_evaluations

    @property
    def win_rate(self) -> float:
        """Win rate among matches."""
        if self.match_count == 0:
            return 0.0
        return self.win_count / self.match_count

    @property
    def override_rate(self) -> float:
        """Override rate among wins."""
        if self.win_count == 0:
            return 0.0
        return self.override_count / self.win_count

    @property
    def shadow_rate(self) -> float:
        """Shadow rate among matches."""
        if self.match_count == 0:
            return 0.0
        return self.shadow_count / self.match_count

    @property
    def grade(self) -> EffectivenessGrade:
        """Determine effectiveness grade."""
        if self.total_evaluations == 0:
            return EffectivenessGrade.DEAD

        if self.shadow_rate > 0.9:
            return EffectivenessGrade.SHADOWED

        if self.win_count == 0 or (self.override_rate > 0.5):
            return EffectivenessGrade.INEFFECTIVE

        if self.match_count < 5:  # Low sample size
            return EffectivenessGrade.MARGINALLY_EFFECTIVE

        if self.win_rate > 0.7 and self.override_rate < 0.1:
            return EffectivenessGrade.HIGHLY_EFFECTIVE

        return EffectivenessGrade.EFFECTIVE


# ═══════════════════════════════════════════════════════════════════════════════
# ConflictHotspot — 반복적 충돌 지점 탐지
# ═══════════════════════════════════════════════════════════════════════════════

class ConflictSeverity(StrEnum):
    """충돌 심각도."""
    CRITICAL = "critical"      # Frequent conflicts, high impact
    HIGH = "high"              # Regular conflicts
    MEDIUM = "medium"          # Occasional conflicts
    LOW = "low"                # Rare conflicts


@dataclass(frozen=True)
class ConflictHotspot:
    """반복적 충돌 지점 탐지 결과.

    governance_lifecycle.toml의 ConflictHotspot(item) 매핑.
    """
    triple: tuple[str, str, str]  # (source, target, relation)

    # Conflict metrics
    total_conflicts: int = 0
    domain_pairs: tuple[tuple[str, str], ...] = ()  # (allow_domain, deny_domain) pairs

    # Time-based
    first_conflict_at: str = ""
    last_conflict_at: str = ""

    # Resolution patterns
    manual_resolution_count: int = 0
    ai_resolution_count: int = 0

    @property
    def source(self) -> str:
        return self.triple[0]

    @property
    def target(self) -> str:
        return self.triple[1]

    @property
    def relation(self) -> str:
        return self.triple[2]

    @property
    def severity(self) -> ConflictSeverity:
        """Determine conflict severity."""
        if self.total_conflicts >= 10:
            return ConflictSeverity.CRITICAL
        if self.total_conflicts >= 5:
            return ConflictSeverity.HIGH
        if self.total_conflicts >= 2:
            return ConflictSeverity.MEDIUM
        return ConflictSeverity.LOW

    @property
    def unique_domain_pairs(self) -> int:
        return len(set(self.domain_pairs))


# ═══════════════════════════════════════════════════════════════════════════════
# UsageProfile — 프로파일 사용 통계
# ═══════════════════════════════════════════════════════════════════════════════

class ReferenceGrade(StrEnum):
    """프로파일 레퍼런스 등급.

    Based on usage patterns and consistency.
    """
    GOLD = "gold"          # High usage, low conflicts, stable
    SILVER = "silver"      # Moderate usage, acceptable conflicts
    BRONZE = "bronze"      # Limited usage, needs improvement
    DRAFT = "draft"        # New or rarely used


@dataclass(frozen=True)
class UsageProfile:
    """프로파일 사용 통계.

    governance_lifecycle.toml의 UsageProfile(item) 매핑.
    """
    profile_name: str

    # Usage metrics
    total_judgments: int = 0
    unique_triples: int = 0
    unique_rules_used: int = 0

    # Quality metrics
    override_rate: float = 0.0
    conflict_rate: float = 0.0

    # Coverage
    rule_coverage: float = 0.0  # % of rules that have been evaluated

    # Time-based
    first_used_at: str = ""
    last_used_at: str = ""

    @property
    def grade(self) -> ReferenceGrade:
        """Determine reference grade."""
        if self.total_judgments < 10:
            return ReferenceGrade.DRAFT

        # Gold: High usage, low issues
        if (self.total_judgments >= 100 and
            self.override_rate < 0.05 and
            self.conflict_rate < 0.02):
            return ReferenceGrade.GOLD

        # Silver: Moderate usage, acceptable issues
        if (self.total_judgments >= 50 and
            self.override_rate < 0.15 and
            self.conflict_rate < 0.05):
            return ReferenceGrade.SILVER

        return ReferenceGrade.BRONZE


# ═══════════════════════════════════════════════════════════════════════════════
# AnalysisReport — S4 종합 산출물
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AnalysisReport:
    """S4 종합 분석 보고서.

    governance_lifecycle.toml의 AnalysisReport(item) 매핑.
    """
    report_id: str
    corpus_version_id: str
    created_at: str

    # Summary statistics
    total_decisions_analyzed: int = 0
    analysis_period_start: str = ""
    analysis_period_end: str = ""

    # Component reports
    rule_effectiveness: tuple[RuleEffectiveness, ...] = ()
    conflict_hotspots: tuple[ConflictHotspot, ...] = ()
    usage_profiles: tuple[UsageProfile, ...] = ()

    # Aggregate insights
    dead_rules: tuple[str, ...] = ()           # rule_ids with no evaluations
    shadowed_rules: tuple[str, ...] = ()       # rule_ids always shadowed
    ineffective_rules: tuple[str, ...] = ()    # rule_ids frequently overridden
    hot_triples: tuple[tuple[str, str, str], ...] = ()  # Most accessed triples

    # Recommendations
    rules_for_deprecation: tuple[str, ...] = ()
    rules_for_promotion: tuple[str, ...] = ()
    rules_needing_review: tuple[str, ...] = ()

    @property
    def health_score(self) -> float:
        """Overall corpus health score (0-100)."""
        if not self.rule_effectiveness:
            return 0.0

        total_rules = len(self.rule_effectiveness)
        dead_count = len(self.dead_rules)
        shadowed_count = len(self.shadowed_rules)
        ineffective_count = len(self.ineffective_rules)

        problem_count = dead_count + shadowed_count + ineffective_count
        healthy_ratio = 1 - (problem_count / total_rules) if total_rules > 0 else 0

        # Factor in conflict rate
        conflict_hotspot_count = len([h for h in self.conflict_hotspots
                                       if h.severity in (ConflictSeverity.CRITICAL,
                                                         ConflictSeverity.HIGH)])
        conflict_penalty = min(0.3, conflict_hotspot_count * 0.05)

        return max(0.0, min(100.0, (healthy_ratio - conflict_penalty) * 100))


# ═══════════════════════════════════════════════════════════════════════════════
# EvidenceAnalyzer — 근거 분석 엔진
# ═══════════════════════════════════════════════════════════════════════════════

class EvidenceAnalyzer:
    """근거 분석 엔진.

    governance_lifecycle.toml의 EvidenceAnalyzer(structure) 매핑.
    DecisionStore의 판단 이력을 분석하여 인사이트 추출.
    """

    __slots__ = ("_decision_store", "_version_store")

    def __init__(
        self,
        decision_store: DecisionStore,
        version_store: CorpusVersionStore | None = None,
    ) -> None:
        """Initialize EvidenceAnalyzer.

        Args:
            decision_store: DecisionStore for reading judgment history
            version_store: Optional CorpusVersionStore for version tracking
        """
        self._decision_store = decision_store
        self._version_store = version_store

    # ── Rule Effectiveness Analysis ─────────────────────────────────

    def analyze_rule_effectiveness(
        self,
        corpus_version_id: str | None = None,
    ) -> tuple[RuleEffectiveness, ...]:
        """Analyze effectiveness of all rules.

        Examines decision history to compute:
        - How often each rule is evaluated
        - How often it wins (is the deciding rule)
        - How often its verdict is overridden
        - How often it's shadowed by higher priority rules

        Uses evidence_summary from StoredDecisionRecord for analysis,
        which is available even for SQLite-restored records.

        Args:
            corpus_version_id: Optional filter by corpus version

        Returns:
            Tuple of RuleEffectiveness for each rule
        """
        from ea_kernel.governance_types import DecisionQueryOptions

        options = None
        if corpus_version_id:
            options = DecisionQueryOptions(corpus_version_id=corpus_version_id)

        stored_records = self._decision_store.query(options)

        # Aggregate by rule_id
        rule_stats: dict[str, dict[str, Any]] = {}

        for stored in stored_records:
            record = stored.record

            # Use evidence_summary which is always available
            evidence_items = stored.evidence_summary

            # Fallback to judgment.evidence if available and summary is empty
            if not evidence_items and record.judgment and record.judgment.evidence:
                from ea_kernel.governance_types import EvidenceSummaryItem
                evidence_items = tuple(
                    EvidenceSummaryItem(
                        rule_id=e.entry.rule.id,
                        domain=e.entry.metadata.domain,
                        matched=e.matched,
                        is_winner=e.is_winner,
                    )
                    for e in record.judgment.evidence
                )

            if not evidence_items:
                continue

            is_override = record.decision_type == "override"

            for evidence in evidence_items:
                rule_id = evidence.rule_id
                domain = evidence.domain

                if rule_id not in rule_stats:
                    rule_stats[rule_id] = {
                        "domain": domain,
                        "total_evaluations": 0,
                        "match_count": 0,
                        "win_count": 0,
                        "override_count": 0,
                        "shadow_count": 0,
                        "first_eval_at": record.timestamp,
                        "last_eval_at": record.timestamp,
                    }

                stats = rule_stats[rule_id]
                stats["total_evaluations"] = int(stats.get("total_evaluations", 0)) + 1
                stats["last_eval_at"] = record.timestamp

                if evidence.matched:
                    stats["match_count"] = int(stats.get("match_count", 0)) + 1

                    if evidence.is_winner:
                        stats["win_count"] = int(stats.get("win_count", 0)) + 1

                        # Check if overridden
                        if is_override:
                            stats["override_count"] = int(stats.get("override_count", 0)) + 1
                    else:
                        # Matched but didn't win = shadowed
                        stats["shadow_count"] = int(stats.get("shadow_count", 0)) + 1

        # Convert to RuleEffectiveness objects
        results: list[RuleEffectiveness] = []
        for rule_id, stats in rule_stats.items():
            results.append(RuleEffectiveness(
                rule_id=rule_id,
                domain=str(stats.get("domain", "unknown")),
                total_evaluations=int(stats.get("total_evaluations", 0)),
                match_count=int(stats.get("match_count", 0)),
                win_count=int(stats.get("win_count", 0)),
                override_count=int(stats.get("override_count", 0)),
                shadow_count=int(stats.get("shadow_count", 0)),
                first_eval_at=str(stats.get("first_eval_at", "")),
                last_eval_at=str(stats.get("last_eval_at", "")),
            ))

        return tuple(sorted(results, key=lambda r: -r.total_evaluations))

    # ── Conflict Hotspot Detection ──────────────────────────────────

    def detect_conflict_hotspots(
        self,
        min_conflicts: int = 2,
        corpus_version_id: str | None = None,
    ) -> tuple[ConflictHotspot, ...]:
        """Detect triples with repeated conflicts.

        Args:
            min_conflicts: Minimum conflicts to qualify as hotspot
            corpus_version_id: Optional filter by corpus version

        Returns:
            Tuple of ConflictHotspot sorted by severity
        """
        from ea_kernel.governance_types import DecisionQueryOptions

        options = None
        if corpus_version_id:
            options = DecisionQueryOptions(corpus_version_id=corpus_version_id)

        stored_records = self._decision_store.query(options)

        # Aggregate conflicts by triple
        hotspot_data: dict[tuple[str, str, str], dict[str, Any]] = {}

        for stored in stored_records:
            record = stored.record
            if record.judgment is None or not record.judgment.conflicts:
                continue

            triple = record.subject_triple

            if triple not in hotspot_data:
                hotspot_data[triple] = {
                    "total_conflicts": 0,
                    "domain_pairs": [],
                    "first_conflict_at": record.timestamp,
                    "last_conflict_at": record.timestamp,
                    "manual_resolution_count": 0,
                    "ai_resolution_count": 0,
                }

            data = hotspot_data[triple]
            data["total_conflicts"] += 1
            data["last_conflict_at"] = record.timestamp

            # Parse conflict messages for domain pairs
            for conflict_msg in record.judgment.conflicts:
                # Expected format: "Domain 'X' allows but 'Y' denies ..."
                if " allows but " in conflict_msg:
                    try:
                        parts = conflict_msg.split("'")
                        if len(parts) >= 4:
                            allow_domain = parts[1]
                            deny_domain = parts[3]
                            data["domain_pairs"].append((allow_domain, deny_domain))
                    except (IndexError, ValueError):
                        pass

            # Track resolution type
            if record.actor.startswith("human:"):
                data["manual_resolution_count"] += 1
            elif record.actor.startswith("ai:"):
                data["ai_resolution_count"] += 1

        # Filter and convert to ConflictHotspot objects
        results: list[ConflictHotspot] = []
        for triple, data in hotspot_data.items():
            if data["total_conflicts"] >= min_conflicts:
                results.append(ConflictHotspot(
                    triple=triple,
                    total_conflicts=data["total_conflicts"],
                    domain_pairs=tuple(data["domain_pairs"]),
                    first_conflict_at=data["first_conflict_at"],
                    last_conflict_at=data["last_conflict_at"],
                    manual_resolution_count=data["manual_resolution_count"],
                    ai_resolution_count=data["ai_resolution_count"],
                ))

        # Sort by severity (total_conflicts descending)
        return tuple(sorted(results, key=lambda h: -h.total_conflicts))

    # ── Usage Profile Analysis ──────────────────────────────────────

    def analyze_usage_profiles(
        self,
        corpus_version_id: str | None = None,
    ) -> tuple[UsageProfile, ...]:
        """Analyze usage patterns per domain/profile.

        Args:
            corpus_version_id: Optional filter by corpus version

        Returns:
            Tuple of UsageProfile per domain
        """
        from ea_kernel.governance_types import DecisionQueryOptions

        options = None
        if corpus_version_id:
            options = DecisionQueryOptions(corpus_version_id=corpus_version_id)

        stored_records = self._decision_store.query(options)

        # Aggregate by domain
        profile_data: dict[str, dict[str, Any]] = {}

        for stored in stored_records:
            record = stored.record
            if record.judgment is None:
                continue

            for domain in record.judgment.domains:
                if domain not in profile_data:
                    profile_data[domain] = {
                        "total_judgments": 0,
                        "triples": set(),
                        "rules_used": set(),
                        "override_count": 0,
                        "conflict_count": 0,
                        "first_used_at": record.timestamp,
                        "last_used_at": record.timestamp,
                    }

                data = profile_data[domain]
                data["total_judgments"] += 1
                data["triples"].add(record.subject_triple)
                data["last_used_at"] = record.timestamp

            # Track rules used - use evidence_summary
            evidence_items = stored.evidence_summary
            if not evidence_items and record.judgment and record.judgment.evidence:
                from ea_kernel.governance_types import EvidenceSummaryItem
                evidence_items = tuple(
                    EvidenceSummaryItem(
                        rule_id=e.entry.rule.id,
                        domain=e.entry.metadata.domain,
                        matched=e.matched,
                        is_winner=e.is_winner,
                    )
                    for e in record.judgment.evidence
                )

            for evidence in evidence_items:
                # Ensure profile exists for evidence domain
                e_domain = evidence.domain
                if e_domain not in profile_data:
                    # If this domain wasn't in judgment.domains (unlikely but possible), init it
                    profile_data[e_domain] = {
                        "total_judgments": 0, # Not primary judgment domain?
                        "triples": set(),
                        "rules_used": set(),
                        "override_count": 0,
                        "conflict_count": 0,
                        "first_used_at": record.timestamp,
                        "last_used_at": record.timestamp,
                    }

                if evidence.matched:
                    profile_data[e_domain]["rules_used"].add(evidence.rule_id)

                # Track issues (attributed to domain of rule or judgment?)
                # Issues usually attributed to the judgment's primary domains.
                # Here we just track rule usage per domain.

        # Convert to UsageProfile objects
        results: list[UsageProfile] = []
        for domain_name, data in profile_data.items():
            total = data["total_judgments"]
            override_rate = data["override_count"] / total if total > 0 else 0
            conflict_rate = data["conflict_count"] / total if total > 0 else 0

            results.append(UsageProfile(
                profile_name=domain_name,
                total_judgments=total,
                unique_triples=len(data["triples"]),
                unique_rules_used=len(data["rules_used"]),
                override_rate=override_rate,
                conflict_rate=conflict_rate,
                first_used_at=data["first_used_at"],
                last_used_at=data["last_used_at"],
            ))

        return tuple(sorted(results, key=lambda p: -p.total_judgments))

    # ── Full Analysis Report ────────────────────────────────────────

    def generate_report(
        self,
        corpus_version_id: str | None = None,
        report_id: str | None = None,
    ) -> AnalysisReport:
        """Generate comprehensive analysis report.

        Combines all analysis components into a single report with
        recommendations for rule management.

        Args:
            corpus_version_id: Optional filter by corpus version
            report_id: Optional custom report ID

        Returns:
            Complete AnalysisReport
        """
        import uuid

        if report_id is None:
            report_id = f"report-{uuid.uuid4().hex[:8]}"

        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"

        # Run all analyses
        effectiveness = self.analyze_rule_effectiveness(corpus_version_id)
        hotspots = self.detect_conflict_hotspots(
            min_conflicts=2,
            corpus_version_id=corpus_version_id,
        )
        profiles = self.analyze_usage_profiles(corpus_version_id)

        # Compute aggregate insights
        dead_rules = tuple(r.rule_id for r in effectiveness
                          if r.grade == EffectivenessGrade.DEAD)
        shadowed_rules = tuple(r.rule_id for r in effectiveness
                               if r.grade == EffectivenessGrade.SHADOWED)
        ineffective_rules = tuple(r.rule_id for r in effectiveness
                                  if r.grade == EffectivenessGrade.INEFFECTIVE)

        # Get hot triples from statistics
        all_stats = self._decision_store.all_statistics()
        hot_triples = tuple(
            s.triple for s in sorted(
                all_stats,
                key=lambda s: -s.total_judgments
            )[:10]
        )

        # Generate recommendations
        rules_for_deprecation = tuple(
            r for r in dead_rules + shadowed_rules
        )[:5]  # Top 5

        rules_for_promotion = tuple(
            r.rule_id for r in effectiveness
            if r.grade == EffectivenessGrade.HIGHLY_EFFECTIVE
        )[:5]

        rules_needing_review = tuple(
            r.rule_id for r in effectiveness
            if r.override_rate > 0.3 and r.win_count > 5
        )[:10]

        # Get time range from decisions
        from ea_kernel.governance_types import DecisionQueryOptions
        DecisionQueryOptions(limit=1) if not corpus_version_id else \
                  DecisionQueryOptions(corpus_version_id=corpus_version_id, limit=1)

        # First and last records
        all_records = self._decision_store.query(
            DecisionQueryOptions(corpus_version_id=corpus_version_id)
            if corpus_version_id else None
        )

        period_start = ""
        period_end = ""
        if all_records:
            timestamps = [r.record.timestamp for r in all_records]
            period_start = min(timestamps)
            period_end = max(timestamps)

        return AnalysisReport(
            report_id=report_id,
            corpus_version_id=corpus_version_id or "",
            created_at=now,
            total_decisions_analyzed=len(all_records),
            analysis_period_start=period_start,
            analysis_period_end=period_end,
            rule_effectiveness=effectiveness,
            conflict_hotspots=hotspots,
            usage_profiles=profiles,
            dead_rules=dead_rules,
            shadowed_rules=shadowed_rules,
            ineffective_rules=ineffective_rules,
            hot_triples=hot_triples,
            rules_for_deprecation=rules_for_deprecation,
            rules_for_promotion=rules_for_promotion,
            rules_needing_review=rules_needing_review,
        )
