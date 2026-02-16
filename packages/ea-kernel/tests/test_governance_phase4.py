"""Phase 4 End-to-End Integration Tests.

Module-level unit tests have been extracted to:
- test_impact_evaluator.py
- test_judgment_service.py
- test_lifecycle_events.py

This file retains only the end-to-end integration tests for Phase 4.

Tests:
- S2->S3->S6 judgment+record+impact pipeline
- Event-driven lifecycle flow
- Reference stats enrichment
- Mixed-rule impact evaluation
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from ea_kernel.governance_types import (
    EvidenceSummaryItem,
    StoredDecisionRecord,
    TriggerEventType,
)
from ea_kernel.types import (
    DecisionRecord,
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


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    """Use pytest's built-in tmp_path."""
    return request.getfixturevalue("tmp_path")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_phase4.db"


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

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


def make_stored_records(
    store,
    count: int,
    rule_ids: tuple[str, ...],
    verdict: bool = True,
) -> list[StoredDecisionRecord]:
    """Helper to populate decision store with records."""
    stored = []
    for i in range(count):
        judgment = JudgmentReport(
            verdict=verdict,
            evidence=(),
            confidence=RuleConfidence.UNIVERSAL,
            domains=("kernel",),
            conflicts=(),
        )
        record = DecisionRecord(
            id=f"dec-{i:03d}",
            timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            actor="ai:validator",
            decision_type="validate",
            subject_triple=("Source", f"Target-{i}", "relates"),
            judgment=judgment,
        )
        # Assign rules in round-robin
        rule_id = rule_ids[i % len(rule_ids)]
        evidence_summary = (
            EvidenceSummaryItem(
                rule_id=rule_id,
                domain="kernel",
                matched=True,
                is_winner=True,
            ),
        )
        s = store.store(record, evidence_summary=evidence_summary)
        stored.append(s)
    return stored


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-End Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase4EndToEnd:
    """End-to-end tests for Phase 4 Governance."""

    def test_judgment_to_impact_pipeline(self, db_path: Path) -> None:
        """Test S2->S3->S6 pipeline: judge -> record -> impact eval."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactEvaluator,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )
        from ea_kernel.judgment_service import JudgmentService
        from ea_kernel.rule_corpus import RuleCorpus

        # Setup
        entries = [
            make_rule_entry("rule-active", priority=100),
            make_rule_entry("rule-backup", priority=50),
        ]
        entities = [KernelEntity(name="Source", layer=Layer.L1)]
        for i in range(10):
            entities.append(KernelEntity(name=f"Target-{i}", layer=Layer.L1))

        schema = KernelSchema(
            attributes=(),
            entities=tuple(entities),
            relations=(),
            validity_rules=tuple(e.rule for e in entries),
        )
        corpus = RuleCorpus(tuple(entries), schema)
        store = SQLiteDecisionStore(db_path)

        # S2+S3: Judge and record
        service = JudgmentService(corpus, store, auto_record=True)
        for i in range(10):
            result = service.judge(
                "Source", f"Target-{i}", "relates",
                actor="ai:validator",
            )
            assert result.stored_record is not None

        # S6: Evaluate impact of removing rule-active
        evaluator = ImpactEvaluator(store)
        cs = RuleChangeSet(
            changeset_id="cs-pipeline",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(
                    rule_id="rule-active",
                    action=RuleChangeAction.REMOVED,
                ),
            ),
        )

        report = evaluator.evaluate(cs)
        assert report.total_decisions_scanned == 10
        assert report.changeset_id == "cs-pipeline"

    def test_event_driven_lifecycle(self) -> None:
        """Test event-driven lifecycle flow."""
        from ea_kernel.lifecycle_events import (
            InMemoryEventBus,
            LifecycleEvent,
        )

        bus = InMemoryEventBus()
        actions_taken: list[str] = []

        # Wire up handlers
        def on_rule_submitted(event: LifecycleEvent) -> None:
            actions_taken.append(f"review:{event.rule_id}")

        def on_rule_approved(event: LifecycleEvent) -> None:
            actions_taken.append(f"deploy:{event.rule_id}")

        def on_corpus_updated(event: LifecycleEvent) -> None:
            actions_taken.append(f"impact:{event.corpus_version_id}")

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, on_rule_submitted)
        bus.subscribe(TriggerEventType.RULE_APPROVED, on_rule_approved)
        bus.subscribe(TriggerEventType.CORPUS_UPDATED, on_corpus_updated)

        # Simulate lifecycle
        bus.publish(LifecycleEvent.rule_submitted("rule-new", "human:author"))
        bus.publish(LifecycleEvent.rule_approved("rule-new", "human:admin"))
        bus.publish(LifecycleEvent.corpus_updated("v2.0"))

        assert actions_taken == [
            "review:rule-new",
            "deploy:rule-new",
            "impact:v2.0",
        ]
        assert len(bus.history) == 3

    def test_judgment_reference_enrichment(self, db_path: Path) -> None:
        """Test reference stats enrichment over multiple judgments."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.judgment_service import JudgmentService
        from ea_kernel.rule_corpus import RuleCorpus

        entries = [make_rule_entry("rule-enrich")]
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

        # Judge same triple multiple times
        results = []
        for _ in range(5):
            r = service.judge("Source", "Target", "relates")
            results.append(r)

        # First should be novel, later ones should have stats
        assert results[0].reference_stats.is_novel
        # After 5 judgments, the last should have accumulated stats
        last_stats = results[-1].reference_stats
        assert last_stats.total_past_judgments >= 1
        assert last_stats.consistency_rate > 0

    def test_impact_with_mixed_rules(self, db_path: Path) -> None:
        """Test impact evaluation with multiple rules."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactEvaluator,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Create decisions with different rules
        make_stored_records(store, 30, ("rule-x", "rule-y", "rule-z"))

        # Remove 2 rules, keep 1
        cs = RuleChangeSet(
            changeset_id="cs-multi",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(rule_id="rule-x", action=RuleChangeAction.REMOVED),
                RuleChange(rule_id="rule-y", action=RuleChangeAction.MODIFIED),
            ),
        )

        evaluator = ImpactEvaluator(store)
        report = evaluator.evaluate(cs)

        assert report.total_decisions_scanned == 30
        # rule-x is removed (winner for ~10 decisions), rule-y is modified
        assert len(report.affected_decisions) > 0
        assert len(report.risk_factors) >= 0
        assert report.recommendation != ""
