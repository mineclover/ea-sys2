"""Phase 1 Integration Tests — Foundation (S3 + Versioning).

Tests for the Governance Lifecycle Phase 1 implementation:
- governance_types: RuleLifecycle, RuleAsset, StoredDecisionRecord, etc.
- decision_store: DecisionStore ABC, InMemory, SQLite implementations
- corpus_version_store: CorpusVersionStore ABC, InMemory, SQLite implementations
- decision_ledger: Store integration

References:
- docs/governance_lifecycle_todo.md: Phase 1 specifications
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from ea_kernel.corpus_version_store import (
    InMemoryCorpusVersionStore,
    SQLiteCorpusVersionStore,
)
from ea_kernel.decision_ledger import DecisionLedger
from ea_kernel.decision_store import (
    InMemoryDecisionStore,
    SQLiteDecisionStore,
)
from ea_kernel.governance_types import (
    DecisionQueryOptions,
    JudgmentStatistics,
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
    is_valid_transition,
)
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Test: Governance Types (Task 1.1)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleLifecycleState:
    """Test RuleLifecycleState and transitions."""

    def test_valid_transitions(self) -> None:
        """Test valid state transitions."""
        # DRAFT → REVIEW
        assert is_valid_transition(RuleLifecycleState.DRAFT, RuleLifecycleState.REVIEW)

        # REVIEW → APPROVED | DRAFT
        assert is_valid_transition(RuleLifecycleState.REVIEW, RuleLifecycleState.APPROVED)
        assert is_valid_transition(RuleLifecycleState.REVIEW, RuleLifecycleState.DRAFT)

        # APPROVED → DEPRECATED
        assert is_valid_transition(RuleLifecycleState.APPROVED, RuleLifecycleState.DEPRECATED)

    def test_invalid_transitions(self) -> None:
        """Test invalid state transitions."""
        # DRAFT → APPROVED (skip REVIEW)
        assert not is_valid_transition(RuleLifecycleState.DRAFT, RuleLifecycleState.APPROVED)

        # DRAFT → DEPRECATED
        assert not is_valid_transition(RuleLifecycleState.DRAFT, RuleLifecycleState.DEPRECATED)

        # DEPRECATED → * (terminal state)
        assert not is_valid_transition(RuleLifecycleState.DEPRECATED, RuleLifecycleState.APPROVED)
        assert not is_valid_transition(RuleLifecycleState.DEPRECATED, RuleLifecycleState.DRAFT)

        # APPROVED → DRAFT (no rollback)
        assert not is_valid_transition(RuleLifecycleState.APPROVED, RuleLifecycleState.DRAFT)


class TestRuleLifecycle:
    """Test RuleLifecycle state machine."""

    def test_initial_state(self) -> None:
        """New lifecycle starts in DRAFT."""
        lc = RuleLifecycle()
        assert lc.current_state == RuleLifecycleState.DRAFT
        assert lc.state_history == ()
        assert not lc.is_active

    def test_valid_transition(self) -> None:
        """Valid transition creates new lifecycle with history."""
        lc = RuleLifecycle()
        lc2 = lc.transition(RuleLifecycleState.REVIEW, actor="alice", reason="Ready for review")

        # Original unchanged
        assert lc.current_state == RuleLifecycleState.DRAFT

        # New state
        assert lc2.current_state == RuleLifecycleState.REVIEW
        assert len(lc2.state_history) == 1

        entry = lc2.state_history[0]
        assert entry[1] == "draft"
        assert entry[2] == "review"
        assert entry[3] == "alice"
        assert entry[4] == "Ready for review"

    def test_full_lifecycle(self) -> None:
        """Test complete lifecycle: DRAFT → REVIEW → APPROVED → DEPRECATED."""
        lc = RuleLifecycle()

        lc = lc.transition(RuleLifecycleState.REVIEW, actor="author")
        assert not lc.is_active

        lc = lc.transition(RuleLifecycleState.APPROVED, actor="reviewer")
        assert lc.is_active

        lc = lc.transition(RuleLifecycleState.DEPRECATED, actor="admin")
        assert not lc.is_active

        assert len(lc.state_history) == 3

    def test_invalid_transition_raises(self) -> None:
        """Invalid transition raises ValueError."""
        lc = RuleLifecycle()

        with pytest.raises(ValueError, match="Invalid transition"):
            lc.transition(RuleLifecycleState.APPROVED, actor="hacker")


class TestRuleAsset:
    """Test RuleAsset type."""

    @pytest.fixture
    def sample_entry(self) -> RuleCorpusEntry:
        rule = KernelValidityRule(
            id="test-rule-001",
            source_pattern="feature*",
            target_pattern="item*",
            relationship_name="flow",
            valid=True,
            priority=50,
        )
        meta = RuleMetadata(
            domain="test",
            tags=("flow",),
            category=RuleCategory.BEHAVIORAL,
            confidence=RuleConfidence.COMMON,
            source="test",
            established_version="1.0.0",
            rationale="Test rule",
            group=RuleGroup.FLOW,
        )
        return RuleCorpusEntry(rule=rule, metadata=meta)

    def test_rule_asset_properties(self, sample_entry: RuleCorpusEntry) -> None:
        """RuleAsset exposes entry properties."""
        provenance = RuleProvenance(author="alice", source_type="manual")
        asset = RuleAsset(entry=sample_entry, provenance=provenance)

        assert asset.id == "test-rule-001"
        assert asset.rule == sample_entry.rule
        assert asset.metadata == sample_entry.metadata
        assert not asset.is_active  # DRAFT by default

    def test_rule_asset_with_lifecycle(self, sample_entry: RuleCorpusEntry) -> None:
        """RuleAsset.with_lifecycle returns new asset."""
        provenance = RuleProvenance(author="alice", source_type="manual")
        asset = RuleAsset(entry=sample_entry, provenance=provenance)

        new_lc = asset.lifecycle.transition(RuleLifecycleState.REVIEW, actor="alice")
        new_lc = new_lc.transition(RuleLifecycleState.APPROVED, actor="bob")

        approved_asset = asset.with_lifecycle(new_lc)

        assert asset.lifecycle.current_state == RuleLifecycleState.DRAFT
        assert approved_asset.lifecycle.current_state == RuleLifecycleState.APPROVED
        assert approved_asset.is_active


class TestJudgmentStatistics:
    """Test JudgmentStatistics type."""

    def test_initial_statistics(self) -> None:
        """New statistics have zero counts."""
        stats = JudgmentStatistics(source="A", target="B", relation="flow")

        assert stats.total_judgments == 0
        assert stats.allow_rate == 0.0
        assert stats.override_rate == 0.0

    def test_with_judgment(self) -> None:
        """with_judgment updates statistics."""
        stats = JudgmentStatistics(source="A", target="B", relation="flow")

        stats = stats.with_judgment(
            verdict=True,
            confidence=RuleConfidence.COMMON,
            domains=("kernel",),
        )

        assert stats.total_judgments == 1
        assert stats.allow_count == 1
        assert stats.deny_count == 0
        assert stats.allow_rate == 1.0

        stats = stats.with_judgment(
            verdict=False,
            confidence=RuleConfidence.UNIVERSAL,
            domains=("profile",),
        )

        assert stats.total_judgments == 2
        assert stats.allow_count == 1
        assert stats.deny_count == 1
        assert stats.allow_rate == 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# Test: DecisionStore (Task 1.2)
# ═══════════════════════════════════════════════════════════════════════════════

def make_decision_record(
    source: str = "A",
    target: str = "B",
    relation: str = "flow",
    actor: str = "human:alice",
    decision_type: str = "accept",
) -> DecisionRecord:
    """Factory for test DecisionRecords."""
    return DecisionRecord(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
        actor=actor,
        decision_type=decision_type,
        subject_triple=(source, target, relation),
        judgment=JudgmentReport(
            verdict=True,
            evidence=(),
            confidence=RuleConfidence.COMMON,
            domains=("kernel",),
            conflicts=(),
        ),
    )


class TestInMemoryDecisionStore:
    """Test InMemoryDecisionStore."""

    def test_store_and_get(self) -> None:
        """Store and retrieve a record."""
        store = InMemoryDecisionStore()
        record = make_decision_record()

        stored = store.store(record, corpus_version_id="v1")

        assert stored.storage_id
        assert stored.record == record
        assert stored.corpus_version_id == "v1"

        retrieved = store.get(stored.storage_id)
        assert retrieved == stored

    def test_query_by_triple(self) -> None:
        """Query by triple."""
        store = InMemoryDecisionStore()

        r1 = make_decision_record(source="A", target="B")
        r2 = make_decision_record(source="A", target="C")
        r3 = make_decision_record(source="A", target="B")

        store.store(r1)
        store.store(r2)
        store.store(r3)

        results = store.query(DecisionQueryOptions(triple=("A", "B", "flow")))
        assert len(results) == 2

    def test_query_by_actor(self) -> None:
        """Query by actor prefix."""
        store = InMemoryDecisionStore()

        store.store(make_decision_record(actor="human:alice"))
        store.store(make_decision_record(actor="human:bob"))
        store.store(make_decision_record(actor="ai:assistant"))

        human_results = store.query(DecisionQueryOptions(actor_prefix="human:"))
        assert len(human_results) == 2

        ai_results = store.query(DecisionQueryOptions(actor_prefix="ai:"))
        assert len(ai_results) == 1

    def test_statistics(self) -> None:
        """Statistics are updated on store."""
        store = InMemoryDecisionStore()

        store.store(make_decision_record(source="A", target="B"))
        store.store(make_decision_record(source="A", target="B"))
        store.store(make_decision_record(source="A", target="B", decision_type="override"))

        stats = store.statistics_for("A", "B", "flow")

        assert stats.total_judgments == 3
        assert stats.override_count == 1


class TestSQLiteDecisionStore:
    """Test SQLiteDecisionStore."""

    @pytest.fixture
    def db_path(self) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)

    def test_persistence(self, db_path: Path) -> None:
        """Records persist across store instances."""
        record = make_decision_record()

        # Store in first instance
        store1 = SQLiteDecisionStore(db_path)
        stored = store1.store(record)
        storage_id = stored.storage_id

        # Retrieve in second instance
        store2 = SQLiteDecisionStore(db_path)
        retrieved = store2.get(storage_id)

        assert retrieved is not None
        assert retrieved.record.id == record.id
        assert retrieved.record.subject_triple == record.subject_triple

    def test_query_with_conditions(self, db_path: Path) -> None:
        """Query with multiple conditions."""
        store = SQLiteDecisionStore(db_path)

        store.store(make_decision_record(actor="human:alice", decision_type="accept"))
        store.store(make_decision_record(actor="human:alice", decision_type="override"))
        store.store(make_decision_record(actor="ai:assistant", decision_type="accept"))

        results = store.query(DecisionQueryOptions(
            actor_prefix="human:",
            decision_type="accept",
        ))
        assert len(results) == 1

    def test_count(self, db_path: Path) -> None:
        """Count with filters."""
        store = SQLiteDecisionStore(db_path)

        for _ in range(5):
            store.store(make_decision_record())

        assert store.count() == 5
        assert store.count(DecisionQueryOptions(actor_prefix="human:")) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Test: CorpusVersionStore (Task 1.3)
# ═══════════════════════════════════════════════════════════════════════════════

def make_corpus_entries(count: int = 3) -> tuple[RuleCorpusEntry, ...]:
    """Factory for test corpus entries."""
    entries = []
    for i in range(count):
        rule = KernelValidityRule(
            id=f"rule-{i:03d}",
            source_pattern="*",
            target_pattern="*",
            relationship_name="flow",
            valid=True,
            priority=50,
        )
        meta = RuleMetadata(
            domain="test",
            tags=("flow",),
            category=RuleCategory.BEHAVIORAL,
            confidence=RuleConfidence.COMMON,
            source="test",
            established_version="1.0.0",
            rationale=f"Test rule {i}",
            group=RuleGroup.FLOW,
        )
        entries.append(RuleCorpusEntry(rule=rule, metadata=meta))
    return tuple(entries)


class TestInMemoryCorpusVersionStore:
    """Test InMemoryCorpusVersionStore."""

    def test_create_and_get_version(self) -> None:
        """Create and retrieve a version."""
        store = InMemoryCorpusVersionStore()
        entries = make_corpus_entries(5)

        version = store.create_version(
            corpus_name="test",
            entries=entries,
            description="Initial version",
        )

        assert version.corpus_name == "test"
        assert version.rule_count == 5
        assert len(version.rule_ids) == 5

        retrieved = store.get(version.version_id)
        assert retrieved == version

    def test_get_entries(self) -> None:
        """Retrieve entries for a version."""
        store = InMemoryCorpusVersionStore()
        entries = make_corpus_entries(3)

        version = store.create_version("test", entries)
        retrieved_entries = store.get_entries(version.version_id)

        assert len(retrieved_entries) == 3
        assert retrieved_entries == entries

    def test_get_latest(self) -> None:
        """Get latest version for a corpus."""
        store = InMemoryCorpusVersionStore()

        store.create_version("test", make_corpus_entries(1))
        v2 = store.create_version("test", make_corpus_entries(2))

        latest = store.get_latest("test")
        assert latest is not None
        assert latest.version_id == v2.version_id

    def test_history(self) -> None:
        """Get version history."""
        store = InMemoryCorpusVersionStore()

        for i in range(5):
            store.create_version("test", make_corpus_entries(i + 1))

        history = store.history("test", limit=3)
        assert len(history) == 3
        # History is latest first
        assert history[0].rule_count == 5
        assert history[2].rule_count == 3

    def test_diff(self) -> None:
        """Diff between versions."""
        store = InMemoryCorpusVersionStore()

        entries1 = make_corpus_entries(3)  # rule-000, rule-001, rule-002
        entries2 = make_corpus_entries(4)[:2] + (  # rule-000, rule-001, rule-003
            RuleCorpusEntry(
                rule=KernelValidityRule(
                    id="rule-003",
                    source_pattern="*",
                    target_pattern="*",
                    relationship_name="flow",
                    valid=True,
                    priority=50,
                ),
                metadata=RuleMetadata(
                    domain="test",
                    tags=("flow",),
                    category=RuleCategory.BEHAVIORAL,
                    confidence=RuleConfidence.COMMON,
                    source="test",
                    established_version="1.0.0",
                    rationale="New rule",
                    group=RuleGroup.FLOW,
                ),
            ),
        )

        v1 = store.create_version("test", entries1)
        v2 = store.create_version("test", entries2, parent_version_id=v1.version_id)

        added, removed, modified = store.diff(v1.version_id, v2.version_id)

        assert "rule-003" in added
        assert "rule-002" in removed


class TestSQLiteCorpusVersionStore:
    """Test SQLiteCorpusVersionStore."""

    @pytest.fixture
    def db_path(self) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)

    def test_persistence(self, db_path: Path) -> None:
        """Versions persist across store instances."""
        entries = make_corpus_entries(3)

        store1 = SQLiteCorpusVersionStore(db_path)
        version = store1.create_version("test", entries)
        version_id = version.version_id

        store2 = SQLiteCorpusVersionStore(db_path)
        retrieved = store2.get(version_id)

        assert retrieved is not None
        assert retrieved.rule_count == 3

    def test_entries_round_trip(self, db_path: Path) -> None:
        """Entries are correctly serialized and deserialized."""
        entries = make_corpus_entries(2)

        store = SQLiteCorpusVersionStore(db_path)
        version = store.create_version("test", entries)

        retrieved = store.get_entries(version.version_id)

        assert len(retrieved) == 2
        assert retrieved[0].rule.id == entries[0].rule.id
        assert retrieved[0].metadata.domain == entries[0].metadata.domain


# ═══════════════════════════════════════════════════════════════════════════════
# Test: DecisionLedger Store Integration (Task 1.4)
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionLedgerStoreIntegration:
    """Test DecisionLedger with DecisionStore integration."""

    def test_record_persists_to_store(self) -> None:
        """record() persists to store when attached."""
        store = InMemoryDecisionStore()
        ledger = DecisionLedger(store=store, corpus_version_id="v1")

        record = make_decision_record()
        ledger.record(record)

        # Both in-memory and store should have the record
        assert ledger.count == 1
        assert store.count() == 1

        stored_records = store.query()
        assert stored_records[0].record.id == record.id
        assert stored_records[0].corpus_version_id == "v1"

    def test_record_without_persist(self) -> None:
        """record(persist=False) skips store."""
        store = InMemoryDecisionStore()
        ledger = DecisionLedger(store=store)

        record = make_decision_record()
        ledger.record(record, persist=False)

        assert ledger.count == 1
        assert store.count() == 0

    def test_backward_compatibility(self) -> None:
        """DecisionLedger without store works as before."""
        ledger = DecisionLedger()

        record = make_decision_record()
        ledger.record(record)

        assert ledger.count == 1
        assert ledger.store is None

    def test_with_store(self) -> None:
        """with_store() attaches store to existing ledger."""
        ledger = DecisionLedger()
        ledger.record(make_decision_record())

        store = InMemoryDecisionStore()
        new_ledger = ledger.with_store(store)

        # Shares in-memory state
        assert new_ledger.count == 1
        assert new_ledger.store is store

        # New records persist
        new_ledger.record(make_decision_record())
        assert store.count() == 1

    def test_replay_from_store(self) -> None:
        """replay_from_store() loads records from store."""
        store = InMemoryDecisionStore()

        # Populate store directly
        store.store(make_decision_record())
        store.store(make_decision_record())

        # Create new ledger and replay
        ledger = DecisionLedger(store=store)
        ledger.replay_from_store()

        assert ledger.count == 2

    def test_statistics_for_delegates_to_store(self) -> None:
        """statistics_for() uses store when available."""
        store = InMemoryDecisionStore()
        ledger = DecisionLedger(store=store)

        ledger.record(make_decision_record(source="A", target="B"))
        ledger.record(make_decision_record(source="A", target="B", decision_type="override"))

        stats = ledger.statistics_for("A", "B", "flow")

        # Should return JudgmentStatistics from store
        assert hasattr(stats, "total_judgments")
        assert stats.total_judgments == 2
        assert stats.override_count == 1

    def test_corpus_version_id_tracking(self) -> None:
        """corpus_version_id is tracked and updatable."""
        store = InMemoryDecisionStore()
        ledger = DecisionLedger(store=store, corpus_version_id="v1")

        ledger.record(make_decision_record())

        # Update version
        ledger.corpus_version_id = "v2"
        ledger.record(make_decision_record())

        all_records = store.query()
        versions = {r.corpus_version_id for r in all_records}
        assert versions == {"v1", "v2"}


# ═══════════════════════════════════════════════════════════════════════════════
# Test: End-to-End S3 Data Flow (Task 1.6)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase1EndToEnd:
    """End-to-end tests for Phase 1 S3 data flow."""

    @pytest.fixture
    def db_path(self) -> Path:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        yield path
        path.unlink(missing_ok=True)

    def test_recording_pipeline(self, db_path: Path) -> None:
        """Full recording pipeline: Ledger → Store → Statistics."""
        # Setup
        store = SQLiteDecisionStore(db_path)
        version_store = SQLiteCorpusVersionStore(db_path)

        # Create corpus version
        entries = make_corpus_entries(5)
        version = version_store.create_version("test", entries)

        # Create ledger with stores
        ledger = DecisionLedger(
            store=store,
            corpus_version_id=version.version_id,
        )

        # Record decisions
        for i in range(10):
            record = make_decision_record(
                source="Feature",
                target="Item",
                decision_type="override" if i % 3 == 0 else "accept",
            )
            ledger.record(record)

        # Verify persistence
        assert store.count() == 10

        # Verify statistics
        stats = store.statistics_for("Feature", "Item", "flow")
        assert stats.total_judgments == 10
        assert stats.override_count == 4  # i=0,3,6,9

    def test_corpus_version_diff_workflow(self, db_path: Path) -> None:
        """Corpus versioning workflow with diffs."""
        version_store = SQLiteCorpusVersionStore(db_path)

        # Create initial version
        v1 = version_store.create_version(
            "test",
            make_corpus_entries(3),
            description="Initial rules",
        )

        # Create updated version with one new rule
        new_entries = make_corpus_entries(3) + (
            RuleCorpusEntry(
                rule=KernelValidityRule(
                    id="rule-new",
                    source_pattern="*",
                    target_pattern="*",
                    relationship_name="flow",
                    valid=True,
                    priority=60,
                ),
                metadata=RuleMetadata(
                    domain="test",
                    tags=("new",),
                    category=RuleCategory.BEHAVIORAL,
                    confidence=RuleConfidence.EMPIRICAL,
                    source="test",
                    established_version="1.1.0",
                    rationale="New empirical rule",
                    group=RuleGroup.FLOW,
                ),
            ),
        )

        v2 = version_store.create_version(
            "test",
            new_entries,
            description="Added new rule",
            parent_version_id=v1.version_id,
        )

        # Verify diff
        added, removed, modified = version_store.diff(v1.version_id, v2.version_id)

        assert "rule-new" in added
        assert len(removed) == 0

    def test_judgment_reproducibility(self, db_path: Path) -> None:
        """Decisions are tagged with corpus version for reproducibility."""
        store = SQLiteDecisionStore(db_path)
        version_store = SQLiteCorpusVersionStore(db_path)

        # Create two corpus versions
        v1 = version_store.create_version("test", make_corpus_entries(3))
        v2 = version_store.create_version("test", make_corpus_entries(5))

        # Create ledger with v1
        ledger = DecisionLedger(store=store, corpus_version_id=v1.version_id)
        ledger.record(make_decision_record())

        # Update to v2
        ledger.corpus_version_id = v2.version_id
        ledger.record(make_decision_record())

        # Query by version
        v1_records = store.query(DecisionQueryOptions(corpus_version_id=v1.version_id))
        v2_records = store.query(DecisionQueryOptions(corpus_version_id=v2.version_id))

        assert len(v1_records) == 1
        assert len(v2_records) == 1

        # Can reproduce judgment with original corpus version
        v1_entries = version_store.get_entries(v1.version_id)
        assert len(v1_entries) == 3
