"""Tests for ea_needs.types — frozen vocabulary types."""

from dataclasses import FrozenInstanceError

import pytest
from ea_needs.types import (
    Desire,
    Justification,
    JustificationType,
    NeedPriority,
    NeedRelationType,
    NeedStatement,
    NeedStatus,
    Stakeholder,
    _generate_id,
    _now,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_id_has_prefix(self):
        result = _generate_id("need")
        assert result.startswith("need-")
        assert len(result) == len("need-") + 8

    def test_generate_id_unique(self):
        ids = {_generate_id("x") for _ in range(100)}
        assert len(ids) == 100

    def test_now_iso_format(self):
        ts = _now()
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_justification_type_values(self):
        assert JustificationType.BECAUSE.value == "because"
        assert JustificationType.IN_ORDER_TO.value == "in_order_to"

    def test_need_priority_values(self):
        assert NeedPriority.CRITICAL.value == "critical"
        assert NeedPriority.HIGH.value == "high"
        assert NeedPriority.MEDIUM.value == "medium"
        assert NeedPriority.LOW.value == "low"

    def test_need_status_values(self):
        assert NeedStatus.DRAFT.value == "draft"
        assert NeedStatus.EXPRESSED.value == "expressed"
        assert NeedStatus.ACKNOWLEDGED.value == "acknowledged"
        assert NeedStatus.ADDRESSED.value == "addressed"
        assert NeedStatus.WITHDRAWN.value == "withdrawn"

    def test_need_relation_type_values(self):
        assert NeedRelationType.DEPENDS_ON.value == "depends_on"
        assert NeedRelationType.CONFLICTS_WITH.value == "conflicts_with"
        assert NeedRelationType.SUPPORTS.value == "supports"
        assert NeedRelationType.REFINES.value == "refines"
        assert NeedRelationType.SUPERSEDES.value == "supersedes"

    def test_enums_are_str(self):
        """All enums inherit from str for JSON serialization."""
        assert isinstance(NeedStatus.DRAFT, str)
        assert isinstance(NeedPriority.HIGH, str)
        assert isinstance(JustificationType.BECAUSE, str)
        assert isinstance(NeedRelationType.SUPPORTS, str)


# ---------------------------------------------------------------------------
# Frozen value objects
# ---------------------------------------------------------------------------

class TestStakeholder:
    def test_creation(self):
        s = Stakeholder(id="sh-001", name="CTO", role="executive", context="cloud migration")
        assert s.name == "CTO"
        assert s.role == "executive"
        assert s.context == "cloud migration"

    def test_frozen(self):
        s = Stakeholder(id="sh-001", name="CTO", role="executive")
        with pytest.raises(FrozenInstanceError):
            s.name = "CFO"

    def test_default_context(self):
        s = Stakeholder(id="sh-001", name="Dev", role="engineer")
        assert s.context == ""


class TestDesire:
    def test_creation_with_target(self):
        d = Desire(action="migrate", subject="payment system", target="cloud")
        assert d.action == "migrate"
        assert d.subject == "payment system"
        assert d.target == "cloud"

    def test_creation_without_target(self):
        d = Desire(action="reduce", subject="deployment time")
        assert d.target is None

    def test_frozen(self):
        d = Desire(action="migrate", subject="db")
        with pytest.raises(FrozenInstanceError):
            d.action = "delete"


class TestJustification:
    def test_because(self):
        j = Justification(type=JustificationType.BECAUSE, description="system has outages")
        assert j.type == JustificationType.BECAUSE
        assert j.description == "system has outages"

    def test_in_order_to(self):
        j = Justification(type=JustificationType.IN_ORDER_TO, description="achieve high availability")
        assert j.type == JustificationType.IN_ORDER_TO

    def test_frozen(self):
        j = Justification(type=JustificationType.BECAUSE, description="x")
        with pytest.raises(FrozenInstanceError):
            j.description = "y"


class TestNeedStatement:
    def test_creation(self):
        ns = NeedStatement(
            stakeholder_id="sh-001",
            desire=Desire(action="migrate", subject="db", target="cloud"),
            justifications=[
                Justification(type=JustificationType.BECAUSE, description="outages"),
            ],
            kernel_refs=["entity:payment-service"],
            tags=["infrastructure", "cloud"],
        )
        assert ns.stakeholder_id == "sh-001"
        assert ns.desire.action == "migrate"
        assert len(ns.justifications) == 1
        assert len(ns.kernel_refs) == 1
        assert "cloud" in ns.tags
        assert ns.expressed_at.endswith("Z")

    def test_frozen(self):
        ns = NeedStatement(
            stakeholder_id="sh-001",
            desire=Desire(action="reduce", subject="cost"),
        )
        with pytest.raises(FrozenInstanceError):
            ns.stakeholder_id = "sh-002"

    def test_defaults(self):
        ns = NeedStatement(
            stakeholder_id="sh-001",
            desire=Desire(action="reduce", subject="cost"),
        )
        assert ns.justifications == []
        assert ns.kernel_refs == []
        assert ns.tags == []
