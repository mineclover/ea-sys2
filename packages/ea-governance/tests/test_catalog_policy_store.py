from __future__ import annotations

from pathlib import Path

from ea_governance.catalog_policy_store import (
    CatalogAutoExpressPolicy,
    SQLiteCatalogAutoExpressPolicyStore,
    evaluate_catalog_auto_express_policy,
)
from ea_ops.events import FeedbackLayer, ServiceOpsSeverity


def test_sqlite_catalog_policy_store_save_get_list(tmp_path: Path):
    store = SQLiteCatalogAutoExpressPolicyStore(tmp_path / "catalog-policies.db")

    policy = CatalogAutoExpressPolicy(
        catalog_id="catalog-001",
        enabled=True,
        allowed_severities=(ServiceOpsSeverity.HIGH, ServiceOpsSeverity.CRITICAL),
        allowed_event_names=("slo_breached", "incident_opened"),
        allowed_feeds_back_to=(FeedbackLayer.NEEDS,),
        stakeholder_event_map={
            "stakeholder-001": ("slo_breached", "incident_opened"),
        },
    )

    saved_id = store.save_policy(policy)
    assert saved_id == "catalog-001"

    loaded = store.get_policy("catalog-001")
    assert loaded is not None
    assert loaded.catalog_id == "catalog-001"
    assert loaded.enabled is True
    assert loaded.allowed_severities == (
        ServiceOpsSeverity.HIGH,
        ServiceOpsSeverity.CRITICAL,
    )
    assert loaded.allowed_event_names == ("slo_breached", "incident_opened")
    assert loaded.allowed_feeds_back_to == (FeedbackLayer.NEEDS,)
    assert loaded.stakeholder_event_map["stakeholder-001"] == (
        "slo_breached",
        "incident_opened",
    )

    listed = store.list_policies()
    assert len(listed) == 1
    assert listed[0].catalog_id == "catalog-001"


def test_catalog_auto_express_policy_evaluates_story_criteria():
    policy = CatalogAutoExpressPolicy(
        catalog_id="catalog-002",
        enabled=True,
        allowed_severities=(ServiceOpsSeverity.HIGH,),
        allowed_event_names=("slo_breached",),
        allowed_feeds_back_to=(FeedbackLayer.NEEDS,),
        stakeholder_event_map={"stakeholder-001": ("slo_breached",)},
    )

    allowed = evaluate_catalog_auto_express_policy(
        policy,
        requested=True,
        event_name="slo_breached",
        severity=ServiceOpsSeverity.HIGH,
        feeds_back_to=FeedbackLayer.NEEDS,
        stakeholder_id="stakeholder-001",
    )
    assert allowed.allowed is True
    assert allowed.reason_codes == ()

    denied = evaluate_catalog_auto_express_policy(
        policy,
        requested=True,
        event_name="incident_opened",
        severity=ServiceOpsSeverity.CRITICAL,
        feeds_back_to=FeedbackLayer.DECISION,
        stakeholder_id="stakeholder-999",
    )
    assert denied.allowed is False
    assert "severity_not_allowed" in denied.reason_codes
    assert "event_name_not_allowed" in denied.reason_codes
    assert "feeds_back_to_not_needs" in denied.reason_codes
    assert "feeds_back_to_not_allowed" in denied.reason_codes
    assert "stakeholder_unmapped" in denied.reason_codes


def test_catalog_auto_express_policy_handles_missing_policy():
    decision = evaluate_catalog_auto_express_policy(
        None,
        requested=True,
        event_name="slo_breached",
        severity=ServiceOpsSeverity.HIGH,
        feeds_back_to=FeedbackLayer.NEEDS,
        stakeholder_id="stakeholder-001",
    )
    assert decision.allowed is False
    assert decision.reason_codes == ("policy_not_found",)
