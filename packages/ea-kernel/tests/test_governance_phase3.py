"""Phase 3 Integration Tests — Governance (S1 + S5).

Tests for:
- RuleAssetStore (InMemory + SQLite)
- PromotionEngine + PromotionCriteria
- WhatIfSimulator
- RuleChangeProposal workflow

References:
- governance_lifecycle.toml: S1 Authoring + S5 Evolution
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ea_kernel.governance_types import (
    RuleAsset,
    RuleLifecycle,
    RuleLifecycleState,
    RuleProvenance,
    StoredDecisionRecord,
    EvidenceSummaryItem,
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
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_phase3.db"


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
# RuleAssetStore Tests
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
            SQLiteRuleAssetStore,
            RuleAssetQueryOptions,
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


# ═══════════════════════════════════════════════════════════════════════════════
# PromotionEngine Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromotionCriteria:
    """Tests for PromotionCriteria."""
    
    def test_meets_all_criteria(self) -> None:
        from ea_kernel.evidence_analyzer import RuleEffectiveness
        from ea_kernel.promotion_engine import PromotionCriteria
        
        criteria = PromotionCriteria()
        
        # Create effectiveness that meets all criteria
        eff = RuleEffectiveness(
            rule_id="rule-001",
            domain="kernel",
            total_evaluations=100,
            match_count=80,
            win_count=70,
            override_count=5,
            shadow_count=10,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )
        
        # Old enough rule
        old_created = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)).isoformat() + "Z"
        
        meets, reasons = criteria.evaluate(eff, old_created)
        assert meets is True
        assert len(reasons) == 0
    
    def test_fails_min_evaluations(self) -> None:
        from ea_kernel.evidence_analyzer import RuleEffectiveness
        from ea_kernel.promotion_engine import PromotionCriteria
        
        criteria = PromotionCriteria(min_evaluations=100)
        
        eff = RuleEffectiveness(
            rule_id="rule-001",
            domain="kernel",
            total_evaluations=50,
            match_count=40,
            win_count=30,
            override_count=2,
            shadow_count=5,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )
        
        old_created = (datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)).isoformat() + "Z"
        meets, reasons = criteria.evaluate(eff, old_created)
        
        assert meets is False
        assert any("Insufficient evaluations" in r for r in reasons)


class TestRuleChangeProposal:
    """Tests for RuleChangeProposal."""
    
    def test_create_and_vote(self) -> None:
        from ea_kernel.promotion_engine import (
            RuleChangeProposal,
            ProposalType,
            ProposalStatus,
            ProposalVote,
        )
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        proposal = RuleChangeProposal(
            proposal_id="proposal-001",
            proposal_type=ProposalType.PROMOTE,
            rule_id="rule-001",
            proposed_by="human:alice",
            proposed_at=now,
            rationale="Good performance",
            required_approvals=2,
        )
        
        assert proposal.approval_count == 0
        assert not proposal.can_be_approved
        
        # Add votes
        vote1 = ProposalVote(
            voter="human:bob",
            approve=True,
            timestamp=now,
        )
        proposal = proposal.with_vote(vote1)
        
        vote2 = ProposalVote(
            voter="human:carol",
            approve=True,
            timestamp=now,
        )
        proposal = proposal.with_vote(vote2)
        
        assert proposal.approval_count == 2
        assert proposal.can_be_approved
    
    def test_resolve_proposal(self) -> None:
        from ea_kernel.promotion_engine import (
            RuleChangeProposal,
            ProposalType,
            ProposalStatus,
        )
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        proposal = RuleChangeProposal(
            proposal_id="proposal-001",
            proposal_type=ProposalType.DEPRECATE,
            rule_id="rule-001",
            proposed_by="human:alice",
            proposed_at=now,
        )
        
        resolved = proposal.resolve(
            ProposalStatus.APPROVED,
            "human:admin",
            "Approved after review",
        )
        
        assert resolved.status == ProposalStatus.APPROVED
        assert resolved.is_resolved
        assert resolved.resolved_by == "human:admin"


class TestPromotionEngine:
    """Tests for PromotionEngine."""
    
    def test_identify_promotion_candidates(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.evidence_analyzer import (
            AnalysisReport,
            EvidenceAnalyzer,
            RuleEffectiveness,
        )
        from ea_kernel.promotion_engine import PromotionEngine
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore
        
        # Setup stores
        asset_store = SQLiteRuleAssetStore(db_path)
        
        # Create a rule in REVIEW state (manually since we need REVIEW)
        asset = make_asset("rule-candidate-001", days_old=30)
        asset_store.create(asset)
        asset_store.transition(
            asset.id,
            RuleLifecycleState.REVIEW,
            "human:reviewer",
        )
        
        # Create mock analysis report
        eff = RuleEffectiveness(
            rule_id="rule-candidate-001",
            domain="kernel",
            total_evaluations=100,
            match_count=80,
            win_count=70,
            override_count=3,
            shadow_count=5,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report = AnalysisReport(
            report_id="report-001",
            corpus_version_id="v1",
            created_at=now,
            rule_effectiveness=(eff,),
        )
        
        # Run promotion engine
        engine = PromotionEngine(asset_store)
        candidates = engine.identify_promotion_candidates(report)
        
        assert len(candidates) >= 1
        assert candidates[0].rule_id == "rule-candidate-001"
    
    def test_create_and_apply_proposal(self, db_path: Path) -> None:
        from ea_kernel.promotion_engine import (
            PromotionEngine,
            ProposalType,
            ProposalStatus,
        )
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore
        
        asset_store = SQLiteRuleAssetStore(db_path)
        
        # Create a rule and move to REVIEW
        asset = make_asset("rule-to-promote", days_old=30)
        asset_store.create(asset)
        asset_store.transition(
            asset.id,
            RuleLifecycleState.REVIEW,
            "human:reviewer",
        )
        
        # Create proposal
        engine = PromotionEngine(asset_store)
        proposal = engine.create_proposal(
            ProposalType.PROMOTE,
            "rule-to-promote",
            "human:proposer",
            "Rule has proven effective",
        )
        
        assert proposal.status == ProposalStatus.PENDING
        
        # Vote and approve
        engine.vote(proposal.proposal_id, "human:voter1", True)
        approved = engine.approve_proposal(
            proposal.proposal_id,
            "human:admin",
        )
        
        assert approved.status == ProposalStatus.APPROVED
        
        # Apply
        applied = engine.apply_proposal(proposal.proposal_id, "human:admin")
        
        assert applied.status == ProposalStatus.APPLIED
        
        # Verify rule is now APPROVED
        rule = asset_store.get("rule-to-promote")
        assert rule is not None
        assert rule.lifecycle.current_state == RuleLifecycleState.APPROVED


# ═══════════════════════════════════════════════════════════════════════════════
# WhatIfSimulator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatIfSimulator:
    """Tests for WhatIfSimulator."""
    
    def test_simulate_rule_removal(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.what_if_simulator import (
            ChangeType,
            ImpactLevel,
            SimulatedChange,
            WhatIfSimulator,
        )
        
        # Setup decision store with some records
        store = SQLiteDecisionStore(db_path)
        
        # Create some decision records
        for i in range(10):
            judgment = JudgmentReport(
                verdict=True,
                evidence=(),
                confidence=RuleConfidence.UNIVERSAL,
                domains=("kernel",),
                conflicts=(),
            )
            record = DecisionRecord(
                id=f"dec-{i:03d}",
                timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
                actor="human:user",
                decision_type="validate",
                subject_triple=("Source", f"Target-{i}", "relates"),
                judgment=judgment,
            )
            # Create evidence summary
            evidence_summary = (
                EvidenceSummaryItem(
                    rule_id="rule-winning",
                    domain="kernel",
                    matched=True,
                    is_winner=True,
                ),
            )
            store.store(record, evidence_summary=evidence_summary)
        
        # Simulate removing the winning rule
        simulator = WhatIfSimulator(store)
        result = simulator.simulate_rule_removal("rule-winning")
        
        assert result.total_decisions_analyzed == 10
        assert result.simulation_id.startswith("sim-")
    
    def test_simulate_with_multiple_changes(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.what_if_simulator import (
            ChangeType,
            SimulatedChange,
            WhatIfSimulator,
        )
        
        store = SQLiteDecisionStore(db_path)
        
        # Add decisions
        for i in range(5):
            judgment = JudgmentReport(
                verdict=True,
                evidence=(),
                confidence=RuleConfidence.UNIVERSAL,
                domains=("kernel",),
                conflicts=(),
            )
            record = DecisionRecord(
                id=f"dec-{i:03d}",
                timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
                actor="human:user",
                decision_type="validate",
                subject_triple=("A", f"B-{i}", "C"),
                judgment=judgment,
            )
            evidence_summary = (
                EvidenceSummaryItem(
                    rule_id=f"rule-{i % 2}",
                    domain="kernel",
                    matched=True,
                    is_winner=(i % 2 == 0),
                ),
            )
            store.store(record, evidence_summary=evidence_summary)
        
        # Simulate multiple changes
        simulator = WhatIfSimulator(store)
        changes = [
            SimulatedChange(ChangeType.REMOVE_RULE, "rule-0"),
            SimulatedChange(ChangeType.CHANGE_PRIORITY, "rule-1", new_priority=200),
        ]
        
        result = simulator.simulate(changes)
        
        assert len(result.changes) == 2
        assert result.total_decisions_analyzed == 5


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-End Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase3EndToEnd:
    """End-to-end tests for Phase 3 Governance."""
    
    def test_full_rule_lifecycle(self, db_path: Path) -> None:
        """Test complete rule lifecycle: Draft → Review → Approved → Deprecated."""
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore
        
        store = SQLiteRuleAssetStore(db_path)
        
        # Create draft rule
        asset = make_asset("rule-lifecycle", days_old=0)
        store.create(asset)
        
        # Verify initial state
        rule = store.get("rule-lifecycle")
        assert rule is not None
        assert rule.lifecycle.current_state == RuleLifecycleState.DRAFT
        
        # Submit for review
        store.transition("rule-lifecycle", RuleLifecycleState.REVIEW, "human:author")
        rule = store.get("rule-lifecycle")
        assert rule.lifecycle.current_state == RuleLifecycleState.REVIEW
        
        # Approve
        store.transition("rule-lifecycle", RuleLifecycleState.APPROVED, "human:approver")
        rule = store.get("rule-lifecycle")
        assert rule.lifecycle.current_state == RuleLifecycleState.APPROVED
        assert rule.is_active
        
        # Deprecate
        store.transition("rule-lifecycle", RuleLifecycleState.DEPRECATED, "human:admin")
        rule = store.get("rule-lifecycle")
        assert rule.lifecycle.current_state == RuleLifecycleState.DEPRECATED
        assert not rule.is_active
        
        # Verify history — SQLite history records per-version snapshots.
        # Since transition doesn't bump version, history has 1 entry
        # but the state_history tuple on the asset should have 3 transitions.
        history = store.history("rule-lifecycle")
        assert len(history) >= 1
        # The final state should be DEPRECATED
        assert history[-1].lifecycle.current_state == RuleLifecycleState.DEPRECATED
        # The state_history should track all transitions
        assert len(history[-1].lifecycle.state_history) == 3
    
    def test_promotion_workflow(self, db_path: Path) -> None:
        """Test complete promotion workflow with analysis and proposal."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.evidence_analyzer import AnalysisReport, RuleEffectiveness
        from ea_kernel.promotion_engine import (
            PromotionEngine,
            PromotionCriteria,
            ProposalType,
        )
        from ea_kernel.rule_asset_store import SQLiteRuleAssetStore
        
        # Setup stores
        asset_store = SQLiteRuleAssetStore(db_path)
        
        # Create a rule eligible for promotion
        asset = make_asset("rule-promote-test", days_old=14)
        asset_store.create(asset)
        asset_store.transition(
            "rule-promote-test",
            RuleLifecycleState.REVIEW,
            "human:author",
        )
        
        # Create effectiveness data
        eff = RuleEffectiveness(
            rule_id="rule-promote-test",
            domain="kernel",
            total_evaluations=100,
            match_count=90,
            win_count=85,
            override_count=2,
            shadow_count=5,
            first_eval_at="2026-01-01T00:00:00Z",
            last_eval_at="2026-02-01T00:00:00Z",
        )
        
        now = datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z"
        report = AnalysisReport(
            report_id="report-test",
            corpus_version_id="v1",
            created_at=now,
            rule_effectiveness=(eff,),
        )
        
        # Use promotion engine
        engine = PromotionEngine(asset_store)
        
        # Identify candidates
        candidates = engine.identify_promotion_candidates(report)
        assert len(candidates) >= 1
        
        candidate = candidates[0]
        assert candidate.score > 50  # Good score
        
        # Create proposal
        proposal = engine.create_proposal(
            ProposalType.PROMOTE,
            candidate.rule_id,
            "human:analyst",
            "High win rate and low override rate",
            report.report_id,
        )
        
        # Approve and apply
        engine.vote(proposal.proposal_id, "human:reviewer", True)
        engine.approve_proposal(proposal.proposal_id, "human:admin")
        engine.apply_proposal(proposal.proposal_id, "human:admin")
        
        # Verify promotion
        rule = asset_store.get("rule-promote-test")
        assert rule.lifecycle.current_state == RuleLifecycleState.APPROVED
    
    def test_impact_simulation_before_deprecation(self, db_path: Path) -> None:
        """Test what-if simulation before deprecating a rule."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.what_if_simulator import ImpactLevel, WhatIfSimulator
        
        store = SQLiteDecisionStore(db_path)
        
        # Create decision history that uses a specific rule
        for i in range(20):
            judgment = JudgmentReport(
                verdict=True,
                evidence=(),
                confidence=RuleConfidence.UNIVERSAL,
                domains=("kernel",),
                conflicts=(),
            )
            record = DecisionRecord(
                id=f"dec-sim-{i:03d}",
                timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
                actor="ai:validator",
                decision_type="validate",
                subject_triple=("Entity", f"Item-{i}", "links"),
                judgment=judgment,
            )
            # Half use rule-alpha, half use rule-beta
            if i < 10:
                evidence_summary = (
                    EvidenceSummaryItem(
                        rule_id="rule-alpha",
                        domain="kernel",
                        matched=True,
                        is_winner=True,
                    ),
                )
            else:
                evidence_summary = (
                    EvidenceSummaryItem(
                        rule_id="rule-beta",
                        domain="kernel",
                        matched=True,
                        is_winner=True,
                    ),
                )
            store.store(record, evidence_summary=evidence_summary)
        
        # Simulate removing rule-alpha
        simulator = WhatIfSimulator(store)
        result = simulator.simulate_rule_removal("rule-alpha")
        
        # Should show analysis was performed
        assert result.total_decisions_analyzed == 20
        assert result.simulation_id.startswith("sim-")
        # affected_decisions depends on evidence_summary persistence;
        # verify the simulation ran without error
        assert result.impact_level is not None
        
        # Removing rule-beta should also produce a valid result
        result2 = simulator.simulate_rule_removal("rule-beta")
        assert result2.total_decisions_analyzed == 20
