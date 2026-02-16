"""Tests for rule_asset_store — InMemory + SQLite implementations.

Extracted from test_governance_phase3.py for module-level focus.

Tests:
- InMemoryRuleAssetStore CRUD + lifecycle transitions
- SQLiteRuleAssetStore persistence + querying
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from ea_kernel.governance_types import (
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
)
from ea_kernel.types import (
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_rule_asset_store.db"


@pytest.fixture
def sample_entry() -> RuleCorpusEntry:
    """Sample RuleCorpusEntry for testing."""
    rule = KernelValidityRule(
        id="rule-test-001",
        source_pattern="Feature",
        target_pattern="Component",
        relationship_name="contains",
        valid=True,
        priority=100,
    )
    meta = RuleMetadata(
        domain="test",
        tags=("test", "phase3"),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="test",
        established_version="1.0.0",
        rationale="Test rule",
        group=RuleGroup.FLOW,
    )
    return RuleCorpusEntry(rule=rule, metadata=meta)


@pytest.fixture
def sample_asset(sample_entry: RuleCorpusEntry) -> RuleAsset:
    """Sample RuleAsset in DRAFT state."""
    now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
    provenance = RuleProvenance(
        author="human:tester",
        source_type="manual",
        source_reference="test",
        created_at=now,
        updated_at=now,
        version=1,
    )
    lifecycle = RuleLifecycle(
        current_state=RuleLifecycleState.DRAFT,
        state_history=(),
    )
    return RuleAsset(
        entry=sample_entry,
        provenance=provenance,
        lifecycle=lifecycle,
    )


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


def make_asset(
    rule_id: str,
    state: RuleLifecycleState = RuleLifecycleState.DRAFT,
    domain: str = "kernel",
    days_old: int = 0,
) -> RuleAsset:
    """Helper to create RuleAsset."""
    created = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_old)
    now = datetime.now(UTC).replace(tzinfo=None)

    provenance = RuleProvenance(
        author="human:tester",
        source_type="manual",
        source_reference="test",
        created_at=created.isoformat() + "Z",
        updated_at=now.isoformat() + "Z",
        version=1,
    )

    lifecycle = RuleLifecycle(
        current_state=state,
        state_history=(),
    )

    return RuleAsset(
        entry=make_rule_entry(rule_id, domain),
        provenance=provenance,
        lifecycle=lifecycle,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryRuleAssetStore Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestInMemoryRuleAssetStore:
    """Tests for InMemoryRuleAssetStore."""

    def test_create_and_get(self, sample_asset: RuleAsset) -> None:
        from ea_kernel.rule_asset_store import InMemoryRuleAssetStore

        store = InMemoryRuleAssetStore()
        created = store.create(sample_asset)

        assert created.id == sample_asset.id

        retrieved = store.get(sample_asset.id)
        assert retrieved is not None
        assert retrieved.id == sample_asset.id

    def test_create_duplicate_fails(self, sample_asset: RuleAsset) -> None:
        from ea_kernel.rule_asset_store import InMemoryRuleAssetStore

        store = InMemoryRuleAssetStore()
        store.create(sample_asset)

        with pytest.raises(ValueError, match="already exists"):
            store.create(sample_asset)

    def test_transition_lifecycle(self, sample_asset: RuleAsset) -> None:
        from ea_kernel.rule_asset_store import InMemoryRuleAssetStore

        store = InMemoryRuleAssetStore()
        store.create(sample_asset)

        # Draft -> Review
        review = store.transition(
            sample_asset.id,
            RuleLifecycleState.REVIEW,
            "human:reviewer",
        )
        assert review.lifecycle.current_state == RuleLifecycleState.REVIEW

        # Review -> Approved
        approved = store.transition(
            sample_asset.id,
            RuleLifecycleState.APPROVED,
            "human:approver",
        )
        assert approved.lifecycle.current_state == RuleLifecycleState.APPROVED

    def test_update_entry(self, sample_asset: RuleAsset) -> None:
        from ea_kernel.rule_asset_store import InMemoryRuleAssetStore

        store = InMemoryRuleAssetStore()
        store.create(sample_asset)

        # Create modified entry
        new_entry = make_rule_entry("rule-test-001", domain="updated")

        updated = store.update_entry(
            sample_asset.id,
            new_entry,
            "human:editor",
        )

        assert updated.metadata.domain == "updated"
        assert updated.provenance.version == 2

    def test_history(self, sample_asset: RuleAsset) -> None:
        from ea_kernel.rule_asset_store import InMemoryRuleAssetStore

        store = InMemoryRuleAssetStore()
        store.create(sample_asset)

        # Make transitions
        store.transition(sample_asset.id, RuleLifecycleState.REVIEW, "human:a")
        store.transition(sample_asset.id, RuleLifecycleState.APPROVED, "human:b")

        history = store.history(sample_asset.id)
        assert len(history) == 3
        assert history[0].lifecycle.current_state == RuleLifecycleState.DRAFT
        assert history[2].lifecycle.current_state == RuleLifecycleState.APPROVED

    def test_list_by_state(self) -> None:
        from ea_kernel.rule_asset_store import InMemoryRuleAssetStore

        store = InMemoryRuleAssetStore()

        # Create assets in different states
        draft = make_asset("rule-draft-001", RuleLifecycleState.DRAFT)
        review = make_asset("rule-review-001", RuleLifecycleState.REVIEW)
        approved = make_asset("rule-approved-001", RuleLifecycleState.APPROVED)

        # Need to handle non-DRAFT creation
        store._assets[draft.id] = draft
        store._history[draft.id] = [draft]
        store._assets[review.id] = review
        store._history[review.id] = [review]
        store._assets[approved.id] = approved
        store._history[approved.id] = [approved]

        drafts = store.list_by_state(RuleLifecycleState.DRAFT)
        assert len(drafts) == 1

        active = store.active_rules()
        assert len(active) == 1
        assert active[0].id == "rule-approved-001"


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteRuleAssetStore Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSQLiteRuleAssetStore:
    """Tests for SQLiteRuleAssetStore."""

    def test_create_and_get(
        self, db_path: Path, sample_asset: RuleAsset,
    ) -> None:
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        store = SQLiteRuleAssetStore(db_path)
        created = store.create(sample_asset)

        assert created.id == sample_asset.id

        # New instance should still find it
        store2 = SQLiteRuleAssetStore(db_path)
        retrieved = store2.get(sample_asset.id)
        assert retrieved is not None
        assert retrieved.id == sample_asset.id

    def test_transition_lifecycle(
        self, db_path: Path, sample_asset: RuleAsset,
    ) -> None:
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        store = SQLiteRuleAssetStore(db_path)
        store.create(sample_asset)

        # Full lifecycle
        store.transition(sample_asset.id, RuleLifecycleState.REVIEW, "human:a")
        store.transition(sample_asset.id, RuleLifecycleState.APPROVED, "human:b")
        store.transition(sample_asset.id, RuleLifecycleState.DEPRECATED, "human:c")

        final = store.get(sample_asset.id)
        assert final is not None
        assert final.lifecycle.current_state == RuleLifecycleState.DEPRECATED

    def test_version_history(
        self, db_path: Path, sample_asset: RuleAsset,
    ) -> None:
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

        store = SQLiteRuleAssetStore(db_path)
        store.create(sample_asset)

        # Update entry
        new_entry = make_rule_entry("rule-test-001", domain="v2")
        store.update_entry(sample_asset.id, new_entry, "human:editor")

        # Get specific version
        v1 = store.get_version(sample_asset.id, 1)
        v2 = store.get_version(sample_asset.id, 2)

        assert v1 is not None
        assert v2 is not None
        assert v1.metadata.domain == "test"
        assert v2.metadata.domain == "v2"

    def test_query_with_filters(self, db_path: Path) -> None:
        from ea_kernel.rule_asset_store import (
            RuleAssetQueryOptions,
            SQLiteRuleAssetStore,
        )

        store = SQLiteRuleAssetStore(db_path)

        # Create multiple assets
        for i in range(5):
            asset = make_asset(f"rule-{i:03d}", domain="kernel" if i < 3 else "profile")
            store.create(asset)

        # Query by domain
        options = RuleAssetQueryOptions(domain="kernel")
        results = store.query(options)
        assert len(results) == 3

        # Query all
        all_results = store.query()
        assert len(all_results) == 5

    def test_active_rules_not_capped_by_default_query_limit(self, db_path: Path) -> None:
        from ea_kernel.rule_asset_store import (
            RuleAssetQueryOptions,
            SQLiteRuleAssetStore,
        )

        store = SQLiteRuleAssetStore(db_path)

        for i in range(120):
            asset = make_asset(f"rule-active-{i:03d}")
            store.create(asset)
            store.transition(asset.id, RuleLifecycleState.REVIEW, "human:reviewer")
            store.transition(asset.id, RuleLifecycleState.APPROVED, "human:approver")

        approved_query = store.query(RuleAssetQueryOptions(state=RuleLifecycleState.APPROVED))
        assert len(approved_query) == 100

        # active_rules/list_by_state must return the complete approved set.
        assert len(store.list_by_state(RuleLifecycleState.APPROVED)) == 120
        assert len(store.active_rules()) == 120
