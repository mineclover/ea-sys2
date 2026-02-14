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
