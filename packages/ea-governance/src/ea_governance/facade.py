from pathlib import Path
from typing import Any

from ea_decision.topic import Topic
from ea_flow.runtime import FlowRuntime
from ea_flow.spec import UseCaseSpec
from ea_kernel.governance import GovernanceSystem as KernelSystem
from ea_kernel.governance_types import CorpusVersionInfo, RuleAsset, RuleLifecycleState
from ea_kernel.judgment_service import EnhancedJudgment
from ea_kernel.model_registration import (
    KernelModelRegistrationService,
    ModelRegistrationError,
    ModelRegistryEntry,
    ValidationRunEntry,
)
from ea_kernel.profile_loader import load_profile_from_content
from ea_kernel.profile_types import KernelProfile
from ea_kernel.types import KernelSchema
from ea_needs.catalog import NeedCatalog

from ea_governance.execution_service import ExecutionService
from ea_governance.kernel_store import GovernanceKernelStore
from ea_governance.layer_store import ALLOWED_LAYERS, GovernanceLayerStore
from ea_governance.needs_store import GovernanceNeedsStore

_KERNEL_MODEL_PREFIX = "model:"


class GovernanceContainer:
    """
    The Main Entry Point for the Horizontal Governance System.

    Integrates:
    - Kernel (Physics/Structure)
    - Decision (Brain/Intent)
    - Flow (Body/Action)
    """

    def __init__(
        self,
        data_dir: Path,
        schema: KernelSchema,
        flow_runtime: FlowRuntime | None = None,
        kernel_system: KernelSystem | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.schema = schema

        # 1. Initialize Core Layer (Kernel)
        self.kernel = kernel_system or KernelSystem(data_dir / "kernel", schema)
        kernel_data_dir = getattr(self.kernel, "data_dir", None)
        if isinstance(kernel_data_dir, Path):
            registration_db_path = kernel_data_dir / "profiles.db"
        else:
            registration_db_path = data_dir / "kernel" / "profiles.db"
        self.model_registration = KernelModelRegistrationService(registration_db_path, schema)

        # 2. Initialize Execution Bridge (Coordination)
        self.execution_service = ExecutionService(
            self.kernel,
            runtime=flow_runtime,
            tx_db_path=data_dir / "transactions.db",
        )

        # 2.5 Initialize layer-scoped stores (one DB file per layer)
        layers_dir = data_dir / "layers"
        self.layer_stores: dict[str, GovernanceLayerStore] = {
            layer: GovernanceLayerStore(layers_dir / f"{layer}.db", layer=layer)
            for layer in ALLOWED_LAYERS
        }

        # 3. Governance-owned DB adapters
        self.kernel_store = GovernanceKernelStore(self.layer_stores["kernel"].db_path)
        self.needs_store = GovernanceNeedsStore(self.layer_stores["needs"].db_path)

        # 4. Reference for direct access if needed
        self.runtime = self.execution_service.runtime

    def create_topic(self, title: str, description: str) -> Topic:
        """Starts a new Design Thinking topic."""
        # This is a lightweight action, maybe no transaction needed yet?
        # Or we can wrap it:
        return Topic(title=title, description=description)

    def propose_initiative(self, title: str, description: str, pattern_name: str | None = None) -> dict[str, Any]:
        """
        Starts a high-level initiative (Method 1: Transactional).
        Returns {Intent/Topic, TransactionID}
        """
        # Start Transaction
        tx = self.execution_service.tx_manager.begin_transaction(f"init_{title}", tx_type="initiative_proposal")

        try:
            topic = Topic(title=title, description=description)

            # Apply Decision Pattern if provided
            if pattern_name:
                from ea_decision.registry import registry
                pattern = registry.get_pattern(pattern_name)
                if pattern:
                    topic.apply_pattern(pattern)

            # Simulate persistence or other logic here

            self.execution_service.tx_manager.commit(tx.id)
            return {"topic": topic, "transaction_id": tx.id}
        except Exception as e:
            self.execution_service.tx_manager.fail(tx.id, str(e))
            raise e

    def execute_decision(self, report_id: str, topic: Topic) -> dict[str, Any]:
        """
        Interprets the modeling actions of a finalized report.
        Returns {"success": bool, "transaction_id": str}
        """
        if not topic.report or topic.report.id != report_id:
            return {"success": False, "error": "Invalid Report ID"}

        success = self.execution_service.interpret_report(topic.report)
        return {
            "success": success,
            "transaction_id": topic.report.transaction_id,
        }

    def execute_use_case(self, use_case: UseCaseSpec, variables: dict[str, Any]) -> dict[str, Any]:
        """
        Interprets a Use Case Specification using the flow runtime.
        """
        tx_name = f"use_case_{use_case.name}"
        tx = self.execution_service.tx_manager.begin_transaction(tx_name, tx_type="use_case_execution")

        try:
            # COORDINATION: Prepare context and resolve execution
            context_vars = {**variables, "governance_system": self.kernel}

            # Interpret process (Procedural Truth)
            result = self.runtime.interpret(use_case, context_vars)

            # Update Transaction with logs
            tx.logs.extend(result.logs)
            if result.success:
                self.execution_service.tx_manager.commit(tx.id)
                return {
                    "success": True,
                    "transaction_id": tx.id,
                    "logs": result.logs,
                    "metrics": {"specs_processed": len(result.step_results)},
                }
            else:
                self.execution_service.tx_manager.fail(tx.id, "Use Case interpretation failed")
                return {"success": False, "transaction_id": tx.id, "logs": result.logs}

        except Exception as e:
            self.execution_service.tx_manager.fail(tx.id, str(e))
            raise e

    def get_transaction_status(self, tx_id: str) -> dict[str, Any] | None:
        """Retrieves the status of a governance transaction."""
        tx = self.execution_service.tx_manager.get_transaction(tx_id)
        if tx:
            return {"id": tx.id, "status": tx.status, "updated_at": tx.updated_at}
        return None

    def get_transaction_logs(self, tx_id: str) -> list[str]:
        """Retrieves execution logs for a specific transaction."""
        tx = self.execution_service.tx_manager.get_transaction(tx_id)
        return tx.logs if tx else []

    def get_transaction_events(self, tx_id: str) -> list[dict[str, Any]]:
        """Retrieves transaction events from persistent store."""
        events = self.execution_service.tx_manager.get_events(tx_id)
        return [
            {
                "id": event.id,
                "tx_id": event.tx_id,
                "event_type": event.event_type,
                "message": event.message,
                "payload": event.payload,
                "created_at": event.created_at,
            }
            for event in events
        ]

    def get_flow_spec(self, anchor_id: str) -> dict[str, Any] | None:
        """
        Retrieves the logic specification (Flow) anchored to a kernel element.
        This is a draft implementation showing how Flow refines Kernel.
        """
        # In a full project, this would query a registry or database.
        # For Phase 8 Demo, we provide a hardcoded example if the anchor matches.
        if anchor_id == "ea:kernel:rule_creation":

            # Example JSON Schema 2020-12
            input_schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["id"],
            }

            return {
                "anchor": anchor_id,
                "type": "Step",
                "name": "AddRuleStep",
                "input_schema": input_schema,
                "format": "jsonschema-2020-12",
            }
        return None

    def _save_kernel_model_snapshot(self, model_name: str, *, actor: str) -> str:
        model_state = self.get_kernel_model_state(model_name, limit_runs=50)
        if model_state is None:
            raise ModelRegistrationError(f"Model not found: {model_name}")
        snapshot_id = f"{_KERNEL_MODEL_PREFIX}{model_name}"
        self.layer_stores["kernel"].save_payload(
            model_id=snapshot_id,
            payload={
                "kind": "kernel_model_state",
                "actor": actor,
                **model_state,
            },
        )
        return snapshot_id

    def register_kernel_model(
        self,
        profile_toml: str,
        *,
        owner: str = "governance",
        created_by: str = "governance",
        model_name: str | None = None,
        activate: bool = False,
        context: dict[str, Any] | None = None,
        on_exists: str = "validate",
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> dict[str, Any]:
        """Register/validate/activate a kernel model through governance control."""
        if on_exists not in ("validate", "error"):
            raise ValueError("on_exists must be 'validate' or 'error'")

        profile = load_profile_from_content(profile_toml, kernel=self.schema)
        if model_name and model_name != profile.name:
            profile = KernelProfile(
                name=model_name,
                version=profile.version,
                kernel_version=profile.kernel_version,
                elements=profile.elements,
                relations=profile.relations,
                validity_rules=profile.validity_rules,
                metadata=profile.metadata,
            )

        tx = self.execution_service.tx_manager.begin_transaction(
            f"kernel_model_register_{profile.name}_{profile.version}",
            tx_type="kernel_model_registry_write",
            payload={
                "operation": "register",
                "model_name": profile.name,
                "version": profile.version,
                "actor": actor,
                "activate": activate,
                "on_exists": on_exists,
            },
        )

        context_obj = {"source": "governance:models/register", **(context or {})}

        try:
            try:
                result = self.model_registration.register(
                    profile,
                    owner=owner,
                    created_by=created_by,
                    context=context_obj,
                )
                created = True
                run_id = result.validation_run_id
            except ModelRegistrationError as err:
                message = str(err)
                if on_exists != "validate" or "already exists" not in message:
                    raise
                rerun = self.model_registration.validate_registered(
                    profile.name,
                    profile.version,
                    context={**context_obj, "mode": "reregister"},
                )
                created = False
                run_id = rerun.run_id
                if not rerun.passed:
                    raise ModelRegistrationError(
                        "Existing model version revalidation failed"
                    ) from err

            activation = None
            if activate:
                activation = self.model_registration.activate(
                    profile.name,
                    profile.version,
                    actor=created_by or actor,
                )

            snapshot_id = self._save_kernel_model_snapshot(profile.name, actor=actor)
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_registered" if created else "kernel_model_revalidated",
                "Kernel model registration handled through governance.",
                payload={
                    "model_name": profile.name,
                    "version": profile.version,
                    "validation_run_id": run_id,
                    "created": created,
                    "actor": actor,
                },
            )
            if activation is not None:
                self.execution_service.tx_manager.add_event(
                    tx.id,
                    "kernel_model_activated",
                    "Kernel model activated through governance.",
                    payload={
                        "model_name": activation.model_name,
                        "status": activation.status,
                        "active_version_id": activation.active_version_id,
                        "actor": created_by or actor,
                    },
                )
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_snapshot_saved",
                "Kernel model snapshot persisted by governance.",
                payload={
                    "model_id": snapshot_id,
                    "model_name": profile.name,
                    "actor": actor,
                },
            )
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        response = {
            "model_name": profile.name,
            "version": profile.version,
            "created": created,
            "validation_run_id": run_id,
            "activated": activation is not None,
            "status": activation.status if activation else "registered",
            "active_version_id": activation.active_version_id if activation else None,
        }
        if return_transaction:
            response["transaction_id"] = tx.id
        return response

    def validate_kernel_model(
        self,
        model_name: str,
        version: str,
        *,
        context: dict[str, Any] | None = None,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> ValidationRunEntry | dict[str, Any]:
        """Validate a registered kernel model through governance control."""
        tx = self.execution_service.tx_manager.begin_transaction(
            f"kernel_model_validate_{model_name}_{version}",
            tx_type="kernel_model_registry_validate",
            payload={
                "operation": "validate",
                "model_name": model_name,
                "version": version,
                "actor": actor,
            },
        )

        try:
            run = self.model_registration.validate_registered(
                model_name,
                version,
                context={"source": "governance:models/validate", **(context or {})},
            )
            snapshot_id = self._save_kernel_model_snapshot(model_name, actor=actor)
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_validated",
                "Kernel model validated through governance.",
                payload={
                    "model_name": model_name,
                    "version": version,
                    "run_id": run.run_id,
                    "passed": run.passed,
                    "actor": actor,
                },
            )
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_snapshot_saved",
                "Kernel model snapshot persisted by governance.",
                payload={
                    "model_id": snapshot_id,
                    "model_name": model_name,
                    "actor": actor,
                },
            )
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"run": run, "transaction_id": tx.id}
        return run

    def activate_kernel_model(
        self,
        model_name: str,
        version: str,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> ModelRegistryEntry | dict[str, Any]:
        """Activate a validated kernel model through governance control."""
        tx = self.execution_service.tx_manager.begin_transaction(
            f"kernel_model_activate_{model_name}_{version}",
            tx_type="kernel_model_registry_write",
            payload={
                "operation": "activate",
                "model_name": model_name,
                "version": version,
                "actor": actor,
            },
        )

        try:
            model = self.model_registration.activate(model_name, version, actor=actor)
            snapshot_id = self._save_kernel_model_snapshot(model_name, actor=actor)
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_activated",
                "Kernel model activated through governance.",
                payload={
                    "model_name": model.model_name,
                    "status": model.status,
                    "active_version_id": model.active_version_id,
                    "actor": actor,
                },
            )
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_snapshot_saved",
                "Kernel model snapshot persisted by governance.",
                payload={
                    "model_id": snapshot_id,
                    "model_name": model_name,
                    "actor": actor,
                },
            )
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"model": model, "transaction_id": tx.id}
        return model

    def get_kernel_model_state(
        self,
        model_name: str,
        *,
        limit_runs: int = 5,
    ) -> dict[str, Any] | None:
        """Return kernel model state (model/versions/validation runs)."""
        model = self.model_registration.get_model(model_name)
        if model is None:
            return None

        versions = self.model_registration.list_versions(model_name)
        runs = self.model_registration.list_validation_runs(
            model_name=model_name,
            limit=limit_runs,
        )
        return {
            "model": {
                "model_id": model.model_id,
                "model_name": model.model_name,
                "owner": model.owner,
                "status": model.status,
                "active_version_id": model.active_version_id,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
            },
            "versions": [
                {
                    "version_id": entry.version_id,
                    "version": entry.version,
                    "content_hash": entry.content_hash,
                    "parent_version_id": entry.parent_version_id,
                    "created_by": entry.created_by,
                    "created_at": entry.created_at,
                }
                for entry in versions
            ],
            "validation_runs": [
                {
                    "run_id": run.run_id,
                    "version_id": run.version_id,
                    "passed": run.passed,
                    "errors": list(run.errors),
                    "context": run.context,
                    "created_at": run.created_at,
                }
                for run in runs
            ],
        }

    # -- Kernel governance APIs ------------------------------------------------

    def submit_kernel_rule(
        self,
        asset: RuleAsset,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        """Submit a kernel rule through governance transaction control."""
        tx = self.execution_service.tx_manager.begin_transaction(
            f"kernel_submit_{asset.id}",
            tx_type="kernel_rule_write",
            payload={"rule_id": asset.id, "actor": actor, "operation": "submit"},
        )
        try:
            saved = self.kernel.submit_rule(asset)
            self.kernel_store.save_rule_asset(saved)
            self.execution_service.tx_manager.add_event(
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
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
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
        """Approve a kernel rule through governance transaction control."""
        tx = self.execution_service.tx_manager.begin_transaction(
            f"kernel_approve_{rule_id}",
            tx_type="kernel_rule_write",
            payload={"rule_id": rule_id, "actor": actor, "operation": "approve"},
        )
        try:
            approved = self.kernel.approve_rule(rule_id, actor)
            self.kernel_store.save_rule_asset(approved)
            self.execution_service.tx_manager.add_event(
                tx.id,
                "kernel_rule_approved",
                "Kernel rule approved through governance.",
                payload={
                    "rule_id": approved.id,
                    "state": approved.lifecycle.current_state.value,
                    "actor": actor,
                },
            )
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
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
        """Reject a kernel rule through governance transaction control."""
        tx = self.execution_service.tx_manager.begin_transaction(
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
            rejected = self.kernel.reject_rule(rule_id, actor, reason=reason)
            self.kernel_store.save_rule_asset(rejected)
            self.execution_service.tx_manager.add_event(
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
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
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
        """Deprecate a kernel rule through governance transaction control."""
        tx = self.execution_service.tx_manager.begin_transaction(
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
            deprecated = self.kernel.deprecate_rule(rule_id, actor, reason=reason)
            self.kernel_store.save_rule_asset(deprecated)
            self.execution_service.tx_manager.add_event(
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
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"rule": deprecated, "transaction_id": tx.id}
        return deprecated

    def evaluate_kernel(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> EnhancedJudgment | dict[str, Any]:
        """Execute kernel judgment through governance transaction control."""
        tx = self.execution_service.tx_manager.begin_transaction(
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
            judgment = self.kernel.evaluate(source, target, relation)
            decision_id = self.kernel_store.save_judgment(
                source=source,
                target=target,
                relation=relation,
                actor=actor,
                judgment=judgment,
            )
            self.execution_service.tx_manager.add_event(
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
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"judgment": judgment, "decision_id": decision_id, "transaction_id": tx.id}
        return judgment

    def create_kernel_snapshot(
        self,
        name: str,
        description: str = "",
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> CorpusVersionInfo | dict[str, Any]:
        """Create corpus snapshot via kernel and persist governance projection."""
        tx = self.execution_service.tx_manager.begin_transaction(
            f"kernel_snapshot_{name}",
            tx_type="kernel_version_write",
            payload={"name": name, "description": description, "actor": actor},
        )
        try:
            version = self.kernel.create_snapshot(name=name, description=description)
            self.kernel_store.save_corpus_version(version)
            self.execution_service.tx_manager.add_event(
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
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"version": version, "transaction_id": tx.id}
        return version

    def list_kernel_versions(
        self,
        corpus_name: str | None = None,
    ) -> tuple[CorpusVersionInfo, ...]:
        """List kernel corpus versions."""
        return self.kernel.list_versions(corpus_name)

    def get_kernel_promotion_proposals(self):
        """Expose kernel promotion proposals through governance entrypoint."""
        return self.kernel.get_promotion_proposals()

    def simulate_kernel_proposal(self, proposal):
        """Expose kernel what-if simulation through governance entrypoint."""
        return self.kernel.simulate_proposal(proposal)

    def get_kernel_corpus_at_version(self, version_id: str):
        """Reconstruct kernel corpus at the given version id."""
        return self.kernel.get_corpus_at_version(version_id)

    def list_kernel_rules(
        self,
        state: RuleLifecycleState | str | None = None,
    ) -> tuple[RuleAsset, ...]:
        """List kernel rules, optionally filtered by lifecycle state."""
        if state is None:
            return self.kernel.rule_store.query()

        lifecycle_state = state
        if isinstance(state, str):
            try:
                lifecycle_state = RuleLifecycleState(state.lower())
            except ValueError as exc:
                raise ValueError(f"Invalid kernel rule state: {state}") from exc

        assert isinstance(lifecycle_state, RuleLifecycleState)
        return self.kernel.rule_store.list_by_state(lifecycle_state)

    def get_kernel_rule_snapshot(self, rule_id: str) -> dict[str, Any] | None:
        """Get governance snapshot payload of a kernel rule."""
        return self.kernel_store.get_rule_asset(rule_id)

    def list_kernel_rule_snapshots(self) -> list[dict[str, Any]]:
        """List governance snapshot payloads of kernel rules."""
        return self.kernel_store.list_rule_assets()

    def get_kernel_judgment_snapshot(self, decision_id: str) -> dict[str, Any] | None:
        """Get governance snapshot payload of a kernel judgment."""
        return self.kernel_store.get_judgment(decision_id)

    def list_kernel_judgment_snapshots(self) -> list[dict[str, Any]]:
        """List governance snapshot payloads of kernel judgments."""
        return self.kernel_store.list_judgments()

    def get_kernel_corpus_version_snapshot(self, version_id: str) -> dict[str, Any] | None:
        """Get governance snapshot payload of a kernel corpus version."""
        return self.kernel_store.get_corpus_version(version_id)

    def list_kernel_corpus_version_snapshots(self) -> list[dict[str, Any]]:
        """List governance snapshot payloads of kernel corpus versions."""
        return self.kernel_store.list_corpus_versions()

    # -- Needs governance APIs -------------------------------------------------

    def _require_needs_catalog(self, catalog_id: str) -> NeedCatalog:
        catalog = self.needs_store.get_catalog(catalog_id)
        if catalog is None:
            raise ValueError(f"Needs catalog {catalog_id} not found")
        return catalog

    def _persist_needs_change(
        self,
        catalog: NeedCatalog,
        *,
        actor: str,
        tx_name: str,
        change_event_type: str,
        change_message: str,
        change_payload: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        tx = self.execution_service.tx_manager.begin_transaction(
            tx_name,
            tx_type="needs_catalog_write",
            payload={
                "catalog_id": catalog.id,
                "actor": actor,
                "needs_count": len(catalog.needs),
                "use_cases_count": len(catalog.use_cases),
            },
        )
        try:
            catalog_id = self.needs_store.save_catalog(catalog)
            self.execution_service.tx_manager.add_event(
                tx.id,
                change_event_type,
                change_message,
                payload={
                    "catalog_id": catalog_id,
                    "actor": actor,
                    **(change_payload or {}),
                },
            )
            self.execution_service.tx_manager.add_event(
                tx.id,
                "needs_catalog_saved",
                "Needs catalog persisted by governance.",
                payload={
                    "catalog_id": catalog_id,
                    "actor": actor,
                    "needs_count": len(catalog.needs),
                    "use_cases_count": len(catalog.use_cases),
                },
            )
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {"catalog_id": catalog_id, "transaction_id": tx.id}

    def create_needs_catalog(
        self,
        name: str,
        description: str = "",
        *,
        actor: str = "governance",
    ) -> dict[str, str]:
        """Create and persist a new needs catalog with transaction history."""
        catalog = NeedCatalog(name=name, description=description)
        return self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_create_{catalog.id}",
            change_event_type="needs_catalog_created",
            change_message="Needs catalog created.",
            change_payload={"name": name},
        )

    def save_needs_catalog(
        self,
        catalog: NeedCatalog,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> str | dict[str, str]:
        """Persist a needs catalog with transaction event history."""
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_save_{catalog.id}",
            change_event_type="needs_catalog_write_requested",
            change_message="Needs catalog write requested.",
        )

        if return_transaction:
            return result
        return result["catalog_id"]

    def _require_layer_store(self, layer: str) -> GovernanceLayerStore:
        store = self.layer_stores.get(layer)
        if store is None:
            raise ValueError(
                f"Unsupported layer {layer!r}; expected one of {', '.join(sorted(self.layer_stores))}"
            )
        return store

    def save_layer_snapshot(
        self,
        layer: str,
        model_id: str,
        payload: dict[str, Any],
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> str | dict[str, str]:
        """Persist arbitrary layer payload into a layer-scoped store."""
        store = self._require_layer_store(layer)
        tx = self.execution_service.tx_manager.begin_transaction(
            f"{layer}_snapshot_{model_id}",
            tx_type=f"{layer}_layer_write",
            payload={
                "layer": layer,
                "model_id": model_id,
                "actor": actor,
            },
        )
        try:
            saved_id = store.save_payload(model_id=model_id, payload=payload)
            self.execution_service.tx_manager.add_event(
                tx.id,
                "layer_snapshot_saved",
                "Layer snapshot persisted by governance.",
                payload={"layer": layer, "model_id": saved_id, "actor": actor},
            )
            self.execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self.execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            return {"model_id": saved_id, "transaction_id": tx.id}
        return saved_id

    def get_layer_snapshot(self, layer: str, model_id: str) -> dict[str, Any] | None:
        """Read layer-scoped payload by model id."""
        store = self._require_layer_store(layer)
        return store.get_payload(model_id)

    def list_layer_snapshots(self, layer: str) -> list[dict[str, Any]]:
        """List layer-scoped payload snapshots."""
        store = self._require_layer_store(layer)
        return [
            {
                "layer": snapshot.layer,
                "model_id": snapshot.model_id,
                "payload": snapshot.payload,
                "updated_at": snapshot.updated_at,
            }
            for snapshot in store.list_snapshots()
        ]

    def add_needs_stakeholder(
        self,
        catalog_id: str,
        *,
        name: str,
        role: str,
        context: str = "",
        actor: str = "governance",
    ) -> dict[str, str]:
        """Add a stakeholder to a needs catalog with transaction history."""
        catalog = self._require_needs_catalog(catalog_id)
        stakeholder = catalog.add_stakeholder(name=name, role=role, context=context)
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_stakeholder_{catalog.id}",
            change_event_type="needs_stakeholder_added",
            change_message="Needs stakeholder added.",
            change_payload={"stakeholder_id": stakeholder.id, "name": stakeholder.name},
        )
        return {**result, "stakeholder_id": stakeholder.id}

    def add_needs_use_case(
        self,
        catalog_id: str,
        *,
        title: str,
        actor_name: str,
        situation: str,
        purpose: str,
        outcome: str = "",
        tags: list[str] | None = None,
        actor: str = "governance",
    ) -> dict[str, str]:
        """Add a use-case to a needs catalog with transaction history."""
        catalog = self._require_needs_catalog(catalog_id)
        use_case = catalog.add_use_case(
            title=title,
            actor=actor_name,
            situation=situation,
            purpose=purpose,
            outcome=outcome,
            tags=tags,
        )
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_use_case_{catalog.id}",
            change_event_type="needs_use_case_added",
            change_message="Needs use-case added.",
            change_payload={"use_case_id": use_case.id, "title": use_case.title},
        )
        return {**result, "use_case_id": use_case.id}

    def express_need_in_catalog(
        self,
        catalog_id: str,
        *,
        stakeholder_id: str,
        action: str,
        subject: str,
        target: str | None = None,
        justifications: list[dict[str, str]] | None = None,
        priority: Any = None,
        kernel_refs: list[str] | None = None,
        tags: list[str] | None = None,
        use_case_id: str | None = None,
        cause_types: list[Any] | None = None,
        purpose: str = "",
        complexity: Any = "procedural",
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Express a need in a catalog through governance transaction control."""
        catalog = self._require_needs_catalog(catalog_id)
        express_kwargs: dict[str, Any] = {
            "stakeholder_id": stakeholder_id,
            "action": action,
            "subject": subject,
            "target": target,
            "justifications": justifications,
            "kernel_refs": kernel_refs,
            "tags": tags,
            "use_case_id": use_case_id,
            "cause_types": cause_types,
            "purpose": purpose,
            "complexity": complexity,
        }
        if priority is not None:
            express_kwargs["priority"] = priority
        need = catalog.express_need(**express_kwargs)
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_express_{catalog.id}",
            change_event_type="needs_expressed",
            change_message="Need expressed in catalog.",
            change_payload={
                "need_id": need.id,
                "lineage_id": need.lineage_id,
                "version": need.version,
            },
        )
        return {
            **result,
            "need_id": need.id,
            "lineage_id": need.lineage_id,
            "version": need.version,
        }

    def revise_need_in_catalog(
        self,
        catalog_id: str,
        need_id: str,
        *,
        changes: dict[str, Any],
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Revise an existing need and persist a new lineage version."""
        catalog = self._require_needs_catalog(catalog_id)
        revised = catalog.revise_need(need_id, **changes)
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_revise_{catalog.id}",
            change_event_type="needs_revised",
            change_message="Need revised in catalog.",
            change_payload={
                "source_need_id": need_id,
                "new_need_id": revised.id,
                "lineage_id": revised.lineage_id,
                "version": revised.version,
            },
        )
        return {
            **result,
            "need_id": revised.id,
            "lineage_id": revised.lineage_id,
            "version": revised.version,
        }

    def add_need_process_unit(
        self,
        catalog_id: str,
        need_id: str,
        *,
        stage: str,
        label: str,
        description: str = "",
        sequence: int | None = None,
        metadata: dict[str, str] | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Add a process unit to a need with governance transaction history."""
        catalog = self._require_needs_catalog(catalog_id)
        unit = catalog.add_process_unit(
            need_id=need_id,
            stage=stage,
            label=label,
            description=description,
            sequence=sequence,
            metadata=metadata,
        )
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_process_unit_{catalog.id}",
            change_event_type="needs_process_unit_added",
            change_message="Needs process unit added.",
            change_payload={
                "need_id": need_id,
                "process_unit_id": unit.id,
                "stage": unit.stage.value,
            },
        )
        return {**result, "process_unit_id": unit.id}

    def inherit_need_decision_evidence(
        self,
        catalog_id: str,
        need_id: str,
        *,
        decision_id: str,
        evidence_refs: list[str],
        actor: str = "governance",
    ) -> dict[str, str]:
        """Inherit decision evidence refs into a need via governance transaction."""
        catalog = self._require_needs_catalog(catalog_id)
        updated = catalog.inherit_decision_evidence(
            need_id=need_id,
            decision_id=decision_id,
            evidence_refs=evidence_refs,
        )
        result = self._persist_needs_change(
            catalog,
            actor=actor,
            tx_name=f"needs_inherit_evidence_{catalog.id}",
            change_event_type="needs_decision_evidence_inherited",
            change_message="Need inherited decision evidence.",
            change_payload={
                "need_id": updated.id,
                "decision_id": decision_id,
                "evidence_count": len(evidence_refs),
            },
        )
        return {**result, "need_id": updated.id}

    def get_needs_catalog(self, catalog_id: str) -> NeedCatalog | None:
        """Retrieve a needs catalog through governance-owned DB store."""
        return self.needs_store.get_catalog(catalog_id)

    def list_needs_catalogs(self) -> list[NeedCatalog]:
        """List all needs catalogs through governance-owned DB store."""
        return self.needs_store.list_catalogs()

    def get_needs_catalog_history(self, catalog_id: str) -> list[dict[str, Any]]:
        """Return transaction-event history for a needs catalog."""
        matches: list[dict[str, Any]] = []
        transactions = self.execution_service.tx_manager.list_transactions(
            tx_type="needs_catalog_write"
        )
        for tx in transactions:
            if tx.payload.get("catalog_id") != catalog_id:
                continue
            events = self.execution_service.tx_manager.get_events(tx.id)
            for event in events:
                matches.append(
                    {
                        "transaction_id": tx.id,
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "message": event.message,
                        "payload": event.payload,
                        "created_at": event.created_at,
                    }
                )
        return sorted(matches, key=lambda item: (item["created_at"], item["event_id"]))

    def get_self_model_diagram(self, lang: str = "en") -> str:
        """
        Generates a Mermaid diagram of the EA System's own architecture
        by projecting it onto a Kernel schema using the SystemSelfModel profile.
        Supports localized descriptions via lang parameter.
        """
        from importlib.resources import files

        from ea_kernel.diagram_exporter import DiagramExporter
        from ea_kernel.graph_view import TopologyGraph
        from ea_kernel.localizer import ProfileLocalizer
        from ea_kernel.profile_loader import load_profile
        from ea_kernel.profile_rule_compiler import build_profile_runtime_schema
        from ea_kernel.rule_corpus import RuleCorpus

        # 1. Load the Self-Model Profile
        # Try relative path from governance package to sibling ea-kernel package
        profile_path = (
            Path(__file__).parent.parent.parent.parent
            / "ea-kernel"
            / "src"
            / "ea_kernel"
            / "profiles"
            / "system_self_model.toml"
        )
        if not profile_path.exists():
            try:
                resource = files("ea_kernel.profiles").joinpath("system_self_model.toml")
                profile_path = Path(str(resource))
            except Exception as exc:
                raise FileNotFoundError("Cannot locate system_self_model.toml profile") from exc

        base_profile = load_profile(profile_path, kernel=self.kernel._base_schema)

        # 2. Apply Localizer
        localizer = ProfileLocalizer()
        self_profile = localizer.localize(base_profile, lang=lang, search_path=profile_path.parent)

        runtime = build_profile_runtime_schema(
            self.kernel._base_schema,
            self_profile,
            include_base_schema=False,
            include_base_rules=False,
        )
        corpus = RuleCorpus.from_kernel_spec(runtime.schema)

        graph = TopologyGraph(runtime.schema, corpus)
        exporter = DiagramExporter(graph)
        return str(exporter.generate_mermaid(show_judgment=False))
