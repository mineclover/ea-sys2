"""Tests for ea_needs.ops_feedback."""

from ea_needs.ops_feedback import build_needs_feedback_draft
from ea_ops.events import FeedbackLayer, ServiceOpsEvent, ServiceOpsSeverity


def _event(name: str, severity: ServiceOpsSeverity, payload: dict[str, object]) -> ServiceOpsEvent:
    return ServiceOpsEvent(
        name=name,
        severity=severity,
        feeds_back_to=FeedbackLayer.NEEDS,
        payload=payload,
    )


def test_build_needs_feedback_draft_for_incident():
    event = _event(
        "incident_opened",
        ServiceOpsSeverity.CRITICAL,
        {
            "trace_id": "trace-1",
            "lineage_id": "lineage-1",
            "service_id": "payments-api",
            "incident_id": "inc-1",
        },
    )
    draft = build_needs_feedback_draft(event)
    assert draft.action == "stabilize"
    assert draft.subject == "incident:inc-1"
    assert draft.priority.value == "critical"
    assert draft.purpose.value == "safety"


def test_build_needs_feedback_draft_for_slo_breach():
    event = _event(
        "slo_breached",
        ServiceOpsSeverity.MEDIUM,
        {
            "trace_id": "trace-1",
            "lineage_id": "lineage-1",
            "service_id": "orders-api",
            "slo_name": "latency_p95",
        },
    )
    draft = build_needs_feedback_draft(event)
    assert draft.action == "improve"
    assert draft.subject == "slo:latency_p95"
    assert draft.priority.value == "medium"
    assert draft.purpose.value == "efficiency"
