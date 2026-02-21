"""Canonical M2 v2 type system contracts.

These types are the single source of truth for M2-level profile contracts.
Runtime checks in ``__post_init__`` enforce required fields and enum usage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ea_profile.v2.state_tokens import parse_state_reference, state_reference_aliases

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
TEAM_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
EVENT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
EXPOSURE_REF_PREFIXES = ("url:", "file:", "api:", "dashboard:")
REQUIRED_CORRELATION_FIELDS = ("trace_id", "lineage_id")


class LayerRole(StrEnum):
    """Allowed v2 layer roles."""

    RUNTIME_SUBSTRATE = "runtime_substrate"
    SYSTEM_LEDGER = "system_ledger"
    CAUSAL_MEMORY = "causal_memory"
    BUSINESS_SKELETON = "business_skeleton"
    DATA_MODELING_MEMORY = "data_modeling_memory"
    SURFACE_MEMORY = "surface_memory"


class FlowEdgeKind(StrEnum):
    """Canonical v2 flow-edge kinds."""

    SUBSTRATE_CONSTRAINT = "substrate_constraint"
    RUNTIME_CAPABILITY_BINDING = "runtime_capability_binding"
    CAUSAL_HANDOFF = "causal_handoff"
    STRUCTURE_REQUEST = "structure_request"
    EXECUTION_SPEC = "execution_spec"
    SURFACE_EXPOSURE = "surface_exposure"
    FEEDBACK_OBSERVATION = "feedback_observation"
    LEGACY_FLOW = "legacy_flow"


class ArtifactTier(StrEnum):
    """Artifact tier classification."""

    FUNCTION = "function"
    UI = "ui"
    DATA = "data"
    EVIDENCE = "evidence"


class TraceRelation(StrEnum):
    """Canonical causal trace relations."""

    INFORMED_BY = "informed_by"
    DERIVED_FROM = "derived_from"
    SATISFIES = "satisfies"
    IMPLEMENTS = "implements"


class GovernanceRetentionPolicy(StrEnum):
    """Governance event retention policies."""

    IMMUTABLE = "immutable"
    TIMEBOXED = "timeboxed"
    EPHEMERAL = "ephemeral"


class InfraAssetType(StrEnum):
    """Allowed infra asset type taxonomy."""

    COMPUTE_SERVICE = "compute_service"
    API_GATEWAY = "api_gateway"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    OBJECT_STORAGE = "object_storage"
    NETWORK = "network"
    OBSERVABILITY = "observability"
    IDENTITY = "identity"


class InfraEnvironment(StrEnum):
    """Allowed infra environment values."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    SANDBOX = "sandbox"
    SHARED = "shared"


class InfraCriticality(StrEnum):
    """Allowed infra criticality tiers."""

    TIER0 = "tier0"
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"


class ServiceOpsSeverity(StrEnum):
    """Severity levels for service operations events."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FeedbackLayer(StrEnum):
    """Allowed feedback destinations for service ops events."""

    DECISION = "decision"
    NEEDS = "needs"
    KERNEL = "kernel"


class EvidenceBindingTarget(StrEnum):
    """Allowed evidence target categories."""

    CODE_COMMIT = "code_commit"
    CI_RUN = "ci_run"
    DEPLOYMENT_RECORD = "deployment_record"
    DASHBOARD_SNAPSHOT = "dashboard_snapshot"
    INCIDENT_TICKET = "incident_ticket"
    RUNBOOK_REF = "runbook_ref"


@dataclass(frozen=True)
class ProfileSpec:
    """Top-level profile metadata contract."""

    id: str
    version: str
    kernel_version: str
    namespace: str
    domain: str

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_non_empty("version", self.version)
        _require_non_empty("kernel_version", self.kernel_version)
        _require_identifier("namespace", self.namespace)
        _require_identifier("domain", self.domain)


@dataclass(frozen=True)
class LayerSpec:
    """Layer declaration contract."""

    id: str
    order: int
    role: LayerRole
    responsibility: str

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        if not isinstance(self.order, int):
            raise TypeError("order must be int")
        _require_enum("role", self.role, LayerRole)
        _require_non_empty("responsibility", self.responsibility)


@dataclass(frozen=True)
class FlowEdgeSpec:
    """Typed edge contract between layers."""

    id: str
    from_layer: str
    to_layer: str
    kind: FlowEdgeKind
    required: bool

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_identifier("from_layer", self.from_layer)
        _require_identifier("to_layer", self.to_layer)
        _require_enum("kind", self.kind, FlowEdgeKind)
        if not isinstance(self.required, bool):
            raise TypeError("required must be bool")


@dataclass(frozen=True)
class StateTokenSpec:
    """Canonical state-token declaration for lifecycle transitions."""

    id: str
    layer: str
    canonical: str
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_identifier("layer", self.layer)
        _require_non_empty("canonical", self.canonical)
        aliases = _as_str_tuple("aliases", self.aliases)
        _ensure_no_duplicates("aliases", aliases)
        object.__setattr__(self, "aliases", aliases)


@dataclass(frozen=True)
class TransitionSpec:
    """Lifecycle transition contract."""

    id: str
    layer: str
    from_state: str
    to_state: str
    requires_trace: bool
    requires_governance_event: str

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_identifier("layer", self.layer)
        _require_non_empty("from_state", self.from_state)
        _require_non_empty("to_state", self.to_state)
        if not isinstance(self.requires_trace, bool):
            raise TypeError("requires_trace must be bool")
        _require_event_name("requires_governance_event", self.requires_governance_event)


@dataclass(frozen=True)
class ArtifactTypeSpec:
    """Projection artifact type contract."""

    id: str
    tier: ArtifactTier
    source_layers: tuple[str, ...]
    kernel_element_pattern: str

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_enum("tier", self.tier, ArtifactTier)
        source_layers = _as_str_tuple("source_layers", self.source_layers)
        if not source_layers:
            raise ValueError("source_layers must contain at least one layer id")
        for layer in source_layers:
            _require_identifier("source_layers[]", layer)
        _ensure_no_duplicates("source_layers", source_layers)
        object.__setattr__(self, "source_layers", source_layers)
        _require_non_empty("kernel_element_pattern", self.kernel_element_pattern)


@dataclass(frozen=True)
class TraceLinkSpec:
    """Cross-layer causal link contract."""

    id: str
    source_type: str
    target_type: str
    relation: TraceRelation
    required: bool

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_identifier("source_type", self.source_type)
        _require_identifier("target_type", self.target_type)
        _require_enum("relation", self.relation, TraceRelation)
        if not isinstance(self.required, bool):
            raise TypeError("required must be bool")


@dataclass(frozen=True)
class GovernanceEventSpec:
    """Governance event schema contract."""

    name: str
    must_include: tuple[str, ...]
    retention_policy: GovernanceRetentionPolicy

    def __post_init__(self) -> None:
        _require_event_name("name", self.name)
        must_include = _as_str_tuple("must_include", self.must_include)
        _ensure_no_duplicates("must_include", must_include)
        for field in REQUIRED_CORRELATION_FIELDS:
            if field not in must_include:
                raise ValueError(f"must_include must contain {field}")
        object.__setattr__(self, "must_include", must_include)
        _require_enum("retention_policy", self.retention_policy, GovernanceRetentionPolicy)


@dataclass(frozen=True)
class LoopContractSpec:
    """Closed-loop enforcement contract."""

    id: str
    path: tuple[str, ...]
    enforce_trace: bool
    enforce_event_chain: bool

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        path = _as_str_tuple("path", self.path)
        if len(path) < 2:
            raise ValueError("path must contain at least two layer ids")
        for layer in path:
            _require_identifier("path[]", layer)
        if path[0] != path[-1]:
            raise ValueError("path must be closed (first layer equals last layer)")
        object.__setattr__(self, "path", path)
        if not isinstance(self.enforce_trace, bool):
            raise TypeError("enforce_trace must be bool")
        if not isinstance(self.enforce_event_chain, bool):
            raise TypeError("enforce_event_chain must be bool")


@dataclass(frozen=True)
class InfraAssetSpec:
    """Infrastructure asset catalog contract."""

    id: str
    asset_type: InfraAssetType
    owner: str
    environment: InfraEnvironment
    criticality: InfraCriticality
    exposure_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        _require_enum("asset_type", self.asset_type, InfraAssetType)
        owner = _require_non_empty("owner", self.owner)
        if TEAM_SLUG_PATTERN.fullmatch(owner) is None:
            raise ValueError("owner must be a team slug (e.g. platform-data)")
        _require_enum("environment", self.environment, InfraEnvironment)
        _require_enum("criticality", self.criticality, InfraCriticality)

        refs = _as_str_tuple("exposure_refs", self.exposure_refs)
        if not refs:
            raise ValueError("exposure_refs must contain at least one reference")
        for ref in refs:
            if not ref.startswith(EXPOSURE_REF_PREFIXES):
                raise ValueError(
                    "exposure_refs entries must start with one of: "
                    + ", ".join(EXPOSURE_REF_PREFIXES)
                )
        if self.asset_type == InfraAssetType.API_GATEWAY and not any(
            ref.startswith(("url:", "api:")) for ref in refs
        ):
            raise ValueError("api_gateway assets require at least one url: or api: exposure_ref")
        object.__setattr__(self, "exposure_refs", refs)


@dataclass(frozen=True)
class ServiceOpsEventSpec:
    """Service operations event contract."""

    name: str
    severity: ServiceOpsSeverity
    must_include: tuple[str, ...]
    feeds_back_to: FeedbackLayer

    def __post_init__(self) -> None:
        _require_event_name("name", self.name)
        _require_enum("severity", self.severity, ServiceOpsSeverity)
        must_include = _as_str_tuple("must_include", self.must_include)
        _ensure_no_duplicates("must_include", must_include)
        for field in REQUIRED_CORRELATION_FIELDS:
            if field not in must_include:
                raise ValueError(f"must_include must contain {field}")
        if self.severity == ServiceOpsSeverity.CRITICAL and not {
            "runbook_url",
            "incident_id",
        }.intersection(must_include):
            raise ValueError(
                "critical severity requires runbook_url or incident_id in must_include"
            )
        object.__setattr__(self, "must_include", must_include)
        _require_enum("feeds_back_to", self.feeds_back_to, FeedbackLayer)


@dataclass(frozen=True)
class EvidenceBindingSpec:
    """Evidence binding contract for audit replay."""

    id: str
    source_type: str
    binds_to: EvidenceBindingTarget
    required_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier("id", self.id)
        source_type = _require_identifier("source_type", self.source_type)
        _require_enum("binds_to", self.binds_to, EvidenceBindingTarget)
        required_fields = _as_str_tuple("required_fields", self.required_fields)
        if len(required_fields) < 3:
            raise ValueError("required_fields must include at least 3 entries")
        _ensure_no_duplicates("required_fields", required_fields)
        if source_type == "surface_artifact" and "environment" not in required_fields:
            raise ValueError(
                "required_fields must include environment when source_type is surface_artifact"
            )
        object.__setattr__(self, "required_fields", required_fields)


@dataclass(frozen=True)
class TypeSystemSpec:
    """Full M2 v2 type-system aggregate."""

    profile: ProfileSpec
    layers: tuple[LayerSpec, ...] = ()
    flow_edges: tuple[FlowEdgeSpec, ...] = ()
    state_tokens: tuple[StateTokenSpec, ...] = ()
    transitions: tuple[TransitionSpec, ...] = ()
    artifact_types: tuple[ArtifactTypeSpec, ...] = ()
    trace_links: tuple[TraceLinkSpec, ...] = ()
    governance_events: tuple[GovernanceEventSpec, ...] = ()
    loop_contracts: tuple[LoopContractSpec, ...] = ()
    infra_assets: tuple[InfraAssetSpec, ...] = ()
    service_ops_events: tuple[ServiceOpsEventSpec, ...] = ()
    evidence_bindings: tuple[EvidenceBindingSpec, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "layers", tuple(self.layers))
        object.__setattr__(self, "flow_edges", tuple(self.flow_edges))
        object.__setattr__(self, "state_tokens", tuple(self.state_tokens))
        object.__setattr__(self, "transitions", tuple(self.transitions))
        object.__setattr__(self, "artifact_types", tuple(self.artifact_types))
        object.__setattr__(self, "trace_links", tuple(self.trace_links))
        object.__setattr__(self, "governance_events", tuple(self.governance_events))
        object.__setattr__(self, "loop_contracts", tuple(self.loop_contracts))
        object.__setattr__(self, "infra_assets", tuple(self.infra_assets))
        object.__setattr__(self, "service_ops_events", tuple(self.service_ops_events))
        object.__setattr__(self, "evidence_bindings", tuple(self.evidence_bindings))

        _ensure_unique("layers.id", (layer.id for layer in self.layers))
        _ensure_unique("flow_edges.id", (edge.id for edge in self.flow_edges))
        _ensure_unique("state_tokens.id", (token.id for token in self.state_tokens))
        _ensure_unique("transitions.id", (item.id for item in self.transitions))
        _ensure_unique("artifact_types.id", (item.id for item in self.artifact_types))
        _ensure_unique("trace_links.id", (item.id for item in self.trace_links))
        _ensure_unique("governance_events.name", (item.name for item in self.governance_events))
        _ensure_unique("loop_contracts.id", (item.id for item in self.loop_contracts))
        _ensure_unique("infra_assets.id", (item.id for item in self.infra_assets))
        _ensure_unique(
            "service_ops_events.name",
            (item.name for item in self.service_ops_events),
        )
        _ensure_unique(
            "evidence_bindings.id",
            (item.id for item in self.evidence_bindings),
        )
        _validate_transition_state_tokens(self.state_tokens, self.transitions)
        _validate_trace_link_evidence_bindings(
            trace_links=self.trace_links,
            evidence_bindings=self.evidence_bindings,
        )


def _validate_transition_state_tokens(
    state_tokens: tuple[StateTokenSpec, ...],
    transitions: tuple[TransitionSpec, ...],
) -> None:
    references_by_layer: dict[str, dict[str, str]] = {}
    for token in state_tokens:
        references = references_by_layer.setdefault(token.layer, {})
        for alias in state_reference_aliases(
            token_id=token.id,
            canonical=token.canonical,
            aliases=token.aliases,
        ):
            existing = references.get(alias)
            if existing is not None and existing != token.id:
                raise ValueError(
                    f"state_tokens alias '{alias}' is ambiguous in layer '{token.layer}'"
                )
            references[alias] = token.id

    for transition in transitions:
        layer_refs = references_by_layer.get(transition.layer)
        if layer_refs is None:
            raise ValueError(
                f"transitions[{transition.id}] references unknown layer '{transition.layer}'"
            )
        _validate_transition_state_reference(
            transition=transition,
            field="from_state",
            reference=transition.from_state,
            layer_references=layer_refs,
        )
        _validate_transition_state_reference(
            transition=transition,
            field="to_state",
            reference=transition.to_state,
            layer_references=layer_refs,
        )


def _validate_transition_state_reference(
    *,
    transition: TransitionSpec,
    field: str,
    reference: str,
    layer_references: dict[str, str],
) -> None:
    if reference == "*":
        return

    referenced_layer, alias = parse_state_reference(reference)
    if referenced_layer and referenced_layer != transition.layer:
        raise ValueError(
            f"transitions[{transition.id}].{field} must reference layer "
            f"'{transition.layer}', got '{referenced_layer}'"
        )
    if alias not in layer_references:
        raise ValueError(
            f"transitions[{transition.id}].{field} references unknown state '{reference}' "
            f"for layer '{transition.layer}'"
        )


def _validate_trace_link_evidence_bindings(
    *,
    trace_links: tuple[TraceLinkSpec, ...],
    evidence_bindings: tuple[EvidenceBindingSpec, ...],
) -> None:
    trace_node_types = {
        link_type
        for link in trace_links
        for link_type in (link.source_type, link.target_type)
    }
    for binding in evidence_bindings:
        if binding.source_type == "surface_artifact" and "environment" not in binding.required_fields:
            raise ValueError(
                "evidence_bindings"
                f"[{binding.id}].required_fields must include environment "
                "when source_type is surface_artifact"
            )
        if binding.source_type not in trace_node_types:
            raise ValueError(
                "evidence_bindings"
                f"[{binding.id}].source_type references unknown trace node type "
                f"'{binding.source_type}'"
            )


def _require_non_empty(field: str, value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be str")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must be a non-empty string")
    return normalized


def _require_identifier(field: str, value: str) -> str:
    normalized = _require_non_empty(field, value)
    if ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{field} must match {ID_PATTERN.pattern}")
    return normalized


def _require_event_name(field: str, value: str) -> str:
    normalized = _require_non_empty(field, value)
    if EVENT_NAME_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{field} must match {EVENT_NAME_PATTERN.pattern}")
    return normalized


def _require_enum(field: str, value: Any, enum_type: type[StrEnum]) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field} must be {enum_type.__name__}")


def _as_str_tuple(field: str, value: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        raise TypeError(f"{field} must be a tuple[str, ...], not str")
    if not isinstance(value, tuple):
        value = tuple(value)
    items = tuple(_require_non_empty(f"{field}[]", item) for item in value)
    return items


def _ensure_no_duplicates(field: str, values: tuple[str, ...]) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"{field} must not contain duplicates")


def _ensure_unique(field: str, values: Any) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        dup = ", ".join(sorted(duplicates))
        raise ValueError(f"{field} must be unique; duplicates: {dup}")
