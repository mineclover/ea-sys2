"""Tests for NeedCatalog JSON serialization roundtrip."""

import json

import pytest
from ea_needs.catalog import NeedCatalog
from ea_needs.types import (
    JustificationType,
    NeedPriority,
    NeedRelationType,
    NeedStatus,
)


@pytest.fixture
def populated_catalog() -> NeedCatalog:
    """Build a catalog with stakeholders, needs, relations, and state transitions."""
    catalog = NeedCatalog(name="Roundtrip Test", description="Serialization tests")

    sh1 = catalog.add_stakeholder("CTO", "executive", "cloud migration")
    sh2 = catalog.add_stakeholder("DevLead", "engineer", "platform team")

    n1 = catalog.express_need(
        stakeholder_id=sh1.id,
        action="migrate",
        subject="payment system",
        target="cloud",
        justifications=[
            {"type": "because", "description": "frequent outages"},
            {"type": "in_order_to", "description": "99.99% availability"},
        ],
        priority=NeedPriority.CRITICAL,
        kernel_refs=["entity:payment-service"],
        tags=["infra"],
    )
    n1.express()
    n1.acknowledge()

    n2 = catalog.express_need(
        stakeholder_id=sh2.id,
        action="add",
        subject="observability",
        priority=NeedPriority.HIGH,
        tags=["monitoring"],
    )

    catalog.relate_needs(n1.id, n2.id, NeedRelationType.SUPPORTS, "observability supports migration")

    return catalog


class TestJsonRoundtrip:
    def test_roundtrip_preserves_structure(self, populated_catalog: NeedCatalog):
        json_str = populated_catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert restored.id == populated_catalog.id
        assert restored.name == populated_catalog.name
        assert restored.description == populated_catalog.description

    def test_roundtrip_preserves_stakeholders(self, populated_catalog: NeedCatalog):
        json_str = populated_catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert len(restored.stakeholders) == 2
        assert restored.stakeholders[0].name == "CTO"
        assert restored.stakeholders[1].name == "DevLead"

    def test_roundtrip_preserves_needs(self, populated_catalog: NeedCatalog):
        json_str = populated_catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert len(restored.needs) == 2

        n1 = restored.needs[0]
        assert n1.status == NeedStatus.ACKNOWLEDGED
        assert n1.priority == NeedPriority.CRITICAL
        assert n1.statement.desire.action == "migrate"
        assert n1.statement.desire.target == "cloud"
        assert len(n1.statement.justifications) == 2
        assert n1.statement.justifications[0].type == JustificationType.BECAUSE
        assert n1.statement.kernel_refs == ["entity:payment-service"]
        assert n1.statement.tags == ["infra"]

        n2 = restored.needs[1]
        assert n2.status == NeedStatus.DRAFT
        assert n2.priority == NeedPriority.HIGH
        assert n2.statement.desire.target is None

    def test_roundtrip_preserves_relations(self, populated_catalog: NeedCatalog):
        json_str = populated_catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert len(restored.relations) == 1
        rel = restored.relations[0]
        assert rel.type == NeedRelationType.SUPPORTS
        assert rel.description == "observability supports migration"

    def test_json_is_valid(self, populated_catalog: NeedCatalog):
        json_str = populated_catalog.to_json()
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert "stakeholders" in data
        assert "needs" in data
        assert "relations" in data

    def test_empty_catalog_roundtrip(self):
        catalog = NeedCatalog(name="Empty")
        json_str = catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert restored.name == "Empty"
        assert restored.stakeholders == []
        assert restored.needs == []
        assert restored.relations == []
