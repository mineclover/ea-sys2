"""ea-ops: Service operations vocabulary and validation helpers."""

from ea_ops.events import (
    FeedbackLayer,
    ServiceOpsEvent,
    ServiceOpsEventSpec,
    ServiceOpsSeverity,
    build_service_ops_event,
    validate_service_ops_event_spec,
    validate_service_ops_payload,
)
from ea_ops.slo import (
    SLOComparison,
    SLOEvaluation,
    SLOTarget,
    evaluate_slo,
    to_slo_breached_event_payload,
)

__all__ = [
    "FeedbackLayer",
    "SLOComparison",
    "SLOEvaluation",
    "SLOTarget",
    "ServiceOpsEvent",
    "ServiceOpsEventSpec",
    "ServiceOpsSeverity",
    "build_service_ops_event",
    "evaluate_slo",
    "to_slo_breached_event_payload",
    "validate_service_ops_event_spec",
    "validate_service_ops_payload",
]

__version__ = "0.1.0"
