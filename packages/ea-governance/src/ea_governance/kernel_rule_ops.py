"""Kernel rule lifecycle and snapshot operations."""

from __future__ import annotations

from typing import Any, cast

from ea_kernel.governance_types import CorpusVersionInfo, RuleAsset, RuleLifecycleState
from ea_kernel.judgment_service import EnhancedJudgment


class KernelRuleOps:
    """Kernel rule submit/approve/reject/deprecate + evaluation + snapshots."""

    def __init__(
        self,
        kernel: Any,
        kernel_store: Any,
        execution_service: Any,
    ) -> None:
        self._kernel = kernel
        self._kernel_store = kernel_store
        self._execution_service = execution_service

    # -- Rule lifecycle --------------------------------------------------------

    def submit_kernel_rule(
        self,
        asset: RuleAsset,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_submit_{asset.id}",
            tx_type="kernel_rule_write",
            payload={"rule_id": asset.id, "actor": actor, "operation": "submit"},
        )
        try:
            saved = self._kernel.submit_rule(asset)
            self._kernel_store.save_rule_asset(saved)
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_rule_submitted",
                "Kernel rule submitted through governance.",
                payload={
                    "rule_id": saved.id,
                    "state": saved.lifecycle.current_state.value,
                    "actor": actor,
                    "author": saved.provenance.author,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"rule": saved, "transaction_id": tx.id}
        return saved

    def approve_kernel_rule(
        self,
        rule_id: str,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_approve_{rule_id}",
            tx_type="kernel_rule_write",
            payload={"rule_id": rule_id, "actor": actor, "operation": "approve"},
        )
        try:
            approved = self._kernel.approve_rule(rule_id, actor)
            self._kernel_store.save_rule_asset(approved)
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_rule_approved",
                "Kernel rule approved through governance.",
                payload={
                    "rule_id": approved.id,
                    "state": approved.lifecycle.current_state.value,
                    "actor": actor,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"rule": approved, "transaction_id": tx.id}
        return approved

    def reject_kernel_rule(
        self,
        rule_id: str,
        *,
        actor: str = "governance",
        reason: str = "",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_reject_{rule_id}",
            tx_type="kernel_rule_write",
            payload={
                "rule_id": rule_id,
                "actor": actor,
                "operation": "reject",
                "reason": reason,
            },
        )
        try:
            rejected = self._kernel.reject_rule(rule_id, actor, reason=reason)
            self._kernel_store.save_rule_asset(rejected)
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_rule_rejected",
                "Kernel rule rejected through governance.",
                payload={
                    "rule_id": rejected.id,
                    "state": rejected.lifecycle.current_state.value,
                    "actor": actor,
                    "reason": reason,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"rule": rejected, "transaction_id": tx.id}
        return rejected

    def deprecate_kernel_rule(
        self,
        rule_id: str,
        *,
        actor: str = "governance",
        reason: str = "",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_deprecate_{rule_id}",
            tx_type="kernel_rule_write",
            payload={
                "rule_id": rule_id,
                "actor": actor,
                "operation": "deprecate",
                "reason": reason,
            },
        )
        try:
            deprecated = self._kernel.deprecate_rule(rule_id, actor, reason=reason)
            self._kernel_store.save_rule_asset(deprecated)
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_rule_deprecated",
                "Kernel rule deprecated through governance.",
                payload={
                    "rule_id": deprecated.id,
                    "state": deprecated.lifecycle.current_state.value,
                    "actor": actor,
                    "reason": reason,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"rule": deprecated, "transaction_id": tx.id}
        return deprecated

    # -- Evaluation ------------------------------------------------------------

    def evaluate_kernel(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> EnhancedJudgment | dict[str, Any]:
        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_judgment_{source}_{relation}_{target}",
            tx_type="kernel_judgment",
            payload={
                "source": source,
                "target": target,
                "relation": relation,
                "actor": actor,
            },
        )
        try:
            judgment = self._kernel.evaluate(source, target, relation)
            decision_id = self._kernel_store.save_judgment(
                source=source,
                target=target,
                relation=relation,
                actor=actor,
                judgment=judgment,
            )
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_judgment_recorded",
                "Kernel judgment executed and snapshotted through governance.",
                payload={
                    "decision_id": decision_id,
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "verdict": judgment.judgment.verdict,
                    "confidence": judgment.judgment.confidence.value,
                    "actor": actor,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"judgment": judgment, "decision_id": decision_id, "transaction_id": tx.id}
        return judgment

    # -- Snapshots -------------------------------------------------------------

    def create_kernel_snapshot(
        self,
        name: str,
        description: str = "",
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> CorpusVersionInfo | dict[str, Any]:
        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_snapshot_{name}",
            tx_type="kernel_version_write",
            payload={"name": name, "description": description, "actor": actor},
        )
        try:
            version = self._kernel.create_snapshot(name=name, description=description)
            self._kernel_store.save_corpus_version(version)
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_snapshot_created",
                "Kernel corpus snapshot created through governance.",
                payload={
                    "version_id": version.version_id,
                    "corpus_name": version.corpus_name,
                    "rule_count": version.rule_count,
                    "actor": actor,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"version": version, "transaction_id": tx.id}
        return version

    def list_kernel_versions(
        self,
        corpus_name: str | None = None,
    ) -> tuple[CorpusVersionInfo, ...]:
        return tuple(cast(tuple[CorpusVersionInfo, ...], self._kernel.list_versions(corpus_name)))

    def get_kernel_promotion_proposals(self) -> tuple[Any, ...]:
        return tuple(cast(tuple[Any, ...], self._kernel.get_promotion_proposals()))

    def simulate_kernel_proposal(self, proposal: Any) -> Any:
        return self._kernel.simulate_proposal(proposal)

    def get_kernel_corpus_at_version(self, version_id: str) -> Any | None:
        return self._kernel.get_corpus_at_version(version_id)

    def list_kernel_rules(
        self,
        state: RuleLifecycleState | str | None = None,
    ) -> tuple[RuleAsset, ...]:
        if state is None:
            return tuple(cast(tuple[RuleAsset, ...], self._kernel.rule_store.query()))

        lifecycle_state = state
        if isinstance(state, str):
            try:
                lifecycle_state = RuleLifecycleState(state.lower())
            except ValueError as exc:
                raise ValueError(f"Invalid kernel rule state: {state}") from exc

        assert isinstance(lifecycle_state, RuleLifecycleState)
        return tuple(
            cast(tuple[RuleAsset, ...], self._kernel.rule_store.list_by_state(lifecycle_state))
        )

    # -- Read-only snapshot queries --------------------------------------------

    def get_kernel_rule_snapshot(self, rule_id: str) -> dict[str, Any] | None:
        return self._kernel_store.get_rule_asset(rule_id)

    def list_kernel_rule_snapshots(self) -> list[dict[str, Any]]:
        return self._kernel_store.list_rule_assets()

    def get_kernel_judgment_snapshot(self, decision_id: str) -> dict[str, Any] | None:
        return self._kernel_store.get_judgment(decision_id)

    def list_kernel_judgment_snapshots(self) -> list[dict[str, Any]]:
        return self._kernel_store.list_judgments()

    def get_kernel_corpus_version_snapshot(self, version_id: str) -> dict[str, Any] | None:
        return self._kernel_store.get_corpus_version(version_id)

    def list_kernel_corpus_version_snapshots(self) -> list[dict[str, Any]]:
        return self._kernel_store.list_corpus_versions()
