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
    ModelRegistryEntry,
    ValidationRunEntry,
)
from ea_kernel.types import KernelSchema
from ea_needs.catalog import NeedCatalog

from ea_governance.decision_trace_ops import DecisionTraceOps
from ea_governance.execution_service import ExecutionService
from ea_governance.kernel_model_ops import KernelModelOps
from ea_governance.kernel_rule_ops import KernelRuleOps
from ea_governance.kernel_store import GovernanceKernelStore
from ea_governance.layer_store import ALLOWED_LAYERS, GovernanceLayerStore, SQLiteGovernanceLayerStore
from ea_governance.needs_ops import NeedsOps
from ea_governance.needs_store import GovernanceNeedsStore


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
            layer: SQLiteGovernanceLayerStore(layers_dir / f"{layer}.db", layer=layer)
            for layer in ALLOWED_LAYERS
        }

        # 3. Governance-owned DB adapters
        self.kernel_store = GovernanceKernelStore(self.layer_stores["kernel"])
        self.needs_store = GovernanceNeedsStore(self.layer_stores["needs"])

        # 4. Reference for direct access if needed
        self.runtime = self.execution_service.runtime

        # 5. Initialize ops modules
        self._decision_trace_ops = DecisionTraceOps(self.layer_stores, self.execution_service)
        self._kernel_model_ops = KernelModelOps(
            self.model_registration,
            self.execution_service,
            self.layer_stores,
            self.kernel_store,
            self._decision_trace_ops,
            self.schema,
        )
        self._kernel_rule_ops = KernelRuleOps(
            self.kernel,
            self.kernel_store,
            self.execution_service,
        )
        self._needs_ops = NeedsOps(self.needs_store, self.execution_service)

    # -- Topic / Initiative / Decision (remain in facade) ----------------------

    def create_topic(self, title: str, description: str) -> Topic:
        """Starts a new Design Thinking topic."""
        return Topic(title=title, description=description)

    def propose_initiative(self, title: str, description: str, pattern_name: str | None = None) -> dict[str, Any]:
        """Starts a high-level initiative (Method 1: Transactional)."""
        tx = self.execution_service.tx_manager.begin_transaction(f"init_{title}", tx_type="initiative_proposal")

        try:
            topic = Topic(title=title, description=description)

            if pattern_name:
                from ea_decision.registry import registry
                pattern = registry.get_pattern(pattern_name)
                if pattern:
                    topic.apply_pattern(pattern)

            self.execution_service.tx_manager.commit(tx.id)
            return {"topic": topic, "transaction_id": tx.id}
        except Exception as e:
            self.execution_service.tx_manager.fail(tx.id, str(e))
            raise e

    def interpret_decision(self, report_id: str, topic: Topic) -> dict[str, Any]:
        """Interprets the modeling actions of a finalized report."""
        if not topic.report or topic.report.id != report_id:
            return {"success": False, "error": "Invalid Report ID"}

        success = self.execution_service.interpret_report(topic.report)
        return {
            "success": success,
            "transaction_id": topic.report.transaction_id,
        }

    def execute_decision(self, report_id: str, topic: Topic) -> dict[str, Any]:
        """Backward-compatible alias for `interpret_decision`."""
        return self.interpret_decision(report_id, topic)

    def interpret_use_case(self, use_case: UseCaseSpec, variables: dict[str, Any]) -> dict[str, Any]:
        """Interprets a Use Case Specification using the flow runtime."""
        tx_name = f"use_case_{use_case.name}"
        tx = self.execution_service.tx_manager.begin_transaction(tx_name, tx_type="use_case_execution")

        try:
            context_vars = {**variables, "governance_system": self.kernel}
            result = self.runtime.interpret(use_case, context_vars)

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

    def execute_use_case(self, use_case: UseCaseSpec, variables: dict[str, Any]) -> dict[str, Any]:
        """Backward-compatible alias for `interpret_use_case`."""
        return self.interpret_use_case(use_case, variables)

    # -- Transaction queries ---------------------------------------------------

    def get_transaction_status(self, tx_id: str) -> dict[str, Any] | None:
        tx = self.execution_service.tx_manager.get_transaction(tx_id)
        if tx:
            return {"id": tx.id, "status": tx.status, "updated_at": tx.updated_at}
        return None

    def get_transaction_logs(self, tx_id: str) -> list[str]:
        tx = self.execution_service.tx_manager.get_transaction(tx_id)
        return tx.logs if tx else []

    def get_transaction_events(self, tx_id: str) -> list[dict[str, Any]]:
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

    # -- Flow spec -------------------------------------------------------------

    def get_flow_spec(self, anchor_id: str) -> dict[str, Any] | None:
        if anchor_id == "ea:kernel:rule_creation":
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

    # -- Layer snapshot (generic) ----------------------------------------------

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
        store = self._require_layer_store(layer)
        return store.get_payload(model_id)

    def list_layer_snapshots(self, layer: str) -> list[dict[str, Any]]:
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

    # -- Self-model diagram ----------------------------------------------------

    def get_self_model_diagram(self, lang: str = "en") -> str:
        from importlib.resources import files

        from ea_kernel.diagram_exporter import DiagramExporter
        from ea_kernel.graph_view import TopologyGraph
        from ea_kernel.localizer import ProfileLocalizer
        from ea_kernel.profile_loader import load_profile
        from ea_kernel.profile_rule_compiler import build_profile_runtime_schema
        from ea_kernel.rule_corpus import RuleCorpus

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

    # ==========================================================================
    # Delegate methods — 100% public API preserved, forwarding to ops modules
    # ==========================================================================

    # -- Decision trace delegates ----------------------------------------------

    @staticmethod
    def _normalize_decision_id(decision_id: str | None) -> str | None:
        return DecisionTraceOps.normalize_decision_id(decision_id)

    @staticmethod
    def _normalize_evidence_refs(evidence_refs: list[str] | tuple[str, ...] | None) -> list[str]:
        return DecisionTraceOps.normalize_evidence_refs(evidence_refs)

    @staticmethod
    def _decision_trace_model_id(decision_id: str) -> str:
        return DecisionTraceOps.decision_trace_model_id(decision_id)

    @staticmethod
    def _decision_trace_warnings(decision_id: str | None, evidence_refs: list[str]) -> list[str]:
        return DecisionTraceOps.decision_trace_warnings(decision_id, evidence_refs)

    def _record_model_decision_trace(self, **kwargs: Any) -> dict[str, Any]:
        return self._decision_trace_ops.record_model_decision_trace(**kwargs)

    def get_model_decision_trace(self, decision_id: str) -> dict[str, Any] | None:
        return self._decision_trace_ops.get_model_decision_trace(decision_id)

    def explore_model_decision_trace(self, decision_id: str) -> dict[str, Any] | None:
        return self._decision_trace_ops.explore_model_decision_trace(decision_id)

    # -- Kernel model delegates ------------------------------------------------

    def _save_kernel_model_snapshot(self, model_name: str, *, actor: str) -> str:
        return self._kernel_model_ops._save_kernel_model_snapshot(model_name, actor=actor)

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
        decision_id: str | None = None,
        evidence_refs: list[str] | tuple[str, ...] | None = None,
        return_transaction: bool = False,
    ) -> dict[str, Any]:
        return self._kernel_model_ops.register_kernel_model(
            profile_toml,
            owner=owner,
            created_by=created_by,
            model_name=model_name,
            activate=activate,
            context=context,
            on_exists=on_exists,
            actor=actor,
            decision_id=decision_id,
            evidence_refs=evidence_refs,
            return_transaction=return_transaction,
        )

    def validate_kernel_model(
        self,
        model_name: str,
        version: str,
        *,
        context: dict[str, Any] | None = None,
        actor: str = "governance",
        decision_id: str | None = None,
        evidence_refs: list[str] | tuple[str, ...] | None = None,
        return_transaction: bool = False,
    ) -> ValidationRunEntry | dict[str, Any]:
        return self._kernel_model_ops.validate_kernel_model(
            model_name,
            version,
            context=context,
            actor=actor,
            decision_id=decision_id,
            evidence_refs=evidence_refs,
            return_transaction=return_transaction,
        )

    def activate_kernel_model(
        self,
        model_name: str,
        version: str,
        *,
        actor: str = "governance",
        decision_id: str | None = None,
        evidence_refs: list[str] | tuple[str, ...] | None = None,
        return_transaction: bool = False,
    ) -> ModelRegistryEntry | dict[str, Any]:
        return self._kernel_model_ops.activate_kernel_model(
            model_name,
            version,
            actor=actor,
            decision_id=decision_id,
            evidence_refs=evidence_refs,
            return_transaction=return_transaction,
        )

    def get_kernel_model_state(self, model_name: str, *, limit_runs: int = 5) -> dict[str, Any] | None:
        return self._kernel_model_ops.get_kernel_model_state(model_name, limit_runs=limit_runs)

    # -- Kernel rule delegates -------------------------------------------------

    def submit_kernel_rule(
        self,
        asset: RuleAsset,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        return self._kernel_rule_ops.submit_kernel_rule(asset, actor=actor, return_transaction=return_transaction)

    def approve_kernel_rule(
        self,
        rule_id: str,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        return self._kernel_rule_ops.approve_kernel_rule(rule_id, actor=actor, return_transaction=return_transaction)

    def reject_kernel_rule(
        self,
        rule_id: str,
        *,
        actor: str = "governance",
        reason: str = "",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        return self._kernel_rule_ops.reject_kernel_rule(rule_id, actor=actor, reason=reason, return_transaction=return_transaction)

    def deprecate_kernel_rule(
        self,
        rule_id: str,
        *,
        actor: str = "governance",
        reason: str = "",
        return_transaction: bool = False,
    ) -> RuleAsset | dict[str, Any]:
        return self._kernel_rule_ops.deprecate_kernel_rule(rule_id, actor=actor, reason=reason, return_transaction=return_transaction)

    def evaluate_kernel(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> EnhancedJudgment | dict[str, Any]:
        return self._kernel_rule_ops.evaluate_kernel(
            source, target, relation, actor=actor, return_transaction=return_transaction,
        )

    def create_kernel_snapshot(
        self,
        name: str,
        description: str = "",
        *,
        actor: str = "governance",
        return_transaction: bool = False,
    ) -> CorpusVersionInfo | dict[str, Any]:
        return self._kernel_rule_ops.create_kernel_snapshot(
            name, description, actor=actor, return_transaction=return_transaction,
        )

    def list_kernel_versions(self, corpus_name: str | None = None) -> tuple[CorpusVersionInfo, ...]:
        return self._kernel_rule_ops.list_kernel_versions(corpus_name)

    def get_kernel_promotion_proposals(self) -> tuple[Any, ...]:
        return self._kernel_rule_ops.get_kernel_promotion_proposals()

    def simulate_kernel_proposal(self, proposal: Any) -> Any:
        return self._kernel_rule_ops.simulate_kernel_proposal(proposal)

    def get_kernel_corpus_at_version(self, version_id: str) -> Any | None:
        return self._kernel_rule_ops.get_kernel_corpus_at_version(version_id)

    def list_kernel_rules(self, state: RuleLifecycleState | str | None = None) -> tuple[RuleAsset, ...]:
        return self._kernel_rule_ops.list_kernel_rules(state)

    def get_kernel_rule_snapshot(self, rule_id: str) -> dict[str, Any] | None:
        return self._kernel_rule_ops.get_kernel_rule_snapshot(rule_id)

    def list_kernel_rule_snapshots(self) -> list[dict[str, Any]]:
        return self._kernel_rule_ops.list_kernel_rule_snapshots()

    def get_kernel_judgment_snapshot(self, decision_id: str) -> dict[str, Any] | None:
        return self._kernel_rule_ops.get_kernel_judgment_snapshot(decision_id)

    def list_kernel_judgment_snapshots(self) -> list[dict[str, Any]]:
        return self._kernel_rule_ops.list_kernel_judgment_snapshots()

    def get_kernel_corpus_version_snapshot(self, version_id: str) -> dict[str, Any] | None:
        return self._kernel_rule_ops.get_kernel_corpus_version_snapshot(version_id)

    def list_kernel_corpus_version_snapshots(self) -> list[dict[str, Any]]:
        return self._kernel_rule_ops.list_kernel_corpus_version_snapshots()

    # -- Needs delegates -------------------------------------------------------

    def _require_needs_catalog(self, catalog_id: str) -> NeedCatalog:
        return self._needs_ops._require_needs_catalog(catalog_id)

    def _persist_needs_change(self, catalog: NeedCatalog, **kwargs: Any) -> dict[str, str]:
        return self._needs_ops._persist_needs_change(catalog, **kwargs)

    def create_needs_catalog(
        self, name: str, description: str = "", *, actor: str = "governance",
    ) -> dict[str, str]:
        return self._needs_ops.create_needs_catalog(name, description, actor=actor)

    def save_needs_catalog(
        self, catalog: NeedCatalog, *, actor: str = "governance", return_transaction: bool = False,
    ) -> str | dict[str, str]:
        return self._needs_ops.save_needs_catalog(catalog, actor=actor, return_transaction=return_transaction)

    def add_needs_stakeholder(
        self,
        catalog_id: str,
        *,
        name: str,
        role: str,
        context: str = "",
        actor: str = "governance",
    ) -> dict[str, str]:
        return self._needs_ops.add_needs_stakeholder(catalog_id, name=name, role=role, context=context, actor=actor)

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
        return self._needs_ops.add_needs_use_case(
            catalog_id, title=title, actor_name=actor_name, situation=situation,
            purpose=purpose, outcome=outcome, tags=tags, actor=actor,
        )

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
        return self._needs_ops.express_need_in_catalog(
            catalog_id, stakeholder_id=stakeholder_id, action=action, subject=subject,
            target=target, justifications=justifications, priority=priority,
            kernel_refs=kernel_refs, tags=tags, use_case_id=use_case_id,
            cause_types=cause_types, purpose=purpose, complexity=complexity, actor=actor,
        )

    def revise_need_in_catalog(
        self,
        catalog_id: str,
        need_id: str,
        *,
        changes: dict[str, Any],
        actor: str = "governance",
    ) -> dict[str, Any]:
        return self._needs_ops.revise_need_in_catalog(catalog_id, need_id, changes=changes, actor=actor)

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
        return self._needs_ops.add_need_process_unit(
            catalog_id, need_id, stage=stage, label=label, description=description,
            sequence=sequence, metadata=metadata, actor=actor,
        )

    def inherit_need_decision_evidence(
        self,
        catalog_id: str,
        need_id: str,
        *,
        decision_id: str,
        evidence_refs: list[str],
        actor: str = "governance",
    ) -> dict[str, str]:
        return self._needs_ops.inherit_need_decision_evidence(
            catalog_id, need_id, decision_id=decision_id, evidence_refs=evidence_refs, actor=actor,
        )

    def get_needs_catalog(self, catalog_id: str) -> NeedCatalog | None:
        return self._needs_ops.get_needs_catalog(catalog_id)

    def list_needs_catalogs(self) -> list[NeedCatalog]:
        return self._needs_ops.list_needs_catalogs()

    def get_needs_catalog_history(self, catalog_id: str) -> list[dict[str, Any]]:
        return self._needs_ops.get_needs_catalog_history(catalog_id)
