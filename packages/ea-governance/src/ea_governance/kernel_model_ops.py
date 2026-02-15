"""Kernel model registration/validation/activation operations."""

from __future__ import annotations

from typing import Any

from ea_kernel.model_registration import (
    ModelRegistrationError,
    ModelRegistryEntry,
    ValidationRunEntry,
)
from ea_kernel.profile_loader import load_profile_from_content
from ea_kernel.profile_types import KernelProfile

from ea_governance.decision_trace_ops import DecisionTraceOps

_KERNEL_MODEL_PREFIX = "model:"


class KernelModelOps:
    """Kernel model registration, validation, activation through governance."""

    def __init__(
        self,
        model_registration: Any,
        execution_service: Any,
        layer_stores: dict[str, Any],
        kernel_store: Any,
        decision_trace_ops: DecisionTraceOps,
        schema: Any,
    ) -> None:
        self._model_registration = model_registration
        self._execution_service = execution_service
        self._layer_stores = layer_stores
        self._kernel_store = kernel_store
        self._dt = decision_trace_ops
        self._schema = schema

    def _save_kernel_model_snapshot(self, model_name: str, *, actor: str) -> str:
        model_state = self.get_kernel_model_state(model_name, limit_runs=50)
        if model_state is None:
            raise ModelRegistrationError(f"Model not found: {model_name}")
        snapshot_id = f"{_KERNEL_MODEL_PREFIX}{model_name}"
        self._layer_stores["kernel"].save_payload(
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
        decision_id: str | None = None,
        evidence_refs: list[str] | tuple[str, ...] | None = None,
        return_transaction: bool = False,
    ) -> dict[str, Any]:
        if on_exists not in ("validate", "error"):
            raise ValueError("on_exists must be 'validate' or 'error'")

        profile = load_profile_from_content(profile_toml, kernel=self._schema)
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

        normalized_decision_id = self._dt.normalize_decision_id(decision_id)
        normalized_evidence_refs = self._dt.normalize_evidence_refs(evidence_refs)
        decision_warnings = self._dt.decision_trace_warnings(
            normalized_decision_id,
            normalized_evidence_refs,
        )

        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_model_register_{profile.name}_{profile.version}",
            tx_type="kernel_model_registry_write",
            payload={
                "operation": "register",
                "model_name": profile.name,
                "version": profile.version,
                "actor": actor,
                "activate": activate,
                "on_exists": on_exists,
                "decision_id": normalized_decision_id,
                "evidence_count": len(normalized_evidence_refs),
            },
        )

        context_obj = {"source": "governance:models/register", **(context or {})}
        if normalized_decision_id is not None and "decision_id" not in context_obj:
            context_obj["decision_id"] = normalized_decision_id
        if normalized_evidence_refs and "evidence_refs" not in context_obj:
            context_obj["evidence_refs"] = list(normalized_evidence_refs)

        try:
            try:
                result = self._model_registration.register(
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
                rerun = self._model_registration.validate_registered(
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
                activation = self._model_registration.activate(
                    profile.name,
                    profile.version,
                    actor=created_by or actor,
                )

            snapshot_id = self._save_kernel_model_snapshot(profile.name, actor=actor)
            self._execution_service.tx_manager.add_event(
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
                self._execution_service.tx_manager.add_event(
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
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_snapshot_saved",
                "Kernel model snapshot persisted by governance.",
                payload={
                    "model_id": snapshot_id,
                    "model_name": profile.name,
                    "actor": actor,
                },
            )
            if normalized_decision_id is not None:
                if decision_warnings:
                    self._execution_service.tx_manager.add_event(
                        tx.id,
                        "decision_trace_warning",
                        "Decision trace evidence warning detected.",
                        payload={
                            "decision_id": normalized_decision_id,
                            "warnings": list(decision_warnings),
                            "operation": "register",
                            "model_name": profile.name,
                            "version": profile.version,
                        },
                    )
                self._dt.record_model_decision_trace(
                    decision_id=normalized_decision_id,
                    operation="register",
                    model_name=profile.name,
                    version=profile.version,
                    status=activation.status if activation else "registered",
                    actor=actor,
                    transaction_id=tx.id,
                    evidence_refs=normalized_evidence_refs,
                    warnings=decision_warnings,
                    detail={
                        "created": created,
                        "validation_run_id": run_id,
                        "activated": activation is not None,
                        "active_version_id": (
                            activation.active_version_id if activation else None
                        ),
                    },
                )
                self._execution_service.tx_manager.add_event(
                    tx.id,
                    "decision_trace_linked",
                    "Model operation linked to decision trace.",
                    payload={
                        "decision_id": normalized_decision_id,
                        "operation": "register",
                        "model_name": profile.name,
                        "version": profile.version,
                    },
                )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        response: dict[str, Any] = {
            "model_name": profile.name,
            "version": profile.version,
            "created": created,
            "validation_run_id": run_id,
            "activated": activation is not None,
            "status": activation.status if activation else "registered",
            "active_version_id": activation.active_version_id if activation else None,
        }
        if normalized_decision_id is not None:
            response["decision_trace"] = {
                "decision_id": normalized_decision_id,
                "trace_model_id": self._dt.decision_trace_model_id(normalized_decision_id),
                "evidence_refs": list(normalized_evidence_refs),
                "warnings": list(decision_warnings),
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
        decision_id: str | None = None,
        evidence_refs: list[str] | tuple[str, ...] | None = None,
        return_transaction: bool = False,
    ) -> ValidationRunEntry | dict[str, Any]:
        normalized_decision_id = self._dt.normalize_decision_id(decision_id)
        normalized_evidence_refs = self._dt.normalize_evidence_refs(evidence_refs)
        decision_warnings = self._dt.decision_trace_warnings(
            normalized_decision_id,
            normalized_evidence_refs,
        )

        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_model_validate_{model_name}_{version}",
            tx_type="kernel_model_registry_validate",
            payload={
                "operation": "validate",
                "model_name": model_name,
                "version": version,
                "actor": actor,
                "decision_id": normalized_decision_id,
                "evidence_count": len(normalized_evidence_refs),
            },
        )

        try:
            context_obj = {"source": "governance:models/validate", **(context or {})}
            if normalized_decision_id is not None and "decision_id" not in context_obj:
                context_obj["decision_id"] = normalized_decision_id
            if normalized_evidence_refs and "evidence_refs" not in context_obj:
                context_obj["evidence_refs"] = list(normalized_evidence_refs)
            run = self._model_registration.validate_registered(
                model_name,
                version,
                context=context_obj,
            )
            snapshot_id = self._save_kernel_model_snapshot(model_name, actor=actor)
            self._execution_service.tx_manager.add_event(
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
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_snapshot_saved",
                "Kernel model snapshot persisted by governance.",
                payload={
                    "model_id": snapshot_id,
                    "model_name": model_name,
                    "actor": actor,
                },
            )
            if normalized_decision_id is not None:
                if decision_warnings:
                    self._execution_service.tx_manager.add_event(
                        tx.id,
                        "decision_trace_warning",
                        "Decision trace evidence warning detected.",
                        payload={
                            "decision_id": normalized_decision_id,
                            "warnings": list(decision_warnings),
                            "operation": "validate",
                            "model_name": model_name,
                            "version": version,
                        },
                    )
                self._dt.record_model_decision_trace(
                    decision_id=normalized_decision_id,
                    operation="validate",
                    model_name=model_name,
                    version=version,
                    status="passed" if run.passed else "failed",
                    actor=actor,
                    transaction_id=tx.id,
                    evidence_refs=normalized_evidence_refs,
                    warnings=decision_warnings,
                    detail={
                        "run_id": run.run_id,
                        "passed": run.passed,
                        "errors": list(run.errors),
                    },
                )
                self._execution_service.tx_manager.add_event(
                    tx.id,
                    "decision_trace_linked",
                    "Model operation linked to decision trace.",
                    payload={
                        "decision_id": normalized_decision_id,
                        "operation": "validate",
                        "model_name": model_name,
                        "version": version,
                        "run_id": run.run_id,
                    },
                )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            response: dict[str, Any] = {"run": run, "transaction_id": tx.id}
            if normalized_decision_id is not None:
                response["decision_trace"] = {
                    "decision_id": normalized_decision_id,
                    "trace_model_id": self._dt.decision_trace_model_id(normalized_decision_id),
                    "evidence_refs": list(normalized_evidence_refs),
                    "warnings": list(decision_warnings),
                }
            return response
        return run

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
        normalized_decision_id = self._dt.normalize_decision_id(decision_id)
        normalized_evidence_refs = self._dt.normalize_evidence_refs(evidence_refs)
        decision_warnings = self._dt.decision_trace_warnings(
            normalized_decision_id,
            normalized_evidence_refs,
        )

        tx = self._execution_service.tx_manager.begin_transaction(
            f"kernel_model_activate_{model_name}_{version}",
            tx_type="kernel_model_registry_write",
            payload={
                "operation": "activate",
                "model_name": model_name,
                "version": version,
                "actor": actor,
                "decision_id": normalized_decision_id,
                "evidence_count": len(normalized_evidence_refs),
            },
        )

        try:
            model = self._model_registration.activate(model_name, version, actor=actor)
            snapshot_id = self._save_kernel_model_snapshot(model_name, actor=actor)
            self._execution_service.tx_manager.add_event(
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
            self._execution_service.tx_manager.add_event(
                tx.id,
                "kernel_model_snapshot_saved",
                "Kernel model snapshot persisted by governance.",
                payload={
                    "model_id": snapshot_id,
                    "model_name": model_name,
                    "actor": actor,
                },
            )
            if normalized_decision_id is not None:
                if decision_warnings:
                    self._execution_service.tx_manager.add_event(
                        tx.id,
                        "decision_trace_warning",
                        "Decision trace evidence warning detected.",
                        payload={
                            "decision_id": normalized_decision_id,
                            "warnings": list(decision_warnings),
                            "operation": "activate",
                            "model_name": model_name,
                            "version": version,
                        },
                    )
                self._dt.record_model_decision_trace(
                    decision_id=normalized_decision_id,
                    operation="activate",
                    model_name=model_name,
                    version=version,
                    status=model.status,
                    actor=actor,
                    transaction_id=tx.id,
                    evidence_refs=normalized_evidence_refs,
                    warnings=decision_warnings,
                    detail={
                        "active_version_id": model.active_version_id,
                        "owner": model.owner,
                    },
                )
                self._execution_service.tx_manager.add_event(
                    tx.id,
                    "decision_trace_linked",
                    "Model operation linked to decision trace.",
                    payload={
                        "decision_id": normalized_decision_id,
                        "operation": "activate",
                        "model_name": model_name,
                        "version": version,
                        "active_version_id": model.active_version_id,
                    },
                )
            self._execution_service.tx_manager.commit(tx.id)
        except Exception as exc:
            self._execution_service.tx_manager.fail(tx.id, str(exc))
            raise

        if return_transaction:
            response: dict[str, Any] = {"model": model, "transaction_id": tx.id}
            if normalized_decision_id is not None:
                response["decision_trace"] = {
                    "decision_id": normalized_decision_id,
                    "trace_model_id": self._dt.decision_trace_model_id(normalized_decision_id),
                    "evidence_refs": list(normalized_evidence_refs),
                    "warnings": list(decision_warnings),
                }
            return response
        return model

    def get_kernel_model_state(
        self,
        model_name: str,
        *,
        limit_runs: int = 5,
    ) -> dict[str, Any] | None:
        model = self._model_registration.get_model(model_name)
        if model is None:
            return None

        versions = self._model_registration.list_versions(model_name)
        runs = self._model_registration.list_validation_runs(
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
