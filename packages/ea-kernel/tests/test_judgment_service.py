"""Tests for judgment_service — S2 Judgment governance-aware judgment.

Extracted from test_governance_phase4.py for module-level focus.

Tests:
- ReferenceStats novel/consensus detection
- JudgmentService with/without store
- EnhancedJudgment consistency checks
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from ea_kernel.types import (
    JudgmentReport,
    KernelEntity,
    KernelSchema,
    KernelValidityRule,
    Layer,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_judgment_service.db"


def make_rule_entry(
    rule_id: str,
    domain: str = "kernel",
    priority: int = 100,
    valid: bool = True,
) -> RuleCorpusEntry:
    """Helper to create RuleCorpusEntry."""
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
        valid=valid,
        priority=priority,
    )
    meta = RuleMetadata(
        domain=domain,
        tags=(domain,),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="test",
        established_version="1.0.0",
        rationale="Test",
        group=RuleGroup.FLOW,
    )
    return RuleCorpusEntry(rule=rule, metadata=meta)


# ═══════════════════════════════════════════════════════════════════════════════
# ReferenceStats Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReferenceStats:
    """Tests for ReferenceStats."""

    def test_novel_stats(self) -> None:
        from ea_kernel.judgment_service import ReferenceStats

        stats = ReferenceStats()
        assert stats.is_novel
        assert stats.consensus_verdict is None

    def test_consistent_stats(self) -> None:
        from ea_kernel.judgment_service import ReferenceStats

        stats = ReferenceStats(
            total_past_judgments=10,
            allow_count=9,
            deny_count=1,
            consistency_rate=0.9,
        )

        assert not stats.is_novel
        assert stats.consensus_verdict is True

    def test_no_consensus(self) -> None:
        from ea_kernel.judgment_service import ReferenceStats

        stats = ReferenceStats(
            total_past_judgments=10,
            allow_count=5,
            deny_count=5,
            consistency_rate=0.5,
        )

        assert stats.consensus_verdict is None


# ═══════════════════════════════════════════════════════════════════════════════
# JudgmentService Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestJudgmentService:
    """Tests for JudgmentService."""

    def test_judge_without_store(self) -> None:
        """JudgmentService works without DecisionStore."""
        from ea_kernel.judgment_service import JudgmentService
        from ea_kernel.rule_corpus import RuleCorpus

        # Build a minimal corpus with one rule
        entries = [make_rule_entry("rule-001")]
        schema = KernelSchema(
            attributes=(),
            entities=(
                KernelEntity(name="Source", layer=Layer.L1),
                KernelEntity(name="Target", layer=Layer.L1),
            ),
            relations=(),
            validity_rules=(entries[0].rule,),
        )
        corpus = RuleCorpus(tuple(entries), schema)

        service = JudgmentService(corpus)
        result = service.judge("Source", "Target", "relates")

        assert result.verdict is True
        assert result.reference_stats.is_novel
        assert result.stored_record is None  # No store configured

    def test_judge_with_auto_record(self, db_path: Path) -> None:
        """JudgmentService auto-records to DecisionStore."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.judgment_service import JudgmentService
        from ea_kernel.rule_corpus import RuleCorpus

        entries = [make_rule_entry("rule-002")]
        schema = KernelSchema(
            attributes=(),
            entities=(
                KernelEntity(name="Source", layer=Layer.L1),
                KernelEntity(name="Target", layer=Layer.L1),
            ),
            relations=(),
            validity_rules=(entries[0].rule,),
        )
        corpus = RuleCorpus(tuple(entries), schema)
        store = SQLiteDecisionStore(db_path)

        service = JudgmentService(corpus, store, auto_record=True)
        result = service.judge("Source", "Target", "relates", actor="human:alice")

        assert result.verdict is True
        assert result.stored_record is not None
        assert result.stored_record.record.actor == "human:alice"

    def test_reference_stats_build_up(self, db_path: Path) -> None:
        """Reference stats accumulate over multiple judgments."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.judgment_service import JudgmentService
        from ea_kernel.rule_corpus import RuleCorpus

        entries = [make_rule_entry("rule-003")]
        schema = KernelSchema(
            attributes=(),
            entities=(),
            relations=(),
            validity_rules=(entries[0].rule,),
        )
        corpus = RuleCorpus(tuple(entries), schema)
        store = SQLiteDecisionStore(db_path)

        service = JudgmentService(corpus, store, auto_record=True)

        # First judgment -- novel
        r1 = service.judge("Source", "Target", "relates")
        assert r1.reference_stats.is_novel

        # Second judgment -- should have stats from first
        r2 = service.judge("Source", "Target", "relates")
        assert r2.reference_stats.total_past_judgments >= 1

    def test_judge_without_auto_record(self, db_path: Path) -> None:
        """JudgmentService without auto_record doesn't store."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.judgment_service import JudgmentService
        from ea_kernel.rule_corpus import RuleCorpus

        entries = [make_rule_entry("rule-004")]
        schema = KernelSchema(
            attributes=(),
            entities=(
                KernelEntity(name="Source", layer=Layer.L1),
                KernelEntity(name="Target", layer=Layer.L1),
            ),
            relations=(),
            validity_rules=(entries[0].rule,),
        )
        corpus = RuleCorpus(tuple(entries), schema)
        store = SQLiteDecisionStore(db_path)

        service = JudgmentService(corpus, store, auto_record=False)
        result = service.judge("Source", "Target", "relates")

        assert result.verdict is True
        assert result.stored_record is None

    def test_enhanced_judgment_consistency(self) -> None:
        """Test EnhancedJudgment consistency checks."""
        from ea_kernel.judgment_service import EnhancedJudgment, ReferenceStats

        judgment = JudgmentReport(
            verdict=True,
            evidence=(),
            confidence=RuleConfidence.UNIVERSAL,
            domains=("kernel",),
            conflicts=(),
        )

        # Consistent with past
        stats = ReferenceStats(
            total_past_judgments=10,
            allow_count=9,
            deny_count=1,
            consistency_rate=0.9,
        )
        enhanced = EnhancedJudgment(judgment=judgment, reference_stats=stats)

        assert enhanced.is_consistent
        assert enhanced.confidence_boost > 0

    def test_enhanced_judgment_inconsistent(self) -> None:
        """Test confidence drop for inconsistent judgments."""
        from ea_kernel.judgment_service import EnhancedJudgment, ReferenceStats

        judgment = JudgmentReport(
            verdict=True,
            evidence=(),
            confidence=RuleConfidence.UNIVERSAL,
            domains=("kernel",),
            conflicts=(),
        )

        # Inconsistent: verdict True but past is mostly deny
        stats = ReferenceStats(
            total_past_judgments=10,
            allow_count=1,
            deny_count=9,
            consistency_rate=0.9,  # high consistency among past (deny)
        )
        enhanced = EnhancedJudgment(judgment=judgment, reference_stats=stats)

        assert not enhanced.is_consistent  # verdict=True but consensus=False
        assert enhanced.confidence_boost < 0  # should have penalty
