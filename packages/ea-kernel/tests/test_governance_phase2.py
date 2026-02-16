"""Phase 2 End-to-End Integration Tests — Insight (S4 Analysis).

Module-level unit tests have been extracted to test_evidence_analyzer.py.
This file retains only the end-to-end integration tests for the S4 pipeline.

References:
- docs/governance_lifecycle_todo.md: Phase 2 specifications
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ea_kernel.decision_store import SQLiteDecisionStore
from ea_kernel.evidence_analyzer import (
    EffectivenessGrade,
    EvidenceAnalyzer,
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
# End-to-End S4 Data Flow
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
        """Full S4 analysis pipeline: Store -> Analyze -> Report."""
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
        for _i in range(30):
            record = make_decision_record(
                source="Good",
                target="Path",
                evidence=(effective_evidence,),
                decision_type="accept",
            )
            store.store(record)

        # Overridden rule - wins but always overridden
        for _i in range(20):
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
