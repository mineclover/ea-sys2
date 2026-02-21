"""Needs catalog operations extracted from GovernanceContainer."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from ea_needs.catalog import NeedCatalog
from ea_needs.ops_feedback import build_needs_feedback_draft
from ea_ops.events import FeedbackLayer, ServiceOpsEventSpec, build_service_ops_event


def _now_iso() -> str:
    return datetime.now(UTC).isoformat() + "Z"


class NeedsOps:
    """Needs catalog CRUD + analysis feedback through governance transaction control."""

    def __init__(
        self,
        needs_store: Any,
        execution_service: Any,
        layer_store: Any = None,
        infra_layer_store: Any = None,
    ) -> None:
        self._needs_store = needs_store
        self._execution_service = execution_service
        self._layer_store = layer_store
        self._infra_layer_store = infra_layer_store

    # -- Internal helpers ------------------------------------------------------

    def _require_needs_catalog(self, catalog_id: str) -> NeedCatalog:
        catalog = self._needs_store.get_catalog(catalog_id)
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
        tx = self._execution_service.tx_manager.begin_transaction(
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
            catalog_id = self._needs_store.save_catalog(catalog)
            self._execution_service.tx_manager.add_event(
                tx.id,
                change_event_type,
                change_message,
                payload={
                    "catalog_id": catalog_id,
                    "actor": actor,
                    **(change_payload or {}),
                },
            )
            self._execution_service.tx_manager.add_event(
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
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {"catalog_id": catalog_id, "transaction_id": tx.id}

    # -- Public API ------------------------------------------------------------

    def create_needs_catalog(
        self,
        name: str,
        description: str = "",
        *,
        actor: str = "governance",
    ) -> dict[str, str]:
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

    def add_needs_stakeholder(
        self,
        catalog_id: str,
        *,
        name: str,
        role: str,
        context: str = "",
        actor: str = "governance",
    ) -> dict[str, str]:
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
        purpose: str = "unspecified",
        complexity: Any = "procedural",
        kernel_change_phase: str | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
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
            "kernel_change_phase": kernel_change_phase,
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
        kernel_change_phase: str | None = None,
        actor: str = "governance",
    ) -> dict[str, str]:
        catalog = self._require_needs_catalog(catalog_id)
        updated = catalog.inherit_decision_evidence(
            need_id=need_id,
            decision_id=decision_id,
            evidence_refs=evidence_refs,
            kernel_change_phase=kernel_change_phase,
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
                "kernel_change_phase": (
                    updated.kernel_change_phase.value
                    if hasattr(updated.kernel_change_phase, "value")
                    else str(updated.kernel_change_phase)
                ),
            },
        )
        return {**result, "need_id": updated.id}

    def get_needs_catalog(self, catalog_id: str) -> NeedCatalog | None:
        return self._needs_store.get_catalog(catalog_id)

    def list_needs_catalogs(self) -> list[NeedCatalog]:
        return self._needs_store.list_catalogs()

    def get_needs_catalog_history(self, catalog_id: str) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        transactions = self._execution_service.tx_manager.list_transactions(
            tx_type="needs_catalog_write"
        )
        for tx in transactions:
            if tx.payload.get("catalog_id") != catalog_id:
                continue
            events = self._execution_service.tx_manager.get_events(tx.id)
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

    def ingest_service_ops_event(
        self,
        *,
        spec: ServiceOpsEventSpec,
        payload: Mapping[str, Any],
        catalog_id: str | None = None,
        stakeholder_id: str | None = None,
        auto_express: bool = False,
        tags: list[str] | None = None,
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Ingest validated service ops event and create needs feedback draft.

        The ingestion path stores:
        - an infra-layer event snapshot (if infra store exists)
        - a needs-layer feedback draft snapshot
        - optional auto-expressed need (for feeds_back_to=needs)
        """
        event = build_service_ops_event(spec, payload)
        trace_id = str(event.payload.get("trace_id", "")).strip()
        lineage_id = str(event.payload.get("lineage_id", "")).strip()
        timestamp = _now_iso()
        event_key = f"{event.name}:{trace_id}:{lineage_id}:{timestamp}"

        tx = self._execution_service.tx_manager.begin_transaction(
            f"service_ops_ingest_{event.name}",
            tx_type="service_ops_ingestion",
            payload={
                "event_name": event.name,
                "severity": event.severity.value,
                "feeds_back_to": event.feeds_back_to.value,
                "trace_id": trace_id,
                "lineage_id": lineage_id,
                "catalog_id": catalog_id,
                "actor": actor,
            },
            trace_id=trace_id,
        )

        infra_snapshot_id: str | None = None
        feedback_snapshot_id: str | None = None
        expressed_need: dict[str, Any] | None = None
        draft = build_needs_feedback_draft(event)
        draft_tags = [tag for tag in draft.tags if tag and tag != "service"]
        merged_tags = list(dict.fromkeys([*draft_tags, *(tags or [])]))

        try:
            if self._infra_layer_store is not None:
                infra_snapshot_id = f"service_ops_event:{event_key}"
                self._infra_layer_store.save_payload(
                    infra_snapshot_id,
                    {
                        "kind": "service_ops_event",
                        "name": event.name,
                        "severity": event.severity.value,
                        "feeds_back_to": event.feeds_back_to.value,
                        "trace_id": trace_id,
                        "lineage_id": lineage_id,
                        "payload": dict(event.payload),
                        "ingested_at": timestamp,
                    },
                )

            feedback_snapshot_id = f"service_ops_feedback:{event_key}"
            feedback_payload = {
                "kind": "service_ops_feedback",
                "event_name": event.name,
                "severity": event.severity.value,
                "feeds_back_to": event.feeds_back_to.value,
                "trace_id": trace_id,
                "lineage_id": lineage_id,
                "catalog_id": catalog_id,
                "stakeholder_id": stakeholder_id,
                "draft": {
                    "action": draft.action,
                    "subject": draft.subject,
                    "priority": draft.priority.value,
                    "purpose": draft.purpose.value,
                    "tags": merged_tags,
                    "rationale": draft.rationale,
                },
                "ingested_at": timestamp,
            }
            if self._layer_store is not None:
                self._layer_store.save_payload(feedback_snapshot_id, feedback_payload)

            if auto_express and event.feeds_back_to == FeedbackLayer.NEEDS:
                if catalog_id is None:
                    raise ValueError("catalog_id is required when auto_express=True")
                if stakeholder_id is None:
                    raise ValueError("stakeholder_id is required when auto_express=True")
                catalog = self._require_needs_catalog(catalog_id)
                service_id = str(event.payload.get("service_id", "")).strip() or None
                need = catalog.express_need(
                    stakeholder_id=stakeholder_id,
                    action=draft.action,
                    subject=draft.subject,
                    target=service_id,
                    justifications=[{"type": "because", "description": draft.rationale}],
                    priority=draft.priority,
                    tags=merged_tags,
                    purpose=draft.purpose,
                    cause_types=["situational"],
                )
                self._needs_store.save_catalog(catalog)
                expressed_need = {
                    "catalog_id": catalog_id,
                    "need_id": need.id,
                    "lineage_id": need.lineage_id,
                    "version": need.version,
                }
                self._execution_service.tx_manager.add_event(
                    tx.id,
                    "needs_expressed_from_service_ops",
                    "Need auto-expressed from service operations event.",
                    payload={
                        "catalog_id": catalog_id,
                        "stakeholder_id": stakeholder_id,
                        **expressed_need,
                    },
                )

            self._execution_service.tx_manager.add_event(
                tx.id,
                "service_ops_event_ingested",
                "Service operations event ingested into infra/needs feedback pipeline.",
                payload={
                    "event_name": event.name,
                    "severity": event.severity.value,
                    "feeds_back_to": event.feeds_back_to.value,
                    "trace_id": trace_id,
                    "lineage_id": lineage_id,
                    "infra_snapshot_id": infra_snapshot_id,
                    "feedback_snapshot_id": feedback_snapshot_id,
                    "auto_express": auto_express,
                    "expressed_need": expressed_need,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "event_name": event.name,
            "severity": event.severity.value,
            "feeds_back_to": event.feeds_back_to.value,
            "trace_id": trace_id,
            "lineage_id": lineage_id,
            "transaction_id": tx.id,
            "infra_snapshot_id": infra_snapshot_id,
            "feedback_snapshot_id": feedback_snapshot_id,
            "needs_feedback_draft": {
                "action": draft.action,
                "subject": draft.subject,
                "priority": draft.priority.value,
                "purpose": draft.purpose.value,
                "tags": merged_tags,
                "rationale": draft.rationale,
            },
            "expressed_need": expressed_need,
        }

    # -- Needs→Governance Feedback (S4 Analysis → Governance Audit) --------

    def publish_analysis_report(
        self,
        catalog_id: str,
        report: Any,
        *,
        actor: str = "governance",
    ) -> dict[str, str]:
        """Record a NeedsAnalysisReport to the governance audit trail.

        Maps to NeedsAuditPort element in 30-needs.toml.
        Creates a transaction of type ``needs_analysis_report`` with the
        report summary persisted as a layer snapshot.
        """
        report_payload = {
            "report_id": report.report_id,
            "created_at": report.created_at,
            "total_needs_analyzed": report.total_needs_analyzed,
            "health_score": report.health_score,
            "unserved_count": len(report.unserved_stakeholders),
            "underserved_count": len(report.underserved_stakeholders),
            "stale_needs_count": report.stale_needs_count,
        }

        tx = self._execution_service.tx_manager.begin_transaction(
            f"needs_analysis_{catalog_id}",
            tx_type="needs_analysis_report",
            payload={
                "catalog_id": catalog_id,
                "actor": actor,
                "report_id": report.report_id,
            },
        )
        try:
            if self._layer_store is not None:
                model_id = f"needs_report_{catalog_id}_{report.report_id}"
                self._layer_store.save_payload(model_id, report_payload)

            self._execution_service.tx_manager.add_event(
                tx.id,
                "needs_analysis_published",
                f"Needs analysis report {report.report_id} published.",
                payload=report_payload,
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "catalog_id": catalog_id,
            "report_id": report.report_id,
            "transaction_id": tx.id,
        }

    def record_needs_version(
        self,
        catalog_id: str,
        *,
        version_label: str,
        summary: str = "",
        actor: str = "governance",
    ) -> dict[str, str]:
        """Record a needs catalog version snapshot to governance.

        Maps to NeedsVersionRecord element in 30-needs.toml.
        Captures the current state of a catalog as a named version.
        """
        catalog = self._require_needs_catalog(catalog_id)

        version_payload = {
            "catalog_id": catalog.id,
            "catalog_name": catalog.name,
            "version_label": version_label,
            "needs_count": len(catalog.needs),
            "stakeholder_count": len(catalog.stakeholders),
            "use_case_count": len(catalog.use_cases),
            "summary": summary,
        }

        tx = self._execution_service.tx_manager.begin_transaction(
            f"needs_version_{catalog_id}",
            tx_type="needs_version_record",
            payload={
                "catalog_id": catalog_id,
                "actor": actor,
                "version_label": version_label,
            },
        )
        try:
            if self._layer_store is not None:
                model_id = f"needs_version_{catalog_id}_{version_label}"
                self._layer_store.save_payload(model_id, version_payload)

            self._execution_service.tx_manager.add_event(
                tx.id,
                "needs_version_recorded",
                f"Needs catalog version '{version_label}' recorded.",
                payload=version_payload,
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "catalog_id": catalog_id,
            "version_label": version_label,
            "transaction_id": tx.id,
        }

    def evaluate_change_policy(
        self,
        catalog_id: str,
        *,
        proposed_change: str,
        change_scope: str = "catalog",
        actor: str = "governance",
    ) -> dict[str, Any]:
        """Evaluate whether a proposed change passes governance policy.

        Maps to NeedsChangePolicy element in 30-needs.toml.
        Returns a policy check result with pass/fail and reasons.
        """
        catalog = self._require_needs_catalog(catalog_id)

        violations: list[str] = []
        warnings: list[str] = []

        # Policy checks derived from governance constraints
        if len(catalog.needs) == 0 and proposed_change in ("publish", "promote"):
            violations.append("Cannot publish/promote a catalog with no needs.")

        if change_scope == "catalog":
            # Check for unresolved needs
            unresolved = [
                n for n in catalog.needs
                if str(n.status) in ("draft", "expressed")
            ]
            if len(unresolved) > len(catalog.needs) * 0.5 and proposed_change == "publish":
                warnings.append(
                    f"Over 50% of needs are unresolved ({len(unresolved)}/{len(catalog.needs)})."
                )

            # Check stakeholder coverage
            if not catalog.stakeholders and proposed_change != "delete":
                violations.append("Catalog has no stakeholders defined.")

        passed = len(violations) == 0

        # Record the policy evaluation
        tx = self._execution_service.tx_manager.begin_transaction(
            f"needs_policy_{catalog_id}",
            tx_type="needs_change_policy",
            payload={
                "catalog_id": catalog_id,
                "actor": actor,
                "proposed_change": proposed_change,
            },
        )
        try:
            self._execution_service.tx_manager.add_event(
                tx.id,
                "needs_policy_evaluated",
                f"Change policy evaluated: {'PASS' if passed else 'FAIL'}",
                payload={
                    "catalog_id": catalog_id,
                    "proposed_change": proposed_change,
                    "change_scope": change_scope,
                    "passed": passed,
                    "violations": violations,
                    "warnings": warnings,
                },
            )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        return {
            "catalog_id": catalog_id,
            "proposed_change": proposed_change,
            "passed": passed,
            "violations": violations,
            "warnings": warnings,
            "transaction_id": tx.id,
        }
