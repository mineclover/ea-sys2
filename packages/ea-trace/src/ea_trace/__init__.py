"""ea-trace: Trace and evidence utilities for governance and lineage replay."""

from ea_trace.chain import (
    LineageError,
    TraceLink,
    TraceNodeRef,
    compose_lineage,
    missing_required_relations,
    replay_lineage_nodes,
)
from ea_trace.evidence import (
    EvidenceBindingSpec,
    EvidenceBindingTarget,
    validate_evidence_binding_spec,
    validate_evidence_payload,
    validate_identifier,
)

__all__ = [
    "EvidenceBindingSpec",
    "EvidenceBindingTarget",
    "LineageError",
    "TraceLink",
    "TraceNodeRef",
    "compose_lineage",
    "missing_required_relations",
    "replay_lineage_nodes",
    "validate_evidence_binding_spec",
    "validate_evidence_payload",
    "validate_identifier",
]

__version__ = "0.1.0"
