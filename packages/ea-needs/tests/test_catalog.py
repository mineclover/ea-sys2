"""Tests for ea_needs.catalog — aggregate root lifecycle."""

import pytest
from ea_needs.catalog import NeedCatalog
from ea_needs.types import (
    JustificationType,
    NeedKernelChangePhase,
    NeedPriority,
    NeedPurpose,
    NeedRelationType,
    NeedStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def catalog() -> NeedCatalog:
    return NeedCatalog(name="Test Catalog", description="For unit tests")


@pytest.fixture
def catalog_with_stakeholder(catalog: NeedCatalog):
    sh = catalog.add_stakeholder("CTO", "executive", "cloud migration")
    return catalog, sh


@pytest.fixture
def catalog_with_need(catalog_with_stakeholder):
    catalog, sh = catalog_with_stakeholder
    need = catalog.express_need(
        stakeholder_id=sh.id,
        action="migrate",
        subject="payment system",
        target="cloud",
        justifications=[
            {"type": "because", "description": "frequent outages"},
            {"type": "in_order_to", "description": "99.99% availability"},
        ],
        priority=NeedPriority.HIGH,
        kernel_refs=["entity:payment-service"],
        tags=["infra", "cloud"],
    )
    return catalog, sh, need


# ---------------------------------------------------------------------------
# Stakeholder management
# ---------------------------------------------------------------------------

class TestStakeholderManagement:
    def test_add_stakeholder(self, catalog: NeedCatalog):
        sh = catalog.add_stakeholder("CTO", "executive", "cloud migration")
        assert sh.name == "CTO"
        assert sh.role == "executive"
        assert sh.id.startswith("sh-")
        assert len(catalog.stakeholders) == 1

    def test_get_stakeholder(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        found = catalog.get_stakeholder(sh.id)
        assert found is sh

    def test_get_stakeholder_not_found(self, catalog: NeedCatalog):
        assert catalog.get_stakeholder("nonexistent") is None


# ---------------------------------------------------------------------------
# Need expression
# ---------------------------------------------------------------------------

class TestNeedExpression:
    def test_express_need(self, catalog_with_need):
        catalog, sh, need = catalog_with_need
        assert need.id.startswith("need-")
        assert need.status == NeedStatus.DRAFT
        assert need.priority == NeedPriority.HIGH
        assert need.kernel_change_phase == NeedKernelChangePhase.PLANNED
        assert need.statement.desire.action == "migrate"
        assert need.statement.desire.subject == "payment system"
        assert need.statement.desire.target == "cloud"
        assert len(need.statement.justifications) == 2
        assert need.statement.justifications[0].type == JustificationType.BECAUSE
        assert need.statement.justifications[1].type == JustificationType.IN_ORDER_TO
        assert need.statement.kernel_refs == ["entity:payment-service"]
        assert "cloud" in need.statement.tags

    def test_express_need_minimal(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        need = catalog.express_need(sh.id, "reduce", "cost")
        assert need.statement.desire.target is None
        assert need.statement.justifications == []
        assert need.priority == NeedPriority.MEDIUM
        assert need.statement.purpose == NeedPurpose.UNSPECIFIED

    def test_express_need_unknown_stakeholder(self, catalog: NeedCatalog):
        with pytest.raises(ValueError, match="not found"):
            catalog.express_need("nonexistent", "do", "something")

    def test_express_need_with_canonical_purpose(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        need = catalog.express_need(
            sh.id,
            "stabilize",
            "incident response",
            purpose=NeedPurpose.SAFETY,
        )
        assert need.statement.purpose == NeedPurpose.SAFETY

    def test_express_need_with_m2_style_purpose_name(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        need = catalog.express_need(
            sh.id,
            "improve",
            "onboarding",
            purpose="NeedPurposeUsability",
        )
        assert need.statement.purpose == NeedPurpose.USABILITY

    def test_express_need_with_string_priority(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        need = catalog.express_need(
            sh.id,
            "stabilize",
            "runtime",
            priority="high",
        )
        assert need.priority == NeedPriority.HIGH

    def test_express_need_rejects_invalid_priority(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        with pytest.raises(ValueError, match="Allowed priority values"):
            catalog.express_need(
                sh.id,
                "stabilize",
                "runtime",
                priority="urgent",
            )

    def test_express_need_rejects_invalid_purpose(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        with pytest.raises(ValueError, match="Allowed purpose values"):
            catalog.express_need(
                sh.id,
                "improve",
                "dashboard",
                purpose="reduce MTTR",
            )


# ---------------------------------------------------------------------------
# Need state transitions
# ---------------------------------------------------------------------------

class TestNeedTransitions:
    def test_full_lifecycle(self, catalog_with_need):
        _, _, need = catalog_with_need
        assert need.status == NeedStatus.DRAFT

        need.express()
        assert need.status == NeedStatus.EXPRESSED

        need.acknowledge()
        assert need.status == NeedStatus.ACKNOWLEDGED

        need.address(decision_ref="topic-abc")
        assert need.status == NeedStatus.ADDRESSED
        assert need.decision_ref == "topic-abc"
        assert need.kernel_change_phase == NeedKernelChangePhase.APPLIED

    def test_withdraw_from_draft(self, catalog_with_need):
        _, _, need = catalog_with_need
        need.withdraw()
        assert need.status == NeedStatus.WITHDRAWN
        assert need.kernel_change_phase == NeedKernelChangePhase.SUPERSEDED

    def test_withdraw_from_expressed(self, catalog_with_need):
        _, _, need = catalog_with_need
        need.express()
        need.withdraw()
        assert need.status == NeedStatus.WITHDRAWN

    def test_withdraw_from_acknowledged(self, catalog_with_need):
        _, _, need = catalog_with_need
        need.express()
        need.acknowledge()
        need.withdraw()
        assert need.status == NeedStatus.WITHDRAWN

    def test_invalid_transition_addressed_to_draft(self, catalog_with_need):
        _, _, need = catalog_with_need
        need.express()
        need.acknowledge()
        need.address()
        with pytest.raises(ValueError, match="Cannot transition"):
            need.transition_to(NeedStatus.DRAFT)

    def test_invalid_transition_draft_to_acknowledged(self, catalog_with_need):
        _, _, need = catalog_with_need
        with pytest.raises(ValueError, match="Cannot transition"):
            need.acknowledge()

    def test_invalid_transition_withdrawn_terminal(self, catalog_with_need):
        _, _, need = catalog_with_need
        need.withdraw()
        with pytest.raises(ValueError, match="Cannot transition"):
            need.express()


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

class TestRelations:
    def test_relate_needs(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        n1 = catalog.express_need(sh.id, "migrate", "db")
        n2 = catalog.express_need(sh.id, "upgrade", "network")

        rel = catalog.relate_needs(n1.id, n2.id, NeedRelationType.DEPENDS_ON, "db needs network")
        assert rel.id.startswith("rel-")
        assert rel.source_id == n1.id
        assert rel.target_id == n2.id
        assert rel.type == NeedRelationType.DEPENDS_ON

    def test_relate_needs_invalid_source(self, catalog_with_need):
        catalog, _, need = catalog_with_need
        with pytest.raises(ValueError, match="Source need"):
            catalog.relate_needs("bad-id", need.id, NeedRelationType.SUPPORTS)

    def test_relate_needs_invalid_target(self, catalog_with_need):
        catalog, _, need = catalog_with_need
        with pytest.raises(ValueError, match="Target need"):
            catalog.relate_needs(need.id, "bad-id", NeedRelationType.SUPPORTS)

    def test_get_relations_for(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        n1 = catalog.express_need(sh.id, "migrate", "db")
        n2 = catalog.express_need(sh.id, "upgrade", "network")
        n3 = catalog.express_need(sh.id, "add", "monitoring")

        catalog.relate_needs(n1.id, n2.id, NeedRelationType.DEPENDS_ON)
        catalog.relate_needs(n3.id, n1.id, NeedRelationType.SUPPORTS)

        rels = catalog.get_relations_for(n1.id)
        assert len(rels) == 2  # n1 is source in one, target in another


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

class TestQueries:
    def test_needs_by_stakeholder(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        sh2 = catalog.add_stakeholder("Dev", "engineer")

        catalog.express_need(sh.id, "migrate", "db")
        catalog.express_need(sh.id, "upgrade", "network")
        catalog.express_need(sh2.id, "add", "monitoring")

        assert len(catalog.needs_by_stakeholder(sh.id)) == 2
        assert len(catalog.needs_by_stakeholder(sh2.id)) == 1

    def test_needs_by_status(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        n1 = catalog.express_need(sh.id, "migrate", "db")
        catalog.express_need(sh.id, "upgrade", "network")
        n1.express()

        assert len(catalog.needs_by_status(NeedStatus.DRAFT)) == 1
        assert len(catalog.needs_by_status(NeedStatus.EXPRESSED)) == 1

    def test_needs_by_priority(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        catalog.express_need(sh.id, "migrate", "db", priority=NeedPriority.CRITICAL)
        catalog.express_need(sh.id, "upgrade", "network", priority=NeedPriority.LOW)

        assert len(catalog.needs_by_priority(NeedPriority.CRITICAL)) == 1
        assert len(catalog.needs_by_priority(NeedPriority.LOW)) == 1
        assert len(catalog.needs_by_priority(NeedPriority.MEDIUM)) == 0

    def test_get_timeline(self, catalog_with_stakeholder):
        catalog, sh = catalog_with_stakeholder
        catalog.express_need(sh.id, "migrate", "db")
        catalog.express_need(sh.id, "upgrade", "network")

        timeline = catalog.get_timeline()
        assert len(timeline) == 2
        assert all(e["type"] == "need_created" for e in timeline)
        # chronologically sorted
        assert timeline[0]["date"] <= timeline[1]["date"]
