"""Convert service ops events into needs-layer feedback drafts."""

from __future__ import annotations

from dataclasses import dataclass

from ea_ops.events import ServiceOpsEvent, ServiceOpsSeverity

from ea_needs.types import NeedPriority, NeedPurpose


@dataclass(frozen=True)
class NeedsFeedbackDraft:
    """Suggested need payload derived from a service ops event."""

    action: str
    subject: str
    priority: NeedPriority
    purpose: NeedPurpose
    tags: tuple[str, ...]
    rationale: str


def _priority_from_severity(severity: ServiceOpsSeverity) -> NeedPriority:
    mapping = {
        ServiceOpsSeverity.CRITICAL: NeedPriority.CRITICAL,
        ServiceOpsSeverity.HIGH: NeedPriority.HIGH,
        ServiceOpsSeverity.MEDIUM: NeedPriority.MEDIUM,
        ServiceOpsSeverity.LOW: NeedPriority.LOW,
    }
    return mapping[severity]


def build_needs_feedback_draft(event: ServiceOpsEvent) -> NeedsFeedbackDraft:
    """Build a needs feedback draft from a validated service ops event."""

    payload = event.payload
    service_id = str(payload.get("service_id", "")).strip()
    service_subject = service_id if service_id else "service"

    if event.name == "incident_opened":
        incident_id = str(payload.get("incident_id", "")).strip()
        subject = incident_id if incident_id else service_subject
        return NeedsFeedbackDraft(
            action="stabilize",
            subject=f"incident:{subject}",
            priority=_priority_from_severity(event.severity),
            purpose=NeedPurpose.SAFETY,
            tags=("ops", "incident", service_subject),
            rationale="Incident lifecycle indicates immediate operational stabilization need.",
        )

    if event.name == "slo_breached":
        slo_name = str(payload.get("slo_name", "")).strip() or "unknown_slo"
        return NeedsFeedbackDraft(
            action="improve",
            subject=f"slo:{slo_name}",
            priority=_priority_from_severity(event.severity),
            purpose=NeedPurpose.EFFICIENCY,
            tags=("ops", "slo", service_subject),
            rationale="SLO breach indicates a measurable service quality gap.",
        )

    if event.name == "deployment_rolled_back":
        deployment_id = str(payload.get("deployment_id", "")).strip() or "unknown_deploy"
        return NeedsFeedbackDraft(
            action="harden",
            subject=f"deployment:{deployment_id}",
            priority=_priority_from_severity(event.severity),
            purpose=NeedPurpose.TRUST,
            tags=("ops", "deployment", service_subject),
            rationale="Rollback signal indicates release safety and regression hardening need.",
        )

    return NeedsFeedbackDraft(
        action="improve",
        subject=f"service:{service_subject}",
        priority=_priority_from_severity(event.severity),
        purpose=NeedPurpose.UNSPECIFIED,
        tags=("ops", service_subject),
        rationale="Operational event indicates continuous improvement need.",
    )
