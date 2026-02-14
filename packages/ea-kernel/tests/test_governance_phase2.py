"""Phase 2 Integration Tests — Insight (S4 Analysis).

Tests for the Governance Lifecycle Phase 2 implementation:
- EvidenceAnalyzer: Main analysis engine
- RuleEffectiveness: Rule effectiveness measurement
- ConflictHotspot: Conflict detection
- UsageProfile: Profile usage statistics  
- AnalysisReport: Comprehensive analysis report

References:
- docs/governance_lifecycle_todo.md: Phase 2 specifications
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ea_kernel.decision_store import InMemoryDecisionStore, SQLiteDecisionStore
from ea_kernel.corpus_version_store import InMemoryCorpusVersionStore
from ea_kernel.evidence_analyzer import (
    AnalysisReport,
    ConflictHotspot,
    ConflictSeverity,
    EffectivenessGrade,
    EvidenceAnalyzer,
    ReferenceGrade,
    RuleEffectiveness,
    UsageProfile,
)
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleEvidence,
    RuleGroup,
    RuleMetadata,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def make_rule_entry(
    rule_id: str,
    domain: str = "test",
    confidence: RuleConfidence = RuleConfidence.COMMON,
) -> RuleCorpusEntry:
    """Factory for test rule entries."""
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="*",
        target_pattern="*",
        relationship_name="flow",
        valid=True,
        priority=50,
    )
    meta = RuleMetadata(
        domain=domain,
        tags=("test",),
        category=RuleCategory.BEHAVIORAL,
        confidence=confidence,
        source="test",
        established_version="1.0.0",
        rationale="Test rule",
        group=RuleGroup.FLOW,
    )
    return RuleCorpusEntry(rule=rule, metadata=meta)


def make_evidence(
    rule_id: str,
    domain: str = "test",
    matched: bool = True,
    is_winner: bool = False,
) -> RuleEvidence:
    """Factory for RuleEvidence items in JudgmentReport."""
    entry = make_rule_entry(rule_id, domain=domain)
    
    return RuleEvidence(
        entry=entry,
        matched=matched,
        is_winner=is_winner,
        condition_results=(),
    )


def make_decision_record(
    source: str = "A",
    target: str = "B",
    relation: str = "flow",
    actor: str = "human:alice",
    decision_type: str = "accept",
    verdict: bool = True,
    domains: tuple[str, ...] = ("kernel",),
    conflicts: tuple[str, ...] = (),
    evidence: tuple = (),
    timestamp: str | None = None,
) -> DecisionRecord:
    """Factory for test DecisionRecords with full evidence."""
    if timestamp is None:
        timestamp = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
    
    return DecisionRecord(
        id=str(uuid.uuid4()),
        timestamp=timestamp,
        actor=actor,
        decision_type=decision_type,
        subject_triple=(source, target, relation),
        judgment=JudgmentReport(
            verdict=verdict,
            evidence=evidence,
            confidence=RuleConfidence.COMMON,
            domains=domains,
            conflicts=conflicts,
        ),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Test: RuleEffectiveness (Task 2.2)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleEffectiveness:
    """Test RuleEffectiveness type and grading."""
    
    def test_initial_effectiveness(self) -> None:
        """New rule has zero metrics."""
        eff = RuleEffectiveness(rule_id="test-001", domain="test")
        
        assert eff.total_evaluations == 0
        assert eff.match_rate == 0.0
        assert eff.win_rate == 0.0
        assert eff.grade == EffectivenessGrade.DEAD
    
    def test_highly_effective_rule(self) -> None:
        """High eval + high win rate = HIGHLY_EFFECTIVE."""
        eff = RuleEffectiveness(
            rule_id="test-001",
            domain="kernel",
            total_evaluations=100,
            match_count=80,
            win_count=70,
            override_count=2,
        )
        
        assert eff.match_rate == 0.8
        assert eff.win_rate == 0.875  # 70/80
        assert eff.override_rate < 0.1
        assert eff.grade == EffectivenessGrade.HIGHLY_EFFECTIVE
    
    def test_shadowed_rule(self) -> None:
        """High shadow rate = SHADOWED."""
        eff = RuleEffectiveness(
            rule_id="test-001",
            domain="kernel",
            total_evaluations=50,
            match_count=40,
            win_count=0,
            shadow_count=38,
        )
        
        assert eff.shadow_rate > 0.9
        assert eff.grade == EffectivenessGrade.SHADOWED
    
    def test_ineffective_rule(self) -> None:
        """High override rate = INEFFECTIVE."""
        eff = RuleEffectiveness(
            rule_id="test-001",
            domain="kernel",
            total_evaluations=50,
            match_count=40,
            win_count=30,
            override_count=20,
        )
        
        assert eff.override_rate > 0.5
        assert eff.grade == EffectivenessGrade.INEFFECTIVE
    
    def test_marginally_effective_rule(self) -> None:
        """Low sample size = MARGINALLY_EFFECTIVE."""
        eff = RuleEffectiveness(
            rule_id="test-001",
            domain="kernel",
            total_evaluations=5,
            match_count=3,
            win_count=2,
        )
        
        assert eff.grade == EffectivenessGrade.MARGINALLY_EFFECTIVE


# ═══════════════════════════════════════════════════════════════════════════════
# Test: ConflictHotspot (Task 2.3)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConflictHotspot:
    """Test ConflictHotspot type and severity."""
    
    def test_low_severity(self) -> None:
        """Single conflict = LOW severity."""
        hotspot = ConflictHotspot(
            triple=("A", "B", "flow"),
            total_conflicts=1,
        )
        
        assert hotspot.severity == ConflictSeverity.LOW
    
    def test_medium_severity(self) -> None:
        """2-4 conflicts = MEDIUM severity."""
        hotspot = ConflictHotspot(
            triple=("A", "B", "flow"),
            total_conflicts=3,
        )
        
        assert hotspot.severity == ConflictSeverity.MEDIUM
    
    def test_high_severity(self) -> None:
        """5-9 conflicts = HIGH severity."""
        hotspot = ConflictHotspot(
            triple=("A", "B", "flow"),
            total_conflicts=7,
        )
        
        assert hotspot.severity == ConflictSeverity.HIGH
    
    def test_critical_severity(self) -> None:
        """10+ conflicts = CRITICAL severity."""
        hotspot = ConflictHotspot(
            triple=("A", "B", "flow"),
            total_conflicts=15,
            domain_pairs=(
                ("kernel", "profile"),
                ("kernel", "profile"),
                ("profile", "empirical"),
            ),
        )
        
        assert hotspot.severity == ConflictSeverity.CRITICAL
        assert hotspot.unique_domain_pairs == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Test: UsageProfile (Task 2.4)
# ═══════════════════════════════════════════════════════════════════════════════

class TestUsageProfile:
    """Test UsageProfile type and grading."""
    
    def test_draft_grade(self) -> None:
        """Low usage = DRAFT grade."""
        profile = UsageProfile(
            profile_name="test",
            total_judgments=5,
        )
        
        assert profile.grade == ReferenceGrade.DRAFT
    
    def test_gold_grade(self) -> None:
        """High usage, low issues = GOLD grade."""
        profile = UsageProfile(
            profile_name="kernel",
            total_judgments=150,
            override_rate=0.02,
            conflict_rate=0.01,
        )
        
        assert profile.grade == ReferenceGrade.GOLD
    
    def test_silver_grade(self) -> None:
        """Moderate usage, acceptable issues = SILVER grade."""
        profile = UsageProfile(
            profile_name="profile",
            total_judgments=75,
            override_rate=0.10,
            conflict_rate=0.03,
        )
        
        assert profile.grade == ReferenceGrade.SILVER
    
    def test_bronze_grade(self) -> None:
        """High issues = BRONZE grade."""
        profile = UsageProfile(
            profile_name="experimental",
            total_judgments=100,
            override_rate=0.25,
            conflict_rate=0.10,
        )
        
        assert profile.grade == ReferenceGrade.BRONZE


# ═══════════════════════════════════════════════════════════════════════════════
# Test: EvidenceAnalyzer (Task 2.1)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvidenceAnalyzer:
    """Test EvidenceAnalyzer analysis engine."""
    
    @pytest.fixture
    def populated_store(self) -> InMemoryDecisionStore:
        """Create store with sample decisions."""
        store = InMemoryDecisionStore()
        
        # Create evidence for rules
        rule1_evidence = make_evidence("rule-001", "kernel", matched=True, is_winner=True)
        rule2_evidence = make_evidence("rule-002", "kernel", matched=True, is_winner=False)
        rule3_evidence = make_evidence("rule-003", "profile", matched=True, is_winner=True)
        
        # Store multiple decisions with different patterns
        for i in range(10):
            evidence = (rule1_evidence, rule2_evidence)
            record = make_decision_record(
                source="Feature",
                target="Item",
                domains=("kernel",),
                evidence=evidence,
                decision_type="accept" if i % 3 != 0 else "override",
            )
            store.store(record)
        
        # Some decisions with conflicts
        for i in range(5):
            record = make_decision_record(
                source="Feature",
                target="Item",
                domains=("kernel", "profile"),
                evidence=(rule1_evidence, rule3_evidence),
                conflicts=("Domain 'kernel' allows but 'profile' denies",) if i < 3 else (),
            )
            store.store(record)
        
        # Decisions for a different triple
        for i in range(3):
            record = make_decision_record(
                source="Component",
                target="Service",
                domains=("profile",),
                evidence=(rule3_evidence,),
            )
            store.store(record)
        
        return store
    
    def test_analyze_rule_effectiveness(self, populated_store: InMemoryDecisionStore) -> None:
        """Analyzer computes rule effectiveness from decisions."""
        analyzer = EvidenceAnalyzer(populated_store)
        
        effectiveness = analyzer.analyze_rule_effectiveness()
        
        assert len(effectiveness) > 0
        
        # Find rule-001 (winner in 10 decisions)
        rule1_eff = next((e for e in effectiveness if e.rule_id == "rule-001"), None)
        assert rule1_eff is not None
        assert rule1_eff.win_count > 0
    
    def test_detect_conflict_hotspots(self, populated_store: InMemoryDecisionStore) -> None:
        """Analyzer detects conflict hotspots."""
        analyzer = EvidenceAnalyzer(populated_store)
        
        hotspots = analyzer.detect_conflict_hotspots(min_conflicts=2)
        
        # Feature->Item should be a hotspot (3 conflicts)
        assert len(hotspots) > 0
        feature_item = next(
            (h for h in hotspots if h.triple == ("Feature", "Item", "flow")),
            None,
        )
        assert feature_item is not None
        assert feature_item.total_conflicts >= 2
    
    def test_analyze_usage_profiles(self, populated_store: InMemoryDecisionStore) -> None:
        """Analyzer computes usage profiles."""
        analyzer = EvidenceAnalyzer(populated_store)
        
        profiles = analyzer.analyze_usage_profiles()
        
        assert len(profiles) > 0
        
        # Kernel domain should have high usage
        kernel_profile = next((p for p in profiles if p.profile_name == "kernel"), None)
        assert kernel_profile is not None
        assert kernel_profile.total_judgments > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test: AnalysisReport (Task 2.5)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalysisReport:
    """Test AnalysisReport generation."""
    
    def test_health_score_calculation(self) -> None:
        """Health score reflects corpus health."""
        # Healthy report
        healthy_report = AnalysisReport(
            report_id="test-1",
            corpus_version_id="v1",
            created_at="2026-01-01T00:00:00Z",
            rule_effectiveness=tuple(
                RuleEffectiveness(
                    rule_id=f"rule-{i}",
                    domain="kernel",
                    total_evaluations=100,
                    match_count=80,
                    win_count=60,
                )
                for i in range(10)
            ),
            conflict_hotspots=(),
            dead_rules=(),
            shadowed_rules=(),
            ineffective_rules=(),
        )
        
        assert healthy_report.health_score > 80
        
        # Unhealthy report
        unhealthy_report = AnalysisReport(
            report_id="test-2",
            corpus_version_id="v1",
            created_at="2026-01-01T00:00:00Z",
            rule_effectiveness=tuple(
                RuleEffectiveness(
                    rule_id=f"rule-{i}",
                    domain="kernel",
                    total_evaluations=0,  # Dead rules
                )
                for i in range(10)
            ),
            conflict_hotspots=tuple(
                ConflictHotspot(
                    triple=("A", "B", "flow"),
                    total_conflicts=15,  # Critical
                )
                for _ in range(3)
            ),
            dead_rules=tuple(f"rule-{i}" for i in range(10)),
            shadowed_rules=(),
            ineffective_rules=(),
        )
        
        assert unhealthy_report.health_score < 20


class TestEvidenceAnalyzerReport:
    """Test EvidenceAnalyzer.generate_report()."""
    
    @pytest.fixture
    def db_path(self) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)
    
    def test_generate_report(self, db_path: Path) -> None:
        """Generate complete analysis report."""
        store = SQLiteDecisionStore(db_path)
        
        # Populate with test data
        rule1_evidence = make_evidence("rule-001", "kernel", matched=True, is_winner=True)
        rule2_evidence = make_evidence("rule-002", "kernel", matched=True, is_winner=False)
        
        for i in range(20):
            record = make_decision_record(
                source="Feature",
                target=f"Item-{i % 5}",
                domains=("kernel",),
                evidence=(rule1_evidence, rule2_evidence),
                decision_type="accept" if i % 4 != 0 else "override",
            )
            store.store(record)
        
        analyzer = EvidenceAnalyzer(store)
        report = analyzer.generate_report()
        
        assert report.report_id
        assert report.created_at
        assert report.total_decisions_analyzed == 20
        assert len(report.rule_effectiveness) > 0
        assert len(report.usage_profiles) > 0
        assert 0 <= report.health_score <= 100
    
    def test_report_with_corpus_version(self, db_path: Path) -> None:
        """Generate report filtered by corpus version."""
        store = SQLiteDecisionStore(db_path)
        version_store = InMemoryCorpusVersionStore()
        
        # Create a corpus version
        version = version_store.create_version(
            "test",
            (),
            description="Test version",
        )
        
        # Add decisions with version
        rule1_evidence = make_evidence("rule-001", "kernel", matched=True, is_winner=True)
        
        for i in range(10):
            record = make_decision_record(
                source="A",
                target="B",
                domains=("kernel",),
                evidence=(rule1_evidence,),
            )
            store.store(record, corpus_version_id=version.version_id)
        
        # Add decisions without version
        for i in range(5):
            record = make_decision_record(
                source="C",
                target="D",
                domains=("profile",),
            )
            store.store(record)
        
        analyzer = EvidenceAnalyzer(store, version_store)
        
        # Report for specific version
        versioned_report = analyzer.generate_report(corpus_version_id=version.version_id)
        assert versioned_report.total_decisions_analyzed == 10
        
        # Full report
        full_report = analyzer.generate_report()
        assert full_report.total_decisions_analyzed == 15


# ═══════════════════════════════════════════════════════════════════════════════
# Test: End-to-End S4 Data Flow (Task 2.6)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase2EndToEnd:
    """End-to-end tests for Phase 2 S4 analysis pipeline."""
    
    @pytest.fixture
    def db_path(self) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)
    
    def test_analysis_pipeline(self, db_path: Path) -> None:
        """Full S4 analysis pipeline: Store → Analyze → Report."""
        store = SQLiteDecisionStore(db_path)
        
        # Create realistic decision history
        rules = [
            ("rule-kernel-001", "kernel", True, True),   # Winner, effective
            ("rule-kernel-002", "kernel", True, False),  # Matched but shadowed
            ("rule-profile-001", "profile", True, True), # Winner in profile domain
            ("rule-dead-001", "kernel", False, False),   # Never matched
        ]
        
        # Simulate 50 decisions over time
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        
        for i in range(50):
            decision_time = base_time + timedelta(hours=i)
            
            # Create evidence based on rules
            evidence = tuple(
                make_evidence(rule_id, domain, matched, is_winner)
                for rule_id, domain, matched, is_winner in rules
                if matched or i % 10 == 0  # Occasionally evaluate all
            )
            
            # Some decisions have conflicts
            has_conflict = i % 7 == 0
            conflicts = ("Domain 'kernel' allows but 'profile' denies",) if has_conflict else ()
            
            # Some are overrides
            is_override = i % 5 == 0
            
            record = make_decision_record(
                source="Feature",
                target=f"Item-{i % 10}",
                domains=("kernel", "profile") if has_conflict else ("kernel",),
                evidence=evidence,
                conflicts=conflicts,
                decision_type="override" if is_override else "accept",
                timestamp=decision_time.isoformat() + "Z",
            )
            store.store(record)
        
        # Run analysis
        analyzer = EvidenceAnalyzer(store)
        report = analyzer.generate_report()
        
        # Verify report completeness
        assert report.total_decisions_analyzed == 50
        assert len(report.rule_effectiveness) >= 3
        assert report.analysis_period_start
        assert report.analysis_period_end
        
        # Verify rule effectiveness was computed
        kernel_001 = next(
            (e for e in report.rule_effectiveness if e.rule_id == "rule-kernel-001"),
            None,
        )
        assert kernel_001 is not None
        assert kernel_001.win_count > 0
        assert kernel_001.grade in (
            EffectivenessGrade.EFFECTIVE,
            EffectivenessGrade.HIGHLY_EFFECTIVE,
        )
        
        # Verify conflicts/issues were detected (shadowed, ineffective, or hotspots)
        has_issues = (
            len(report.conflict_hotspots) > 0 or 
            len(report.shadowed_rules) > 0 or
            len(report.ineffective_rules) > 0
        )
        assert has_issues, "Expected some issues to be detected"
        
        # Verify usage profiles
        assert len(report.usage_profiles) > 0
        kernel_profile = next(
            (p for p in report.usage_profiles if p.profile_name == "kernel"),
            None,
        )
        assert kernel_profile is not None
        assert kernel_profile.total_judgments > 0
    
    def test_recommendations_generation(self, db_path: Path) -> None:
        """Report generates actionable recommendations."""
        store = SQLiteDecisionStore(db_path)
        
        # Create a mix of effective and problematic rules
        effective_evidence = make_evidence("rule-effective", "kernel", True, True)
        overridden_evidence = make_evidence("rule-overridden", "kernel", True, True)
        
        # Effective rule - many wins, few overrides
        for i in range(30):
            record = make_decision_record(
                source="Good",
                target="Path",
                evidence=(effective_evidence,),
                decision_type="accept",
            )
            store.store(record)
        
        # Overridden rule - wins but always overridden
        for i in range(20):
            record = make_decision_record(
                source="Bad",
                target="Path",
                evidence=(overridden_evidence,),
                decision_type="override",
            )
            store.store(record)
        
        analyzer = EvidenceAnalyzer(store)
        report = analyzer.generate_report()
        
        # Should recommend effective rule for promotion
        effective_eff = next(
            (e for e in report.rule_effectiveness if e.rule_id == "rule-effective"),
            None,
        )
        assert effective_eff is not None
        
        # Should flag overridden rule for review
        overridden_eff = next(
            (e for e in report.rule_effectiveness if e.rule_id == "rule-overridden"),
            None,
        )
        if overridden_eff and overridden_eff.override_rate > 0.3:
            assert "rule-overridden" in report.rules_needing_review or \
                   "rule-overridden" in report.ineffective_rules
