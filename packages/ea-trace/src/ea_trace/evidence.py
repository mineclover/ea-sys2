"""Evidence binding schema utilities for cross-layer traceability."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")


class EvidenceBindingTarget(StrEnum):
    """Allowed evidence target categories for v2 baseline."""

    CODE_COMMIT = "code_commit"
    CI_RUN = "ci_run"
    DEPLOYMENT_RECORD = "deployment_record"
    DASHBOARD_SNAPSHOT = "dashboard_snapshot"
    INCIDENT_TICKET = "incident_ticket"
    RUNBOOK_REF = "runbook_ref"


@dataclass(frozen=True)
class EvidenceBindingSpec:
    """Contract between a source entity and a required evidence target."""

    id: str
    source_type: str
    binds_to: EvidenceBindingTarget
    required_fields: tuple[str, ...]


def validate_identifier(value: str) -> bool:
    """Check whether identifier matches the v2 baseline pattern."""

    return bool(ID_PATTERN.fullmatch(value))


def validate_evidence_binding_spec(spec: EvidenceBindingSpec) -> list[str]:
    """Validate an EvidenceBindingSpec against the v2 constraints."""

    errors: list[str] = []

    if not validate_identifier(spec.id):
        errors.append("id must match ^[a-z0-9][a-z0-9._-]{2,63}$")

    if not spec.source_type.strip():
        errors.append("source_type must be a non-empty string")

    if len(spec.required_fields) < 3:
        errors.append("required_fields must include at least 3 entries")

    if len(set(spec.required_fields)) != len(spec.required_fields):
        errors.append("required_fields must not contain duplicates")

    if spec.source_type == "surface_artifact" and "environment" not in spec.required_fields:
        errors.append(
            "required_fields must include environment when source_type is surface_artifact"
        )

    return errors


def validate_evidence_payload(
    spec: EvidenceBindingSpec,
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate payload keys for a binding; returns missing fields as errors."""

    errors: list[str] = []
    for field in spec.required_fields:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"missing required evidence field: {field}")
    return errors
