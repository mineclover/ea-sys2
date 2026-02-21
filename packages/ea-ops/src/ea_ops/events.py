"""Service operations event vocabulary and validation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

EVENT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
REQUIRED_CORRELATION_FIELDS = ("trace_id", "lineage_id")


class ServiceOpsSeverity(StrEnum):
    """Severity levels for service operations events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackLayer(StrEnum):
    """Allowed feedback destinations for ops events."""

    DECISION = "decision"
    NEEDS = "needs"
    KERNEL = "kernel"


@dataclass(frozen=True)
class ServiceOpsEventSpec:
    """Declarative spec describing an ops event contract."""

    name: str
    severity: ServiceOpsSeverity
    must_include: tuple[str, ...]
    feeds_back_to: FeedbackLayer


@dataclass(frozen=True)
class ServiceOpsEvent:
    """Runtime representation of a validated service operations event."""

    name: str
    severity: ServiceOpsSeverity
    feeds_back_to: FeedbackLayer
    payload: Mapping[str, Any]


def validate_service_ops_event_spec(spec: ServiceOpsEventSpec) -> list[str]:
    """Validate ServiceOpsEventSpec against v2 baseline constraints."""

    errors: list[str] = []

    if not EVENT_NAME_PATTERN.fullmatch(spec.name):
        errors.append("name must match ^[a-z0-9][a-z0-9._-]{2,63}$")

    if len(set(spec.must_include)) != len(spec.must_include):
        errors.append("must_include must not contain duplicates")

    for field in REQUIRED_CORRELATION_FIELDS:
        if field not in spec.must_include:
            errors.append(f"must_include must contain {field}")

    if spec.severity == ServiceOpsSeverity.CRITICAL and not {
        "runbook_url",
        "incident_id",
    }.intersection(spec.must_include):
        errors.append(
            "critical severity requires runbook_url or incident_id in must_include"
        )

    return errors


def validate_service_ops_payload(
    spec: ServiceOpsEventSpec,
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate payload for required fields declared by the spec."""

    errors: list[str] = []
    for field in spec.must_include:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"missing required ops field: {field}")
    return errors


def build_service_ops_event(
    spec: ServiceOpsEventSpec,
    payload: Mapping[str, Any],
) -> ServiceOpsEvent:
    """Build a validated and normalized service operations event."""

    errors = validate_service_ops_event_spec(spec)
    errors.extend(validate_service_ops_payload(spec, payload))
    if errors:
        raise ValueError("; ".join(errors))

    normalized_payload = {key: payload[key] for key in sorted(payload.keys())}
    return ServiceOpsEvent(
        name=spec.name,
        severity=spec.severity,
        feeds_back_to=spec.feeds_back_to,
        payload=normalized_payload,
    )
