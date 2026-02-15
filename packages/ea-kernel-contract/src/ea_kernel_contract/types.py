"""Types for ea-kernel contract snapshots and governance consumers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

JsonObject = dict[str, Any]

FeedbackTargetType = Literal[
    "entity_type",
    "relation_type",
    "rule",
    "layer_constraint",
]

RelationshipEvaluationReason = Literal[
    "unknown_entity",
    "unknown_relation",
    "constraint_denied",
    "no_matching_rule",
    "condition_failed",
    "rule_verdict",
]

DEFAULT_MANAGED_GOVERNANCE_LAYERS: tuple[str, ...] = (
    "infra",
    "decision",
    "needs",
    "kernel",
    "flow",
)


@dataclass(frozen=True)
class ContractPaths:
    """Resolved snapshot file paths."""

    contract_dir: Path
    schema_path: Path
    rules_path: Path
    vectors_path: Path


@dataclass(frozen=True)
class ContractBundle:
    """Loaded contract payloads."""

    paths: ContractPaths
    schema: JsonObject
    rules: JsonObject
    vectors: JsonObject

    @property
    def kernel_version(self) -> str:
        """Kernel version declared by the schema snapshot."""
        version = self.schema.get("kernel_version")
        if not isinstance(version, str):
            return ""
        return version


@dataclass(frozen=True)
class ContractIndex:
    """Fast lookup maps built from a validated contract bundle."""

    entity_by_name: dict[str, JsonObject]
    relation_by_name: dict[str, JsonObject]
    attribute_by_name: dict[str, JsonObject]
    rule_by_id: dict[str, JsonObject]
    fallback_rule_by_relation: dict[str, JsonObject]
    layer_constraint_by_id: dict[str, JsonObject]
    vector_by_id: dict[str, JsonObject]


@dataclass(frozen=True)
class ContractModel:
    """Validated bundle + lookup index + deterministic fingerprint."""

    bundle: ContractBundle
    index: ContractIndex
    fingerprint: str


@dataclass(frozen=True)
class FeedbackTarget:
    """Canonical target identifier for governance feedback routing."""

    target_type: FeedbackTargetType
    target_id: str
    canonical_id: str


@dataclass(frozen=True)
class ConditionEvaluation:
    """Condition-level diagnostic result for a winner rule."""

    condition_type: str
    passed: bool
    note: str


@dataclass(frozen=True)
class RelationshipEvaluation:
    """Relationship judgment report computed from snapshot rules."""

    allowed: bool
    reason: RelationshipEvaluationReason
    winner_rule_id: str | None
    matched_rule_ids: tuple[str, ...]
    blocking_constraint_id: str | None
    condition_checks: tuple[ConditionEvaluation, ...]
    notes: str


@dataclass(frozen=True)
class GovernanceLayerCatalog:
    """Layer model catalog derived from governance reference snapshot."""

    reference_path: Path
    layers: tuple[str, ...]
    profile_models: tuple[tuple[str, str], ...]
    expected_managed_layers: tuple[str, ...]
    managed_layers: tuple[str, ...]
    missing_managed_layers: tuple[str, ...]
    unexpected_layers: tuple[str, ...]
    governance_layer_present: bool

    @property
    def is_valid(self) -> bool:
        return len(self.missing_managed_layers) == 0


@dataclass(frozen=True)
class LayerContractOverlay:
    """Layer-scoped overlay patch for rules/constraints/vectors."""

    layer_id: str
    source: str | None = None
    explicit_rules: tuple[JsonObject, ...] = ()
    fallback_rules: tuple[JsonObject, ...] = ()
    layer_constraints: tuple[JsonObject, ...] = ()
    vectors: tuple[JsonObject, ...] = ()


@dataclass(frozen=True)
class LayerContractComposeOptions:
    """Composition controls for overlay merge behavior."""

    namespace_ids: bool = True
    namespace_separator: str = ":"
    merge_vectors: bool = False
    allow_rule_id_collision: bool = False
    allow_constraint_id_collision: bool = False


@dataclass(frozen=True)
class LayerContractConvention:
    """Package/filesystem naming convention for layer contract SDKs."""

    layer_id: str
    layer_slug: str
    ts_package_name: str
    py_package_name: str
    contracts_dir: str
    schema_file: str
    rules_file: str
    vectors_file: str
    feedback_id_prefix: str


@dataclass(frozen=True)
class DecisionTraceOperation:
    """One model operation linked to a governance decision."""

    id: str
    operation: str
    model_name: str
    version: str
    status: str
    actor: str
    transaction_id: str
    evidence_refs: tuple[str, ...]
    warnings: tuple[str, ...]
    detail: JsonObject
    created_at: str


@dataclass(frozen=True)
class DecisionTraceImpact:
    """Impact entry emitted by a decision-linked model operation."""

    operation: str
    model_name: str
    version: str
    status: str
    transaction_id: str
    actor: str
    created_at: str
    detail: JsonObject | None = None


@dataclass(frozen=True)
class DecisionTraceHistoryEvent:
    """Timeline event for decision trace exploration."""

    transaction_id: str
    event_type: str
    message: str
    created_at: str
    payload: JsonObject | None = None
    event_id: int | None = None


@dataclass(frozen=True)
class DecisionTraceContract:
    """DecisionTraceContract v1 payload shape for /models decision governance."""

    kind: str
    contract_version: str
    decision_id: str
    created_at: str
    updated_at: str
    evidence_refs: tuple[str, ...]
    warnings: tuple[str, ...]
    operations: tuple[DecisionTraceOperation, ...]
    impact: tuple[DecisionTraceImpact, ...]
    history: tuple[DecisionTraceHistoryEvent, ...]


@dataclass(frozen=True)
class DecisionTraceExploration:
    """Exploration projection (evidence/impact/history) for a decision trace."""

    decision_id: str
    contract_version: str
    evidence: JsonObject
    impact: JsonObject
    history: tuple[DecisionTraceHistoryEvent, ...]
