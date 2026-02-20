"""Profile types for the profile framework.

Contains both core profile data types (KernelProfile, ProfileElement, etc.)
and framework interface types (PatternType, QualityReport, etc.).

Kernel-agnostic: no dependency on ea_kernel.types. Other layers can import
these types without depending on ea-kernel core types.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

# Kernel-agnostic type alias (same definition as ea_kernel.types.I18nString)
I18nString = str | dict[str, str]


# ── Schema Port ────────────────────────────────────────────────

@runtime_checkable
class SchemaPort(Protocol):
    """Minimal schema interface for profile validation.

    KernelSchema satisfies this naturally (duck typing).
    Entities must have `.name: str` and `.is_abstract: bool`.
    Relations must have `.name: str`.
    """

    @property
    def entities(self) -> Sequence[Any]: ...

    @property
    def relations(self) -> Sequence[Any]: ...


# ── Condition Registry ─────────────────────────────────────────

class ConditionRegistry:
    """Configurable condition vocabulary for profile rules.

    Each layer can register its own TOML key → condition_type mappings.
    The kernel default registry provides the standard kernel conditions.
    """

    __slots__ = ("_map",)

    def __init__(self) -> None:
        self._map: dict[str, str] = {}

    def register(self, toml_key: str, condition_type: str) -> None:
        """Register a TOML condition key → condition_type mapping."""
        self._map[toml_key] = condition_type

    def resolve(self, toml_key: str) -> str | None:
        """Resolve a TOML condition key to its condition_type."""
        return self._map.get(toml_key)

    @classmethod
    def kernel_default(cls) -> ConditionRegistry:
        """Pre-configured with kernel condition types."""
        reg = cls()
        reg._map = {
            "LAYER_ORDER": "layer_order",
            "SAME_LAYER": "same_layer",
            "SAME_BRANCH": "same_branch",
            "ANCESTOR_OF": "ancestor_of",
            "SAME_CATEGORY": "same_category",
        }
        return reg


# ── Kernel-Agnostic Rule Types ─────────────────────────────────

@dataclass(frozen=True, eq=False)
class RuleCondition:
    """Generic rule condition (kernel-agnostic).

    condition_type is an opaque string; each layer defines its own
    condition vocabulary (e.g., kernel uses "same_layer", "layer_order").

    Cross-type equality: RuleCondition and any subclass (e.g.,
    KernelRuleCondition) with the same field values are considered equal.
    """
    condition_type: str
    parameters: tuple[tuple[str, str], ...] = ()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RuleCondition):
            return NotImplemented
        return (str(self.condition_type), self.parameters) == (
            str(other.condition_type), other.parameters,
        )

    def __hash__(self) -> int:
        return hash((str(self.condition_type), self.parameters))


@dataclass(frozen=True, eq=False)
class ProfileRule:
    """Generic validity rule for any layer's profile (kernel-agnostic).

    This is the base rule type used by the profile framework. Layer-specific
    rule types (e.g., KernelValidityRule) extend this with narrower type
    annotations while maintaining structural compatibility.

    Cross-type equality: ProfileRule and any subclass (e.g.,
    KernelValidityRule) with the same field values are considered equal.
    """
    id: str
    source_pattern: str
    target_pattern: str
    relationship_name: str
    valid: bool = True
    priority: int = 0
    conditions: tuple[RuleCondition, ...] = ()
    description: I18nString = ""
    notes: str = ""
    scope: str = ""  # "" (global) | "sibling" | "subtree"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProfileRule):
            return NotImplemented
        return (
            self.id, self.source_pattern, self.target_pattern,
            self.relationship_name, self.valid, self.priority,
            self.conditions, self.description, self.notes,
            self.scope,
        ) == (
            other.id, other.source_pattern, other.target_pattern,
            other.relationship_name, other.valid, other.priority,
            other.conditions, other.description, other.notes,
            other.scope,
        )

    def __hash__(self) -> int:
        return hash((
            self.id, self.source_pattern, self.target_pattern,
            self.relationship_name, self.valid, self.priority,
            self.conditions, self.description, self.notes,
            self.scope,
        ))

# ── Core Profile Types ──────────────────────────────────────────

@dataclass(frozen=True)
class ProfileElement:
    """A domain element mapped to a kernel entity type."""
    name: str            # "BusinessProcess"
    kernel_type: str     # "step" (kernel entity name)
    layer: str           # "Business" (domain layer)
    category: str        # "Behavior" (domain category)
    description: I18nString = ""
    display_name: I18nString = ""


# ── Cross-layer element identity ──────────────────────────────
#
# When multiple profiles share element names (e.g. each layer defines
# its own ``GovernanceModelPort``), a globally unique node ID is needed.
# Convention: ``{layer_key}::{element_name}``  (double-colon).
# This is distinct from the rule-ID namespace ``{layer}:{rule_id}``
# (single-colon) used during profile composition.

def make_node_id(layer_key: str, name: str) -> str:
    """Create a globally unique element node ID: ``{layer_key}::{name}``."""
    return f"{layer_key}::{name}"


def parse_node_id(node_id: str) -> tuple[str, str]:
    """Split a node ID back into ``(layer_key, element_name)``."""
    layer_key, _, name = node_id.partition("::")
    return layer_key, name


@dataclass(frozen=True)
class ProfileRelation:
    """A domain relation mapped to a kernel relation."""
    name: str            # "Serving"
    kernel_relation: str  # "association" (kernel relation name)
    description: I18nString = ""
    display_name: I18nString = ""
    direction: str = ""  # "in" | "out" | "" (unspecified)


@dataclass(frozen=True)
class ProfileStateTransition:
    """A declarative state machine transition for a profile."""
    from_state: str
    to_state: str
    guard_condition: str = ""
    description: I18nString = ""


@dataclass(frozen=True)
class ProfileArtifactType:
    """A declarative surface artifact type definition for a profile."""
    name: str
    tier: str
    description: I18nString = ""
    kernel_element_pattern: str = ""


@dataclass(frozen=True)
class LayerDefinition:
    """A declarative layer definition inside a layer stack."""
    name: str
    order: int
    depends_on: tuple[str, ...] = ()
    responsibility: I18nString = ""
    model_perspective: str = ""


@dataclass(frozen=True)
class LayerStack:
    """A declarative layer stack definition for profile metadata."""
    layers: tuple[LayerDefinition, ...] = ()
    definition_flow: str = ""
    runtime_flow: str = ""
    feedback_flow: str = ""


@dataclass(frozen=True)
class ProfileMetadata:
    """Typed metadata for a kernel profile."""
    standard: str          # "ArchiMate 3.2", "TOGAF 10"
    organization: str      # "The Open Group", "Zachman International"
    extra: dict[str, str] | None = None  # additional key-value pairs


@dataclass(frozen=True)
class KernelProfile:
    """A domain profile that maps elements/relations to kernel types."""
    name: str
    version: str
    kernel_version: str  # required kernel version
    elements: tuple[ProfileElement, ...]
    relations: tuple[ProfileRelation, ...]
    validity_rules: tuple[ProfileRule, ...] = ()
    metadata: ProfileMetadata | None = None
    state_transitions: tuple[ProfileStateTransition, ...] = ()
    artifact_types: tuple[ProfileArtifactType, ...] = ()
    layer_stack: LayerStack | None = None

    def get_element(self, name: str) -> ProfileElement | None:
        for e in self.elements:
            if e.name == name:
                return e
        return None

    def get_relation(self, name: str) -> ProfileRelation | None:
        for r in self.relations:
            if r.name == name:
                return r
        return None

    def elements_in_layer(self, layer: str) -> tuple[ProfileElement, ...]:
        return tuple(e for e in self.elements if e.layer == layer)

    def elements_in_category(self, category: str) -> tuple[ProfileElement, ...]:
        return tuple(e for e in self.elements if e.category == category)

    def domain_layers(self) -> tuple[str, ...]:
        seen: list[str] = []
        for e in self.elements:
            if e.layer not in seen:
                seen.append(e.layer)
        return tuple(seen)

    def matching_elements(self, pattern: str) -> tuple[ProfileElement, ...]:
        """Find elements matching a validity rule pattern.

        Patterns: "*" (all), "@Category", "#Layer", "ElementName" (exact).
        """
        if pattern == "*":
            return self.elements
        if pattern.startswith("@"):
            return self.elements_in_category(pattern[1:])
        if pattern.startswith("#"):
            return self.elements_in_layer(pattern[1:])
        elem = self.get_element(pattern)
        return (elem,) if elem else ()


# ── Framework Interface Types ───────────────────────────────────

class PatternType(StrEnum):
    """Pattern classification for validity rule source/target patterns."""
    WILDCARD = "wildcard"       # "*"
    CATEGORY = "category"       # "@CategoryName"
    LAYER = "layer"             # "#LayerName"
    EXACT = "exact"             # "ElementName"


def classify_pattern(pattern: str) -> PatternType:
    """Classify a validity rule pattern string."""
    if pattern == "*":
        return PatternType.WILDCARD
    if pattern.startswith("@"):
        return PatternType.CATEGORY
    if pattern.startswith("#"):
        return PatternType.LAYER
    return PatternType.EXACT


def match_pattern(element: ProfileElement, pattern: str) -> bool:
    """Check if an element matches a validity rule pattern."""
    if pattern == "*":
        return True
    if pattern.startswith("@"):
        return element.category == pattern[1:]
    if pattern.startswith("#"):
        return element.layer == pattern[1:]
    return element.name == pattern


class ValidationCategory(StrEnum):
    """Outcome categories for build-time validation."""
    ENTITY_NOT_FOUND = "entity_not_found"
    NO_MATCHING_RULE = "no_matching_rule"
    CONDITION_FAILED = "condition_failed"
    LAYER_CONSTRAINT = "layer_constraint"
    EXPLICIT_DENY = "explicit_deny"
    ALLOWED = "allowed"


class ProfileBuildError(Exception):
    """Raised when profile build-time validation fails."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"{len(errors)} build error(s): {'; '.join(errors[:3])}")


@dataclass(frozen=True)
class QualityReport:
    """Quality gate analysis result for a built profile."""
    passed: bool
    dead_rules: tuple[str, ...]
    conflicting_rules: tuple[tuple[str, str], ...]
    missing_fallbacks: tuple[str, ...]
    invalid_patterns: tuple[str, ...]
    invalid_kernel_refs: tuple[str, ...]
    coverage: float


# ── Serialization ────────────────────────────────────────────────

@dataclass(frozen=True)
class ProfileVersion:
    """Stored profile version snapshot."""
    id: str                          # uuid4 hex
    profile_name: str
    version: str
    content_hash: str                # sha256
    data: dict[str, Any]             # serialized profile dict
    created_at: str                  # ISO 8601 UTC
    parent_id: str | None = None
    author: str = ""
    description: str = ""
    origin: str = ""                 # ProfileOrigin value, empty = unknown


class ProfileOrigin(StrEnum):
    """How a profile was loaded."""
    BUILTIN = "builtin"
    BUILDER = "builder"
    TOML = "toml"
    STORE = "store"
    COMPOSED = "composed"


# ── Diff ─────────────────────────────────────────────────────────

class DiffChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass(frozen=True)
class ElementChange:
    change_type: DiffChangeType
    element_name: str
    field: str = ""
    old_value: str = ""
    new_value: str = ""


@dataclass(frozen=True)
class RelationChange:
    change_type: DiffChangeType
    relation_name: str
    field: str = ""
    old_value: str = ""
    new_value: str = ""


@dataclass(frozen=True)
class RuleChange:
    change_type: DiffChangeType
    rule_id: str
    field: str = ""
    old_value: str = ""
    new_value: str = ""


@dataclass(frozen=True)
class ProfileDiff:
    """Structural diff between two profiles."""
    from_name: str
    from_version: str
    to_name: str
    to_version: str
    identical: bool
    element_changes: tuple[ElementChange, ...] = ()
    relation_changes: tuple[RelationChange, ...] = ()
    rule_changes: tuple[RuleChange, ...] = ()


# ── Store ────────────────────────────────────────────────────────

class ProfileStoreError(Exception):
    """Raised on profile store operational errors."""


class ProfileRegistryError(Exception):
    """Raised on profile registry operational errors."""


# ── Query ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProfileTag:
    """A named tag pointing to a profile version."""
    name: str
    profile_name: str
    version_id: str
    created_at: str = ""


# ── Backup ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class BackupFileEntry:
    """Single TOML file within a backup snapshot."""
    file_key: str       # "kernel_schema", "archimate", etc.
    file_path: str      # "specs/kernel_schema.toml" (relative path)
    content_hash: str   # SHA256
    content: str        # TOML raw text (byte-exact restore)
    size_bytes: int


@dataclass(frozen=True)
class BackupSnapshot:
    """Point-in-time snapshot of all 7 managed TOML files."""
    id: str                 # uuid4 hex
    version: str            # user-supplied or auto ISO timestamp
    created_at: str         # ISO 8601 UTC
    author: str
    description: str
    parent_id: str | None   # previous snapshot (auto-chaining)
    content_hash: str       # composite SHA256 of all file hashes
    files: tuple[BackupFileEntry, ...]


class BackupError(Exception):
    """Raised on backup/restore operational errors."""


# ── Audit ──────────────────────────────────────────────────────

class AuditSeverity(StrEnum):
    """Severity level for audit findings."""
    ERROR = "error"       # Must fix: invalid refs, conflicting rules
    WARNING = "warning"   # Should fix: dead rules, low coverage
    INFO = "info"         # Good to know: missing fallbacks


@dataclass(frozen=True)
class AuditFinding:
    """Single audit finding with severity and context."""
    severity: AuditSeverity
    category: str          # "invalid_kernel_ref", "dead_rule", etc.
    message: str
    rule_id: str = ""


@dataclass(frozen=True)
class AuditResult:
    """Audit result for a single profile."""
    profile_name: str
    passed: bool
    findings: tuple[AuditFinding, ...]
    quality: QualityReport


@dataclass(frozen=True)
class RegistryAuditReport:
    """Aggregated audit result for all profiles in a registry."""
    total_profiles: int
    passed_profiles: int
    results: tuple[AuditResult, ...]


@dataclass(frozen=True)
class DriftEntry:
    """A single drift finding when kernel changes affect a profile."""
    category: str          # "broken_type_ref", "broken_relation_ref", "rule_pattern_broken"
    message: str
    element_or_rule: str   # what's affected
