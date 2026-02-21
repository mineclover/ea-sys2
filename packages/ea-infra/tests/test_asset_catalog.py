"""Tests for infra asset catalog model + stores."""

from __future__ import annotations

from pathlib import Path

import pytest
from ea_infra.asset_catalog import (
    InfraAssetCatalogStore,
    InfraAssetQuery,
    InMemoryInfraAssetCatalogStore,
    SQLiteInfraAssetCatalogStore,
)
from ea_profile.v2.types import (
    InfraAssetSpec,
    InfraAssetType,
    InfraCriticality,
    InfraEnvironment,
)


def _asset(
    asset_id: str,
    *,
    owner: str,
    environment: InfraEnvironment,
    criticality: InfraCriticality,
    asset_type: InfraAssetType,
    exposure_refs: tuple[str, ...],
) -> InfraAssetSpec:
    return InfraAssetSpec(
        id=asset_id,
        asset_type=asset_type,
        owner=owner,
        environment=environment,
        criticality=criticality,
        exposure_refs=exposure_refs,
    )


def _sample_assets() -> tuple[InfraAssetSpec, InfraAssetSpec, InfraAssetSpec]:
    return (
        _asset(
            "infra-api-gateway-prod",
            owner="platform-network",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER0,
            asset_type=InfraAssetType.API_GATEWAY,
            exposure_refs=("url:https://api.company.com/orders", "api:orders-public"),
        ),
        _asset(
            "infra-db-prod",
            owner="platform-data",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER1,
            asset_type=InfraAssetType.DATABASE,
            exposure_refs=("file:infra/db/orders-primary.tf",),
        ),
        _asset(
            "infra-cache-staging",
            owner="platform-data",
            environment=InfraEnvironment.STAGING,
            criticality=InfraCriticality.TIER2,
            asset_type=InfraAssetType.CACHE,
            exposure_refs=("dashboard:grafana/orders-cache",),
        ),
    )


def test_infra_asset_spec_enforces_field_constraints():
    with pytest.raises(TypeError, match="asset_type must be InfraAssetType"):
        InfraAssetSpec(
            id="infra-invalid-asset-type",
            asset_type="api_gateway",  # type: ignore[arg-type]
            owner="platform-network",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER1,
            exposure_refs=("url:https://api.company.com/orders",),
        )

    with pytest.raises(TypeError, match="environment must be InfraEnvironment"):
        InfraAssetSpec(
            id="infra-invalid-environment",
            asset_type=InfraAssetType.API_GATEWAY,
            owner="platform-network",
            environment="prod",  # type: ignore[arg-type]
            criticality=InfraCriticality.TIER1,
            exposure_refs=("url:https://api.company.com/orders",),
        )

    with pytest.raises(TypeError, match="criticality must be InfraCriticality"):
        InfraAssetSpec(
            id="infra-invalid-criticality",
            asset_type=InfraAssetType.API_GATEWAY,
            owner="platform-network",
            environment=InfraEnvironment.PROD,
            criticality="tier1",  # type: ignore[arg-type]
            exposure_refs=("url:https://api.company.com/orders",),
        )

    with pytest.raises(ValueError, match="owner must be a team slug"):
        InfraAssetSpec(
            id="infra-invalid-owner",
            asset_type=InfraAssetType.COMPUTE_SERVICE,
            owner="Platform Team",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER1,
            exposure_refs=("file:infra/compute/orders-service.yaml",),
        )

    with pytest.raises(ValueError, match="exposure_refs entries must start"):
        InfraAssetSpec(
            id="infra-invalid-ref-prefix",
            asset_type=InfraAssetType.DATABASE,
            owner="platform-data",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER1,
            exposure_refs=("arn:aws:rds:orders",),
        )


def test_infra_asset_spec_requires_url_or_api_for_api_gateway():
    with pytest.raises(ValueError, match="api_gateway assets require"):
        InfraAssetSpec(
            id="infra-api-gateway-invalid",
            asset_type=InfraAssetType.API_GATEWAY,
            owner="platform-network",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER1,
            exposure_refs=("file:infra/k8s/orders-gateway.yaml",),
        )


def test_infra_asset_query_validates_bounds_and_owner():
    with pytest.raises(ValueError, match="owner must be a non-empty string when provided"):
        InfraAssetQuery(owner="   ")

    with pytest.raises(ValueError, match="limit must be >= 0"):
        InfraAssetQuery(limit=-1)

    with pytest.raises(ValueError, match="offset must be >= 0"):
        InfraAssetQuery(offset=-1)


def test_catalog_store_protocol_conformance(tmp_path: Path):
    memory = InMemoryInfraAssetCatalogStore()
    sqlite = SQLiteInfraAssetCatalogStore(tmp_path / "infra-assets.db")
    assert isinstance(memory, InfraAssetCatalogStore)
    assert isinstance(sqlite, InfraAssetCatalogStore)


def test_in_memory_catalog_store_save_get_list_and_filters():
    store = InMemoryInfraAssetCatalogStore()
    gateway, database, cache = _sample_assets()

    assert store.save(gateway) == gateway.id
    assert store.save(database) == database.id
    assert store.save(cache) == cache.id

    loaded = store.get("infra-api-gateway-prod")
    assert loaded == gateway

    by_owner = store.list(query=InfraAssetQuery(owner="platform-data", limit=10))
    assert [asset.id for asset in by_owner] == ["infra-cache-staging", "infra-db-prod"]

    by_environment = store.list(query=InfraAssetQuery(environment=InfraEnvironment.PROD, limit=10))
    assert [asset.id for asset in by_environment] == ["infra-api-gateway-prod", "infra-db-prod"]

    by_criticality = store.list(query=InfraAssetQuery(criticality=InfraCriticality.TIER1, limit=10))
    assert [asset.id for asset in by_criticality] == ["infra-db-prod"]

    page = store.list(query=InfraAssetQuery(owner="platform-data", limit=1, offset=1))
    assert [asset.id for asset in page] == ["infra-db-prod"]

    assert store.count(query=InfraAssetQuery(owner="platform-data")) == 2
    assert store.count(query=InfraAssetQuery(environment=InfraEnvironment.PROD)) == 2
    assert store.count(query=InfraAssetQuery(criticality=InfraCriticality.TIER1)) == 1


def test_sqlite_catalog_store_save_get_list_and_filters(tmp_path: Path):
    db_path = tmp_path / "infra-assets.db"
    gateway, database, cache = _sample_assets()

    store = SQLiteInfraAssetCatalogStore(db_path)
    store.save(gateway)
    store.save(database)
    store.save(cache)

    reloaded = SQLiteInfraAssetCatalogStore(db_path)
    loaded = reloaded.get("infra-api-gateway-prod")
    assert loaded == gateway

    by_owner = reloaded.list(query=InfraAssetQuery(owner="platform-data", limit=10))
    assert [asset.id for asset in by_owner] == ["infra-cache-staging", "infra-db-prod"]

    by_environment = reloaded.list(
        query=InfraAssetQuery(environment=InfraEnvironment.PROD, limit=10),
    )
    assert [asset.id for asset in by_environment] == ["infra-api-gateway-prod", "infra-db-prod"]

    by_criticality = reloaded.list(
        query=InfraAssetQuery(criticality=InfraCriticality.TIER1, limit=10),
    )
    assert [asset.id for asset in by_criticality] == ["infra-db-prod"]

    assert reloaded.count(query=InfraAssetQuery(owner="platform-data")) == 2
    assert reloaded.count(query=InfraAssetQuery(environment=InfraEnvironment.PROD)) == 2
    assert reloaded.count(query=InfraAssetQuery(criticality=InfraCriticality.TIER1)) == 1


def test_sqlite_catalog_store_upserts_existing_asset(tmp_path: Path):
    store = SQLiteInfraAssetCatalogStore(tmp_path / "infra-assets.db")
    _, database, _ = _sample_assets()
    store.save(database)

    updated = _asset(
        "infra-db-prod",
        owner="platform-data",
        environment=InfraEnvironment.PROD,
        criticality=InfraCriticality.TIER0,
        asset_type=InfraAssetType.DATABASE,
        exposure_refs=("api:orders-db-admin",),
    )
    store.save(updated)

    loaded = store.get("infra-db-prod")
    assert loaded == updated
