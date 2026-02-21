from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("fastapi")

from ea_governance.api_router import governance_router
from ea_ops.events import ServiceOpsEventSpec
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeGovernanceContainer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._infra_snapshots: dict[str, dict[str, Any]] = {
            "service_ops_event:evt-001": {
                "kind": "service_ops_event",
                "name": "slo_breached",
                "severity": "high",
                "feeds_back_to": "needs",
                "trace_id": "trace-001",
                "lineage_id": "lineage-001",
                "payload": {
                    "trace_id": "trace-001",
                    "lineage_id": "lineage-001",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
                "ingested_at": "2026-02-21T10:00:00+00:00Z",
            },
            "service_ops_event:evt-002": {
                "kind": "service_ops_event",
                "name": "slo_recovered",
                "severity": "medium",
                "feeds_back_to": "needs",
                "trace_id": "trace-001",
                "lineage_id": "lineage-001",
                "payload": {
                    "trace_id": "trace-001",
                    "lineage_id": "lineage-001",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
                "ingested_at": "2026-02-21T10:05:00+00:00Z",
            },
            "service_ops_event:evt-003": {
                "kind": "service_ops_event",
                "name": "error_rate_spike",
                "severity": "critical",
                "feeds_back_to": "needs",
                "trace_id": "trace-002",
                "lineage_id": "lineage-002",
                "payload": {
                    "trace_id": "trace-002",
                    "lineage_id": "lineage-002",
                    "service_id": "orders-api",
                    "slo_name": "error_rate",
                },
                "ingested_at": "2026-02-21T11:00:00+00:00Z",
            },
            "infra_misc:ignored": {
                "kind": "misc",
                "ingested_at": "2026-02-21T09:00:00+00:00Z",
            },
        }

    def ingest_service_ops_event(
        self,
        *,
        spec: ServiceOpsEventSpec,
        payload: dict[str, Any],
        catalog_id: str | None = None,
        stakeholder_id: str | None = None,
        auto_express: bool = False,
        tags: list[str] | None = None,
        actor: str = "api-user",
    ) -> dict[str, Any]:
        tx_suffix = len(self.calls) + 1
        tx_id = f"tx-api-{tx_suffix:03d}"
        infra_snapshot_id = f"service_ops_event:{tx_id}"
        self.calls.append(
            {
                "spec": spec,
                "payload": payload,
                "catalog_id": catalog_id,
                "stakeholder_id": stakeholder_id,
                "auto_express": auto_express,
                "tags": tags,
                "actor": actor,
            }
        )
        self._infra_snapshots[infra_snapshot_id] = {
            "kind": "service_ops_event",
            "name": spec.name,
            "severity": spec.severity.value,
            "feeds_back_to": spec.feeds_back_to.value,
            "trace_id": str(payload["trace_id"]),
            "lineage_id": str(payload["lineage_id"]),
            "payload": dict(payload),
            "ingested_at": f"2026-02-21T12:{tx_suffix:02d}:00+00:00Z",
        }
        return {
            "event_name": spec.name,
            "severity": spec.severity.value,
            "feeds_back_to": spec.feeds_back_to.value,
            "trace_id": str(payload["trace_id"]),
            "lineage_id": str(payload["lineage_id"]),
            "transaction_id": tx_id,
            "infra_snapshot_id": infra_snapshot_id,
            "feedback_snapshot_id": f"service_ops_feedback:{tx_id}",
            "needs_feedback_draft": {
                "action": "improve",
                "subject": "slo:latency_p95",
                "priority": "high",
                "purpose": "efficiency",
                "tags": ["ops", "slo", "payments-api"],
                "rationale": "SLO breach indicates measurable service quality gap.",
            },
            "expressed_need": None,
        }

    def list_layer_snapshots(self, layer: str) -> list[dict[str, Any]]:
        if layer != "infra":
            return []
        return [
            {
                "layer": "infra",
                "model_id": model_id,
                "payload": payload,
                "updated_at": str(payload.get("ingested_at", "")),
            }
            for model_id, payload in sorted(self._infra_snapshots.items())
        ]

    def get_layer_snapshot(self, layer: str, model_id: str) -> dict[str, Any] | None:
        if layer != "infra":
            return None
        return self._infra_snapshots.get(model_id)


def _build_client(container: _FakeGovernanceContainer) -> TestClient:
    app = FastAPI()
    app.state.governance_container = container
    app.include_router(governance_router)
    return TestClient(app)


def test_ops_event_list_endpoint_supports_limit_offset_pagination() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.get(
        "/governance/ops-events",
        params={"limit": 2, "offset": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert [item["id"] for item in body["items"]] == [
        "service_ops_event:evt-002",
        "service_ops_event:evt-001",
    ]


def test_ops_event_list_endpoint_filters_by_correlation_event_name_and_time_range() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.get(
        "/governance/ops-events",
        params={
            "trace_id": "trace-001",
            "lineage_id": "lineage-001",
            "event_name": "slo_recovered",
            "ingested_from": "2026-02-21T10:03:00Z",
            "ingested_to": "2026-02-21T10:06:00Z",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "service_ops_event:evt-002"
    assert body["items"][0]["trace_id"] == "trace-001"
    assert body["items"][0]["lineage_id"] == "lineage-001"
    assert body["items"][0]["event_name"] == "slo_recovered"


def test_ops_event_get_endpoint_returns_record_or_404() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.get("/governance/ops-events/service_ops_event:evt-001")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "service_ops_event:evt-001"
    assert body["event_name"] == "slo_breached"
    assert body["trace_id"] == "trace-001"
    assert body["lineage_id"] == "lineage-001"

    missing = client.get("/governance/ops-events/service_ops_event:missing")
    assert missing.status_code == 404
    detail = missing.json()["detail"]
    assert detail["error"] == "ops_event_not_found"


def test_ops_event_ingestion_endpoint_success() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.post(
        "/governance/ops-events/ingest",
        json={
            "spec": {
                "name": "slo_breached",
                "severity": "high",
                "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                "feeds_back_to": "needs",
            },
            "payload": {
                "trace_id": "trace-api-001",
                "lineage_id": "lineage-api-001",
                "service_id": "payments-api",
                "slo_name": "latency_p95",
            },
            "catalog_id": "catalog-001",
            "stakeholder_id": "stakeholder-001",
            "auto_express": False,
            "tags": ["ops", "slo"],
            "actor": "ops-bot",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transaction_id"] == "tx-api-001"
    assert body["trace_id"] == "trace-api-001"
    assert body["lineage_id"] == "lineage-api-001"
    assert body["snapshot_id"] == "service_ops_feedback:tx-api-001"
    assert body["infra_snapshot_id"] == "service_ops_event:tx-api-001"
    assert body["feedback_snapshot_id"] == "service_ops_feedback:tx-api-001"

    assert len(container.calls) == 1
    call = container.calls[0]
    assert isinstance(call["spec"], ServiceOpsEventSpec)
    assert call["spec"].name == "slo_breached"
    assert call["spec"].must_include == (
        "trace_id",
        "lineage_id",
        "service_id",
        "slo_name",
    )
    assert call["payload"]["trace_id"] == "trace-api-001"


def test_ops_event_ingestion_endpoint_returns_structured_spec_validation_error() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.post(
        "/governance/ops-events/ingest",
        json={
            "spec": {
                "name": "slo_breached",
                "severity": "high",
                "must_include": ["lineage_id", "service_id", "slo_name"],
                "feeds_back_to": "needs",
            },
            "payload": {
                "trace_id": "trace-api-001",
                "lineage_id": "lineage-api-001",
                "service_id": "payments-api",
                "slo_name": "latency_p95",
            },
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "ops_event_validation_error"
    assert detail["message"] == "Service ops ingestion request failed validation"
    assert any(
        issue["field"] == "spec.must_include" and "must_include must contain trace_id" in issue["message"]
        for issue in detail["issues"]
    )
    assert container.calls == []


def test_ops_event_ingestion_endpoint_returns_structured_payload_validation_error() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.post(
        "/governance/ops-events/ingest",
        json={
            "spec": {
                "name": "slo_breached",
                "severity": "high",
                "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                "feeds_back_to": "needs",
            },
            "payload": {
                "trace_id": "trace-api-001",
                "lineage_id": "lineage-api-001",
                "service_id": "payments-api",
            },
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error"] == "ops_event_validation_error"
    assert any(
        issue["field"] == "payload.slo_name" and "missing required ops field: slo_name" in issue["message"]
        for issue in detail["issues"]
    )
    assert container.calls == []


def test_ops_event_bulk_ingestion_endpoint_success_with_partial_strategy_contract() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.post(
        "/governance/ops-events/ingest/bulk",
        json=[
            {
                "spec": {
                    "name": "slo_breached",
                    "severity": "high",
                    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                    "feeds_back_to": "needs",
                },
                "payload": {
                    "trace_id": "trace-bulk-001",
                    "lineage_id": "lineage-bulk-001",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
                "actor": "ops-bot",
            },
            {
                "spec": {
                    "name": "slo_recovered",
                    "severity": "medium",
                    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                    "feeds_back_to": "needs",
                },
                "payload": {
                    "trace_id": "trace-bulk-001",
                    "lineage_id": "lineage-bulk-001",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
                "actor": "ops-bot",
            },
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "partial"
    assert body["success_count"] == 2
    assert body["failed_count"] == 0
    assert len(body["results"]) == 2
    assert body["results"][0]["status"] == "success"
    assert body["results"][1]["status"] == "success"
    assert body["results"][0]["result"]["transaction_id"] == "tx-api-001"
    assert body["results"][1]["result"]["transaction_id"] == "tx-api-002"
    assert len(container.calls) == 2


def test_ops_event_bulk_ingestion_endpoint_partial_failure_does_not_abort() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.post(
        "/governance/ops-events/ingest/bulk",
        json=[
            {
                "spec": {
                    "name": "slo_breached",
                    "severity": "high",
                    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                    "feeds_back_to": "needs",
                },
                "payload": {
                    "trace_id": "trace-bulk-002",
                    "lineage_id": "lineage-bulk-002",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
            },
            {
                "spec": {
                    "name": "slo_breached",
                    "severity": "high",
                    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                    "feeds_back_to": "needs",
                },
                "payload": {
                    "trace_id": "trace-bulk-002",
                    "lineage_id": "lineage-bulk-002",
                    "service_id": "payments-api",
                },
            },
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["strategy"] == "partial"
    assert body["success_count"] == 1
    assert body["failed_count"] == 1
    assert body["results"][0]["status"] == "success"
    assert body["results"][1]["status"] == "failed"
    assert body["results"][1]["error"]["error"] == "ops_event_validation_error"
    assert any(
        issue["field"] == "items[1].payload.slo_name"
        and "missing required ops field: slo_name" in issue["message"]
        for issue in body["results"][1]["error"]["issues"]
    )
    assert len(container.calls) == 1


def test_ops_event_bulk_ingestion_endpoint_validates_trace_lineage_correlation() -> None:
    container = _FakeGovernanceContainer()
    client = _build_client(container)

    response = client.post(
        "/governance/ops-events/ingest/bulk",
        json=[
            {
                "spec": {
                    "name": "slo_breached",
                    "severity": "high",
                    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                    "feeds_back_to": "needs",
                },
                "payload": {
                    "trace_id": "trace-bulk-003",
                    "lineage_id": "lineage-bulk-003",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
            },
            {
                "spec": {
                    "name": "slo_recovered",
                    "severity": "medium",
                    "must_include": ["trace_id", "lineage_id", "service_id", "slo_name"],
                    "feeds_back_to": "needs",
                },
                "payload": {
                    "trace_id": "trace-bulk-999",
                    "lineage_id": "lineage-bulk-003",
                    "service_id": "payments-api",
                    "slo_name": "latency_p95",
                },
            },
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success_count"] == 1
    assert body["failed_count"] == 1
    assert body["results"][1]["status"] == "failed"
    assert any(
        issue["field"] == "items[1].payload.trace_id"
        and "bulk correlation mismatch" in issue["message"]
        for issue in body["results"][1]["error"]["issues"]
    )
    assert len(container.calls) == 1
