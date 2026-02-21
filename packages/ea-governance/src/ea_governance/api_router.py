"""Governance service API routers (FastAPI).

Extracts governance_service query endpoints from ea-kernel's server.py
into ea-governance, fixing the reverse dependency direction.

Usage in ea-kernel server:
    from ea_governance.api_router import governance_router, layer_schema_router
    app.include_router(governance_router)
    app.include_router(layer_schema_router)
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ea_ops.events import (
    FeedbackLayer,
    ServiceOpsEventSpec,
    ServiceOpsSeverity,
    validate_service_ops_event_spec,
    validate_service_ops_payload,
)
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ea_governance.governance_service import (
    business_flow_topology,
    cross_layer_summary,
    governance_dashboard,
    layer_profile_detail,
    layer_schema,
    list_managed_layers,
)

governance_router = APIRouter(prefix="/governance", tags=["governance"])
layer_schema_router = APIRouter(tags=["layers"])


class ServiceOpsEventSpecRequest(BaseModel):
    """ServiceOpsEventSpec request payload."""

    name: str = Field(min_length=3, max_length=64)
    severity: ServiceOpsSeverity
    must_include: tuple[str, ...]
    feeds_back_to: FeedbackLayer


class ServiceOpsIngestionRequest(BaseModel):
    """Single event ingestion API payload."""

    spec: ServiceOpsEventSpecRequest
    payload: dict[str, Any]
    catalog_id: str | None = None
    stakeholder_id: str | None = None
    auto_express: bool = False
    tags: list[str] | None = None
    actor: str = "api-user"


def _resolve_governance_container(request: Request) -> Any:
    container = getattr(request.app.state, "governance_container", None)
    if container is not None:
        return container

    system = getattr(request.app.state, "system", None)
    schema = getattr(system, "_base_schema", None)
    system_data_dir = getattr(system, "data_dir", None)
    data_dir = system_data_dir.parent if isinstance(system_data_dir, Path) else None
    if data_dir is None or schema is None:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ops_ingestion_configuration_error",
                "message": "governance container is not initialized",
                "issues": [
                    {
                        "field": "app.state.governance_container",
                        "message": (
                            "set app.state.governance_container or provide app.state.system "
                            "with data_dir/_base_schema"
                        ),
                    }
                ],
            },
        )

    from ea_governance.facade import GovernanceContainer

    container = GovernanceContainer(data_dir, schema, kernel_system=system)
    request.app.state.governance_container = container
    registration = getattr(request.app.state, "registration", None)
    if registration is None:
        request.app.state.registration = getattr(container, "model_registration", None)
    return container


def _validation_issue(field: str, message: str) -> dict[str, str]:
    return {"field": field, "message": message}


def _validation_error(issues: list[dict[str, str]]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": "ops_event_validation_error",
            "message": "Service ops ingestion request failed validation",
            "issues": issues,
        },
    )


def _spec_validation_issues(errors: list[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for message in errors:
        field = "spec"
        if message.startswith("name "):
            field = "spec.name"
        elif message.startswith("must_include "):
            field = "spec.must_include"
        issues.append(_validation_issue(field, message))
    return issues


def _payload_validation_issues(errors: list[str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    marker = "missing required ops field:"
    for message in errors:
        field = "payload"
        if message.startswith(marker):
            required_field = message[len(marker):].strip()
            if required_field:
                field = f"payload.{required_field}"
        issues.append(_validation_issue(field, message))
    return issues


def _ingestion_response(result: Mapping[str, Any]) -> dict[str, Any]:
    infra_snapshot_id = result.get("infra_snapshot_id")
    feedback_snapshot_id = result.get("feedback_snapshot_id")
    snapshot_id = feedback_snapshot_id or infra_snapshot_id
    return {
        **dict(result),
        "transaction_id": str(result.get("transaction_id", "")),
        "trace_id": str(result.get("trace_id", "")),
        "lineage_id": str(result.get("lineage_id", "")),
        "snapshot_id": snapshot_id,
    }


@governance_router.get("/layers")
def list_governance_layers() -> dict[str, Any]:
    """List all managed EA-sys layers and governance stack profiles."""
    return list_managed_layers()


@governance_router.get("/layers/summary")
def governance_cross_layer_summary() -> dict[str, Any]:
    """Cross-layer comparison: node/edge counts, top relations."""
    return cross_layer_summary()


@governance_router.get("/layers/{layer_key}")
def governance_layer_detail(layer_key: str) -> dict[str, Any]:
    """Specific layer profile detail + topology metrics."""
    result = layer_profile_detail(layer_key)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@governance_router.get("/business-flow")
def governance_business_flow(lang: str | None = None) -> dict[str, Any]:
    """Cross-layer business flow topology for graph visualization."""
    result = business_flow_topology(lang=lang)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@governance_router.get("/dashboard")
def governance_dashboard_endpoint() -> dict[str, Any]:
    """Overall governance status: layers, schema, frameworks."""
    return governance_dashboard()


@governance_router.post("/ops-events/ingest")
def ingest_service_ops_event(
    request: Request,
    body: ServiceOpsIngestionRequest,
) -> dict[str, Any]:
    """Ingest a single service operations event through governance pipeline."""
    spec = ServiceOpsEventSpec(
        name=body.spec.name,
        severity=body.spec.severity,
        must_include=tuple(body.spec.must_include),
        feeds_back_to=body.spec.feeds_back_to,
    )
    spec_errors = validate_service_ops_event_spec(spec)
    payload_errors = validate_service_ops_payload(spec, body.payload)
    issues = _spec_validation_issues(spec_errors) + _payload_validation_issues(payload_errors)
    if issues:
        raise _validation_error(issues)

    container = _resolve_governance_container(request)
    try:
        result = container.ingest_service_ops_event(
            spec=spec,
            payload=body.payload,
            catalog_id=body.catalog_id,
            stakeholder_id=body.stakeholder_id,
            auto_express=body.auto_express,
            tags=body.tags,
            actor=body.actor,
        )
    except ValueError as err:
        raise _validation_error([_validation_issue("request", str(err))]) from err

    return _ingestion_response(result)


@layer_schema_router.get("/layers/{layer_key}/schema")
def get_layer_schema(
    layer_key: str,
    lang: str | None = None,
) -> dict[str, Any]:
    """Layer M2 schema — raw profile elements, relations, and rules."""
    result = layer_schema(layer_key, lang=lang)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@layer_schema_router.get("/layers/{layer_key}/m2")
def get_layer_m2(
    layer_key: str,
    lang: str | None = None,
) -> dict[str, Any]:
    """Layer M2 schema alias — explicit M2 endpoint for layer-first clients."""
    result = layer_schema(layer_key, lang=lang)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
