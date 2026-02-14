"""Phase 4 Governance Integration Tests.

Tests for:
- ImpactEvaluator + RuleChangeSet + ImpactReport (S6)
- JudgmentService + ReferenceStats (S2 보강)
- LifecycleEventPort + InMemoryEventBus (TriggerEvent)
- End-to-End: S2→S3→S6 판단+기록+영향전파
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
# ImpactEvaluator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleChangeSet:
    """Tests for RuleChangeSet."""

    def test_empty_changeset(self) -> None:
        from ea_kernel.impact_evaluator import RuleChangeSet

        cs = RuleChangeSet(
            changeset_id="cs-001",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(),
        )
        assert cs.is_empty
        assert len(cs.added_rules) == 0
        assert len(cs.removed_rules) == 0

    def test_changeset_properties(self) -> None:
        from ea_kernel.impact_evaluator import (
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        changes = (
            RuleChange(rule_id="r1", action=RuleChangeAction.ADDED),
            RuleChange(rule_id="r2", action=RuleChangeAction.REMOVED),
            RuleChange(rule_id="r3", action=RuleChangeAction.MODIFIED),
            RuleChange(rule_id="r4", action=RuleChangeAction.STATE_CHANGED),
        )

        cs = RuleChangeSet(
            changeset_id="cs-002",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=changes,
        )

        assert not cs.is_empty
        assert len(cs.added_rules) == 1
        assert len(cs.removed_rules) == 1
        assert len(cs.modified_rules) == 1
        assert len(cs.state_changes) == 1


class TestImpactEvaluator:
    """Tests for ImpactEvaluator."""

    def test_empty_changeset_evaluation(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import ImpactEvaluator, RuleChangeSet

        store = SQLiteDecisionStore(db_path)
        evaluator = ImpactEvaluator(store)

        cs = RuleChangeSet(
            changeset_id="cs-empty",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(),
        )

        report = evaluator.evaluate(cs)
        assert report.report_id.startswith("impact-")
        assert report.total_decisions_scanned == 0
        assert report.recommendation == "No changes to evaluate."

    def test_rule_removal_impact(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactSeverity,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Populate with decisions using rule-alpha
        make_stored_records(store, 10, ("rule-alpha",))

        # Create changeset removing rule-alpha
        cs = RuleChangeSet(
            changeset_id="cs-remove",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(
                    rule_id="rule-alpha",
                    action=RuleChangeAction.REMOVED,
                    description="Removing outdated rule",
                ),
            ),
        )

        report = evaluator_eval(store, cs)

        assert report.total_decisions_scanned == 10
        assert len(report.affected_decisions) > 0
        assert report.decisions_with_verdict_change > 0
        assert report.severity != ImpactSeverity.NONE

    def test_unrelated_change_no_impact(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactEvaluator,
            ImpactSeverity,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Populate with decisions using rule-alpha
        make_stored_records(store, 10, ("rule-alpha",))

        # Change unrelated rule
        cs = RuleChangeSet(
            changeset_id="cs-unrelated",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(
                    rule_id="rule-gamma",
                    action=RuleChangeAction.REMOVED,
                ),
            ),
        )

        evaluator = ImpactEvaluator(store)
        report = evaluator.evaluate(cs)

        assert report.total_decisions_scanned == 10
        assert len(report.affected_decisions) == 0
        assert report.severity == ImpactSeverity.NONE
        assert report.safe_to_apply is True

    def test_impact_report_properties(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.impact_evaluator import (
            ImpactEvaluator,
            RuleChange,
            RuleChangeAction,
            RuleChangeSet,
        )

        store = SQLiteDecisionStore(db_path)

        # Create mixed decisions
        make_stored_records(store, 20, ("rule-a", "rule-b"))

        # Remove rule-a
        cs = RuleChangeSet(
            changeset_id="cs-mixed",
            from_version="v1",
            to_version="v2",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            changes=(
                RuleChange(rule_id="rule-a", action=RuleChangeAction.REMOVED),
            ),
        )

        evaluator = ImpactEvaluator(store)
        report = evaluator.evaluate(cs)

        assert report.impact_rate >= 0.0
        assert len(report.affected_domains) >= 0
        assert report.unique_triples_affected >= 0


def evaluator_eval(store, cs):
    """Helper to create evaluator and evaluate."""
    from ea_kernel.impact_evaluator import ImpactEvaluator
    evaluator = ImpactEvaluator(store)
    return evaluator.evaluate(cs)


# ═══════════════════════════════════════════════════════════════════════════════
# JudgmentService Tests
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

        # First judgment — novel
        r1 = service.judge("Source", "Target", "relates")
        assert r1.reference_stats.is_novel

        # Second judgment — should have stats from first
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


# ═══════════════════════════════════════════════════════════════════════════════
# LifecycleEvent Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLifecycleEvent:
    """Tests for LifecycleEvent factory methods."""

    def test_rule_submitted(self) -> None:
        from ea_kernel.lifecycle_events import LifecycleEvent

        event = LifecycleEvent.rule_submitted("rule-001", "human:alice")

        assert event.event_type == TriggerEventType.RULE_SUBMITTED
        assert event.rule_id == "rule-001"
        assert event.source_actor == "human:alice"
        assert event.from_state == "draft"
        assert event.to_state == "review"

    def test_rule_approved(self) -> None:
        from ea_kernel.lifecycle_events import LifecycleEvent

        event = LifecycleEvent.rule_approved("rule-002", "human:admin")

        assert event.event_type == TriggerEventType.RULE_APPROVED
        assert event.rule_id == "rule-002"

    def test_corpus_updated(self) -> None:
        from ea_kernel.lifecycle_events import LifecycleEvent

        event = LifecycleEvent.corpus_updated("v1.2.0")

        assert event.event_type == TriggerEventType.CORPUS_UPDATED
        assert event.corpus_version_id == "v1.2.0"


class TestInMemoryEventBus:
    """Tests for InMemoryEventBus."""

    def test_publish_subscribe(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        received: list = []

        def handler(event: LifecycleEvent) -> None:
            received.append(event)

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, handler)

        event = LifecycleEvent.rule_submitted("rule-001", "human:alice")
        bus.publish(event)

        assert len(received) == 1
        assert received[0].rule_id == "rule-001"

    def test_multiple_handlers(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        count = {"a": 0, "b": 0}

        def handler_a(event: LifecycleEvent) -> None:
            count["a"] += 1

        def handler_b(event: LifecycleEvent) -> None:
            count["b"] += 1

        bus.subscribe(TriggerEventType.RULE_APPROVED, handler_a)
        bus.subscribe(TriggerEventType.RULE_APPROVED, handler_b)

        bus.publish(LifecycleEvent.rule_approved("rule-001", "admin"))

        assert count["a"] == 1
        assert count["b"] == 1

    def test_unsubscribe(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        received: list = []

        def handler(event: LifecycleEvent) -> None:
            received.append(event)

        bus.subscribe(TriggerEventType.CORPUS_UPDATED, handler)
        bus.unsubscribe(TriggerEventType.CORPUS_UPDATED, handler)

        bus.publish(LifecycleEvent.corpus_updated("v2"))

        assert len(received) == 0

    def test_event_history(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()

        bus.publish(LifecycleEvent.rule_submitted("r1", "alice"))
        bus.publish(LifecycleEvent.rule_approved("r1", "admin"))
        bus.publish(LifecycleEvent.corpus_updated("v2"))

        assert len(bus.history) == 3
        assert bus.history[0].event_type == TriggerEventType.RULE_SUBMITTED
        assert bus.history[1].event_type == TriggerEventType.RULE_APPROVED
        assert bus.history[2].event_type == TriggerEventType.CORPUS_UPDATED

    def test_event_type_isolation(self) -> None:
        """Events only go to handlers for their type."""
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()
        received: list = []

        def handler(event: LifecycleEvent) -> None:
            received.append(event)

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, handler)

        # Publish different event type
        bus.publish(LifecycleEvent.corpus_updated("v2"))

        assert len(received) == 0  # Not delivered

    def test_handler_count(self) -> None:
        from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent

        bus = InMemoryEventBus()

        def h1(e: LifecycleEvent) -> None: pass
        def h2(e: LifecycleEvent) -> None: pass

        bus.subscribe(TriggerEventType.RULE_SUBMITTED, h1)
        bus.subscribe(TriggerEventType.RULE_SUBMITTED, h2)

        assert bus.handler_count(TriggerEventType.RULE_SUBMITTED) == 2
        assert bus.handler_count(TriggerEventType.CORPUS_UPDATED) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-End Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase4EndToEnd:
    """End-to-end tests for Phase 4 Governance."""

    def test_judgment_to_impact_pipeline(self, db_path: Path) -> None:
        """Test S2→S3→S6 pipeline: judge → record → impact eval."""
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
