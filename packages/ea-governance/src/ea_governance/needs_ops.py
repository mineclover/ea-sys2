"""Needs catalog operations extracted from GovernanceContainer."""

from __future__ import annotations

from typing import Any

from ea_needs.catalog import NeedCatalog


class NeedsOps:
    """Needs catalog CRUD through governance transaction control."""

    def __init__(
        self,
        needs_store: Any,
        execution_service: Any,
    ) -> None:
        self._needs_store = needs_store
        self._execution_service = execution_service

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
        purpose: str = "",
        complexity: Any = "procedural",
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
        actor: str = "governance",
    ) -> dict[str, str]:
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
