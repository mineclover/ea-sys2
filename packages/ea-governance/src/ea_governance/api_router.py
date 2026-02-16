"""Governance service API routers (FastAPI).

Extracts governance_service query endpoints from ea-kernel's server.py
into ea-governance, fixing the reverse dependency direction.

Usage in ea-kernel server:
    from ea_governance.api_router import governance_router, layer_schema_router
    app.include_router(governance_router)
    app.include_router(layer_schema_router)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from ea_governance.governance_service import (
    cross_layer_summary,
    governance_dashboard,
    layer_profile_detail,
    layer_schema,
    list_managed_layers,
)

governance_router = APIRouter(prefix="/governance", tags=["governance"])
layer_schema_router = APIRouter(tags=["layers"])


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


@governance_router.get("/dashboard")
def governance_dashboard_endpoint() -> dict[str, Any]:
    """Overall governance status: layers, schema, frameworks."""
    return governance_dashboard()


@layer_schema_router.get("/layers/{layer_key}/schema")
def get_layer_schema(layer_key: str, lang: str | None = None) -> dict[str, Any]:
    """Layer M2 schema — raw profile elements, relations, and rules."""
    result = layer_schema(layer_key, lang=lang)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
