"""Tests for ea_trace.evidence."""

from ea_trace.evidence import (
    EvidenceBindingSpec,
    EvidenceBindingTarget,
    validate_evidence_binding_spec,
    validate_evidence_payload,
    validate_identifier,
)


def test_validate_identifier_accepts_v2_pattern():
    assert validate_identifier("kernel_change_to_code_commit")
    assert validate_identifier("orders.api-gateway.prod")


def test_validate_identifier_rejects_invalid_pattern():
    assert not validate_identifier("A")
    assert not validate_identifier("bad id")


def test_validate_evidence_binding_spec_requires_minimum_fields():
    spec = EvidenceBindingSpec(
        id="kernel_change_bind",
        source_type="kernel_change",
        binds_to=EvidenceBindingTarget.CODE_COMMIT,
        required_fields=("repo", "commit_sha"),
    )
    errors = validate_evidence_binding_spec(spec)
    assert "required_fields must include at least 3 entries" in errors


def test_validate_evidence_binding_spec_enforces_surface_artifact_constraint():
    spec = EvidenceBindingSpec(
        id="surface_to_deployment",
        source_type="surface_artifact",
        binds_to=EvidenceBindingTarget.DEPLOYMENT_RECORD,
        required_fields=("service_id", "deployment_id", "dashboard_url"),
    )
    errors = validate_evidence_binding_spec(spec)
    assert any("environment" in error for error in errors)


def test_validate_evidence_payload_reports_missing_fields():
    spec = EvidenceBindingSpec(
        id="flow_execution_to_ci_run",
        source_type="flow_execution",
        binds_to=EvidenceBindingTarget.CI_RUN,
        required_fields=("pipeline", "run_id", "status"),
    )
    errors = validate_evidence_payload(spec, {"pipeline": "build-main", "run_id": ""})
    assert errors == [
        "missing required evidence field: run_id",
        "missing required evidence field: status",
    ]
