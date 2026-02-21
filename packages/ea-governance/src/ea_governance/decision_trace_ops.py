"""Decision trace operations extracted from GovernanceContainer."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from ea_trace.chain import (
    LineageError,
    TraceLink,
    TraceNodeRef,
    compose_lineage,
    missing_required_relations,
    replay_lineage_nodes,
)

_DECISION_TRACE_PREFIX = "decision_trace:"
_DECISION_TRACE_KIND = "decision_trace_contract"
_DECISION_TRACE_VERSION = "1.0"
_MISSING_EVIDENCE_WARNING = "missing_evidence_refs"
_INVALID_CAUSE_TYPE_PREFIX = "invalid_cause_type:"
_INVALID_CHANGE_PHASE_PREFIX = "invalid_change_phase:"
_LINEAGE_REQUIRED_RELATIONS = ("drives", "materializes")

_ALLOWED_CAUSE_TYPES = frozenset({"decision", "need"})
_CAUSE_TYPE_ALIASES = {
    "needs": "need",
}

_ALLOWED_CHANGE_PHASES = frozenset({"planned", "applied", "superseded", "rolled_back"})
_CHANGE_PHASE_ALIASES = {
    "pending": "planned",
    "registered": "planned",
    "validated": "planned",
    "active": "applied",
    "implemented": "applied",
    "done": "applied",
    "deprecated": "superseded",
    "historical": "superseded",
    "rollback": "rolled_back",
    "rolledback": "rolled_back",
}
_OPERATION_PHASE_DEFAULT = {
    "register": "planned",
    "validate": "planned",
    "activate": "applied",
}


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
    def normalize_cause_id(cause_id: str | None) -> str | None:
        if cause_id is None:
            return None
        normalized = cause_id.strip()
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
    def _to_trace_node(node_type: str, node_id: str) -> TraceNodeRef:
        return TraceNodeRef(node_type=node_type, node_id=node_id)

    @classmethod
    def _build_links_for_operation(
        cls,
        *,
        decision_id: str,
        cause_type: str,
        cause_id: str,
        operation_id: str,
        model_name: str,
        version: str,
    ) -> list[TraceLink]:
        links: list[TraceLink] = []

        decision_node = cls._to_trace_node("decision_record", decision_id)
        operation_node = cls._to_trace_node("kernel_model_operation", operation_id)
        model_node = cls._to_trace_node("kernel_model", f"{model_name}:{version}")

        if cause_type != "decision" or cause_id != decision_id:
            source = cls._to_trace_node(f"{cause_type}_record", cause_id)
            links.append(
                TraceLink(
                    source=source,
                    target=decision_node,
                    relation="causes",
                    required=True,
                )
            )

        links.append(
            TraceLink(
                source=decision_node,
                target=operation_node,
                relation="drives",
                required=True,
            )
        )
        links.append(
            TraceLink(
                source=operation_node,
                target=model_node,
                relation="materializes",
                required=True,
            )
        )
        return links

    @staticmethod
    def _serialize_trace_link(link: TraceLink) -> dict[str, Any]:
        return {
            "source_type": link.source.node_type,
            "source_id": link.source.node_id,
            "target_type": link.target.node_type,
            "target_id": link.target.node_id,
            "relation": link.relation,
            "required": bool(link.required),
        }

    @classmethod
    def _deserialize_trace_links(cls, rows: list[dict[str, Any]]) -> list[TraceLink]:
        links: list[TraceLink] = []
        for row in rows:
            source_type = row.get("source_type")
            source_id = row.get("source_id")
            target_type = row.get("target_type")
            target_id = row.get("target_id")
            relation = row.get("relation")
            required = row.get("required", True)
            if not all(
                isinstance(item, str) and item.strip()
                for item in (source_type, source_id, target_type, target_id, relation)
            ):
                continue
            links.append(
                TraceLink(
                    source=cls._to_trace_node(str(source_type), str(source_id)),
                    target=cls._to_trace_node(str(target_type), str(target_id)),
                    relation=str(relation),
                    required=bool(required),
                )
            )
        return links

    @staticmethod
    def _trace_link_key(link: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            str(link.get("source_type", "")),
            str(link.get("source_id", "")),
            str(link.get("target_type", "")),
            str(link.get("target_id", "")),
            str(link.get("relation", "")),
        )

    @classmethod
    def normalize_cause_type(
        cls,
        cause_type: str | None,
        *,
        default: str = "decision",
    ) -> tuple[str, str | None]:
        token = (cause_type or "").strip().lower().replace("-", "_")
        if len(token) == 0:
            return default, None
        token = _CAUSE_TYPE_ALIASES.get(token, token)
        if token in _ALLOWED_CAUSE_TYPES:
            return token, None
        return default, f"{_INVALID_CAUSE_TYPE_PREFIX}{token}"

    @classmethod
    def default_change_phase(cls, operation: str | None) -> str:
        op = (operation or "").strip().lower()
        return _OPERATION_PHASE_DEFAULT.get(op, "planned")

    @classmethod
    def normalize_change_phase(
        cls,
        change_phase: str | None,
        *,
        operation: str | None = None,
    ) -> tuple[str, str | None]:
        token = (change_phase or "").strip().lower().replace("-", "_")
        default = cls.default_change_phase(operation)
        if len(token) == 0:
            return default, None
        token = _CHANGE_PHASE_ALIASES.get(token, token)
        if token in _ALLOWED_CHANGE_PHASES:
            return token, None
        return default, f"{_INVALID_CHANGE_PHASE_PREFIX}{token}"

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
        cause_type: str,
        cause_id: str | None,
        change_phase: str,
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
                "causes": [],
                "phase_timeline": [],
                "history": [],
                "trace_links": [],
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
            trace["causes"] = [
                item
                for item in trace.get("causes", [])
                if isinstance(item, dict)
            ]
            trace["phase_timeline"] = [
                item
                for item in trace.get("phase_timeline", [])
                if isinstance(item, dict)
            ]
            trace["history"] = [
                item
                for item in trace.get("history", [])
                if isinstance(item, dict)
            ]
            trace["trace_links"] = [
                item
                for item in trace.get("trace_links", [])
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

        resolved_cause_id = cause_id or decision_id
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
                "cause_type": cause_type,
                "cause_id": cause_id,
                "change_phase": change_phase,
                "detail": dict(detail or {}),
                "created_at": now,
            }
        )
        trace["operations"] = operations

        raw_trace_links = cast(list[dict[str, Any]], trace["trace_links"])
        known_link_keys = {self._trace_link_key(link) for link in raw_trace_links}
        for link in self._build_links_for_operation(
            decision_id=decision_id,
            cause_type=cause_type,
            cause_id=resolved_cause_id,
            operation_id=op_id,
            model_name=model_name,
            version=version,
        ):
            serialized = self._serialize_trace_link(link)
            key = self._trace_link_key(serialized)
            if key in known_link_keys:
                continue
            raw_trace_links.append(serialized)
            known_link_keys.add(key)

        impact = cast(list[dict[str, Any]], trace["impact"])
        impact_entry: dict[str, Any] = {
            "operation": operation,
            "model_name": model_name,
            "version": version,
            "status": status,
            "transaction_id": transaction_id,
            "actor": actor,
            "cause_type": cause_type,
            "cause_id": cause_id,
            "change_phase": change_phase,
            "created_at": now,
        }
        if detail:
            impact_entry["detail"] = dict(detail)
        impact.append(impact_entry)

        causes = cast(list[dict[str, Any]], trace["causes"])
        if resolved_cause_id and not any(
            row.get("cause_type") == cause_type and row.get("cause_id") == resolved_cause_id
            for row in causes
        ):
            causes.append(
                {
                    "cause_type": cause_type,
                    "cause_id": resolved_cause_id,
                    "first_seen_at": now,
                }
            )

        phase_timeline = cast(list[dict[str, Any]], trace["phase_timeline"])
        phase_timeline.append(
            {
                "transaction_id": transaction_id,
                "operation": operation,
                "phase": change_phase,
                "status": status,
                "created_at": now,
            }
        )

        history = cast(list[dict[str, Any]], trace["history"])
        history.append(
            {
                "transaction_id": transaction_id,
                "event_type": "decision_trace_linked",
                "message": "Model operation linked to decision trace.",
                "operation": operation,
                "cause_type": cause_type,
                "cause_id": resolved_cause_id,
                "change_phase": change_phase,
                "created_at": now,
            }
        )

        trace["cause_type"] = cause_type
        trace["cause_id"] = resolved_cause_id
        trace["latest_change_phase"] = change_phase
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

        causes: list[dict[str, str]] = []
        phase_counts: dict[str, int] = {}
        latest_phase: str | None = None
        for row in operations:
            phase = str(row.get("change_phase", ""))
            if phase:
                phase_counts[phase] = phase_counts.get(phase, 0) + 1
                latest_phase = phase

            cause_type = row.get("cause_type")
            cause_id = row.get("cause_id")
            if (
                isinstance(cause_type, str)
                and isinstance(cause_id, str)
                and not any(
                    item["cause_type"] == cause_type and item["cause_id"] == cause_id
                    for item in causes
                )
            ):
                causes.append({"cause_type": cause_type, "cause_id": cause_id})

        serialized_links = [
            row
            for row in trace.get("trace_links", [])
            if isinstance(row, dict)
        ]
        parsed_links = self._deserialize_trace_links(serialized_links)

        start_cause_type = trace.get("cause_type")
        start_cause_id = trace.get("cause_id")
        if (
            isinstance(start_cause_type, str)
            and isinstance(start_cause_id, str)
            and start_cause_id
        ):
            start_type = f"{start_cause_type}_record"
            start_node = self._to_trace_node(start_type, start_cause_id)
        else:
            start_node = self._to_trace_node("decision_record", str(trace.get("decision_id", "")))

        replayed_nodes = replay_lineage_nodes(parsed_links, start_node)
        replayed = [
            {"node_type": node.node_type, "node_id": node.node_id}
            for node in replayed_nodes
        ]

        latest_operation_id = ""
        if operations:
            latest_operation_id = str(operations[-1].get("id", ""))

        path_to_latest: list[dict[str, Any]] = []
        path_error: str | None = None
        if latest_operation_id:
            target_node = self._to_trace_node("kernel_model_operation", latest_operation_id)
            try:
                for link in compose_lineage(parsed_links, start_node, target_node):
                    path_to_latest.append(
                        {
                            "source_type": link.source.node_type,
                            "source_id": link.source.node_id,
                            "relation": link.relation,
                            "target_type": link.target.node_type,
                            "target_id": link.target.node_id,
                        }
                    )
            except LineageError as err:
                path_error = str(err)

        missing_relations = sorted(
            missing_required_relations(parsed_links, _LINEAGE_REQUIRED_RELATIONS)
        )

        return {
            "decision_id": trace.get("decision_id"),
            "contract_version": trace.get("contract_version"),
            "causal_context": {
                "cause_type": trace.get("cause_type"),
                "cause_id": trace.get("cause_id"),
                "causes": causes,
                "latest_change_phase": trace.get("latest_change_phase") or latest_phase,
                "phase_counts": phase_counts,
            },
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
            "lineage": {
                "start_node": {
                    "node_type": start_node.node_type,
                    "node_id": start_node.node_id,
                },
                "replayed_nodes": replayed,
                "path_to_latest_operation": path_to_latest,
                "missing_required_relations": missing_relations,
                "path_error": path_error,
            },
            "history": history,
        }
