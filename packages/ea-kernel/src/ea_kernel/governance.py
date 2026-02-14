"""Governance Facade — Unified Interface for Governance Lifecycle.

Provides a single entry point (GovernanceSystem) to interact with:
- Rule Authoring (S1)
- Judgment (S2)
- Recording (S3)
- Analysis (S4)
- Evolution (S5)
- Impact (S6)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING


from ea_kernel.corpus_version_store import SQLiteCorpusVersionStore
from ea_kernel.decision_store import SQLiteDecisionStore
from ea_kernel.evidence_analyzer import EvidenceAnalyzer
from ea_kernel.judgment_service import JudgmentService
from ea_kernel.lifecycle_controller import LifecycleController
from ea_kernel.lifecycle_events import InMemoryEventBus
from ea_kernel.notification_service import MockNotificationService
from ea_kernel.promotion_engine import PromotionEngine
from ea_kernel.rule_asset_store import SQLiteRuleAssetStore
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.what_if_simulator import WhatIfSimulator
from ea_kernel.types import KernelSchema, RuleConfidence
from ea_kernel.promotion_engine import PromotionEngine, RuleChangeProposal
from ea_kernel.what_if_simulator import WhatIfSimulator, SimulationResult
from ea_kernel.governance_types import (
    AnalysisReport,
    EnhancedJudgment,
    RuleAsset,
    RuleLifecycleState,
    CorpusVersionInfo,
)


class GovernanceSystem:
    """Unified Governance System Facade."""
    
    def __init__(self, data_dir: Path, schema: KernelSchema) -> None:
        self.data_dir = data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Stores
        self.rule_store = SQLiteRuleAssetStore(data_dir / "rules.db")
        self.decision_store = SQLiteDecisionStore(data_dir / "decisions.db")
        self.version_store = SQLiteCorpusVersionStore(data_dir / "versions.db")
        
        # 2. Engines & Services
        self.event_bus = InMemoryEventBus()
        self.notification = MockNotificationService()
        
        self.analyzer = EvidenceAnalyzer(
            decision_store=self.decision_store,
            version_store=self.version_store,
        )
        
        from ea_kernel.promotion_engine import PromotionCriteria

        self.promotion = PromotionEngine(
            asset_store=self.rule_store,
            criteria=PromotionCriteria(
                min_evaluations=0,
                min_matches=0,
                min_wins=0,
                min_age_days=0,
            )
        )
        
        self.simulator = WhatIfSimulator(
            decision_store=self.decision_store,
            asset_store=self.rule_store,
        )
        
        # 3. Corpus & Judgment
        # We need to inject active rules into the schema so find_matching_rules works
        self._base_schema = schema
        self._rebuild_corpus()
        
        # 4. Controller (Automation)
        self.controller = LifecycleController(
            event_bus=self.event_bus,
            rule_store=self.rule_store,
            corpus_store=self.version_store,
            notification_service=self.notification,
            impact_evaluator=None,  # Not fully wired yet
            promotion_engine=self.promotion,
            what_if_simulator=self.simulator,
            active_corpus=self.corpus,
        )

    def _rebuild_corpus(self) -> None:
        """Rebuild RuleCorpus from active rules + base schema."""
        active_assets = self.rule_store.active_rules()
        active_rules = tuple(asset.rule for asset in active_assets)
        entries = tuple(asset.entry for asset in active_assets)
        
        # Create new schema with active rules
        # Note: We assume base schema rules are foundational and always present
        combined_rules = self._base_schema.validity_rules + active_rules
        
        new_schema = KernelSchema(
            attributes=self._base_schema.attributes,
            entities=self._base_schema.entities,
            relations=self._base_schema.relations,
            validity_rules=combined_rules,
            layer_constraints=self._base_schema.layer_constraints,
        )
        
        self.corpus = RuleCorpus(entries, new_schema)
        
        # Update judgment service reference
        self.judgment = JudgmentService(
            corpus=self.corpus,
            decision_store=self.decision_store,
            auto_record=True, # Default to True
        )
        # If controller exists, update its reference
        if hasattr(self, 'controller'):
            self.controller.active_corpus = self.corpus
            
    # ── Version Management ─────────────────────────────────────────

    def create_snapshot(self, name: str, description: str = "") -> CorpusVersionInfo:
        """Create a persistent snapshot of the current active corpus."""
        return self.version_store.create_version(
            corpus_name=name,
            entries=self.corpus.entries,
            description=description,
            # parent_version_id could be tracked if we maintained current version ID
        )
        
    def list_versions(self, corpus_name: str | None = None) -> tuple[CorpusVersionInfo, ...]:
        """List available corpus versions."""
        if corpus_name:
            return self.version_store.history(corpus_name)
        return self.version_store.query() # all

    def get_corpus_at_version(self, version_id: str) -> RuleCorpus | None:
        """Reconstruct RuleCorpus at a specific version."""
        # Check current first (optional optimization provided caller handles it)
        
        entries = self.version_store.get_entries(version_id)
        if not entries and not self.version_store.get(version_id):
            # Version not found or empty
            if not self.version_store.get(version_id):
                return None
        
        # Convert entries to rules
        rules = tuple(e.rule for e in entries)
        combined_rules = self._base_schema.validity_rules + rules
        
        new_schema = KernelSchema(
            attributes=self._base_schema.attributes,
            entities=self._base_schema.entities,
            relations=self._base_schema.relations,
            validity_rules=combined_rules,
            layer_constraints=self._base_schema.layer_constraints,
        )
        
        return RuleCorpus(entries, new_schema)

    # ── S1 Authoring ───────────────────────────────────────────────

    def submit_rule(self, asset: RuleAsset) -> RuleAsset:
        """S1: Submit a new rule (Draft)."""
        # Save to store
        saved = self.rule_store.create(asset)
        
        # Trigger automation
        from ea_kernel.lifecycle_events import LifecycleEvent
        self.event_bus.publish(LifecycleEvent.rule_submitted(
            rule_id=saved.id, 
            actor=saved.provenance.author
        ))
        return saved
    
    def approve_rule(self, rule_id: str, actor: str) -> RuleAsset:
        """S1/S5: Approve a rule."""
        from ea_kernel.governance_types import RuleLifecycleState
        
        current = self.rule_store.get(rule_id)
        if current and current.lifecycle.current_state == RuleLifecycleState.DRAFT:
             self.rule_store.transition(rule_id, RuleLifecycleState.REVIEW, actor)
        
        approved = self.rule_store.transition(
            rule_id, 
            RuleLifecycleState.APPROVED, 
            actor, 
            "Approved via Facade"
        )
        
        # Rebuild corpus to include new active rule
        self._rebuild_corpus()
        
        # Trigger event
        from ea_kernel.lifecycle_events import LifecycleEvent
        self.event_bus.publish(LifecycleEvent.rule_approved(rule_id, actor))
        
        return approved

    def reject_rule(self, rule_id: str, actor: str, reason: str = "") -> RuleAsset:
        """S1: Reject a rule in review (send back to Draft)."""
        from ea_kernel.governance_types import RuleLifecycleState
        
        # Helper: Ensure it is in REVIEW state or transition it there if DRAFT (not typical for reject but possible logic)
        # Assuming store.transition handles validity.
        # Strict flow: DRAFT -> REVIEW -> DRAFT (Reject)
        
        # Just attempt transition to DRAFT (assuming it's in REVIEW)
        # Note: RuleAssetStore usually enforces valid transitions.
        # If current logic requires specific previous state, we should check.
        # For simplicity, we assume the store handles it.
        
        rejected = self.rule_store.transition(
            rule_id,
            RuleLifecycleState.DRAFT,
            actor,
            reason or "Rejected via Facade"
        )
        return rejected

    def deprecate_rule(self, rule_id: str, actor: str, reason: str = "") -> RuleAsset:
        """S1: Deprecate an approved rule."""
        from ea_kernel.governance_types import RuleLifecycleState
        
        deprecated = self.rule_store.transition(
            rule_id,
            RuleLifecycleState.DEPRECATED,
            actor,
            reason or "Deprecated via Facade"
        )
        
        # Rule is no longer active, must rebuild corpus
        self._rebuild_corpus()
        
        return deprecated

    def evaluate(self, source: str, target: str, rel: str) -> EnhancedJudgment:
        """S2/S3: Execute judgment and record it."""
        return self.judgment.judge(source, target, rel)

    def analyze(self) -> AnalysisReport:
        """S4: Analyze evidence."""
        return self.analyzer.generate_report()

    def run_automation(self) -> None:
        """S5: Run automation loop (Analyze -> Promote)."""
        report = self.analyze()
        self.controller.run_auto_promotion(report)

    # ── S5 Evolution (Promotion & What-If) ─────────────────────────

    def get_promotion_proposals(self) -> tuple[RuleChangeProposal, ...]:
        """S5: Generate rule promotion proposals based on analysis."""
        from ea_kernel.promotion_engine import ProposalType
        
        # 1. Analyze
        report = self.analyze()
        
        # 2. Identify candidates
        # Uses engine's configured criteria
        candidates = self.promotion.identify_promotion_candidates(report)
        
        # 3. Create proposals for candidates
        for cand in candidates:
            if not cand.meets_criteria:
                continue
                
            # Check if proposal already exists
            existing = [p for p in self.promotion.list_proposals() 
                        if p.rule_id == cand.rule_id and p.proposal_type == ProposalType.PROMOTE]
            
            # Filter for active proposals
            active_existing = [p for p in existing if not p.is_resolved]
            
            if not active_existing:
                self.promotion.create_proposal(
                    proposal_type=ProposalType.PROMOTE,
                    rule_id=cand.rule_id,
                    proposed_by="system:automation",
                    rationale=f"Met promotion criteria with score {cand.score:.1f}",
                    evidence_report_id=report.report_id
                )
                
        return self.promotion.list_proposals()

    def simulate_proposal(self, proposal: RuleChangeProposal) -> SimulationResult:
        """S5: Simulate a rule change proposal."""
        from ea_kernel.what_if_simulator import SimulatedChange, ChangeType
        
        # Simple mapping for demo: assume PROMOTE -> MODIFY_RULE
        # In a real scenario, we would construct the modified rule content
        change = SimulatedChange(
            change_type=ChangeType.MODIFY_RULE, 
            rule_id=proposal.rule_id
        )
        
        return self.simulator.simulate([change])

