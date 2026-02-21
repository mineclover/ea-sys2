"""Tests for ea_ops.events."""

import pytest
from ea_ops.events import (
    FeedbackLayer,
    ServiceOpsEventSpec,
    ServiceOpsSeverity,
    build_service_ops_event,
    validate_service_ops_event_spec,
    validate_service_ops_payload,
)


def test_validate_service_ops_event_spec_accepts_valid_spec():
    spec = ServiceOpsEventSpec(
        name="incident_opened",
        severity=ServiceOpsSeverity.HIGH,
        must_include=("trace_id", "lineage_id", "service_id", "incident_id"),
        feeds_back_to=FeedbackLayer.DECISION,
    )
    assert validate_service_ops_event_spec(spec) == []


def test_validate_service_ops_event_spec_checks_critical_constraint():
    spec = ServiceOpsEventSpec(
        name="incident_critical",
        severity=ServiceOpsSeverity.CRITICAL,
        must_include=("trace_id", "lineage_id", "service_id"),
        feeds_back_to=FeedbackLayer.NEEDS,
    )
    errors = validate_service_ops_event_spec(spec)
    assert any("critical severity" in error for error in errors)


def test_validate_service_ops_payload_reports_missing_fields():
    spec = ServiceOpsEventSpec(
        name="slo_breached",
        severity=ServiceOpsSeverity.MEDIUM,
        must_include=("trace_id", "lineage_id", "service_id", "slo_name"),
        feeds_back_to=FeedbackLayer.NEEDS,
    )
    errors = validate_service_ops_payload(spec, {"trace_id": "t-1", "lineage_id": "l-1"})
    assert errors == [
        "missing required ops field: service_id",
        "missing required ops field: slo_name",
    ]


def test_build_service_ops_event_normalizes_payload():
    spec = ServiceOpsEventSpec(
        name="deployment_rolled_back",
        severity=ServiceOpsSeverity.HIGH,
        must_include=(
            "trace_id",
            "lineage_id",
            "service_id",
            "deployment_id",
            "rollback_reason",
        ),
        feeds_back_to=FeedbackLayer.KERNEL,
    )
    payload = {
        "rollback_reason": "healthcheck_failed",
        "trace_id": "t-1",
        "lineage_id": "l-1",
        "service_id": "orders-api",
        "deployment_id": "dep-100",
    }
    event = build_service_ops_event(spec, payload)
    assert event.name == "deployment_rolled_back"
    assert list(event.payload.keys()) == sorted(payload.keys())


def test_build_service_ops_event_raises_for_invalid_payload():
    spec = ServiceOpsEventSpec(
        name="incident_opened",
        severity=ServiceOpsSeverity.HIGH,
        must_include=("trace_id", "lineage_id", "service_id", "incident_id"),
        feeds_back_to=FeedbackLayer.DECISION,
    )
    with pytest.raises(ValueError):
        build_service_ops_event(spec, {"trace_id": "t-1"})
