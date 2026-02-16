"""Tests for ea_needs.needs_service — service layer pure functions."""

import pytest

from ea_needs.catalog import NeedCatalog
from ea_needs.needs_service import (
    catalog_summary,
    describe_need,
    list_needs,
    list_stakeholders,
    list_use_cases,
    need_lineage,
)
from ea_needs.types import NeedPriority


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_catalog() -> NeedCatalog:
    return NeedCatalog(name="Empty", description="No data")


@pytest.fixture
def populated_catalog() -> NeedCatalog:
    catalog = NeedCatalog(name="Test Catalog", description="For service tests")
    sh = catalog.add_stakeholder("CTO", "executive", "cloud migration")
    catalog.add_use_case(
        title="Migrate payment",
        actor="DevOps",
        situation="legacy on-prem",
        purpose="move to cloud",
    )
    n1 = catalog.express_need(
        stakeholder_id=sh.id,
        action="migrate",
        subject="payment system",
        target="cloud",
        justifications=[{"type": "because", "description": "frequent outages"}],
        priority=NeedPriority.HIGH,
        tags=["infra"],
    )
    n1.express()

    catalog.express_need(
        stakeholder_id=sh.id,
        action="reduce",
        subject="deployment time",
        priority=NeedPriority.MEDIUM,
    )

    catalog.add_process_unit(
        need_id=n1.id,
        stage="identify",
        label="Identify outage sources",
    )
    return catalog


# ---------------------------------------------------------------------------
# list_stakeholders
# ---------------------------------------------------------------------------

class TestListStakeholders:
    def test_empty_catalog(self, empty_catalog: NeedCatalog):
        result = list_stakeholders(catalog=empty_catalog)
        assert result["count"] == 0
        assert result["stakeholders"] == []

    def test_populated(self, populated_catalog: NeedCatalog):
        result = list_stakeholders(catalog=populated_catalog)
        assert result["count"] == 1
        assert result["stakeholders"][0]["name"] == "CTO"
        assert result["stakeholders"][0]["role"] == "executive"


# ---------------------------------------------------------------------------
# list_use_cases
# ---------------------------------------------------------------------------

class TestListUseCases:
    def test_empty_catalog(self, empty_catalog: NeedCatalog):
        result = list_use_cases(catalog=empty_catalog)
        assert result["count"] == 0

    def test_populated(self, populated_catalog: NeedCatalog):
        result = list_use_cases(catalog=populated_catalog)
        assert result["count"] == 1
        assert result["use_cases"][0]["title"] == "Migrate payment"
        assert result["use_cases"][0]["actor"] == "DevOps"


# ---------------------------------------------------------------------------
# list_needs
# ---------------------------------------------------------------------------

class TestListNeeds:
    def test_empty_catalog(self, empty_catalog: NeedCatalog):
        result = list_needs(catalog=empty_catalog)
        assert result["count"] == 0
        assert result["filter"]["status"] is None

    def test_all_needs(self, populated_catalog: NeedCatalog):
        result = list_needs(catalog=populated_catalog)
        assert result["count"] == 2

    def test_filter_by_status(self, populated_catalog: NeedCatalog):
        result = list_needs(catalog=populated_catalog, status="expressed")
        assert result["count"] == 1
        assert result["needs"][0]["action"] == "migrate"
        assert result["filter"]["status"] == "expressed"

    def test_filter_no_match(self, populated_catalog: NeedCatalog):
        result = list_needs(catalog=populated_catalog, status="addressed")
        assert result["count"] == 0


# ---------------------------------------------------------------------------
# describe_need
# ---------------------------------------------------------------------------

class TestDescribeNeed:
    def test_not_found(self, empty_catalog: NeedCatalog):
        result = describe_need(catalog=empty_catalog, need_id="nonexistent")
        assert result is None

    def test_describe(self, populated_catalog: NeedCatalog):
        need_id = populated_catalog.needs[0].id
        result = describe_need(catalog=populated_catalog, need_id=need_id)
        assert result is not None
        assert result["status"] == "expressed"
        assert result["statement"]["desire"]["action"] == "migrate"
        assert len(result["statement"]["justifications"]) == 1
        assert len(result["process_units"]) == 1
        assert result["process_units"][0]["stage"] == "identify"


# ---------------------------------------------------------------------------
# need_lineage
# ---------------------------------------------------------------------------

class TestNeedLineage:
    def test_not_found(self, empty_catalog: NeedCatalog):
        result = need_lineage(catalog=empty_catalog, lineage_id="nonexistent")
        assert result is None

    def test_single_version(self, populated_catalog: NeedCatalog):
        lid = populated_catalog.needs[0].lineage_id
        result = need_lineage(catalog=populated_catalog, lineage_id=lid)
        assert result is not None
        assert result["count"] == 1
        assert result["lineage_id"] == lid

    def test_multiple_versions(self, populated_catalog: NeedCatalog):
        original = populated_catalog.needs[0]
        populated_catalog.revise_need(original.id, action="migrate-v2")
        result = need_lineage(catalog=populated_catalog, lineage_id=original.lineage_id)
        assert result is not None
        assert result["count"] == 2
        assert result["versions"][0]["version"] < result["versions"][1]["version"]


# ---------------------------------------------------------------------------
# catalog_summary
# ---------------------------------------------------------------------------

class TestCatalogSummary:
    def test_empty_catalog(self, empty_catalog: NeedCatalog):
        result = catalog_summary(catalog=empty_catalog)
        assert result["name"] == "Empty"
        assert result["stakeholder_count"] == 0
        assert result["need_count"] == 0
        assert result["status_distribution"] == {}

    def test_populated(self, populated_catalog: NeedCatalog):
        result = catalog_summary(catalog=populated_catalog)
        assert result["stakeholder_count"] == 1
        assert result["use_case_count"] == 1
        assert result["need_count"] == 2
        assert result["process_unit_count"] == 1
        dist = result["status_distribution"]
        assert dist["expressed"] == 1
        assert dist["draft"] == 1
