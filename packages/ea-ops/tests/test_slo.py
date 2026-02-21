"""Tests for ea_ops.slo."""

from ea_ops.slo import (
    SLOComparison,
    SLOTarget,
    evaluate_slo,
    to_slo_breached_event_payload,
)


def test_evaluate_slo_gte_breached_when_below_target():
    target = SLOTarget(name="availability", objective=99.9, comparison=SLOComparison.GTE)
    evaluation = evaluate_slo(99.5, target)
    assert evaluation.breached is True
    assert evaluation.margin < 0


def test_evaluate_slo_lte_breached_when_above_target():
    target = SLOTarget(name="latency_p95", objective=150.0, comparison=SLOComparison.LTE)
    evaluation = evaluate_slo(180.0, target)
    assert evaluation.breached is True
    assert evaluation.margin < 0


def test_to_slo_breached_event_payload_contains_correlation_fields():
    target = SLOTarget(name="error_rate", objective=0.01, comparison=SLOComparison.LTE)
    evaluation = evaluate_slo(0.03, target)
    payload = to_slo_breached_event_payload(
        service_id="payments-api",
        evaluation=evaluation,
        trace_id="trace-1",
        lineage_id="lineage-1",
    )
    assert payload["trace_id"] == "trace-1"
    assert payload["lineage_id"] == "lineage-1"
    assert payload["service_id"] == "payments-api"
    assert payload["slo_name"] == "error_rate"
    assert payload["breached"] is True
