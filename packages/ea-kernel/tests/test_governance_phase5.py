"""Phase 5 Governance Automation Tests.

Tests for:
- LifecycleController (S1, S5, S6 automation)
- Event-Driven Workflow
- Auto-Promotion Logic
- Notification Routing
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ea_kernel.governance_types import (
    RuleLifecycle,
    RuleLifecycleState, 
    RuleProvenance, 
    TriggerEventType,
    RuleAsset,
)
from ea_kernel.lifecycle_events import InMemoryEventBus, LifecycleEvent
from ea_kernel.notification_service import MockNotificationService
from ea_kernel.rule_asset_store import RuleAssetStore, SQLiteRuleAssetStore
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
def tmp_path(request: pytest.FixtureRequest) -> Path:
    return request.getfixturevalue("tmp_path")

@pytest.fixture
def rule_store(tmp_path: Path) -> RuleAssetStore:
    db_path = tmp_path / "rules_p5.db"
    store = SQLiteRuleAssetStore(db_path)
    # store initialized implicitly or check if needed
    return store

@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()

@pytest.fixture
def notifier() -> MockNotificationService:
    return MockNotificationService()

@pytest.fixture
def controller(
    event_bus, 
    rule_store, 
    notifier,
) -> LifecycleController:
    from ea_kernel.lifecycle_controller import LifecycleController
    return LifecycleController(
        event_bus=event_bus,
        rule_store=rule_store,
        corpus_store=None,  # Not testing corpus store here
        notification_service=notifier,
    )

def make_rule_asset(store: RuleAssetStore, rule_id: str, state: RuleLifecycleState) -> None:
    """Helper: Create and store a rule asset."""
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="Source",
        target_pattern="Target",
        relationship_name="relates",
    )
    meta = RuleMetadata(
        domain="test",
        tags=(),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="test",
        established_version="1.0",
        rationale="test",
        group=RuleGroup.FLOW,
    )
    entry = RuleCorpusEntry(rule=rule, metadata=meta)
    provenance = RuleProvenance(
        author="human:author",
        source_type="manual",
        source_reference="test-ref",
    )
    
    # Must create as DRAFT first
    lifecycle_draft = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    asset = RuleAsset(entry=entry, provenance=provenance, lifecycle=lifecycle_draft)
    store.create(asset)
    
    # Transition to target state
    if state == RuleLifecycleState.REVIEW:
        store.transition(rule_id, RuleLifecycleState.REVIEW, "human:author", "Submit")
    elif state == RuleLifecycleState.APPROVED:
        store.transition(rule_id, RuleLifecycleState.REVIEW, "human:author", "Submit")
        store.transition(rule_id, RuleLifecycleState.APPROVED, "human:reviewer", "Approve")
    elif state == RuleLifecycleState.DEPRECATED:
        store.transition(rule_id, RuleLifecycleState.REVIEW, "human:author", "Submit")
        store.transition(rule_id, RuleLifecycleState.APPROVED, "human:reviewer", "Approve")
        store.transition(rule_id, RuleLifecycleState.DEPRECATED, "human:admin", "Deprecate")

# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestLifecycleControllerEvents:
    
    def test_rule_submitted_notification(
        self, 
        controller, 
        rule_store, 
        event_bus, 
        notifier,
    ) -> None:
        """RULE_SUBMITTED triggers notification to reviewer."""
        # Setup: Create rule in Draft/Review
        make_rule_asset(rule_store, "rule-sub", RuleLifecycleState.DRAFT)
        
        # Trigger event
        event_bus.publish(LifecycleEvent.rule_submitted("rule-sub", "human:author"))
        
        # Check notification
        assert len(notifier.sent) == 1
        assert notifier.sent[0].recipient == "role:reviewer"
        assert "rule-sub" in notifier.sent[0].subject

    def test_rule_approved_notification(
        self, 
        controller, 
        rule_store, 
        event_bus, 
        notifier,
    ) -> None:
        """RULE_APPROVED triggers notification to author and subscribers."""
        # Setup
        make_rule_asset(rule_store, "rule-app", RuleLifecycleState.APPROVED)
        
        # Trigger event
        event_bus.publish(LifecycleEvent.rule_approved("rule-app", "human:admin"))
        
        # Check notifications
        assert len(notifier.sent) >= 2
        # To author
        assert any(n.recipient == "human:author" for n in notifier.sent)
        # To subscribers
        assert any(n.recipient == "role:subscriber" for n in notifier.sent)

    def test_corpus_updated_notification(
        self, 
        controller, 
        event_bus, 
        notifier,
    ) -> None:
        """CORPUS_UPDATED triggers general notification."""
        event_bus.publish(LifecycleEvent.corpus_updated("v2.5.0", "v2.4.0"))
        
        assert len(notifier.sent) >= 1
        assert "v2.5.0" in notifier.sent[0].subject


class TestAutoPromotion:
    
    def test_auto_promotion_flow(
        self,
        tmp_path,
        rule_store,
        event_bus,
        notifier,
    ) -> None:
        """Test AnalysisReport -> Promotion Proposal -> Notification."""
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.evidence_analyzer import (
            AnalysisReport, 
            RuleEffectiveness,
            EffectivenessGrade
        )
        from ea_kernel.lifecycle_controller import LifecycleController
        from ea_kernel.promotion_engine import PromotionEngine
        from ea_kernel.what_if_simulator import WhatIfSimulator, SimulationResult, ImpactLevel
        
        # Setup Mocks / Engines
        decision_store = SQLiteDecisionStore(tmp_path / "decisions_p5.db")
        # decision_store.initialize() # Not needed for SQLiteDecisionStore
        
        promotion_engine = PromotionEngine(rule_store)
        what_if_simulator = WhatIfSimulator(decision_store)
        
        # Mock WhatIfSimulator by subclassing since it uses assertions (slots)
        class MockSimulator(WhatIfSimulator):
            def simulate(self, changes, limit=1000):
                return SimulationResult(
                    simulation_id="sim-mock",
                    created_at="",
                    changes=tuple(changes),
                    safe_to_apply=True,
                    impact_level=ImpactLevel.LOW,
                )
        
        what_if_simulator = MockSimulator(decision_store)
        
        controller = LifecycleController(
            event_bus=event_bus,
            rule_store=rule_store,
            corpus_store=None,
            notification_service=notifier,
            promotion_engine=promotion_engine,
            what_if_simulator=what_if_simulator,
        )
        
        # Setup: Rule in REVIEW state
        make_rule_asset(rule_store, "rule-promo", RuleLifecycleState.REVIEW)
        
        # Create fake AnalysisReport with good effectiveness for rule-promo
        eff = RuleEffectiveness(
            rule_id="rule-promo",
            domain="test",
            total_evaluations=100,
            match_count=50,
            win_count=40,
            override_count=0,
            shadow_count=0,
        )
        
        report = AnalysisReport(
            report_id="report-001",
            corpus_version_id="v1",
            analysis_period_start="",
            analysis_period_end="",
            created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
            total_decisions_analyzed=100,
            rule_effectiveness=(eff,),
            conflict_hotspots=(),
            usage_profiles=(),
        )
        
        # Execute Auto-Promotion
        controller.run_auto_promotion(report)
        
        # Check: Proposal created
        proposals = promotion_engine.list_proposals()
        assert len(proposals) == 1
        assert proposals[0].rule_id == "rule-promo"
        assert "Auto-promotion" in proposals[0].rationale
        
        # Check: Notification sent
        assert len(notifier.sent) == 1
        assert "Auto-Promotion Proposal" in notifier.sent[0].subject
        assert "rule-promo" in notifier.sent[0].subject

