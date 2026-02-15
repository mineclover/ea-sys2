"""Lifecycle Controller — Governance Automation (Phase 5).

Coordinates the governance loop:
- S1 (Authoring) → Notification
- S5 (Evaluation) → Promotion Proposal
- S6 (Impact) → Notification
- TriggerEvent handlers (RuleSubmitted, RuleApproved, CorpusUpdated)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ea_kernel.governance_types import TriggerEventType
from ea_kernel.notification_service import Notification, NotificationService

if TYPE_CHECKING:
    from ea_kernel.corpus_version_store import CorpusVersionStore
    from ea_kernel.evidence_analyzer import AnalysisReport
    from ea_kernel.impact_evaluator import ImpactEvaluator
    from ea_kernel.lifecycle_events import LifecycleEvent, LifecycleEventPort
    from ea_kernel.promotion_engine import PromotionEngine
    from ea_kernel.rule_asset_store import RuleAssetStore
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.what_if_simulator import WhatIfSimulator


class LifecycleController:
    """Coordinates the governance lifecycle loop.

    - Subscribes to lifecycle TriggerEvents.
    - Executes automated actions (notify, impact eval, promote).
    """

    def __init__(
        self,
        event_bus: LifecycleEventPort,
        rule_store: RuleAssetStore,
        corpus_store: CorpusVersionStore,
        notification_service: NotificationService,
        impact_evaluator: ImpactEvaluator | None = None,
        promotion_engine: PromotionEngine | None = None,
        what_if_simulator: WhatIfSimulator | None = None,
        # Optional: current active corpus for live updates (if needed)
        active_corpus: RuleCorpus | None = None,
    ) -> None:
        self.bus = event_bus
        self.rule_store = rule_store
        self.corpus_store = corpus_store
        self.notifier = notification_service
        self.impact_evaluator = impact_evaluator
        self.promotion_engine = promotion_engine
        self.what_if_simulator = what_if_simulator
        self.active_corpus = active_corpus

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        """Subscribe to lifecycle trigger events."""
        self.bus.subscribe(TriggerEventType.RULE_SUBMITTED, self.on_rule_submitted)
        self.bus.subscribe(TriggerEventType.RULE_APPROVED, self.on_rule_approved)
        self.bus.subscribe(TriggerEventType.CORPUS_UPDATED, self.on_corpus_updated)

    # ── Event Handlers ───────────────────────────────────────────────

    def on_rule_submitted(self, event: LifecycleEvent) -> None:
        """Handle RULE_SUBMITTED: notify reviewers, check auto-approve."""

        # Check rule asset
        asset = self.rule_store.get(event.rule_id)
        rule_name = asset.entry.rule.id if asset else event.rule_id

        # Notify
        self.notifier.send(Notification(
            recipient="role:reviewer",
            subject=f"Rule Submitted: {rule_name}",
            message=f"Rule {rule_name} submitted by {event.source_actor}. Please review.",
            level="info",
        ))

        # Auto-approve: rules from trusted system sources skip review
        if asset and asset.provenance.source_type == "kernel":
            self.notifier.send(Notification(
                recipient="role:reviewer",
                subject=f"Auto-Approved: {rule_name}",
                message=f"Rule {rule_name} auto-approved (source_type=kernel).",
                level="info",
            ))

    def on_rule_approved(self, event: LifecycleEvent) -> None:
        """Handle RULE_APPROVED: update corpus, create snapshot."""
        rule_id = event.rule_id
        asset = self.rule_store.get(rule_id)
        if not asset:
            self.notifier.send(Notification(
                recipient="admin",
                subject=f"Error: Rule Approved but not found {rule_id}",
                message="Asset missing in store.",
                level="error",
            ))
            return

        rule_name = asset.entry.rule.id

        # 1. Update active corpus (if managed here)
        # Note: Corpus update usually happens via deployment pipeline or dynamic reload.
        # Here we simulate creating a new corpus version snapshot.

        if self.corpus_store and self.active_corpus:
            # Create a new corpus version snapshot including the approved rule
            version_info = self.corpus_store.create_version(
                corpus_name="kernel",
                entries=self.active_corpus.entries,
                description=f"Rule approved: {rule_name} by {event.source_actor}",
                parent_version_id=self._get_latest_version_id(),
            )
            # Publish corpus updated event
            from ea_kernel.lifecycle_events import LifecycleEvent

            self.bus.publish(LifecycleEvent.corpus_updated(
                corpus_version_id=version_info.version_id,
                previous_version_id=version_info.parent_version_id,
                actor=event.source_actor,
            ))

        # Notify author
        self.notifier.send(Notification(
            recipient=asset.provenance.author,
            subject=f"Rule Approved: {rule_name}",
            message=f"Your rule {rule_name} has been approved by {event.source_actor}.",
            level="success",
        ))

        # Notify interest group
        self.notifier.send(Notification(
            recipient="role:subscriber",
            subject=f"New Rule Active: {rule_name}",
            message=f"Rule {rule_name} is now active (v{asset.provenance.version}).",
            level="info",
        ))

        # Trigger corpus update event handled separately if corpus version changes

    def on_corpus_updated(self, event: LifecycleEvent) -> None:
        """Handle CORPUS_UPDATED: run impact analysis."""
        version_id = event.corpus_version_id
        previous_version = event.previous_version_id

        self.notifier.send(Notification(
            recipient="all",
            subject=f"Corpus Updated: {version_id}",
            message=f"System rules updated to version {version_id}.",
            level="info",
        ))

        if self.impact_evaluator and previous_version:
            # Build changeset from corpus version diff
            added, removed, modified = self.corpus_store.diff(previous_version, version_id)

            if added or removed or modified:
                import uuid

                from ea_kernel.impact_evaluator import RuleChange, RuleChangeAction, RuleChangeSet

                changes: list[RuleChange] = []
                for rid in added:
                    changes.append(RuleChange(rule_id=rid, action=RuleChangeAction.ADDED))
                for rid in removed:
                    changes.append(RuleChange(rule_id=rid, action=RuleChangeAction.REMOVED))
                for rid in modified:
                    changes.append(RuleChange(rule_id=rid, action=RuleChangeAction.MODIFIED))

                changeset = RuleChangeSet(
                    changeset_id=f"cs-{uuid.uuid4().hex[:8]}",
                    from_version=previous_version,
                    to_version=version_id,
                    created_at=event.timestamp,
                    changes=tuple(changes),
                )

                report = self.impact_evaluator.evaluate(changeset)
                if not report.safe_to_apply:
                    self.notifier.send(Notification(
                        recipient="role:reviewer",
                        subject=f"Impact Alert: Corpus {version_id}",
                        message=f"Severity={report.severity.value}. {report.recommendation}",
                        level="warning",
                    ))

        # i18n audit trigger — 스키마 변경 시 번역 동기화 확인
        try:
            from ea_kernel.schema_loader import audit_i18n_patch, load_kernel_schema_from_package
            schema = load_kernel_schema_from_package()
            for lang in ("ko",):
                report = audit_i18n_patch(schema, lang)
                if not report.is_clean:
                    self.notifier.send(Notification(
                        recipient="i18n-team",
                        subject=f"i18n Audit Alert ({lang}): {report.total_issues} issues",
                        message=f"Coverage: {report.coverage:.0%}, Missing: {len(report.missing)}, Stale: {len(report.stale)}",
                        level="warning",
                    ))
        except Exception:
            pass  # i18n 감사 실패가 코퍼스 업데이트를 막으면 안 됨

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_latest_version_id(self) -> str:
        """Get the latest corpus version ID, or empty string if none."""
        latest = self.corpus_store.get_latest("kernel")
        return latest.version_id if latest else ""

    # ── Automation Logic ─────────────────────────────────────────────

    def run_auto_promotion(self, analysis_report: AnalysisReport) -> None:
        """Use S4 AnalysisReport to drive S5 Rule Evolution.

        1. Identify candidates (empirical -> common -> universal)
        2. Create proposals
        3. Simulate what-if
        4. Submit or auto-approve
        """
        if not self.promotion_engine:
            return

        from ea_kernel.promotion_engine import ProposalType
        from ea_kernel.what_if_simulator import ChangeType, SimulatedChange

        candidates = self.promotion_engine.identify_promotion_candidates(analysis_report)

        for candidate in candidates:
            # Create proposal
            self.promotion_engine.create_proposal(
                proposal_type=ProposalType.PROMOTE,
                rule_id=candidate.rule_id,
                proposed_by="system:auto-promoter",
                rationale=f"Auto-promotion based on analysis. Score: {candidate.score:.1f}",
                evidence_report_id=analysis_report.report_id,
            )

            # Simulate (S5 WhatIf)
            if self.what_if_simulator:
                # Promotion = activating a REVIEW rule -> ADD_RULE to corpus
                sim_change = SimulatedChange(
                    change_type=ChangeType.ADD_RULE,
                    rule_id=candidate.rule_id,
                )

                result = self.what_if_simulator.simulate([sim_change])
                if not result.safe_to_apply:
                    # Skip unsafe automation
                    self.notifier.send(Notification(
                        recipient="admin",
                        subject=f"Auto-Promotion Blocked: {candidate.rule_id}",
                        message=f"Simulation deemed unsafe. Impact: {result.impact_level}",
                        level="warning",
                    ))
                    continue

            # Notify Reviewer
            self.notifier.send(Notification(
                recipient="role:reviewer",
                subject=f"Auto-Promotion Proposal: {candidate.rule_id}",
                message="Proposed promotion to APPROVED based on analysis.",
                level="info",
            ))
