"""Decision trace operations extracted from GovernanceContainer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

_DECISION_TRACE_PREFIX = "decision_trace:"
_DECISION_TRACE_KIND = "decision_trace_contract"
_DECISION_TRACE_VERSION = "1.0"
_MISSING_EVIDENCE_WARNING = "missing_evidence_refs"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DecisionTraceOps:
    """Encapsulates decision-trace read/write against layer stores."""

    def __init__(
        self,
        layer_stores: dict[str, Any],
        execution_service: Any,
    ) -> None:
        self._layer_stores = layer_stores
        self._execution_service = execution_service

    # -- Static helpers --------------------------------------------------------

    @staticmethod
    def normalize_decision_id(decision_id: str | None) -> str | None:
        if decision_id is None:
            return None
        normalized = decision_id.strip()
        if len(normalized) == 0:
            return None
        return normalized

    @staticmethod
    def normalize_evidence_refs(
        evidence_refs: list[str] | tuple[str, ...] | None,
    ) -> list[str]:
        if evidence_refs is None:
            return []
        normalized: list[str] = []
        for raw in evidence_refs:
            value = raw.strip()
            if len(value) == 0:
                continue
            if value not in normalized:
                normalized.append(value)
        return normalized

    @staticmethod
    def decision_trace_model_id(decision_id: str) -> str:
        return f"{_DECISION_TRACE_PREFIX}{decision_id}"

    @staticmethod
    def decision_trace_warnings(
        decision_id: str | None,
        evidence_refs: list[str],
    ) -> list[str]:
        warnings: list[str] = []
        if decision_id is not None and len(evidence_refs) == 0:
            warnings.append(_MISSING_EVIDENCE_WARNING)
        return warnings

    # -- Mutating operations ---------------------------------------------------

    def record_model_decision_trace(
        self,
        *,
        decision_id: str,
        operation: str,
        model_name: str,
        version: str,
        status: str,
        actor: str,
        transaction_id: str,
        evidence_refs: list[str],
        warnings: list[str],
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        store = self._layer_stores["decision"]
        model_id = self.decision_trace_model_id(decision_id)
        existing = store.get_payload(model_id)

        if (
            existing is None
            or existing.get("kind") != _DECISION_TRACE_KIND
            or existing.get("decision_id") != decision_id
        ):
            trace: dict[str, Any] = {
                "kind": _DECISION_TRACE_KIND,
                "contract_version": _DECISION_TRACE_VERSION,
                "decision_id": decision_id,
                "created_at": _now_iso(),
                "updated_at": "",
                "evidence_refs": [],
                "warnings": [],
                "operations": [],
                "impact": [],
                "history": [],
            }
        else:
            trace = dict(existing)
            trace["evidence_refs"] = [
                item
                for item in trace.get("evidence_refs", [])
                if isinstance(item, str)
            ]
            trace["warnings"] = [
                item
                for item in trace.get("warnings", [])
                if isinstance(item, str)
            ]
            trace["operations"] = [
                item
                for item in trace.get("operations", [])
                if isinstance(item, dict)
            ]
            trace["impact"] = [
                item
                for item in trace.get("impact", [])
                if isinstance(item, dict)
            ]
            trace["history"] = [
                item
                for item in trace.get("history", [])
                if isinstance(item, dict)
            ]

        now = _now_iso()
        merged_evidence_refs = cast(list[str], trace["evidence_refs"])
        for ref in evidence_refs:
            if ref not in merged_evidence_refs:
                merged_evidence_refs.append(ref)

        merged_warnings = cast(list[str], trace["warnings"])
        for warning in warnings:
            if warning not in merged_warnings:
                merged_warnings.append(warning)

        operations = cast(list[dict[str, Any]], trace["operations"])
        op_id = f"{operation}:{transaction_id}"
        operations = [
            row
            for row in operations
            if str(row.get("id", "")) != op_id
        ]
        operations.append(
            {
                "id": op_id,
                "operation": operation,
                "model_name": model_name,
                "version": version,
                "status": status,
                "actor": actor,
                "transaction_id": transaction_id,
                "evidence_refs": list(evidence_refs),
                "warnings": list(warnings),
                "detail": dict(detail or {}),
                "created_at": now,
            }
        )
        trace["operations"] = operations

        impact = cast(list[dict[str, Any]], trace["impact"])
        impact_entry: dict[str, Any] = {
            "operation": operation,
            "model_name": model_name,
            "version": version,
            "status": status,
            "transaction_id": transaction_id,
            "actor": actor,
            "created_at": now,
        }
        if detail:
            impact_entry["detail"] = dict(detail)
        impact.append(impact_entry)

        history = cast(list[dict[str, Any]], trace["history"])
        history.append(
            {
                "transaction_id": transaction_id,
                "event_type": "decision_trace_linked",
                "message": "Model operation linked to decision trace.",
                "operation": operation,
                "created_at": now,
            }
        )

        trace["updated_at"] = now
        store.save_payload(model_id=model_id, payload=trace)
        return trace

    # -- Read operations -------------------------------------------------------

    def get_model_decision_trace(self, decision_id: str) -> dict[str, Any] | None:
        """Read model decision trace contract from the decision layer store."""
        normalized = self.normalize_decision_id(decision_id)
        if normalized is None:
            raise ValueError("decision_id must be a non-empty string")
        return self._layer_stores["decision"].get_payload(
            self.decision_trace_model_id(normalized)
        )

    def explore_model_decision_trace(self, decision_id: str) -> dict[str, Any] | None:
        """Return evidence/impact/history exploration view for one decision id."""
        trace = self.get_model_decision_trace(decision_id)
        if trace is None:
            return None

        operations = [
            row
            for row in trace.get("operations", [])
            if isinstance(row, dict)
        ]
        warnings = [
            row
            for row in trace.get("warnings", [])
            if isinstance(row, str)
        ]
        evidence_refs = [
            row
            for row in trace.get("evidence_refs", [])
            if isinstance(row, str)
        ]

        missing_evidence_operations = [
            str(row.get("operation"))
            for row in operations
            if any(
                isinstance(warning, str) and warning == _MISSING_EVIDENCE_WARNING
                for warning in cast(list[Any], row.get("warnings", []))
            )
        ]

        tx_ids: list[str] = []
        for row in operations:
            tx_id = row.get("transaction_id")
            if isinstance(tx_id, str) and tx_id not in tx_ids:
                tx_ids.append(tx_id)

        history: list[dict[str, Any]] = [
            row
            for row in trace.get("history", [])
            if isinstance(row, dict)
        ]
        for tx_id in tx_ids:
            tx = self._execution_service.tx_manager.get_transaction(tx_id)
            if tx is None:
                continue
            history.append(
                {
                    "transaction_id": tx.id,
                    "event_type": "transaction_status",
                    "message": f"Transaction status: {tx.status.value}",
                    "created_at": tx.updated_at,
                }
            )
            for event in self._execution_service.tx_manager.get_events(tx_id):
                history.append(
                    {
                        "transaction_id": event.tx_id,
                        "event_id": event.id,
                        "event_type": event.event_type,
                        "message": event.message,
                        "payload": event.payload,
                        "created_at": event.created_at,
                    }
                )

        history.sort(
            key=lambda row: (
                str(row.get("created_at", "")),
                str(row.get("event_id", "")),
                str(row.get("event_type", "")),
            )
        )

        return {
            "decision_id": trace.get("decision_id"),
            "contract_version": trace.get("contract_version"),
            "evidence": {
                "refs": evidence_refs,
                "warnings": warnings,
                "missing_evidence_operations": missing_evidence_operations,
            },
            "impact": {
                "total_operations": len(operations),
                "operations": operations,
                "models": sorted(
                    {
                        str(row.get("model_name"))
                        for row in operations
                        if isinstance(row.get("model_name"), str)
                    }
                ),
            },
            "history": history,
        }
