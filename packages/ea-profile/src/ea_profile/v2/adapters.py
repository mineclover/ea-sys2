"""Backward-compatible adapters between legacy ea_profile types and v2 specs."""

from __future__ import annotations

import hashlib
import logging
import re
import warnings
from typing import Any

from ea_profile.types import (
    KernelProfile,
    LayerDefinition,
    LayerStack,
    ProfileArtifactType,
    ProfileMetadata,
    ProfileStateTransition,
)
from ea_profile.v2.state_tokens import canonicalize_state_token, layered_state_reference
from ea_profile.v2.types import (
    ArtifactTier,
    ArtifactTypeSpec,
    FlowEdgeKind,
    FlowEdgeSpec,
    LayerRole,
    LayerSpec,
    ProfileSpec,
    StateTokenSpec,
    TransitionSpec,
    TypeSystemSpec,
)

_FLOW_SPLIT_RE = re.compile(r"\s*(?:->|>|,)\s*")
_LOGGER = logging.getLogger(__name__)
_LEGACY_PROFILE_DEPRECATION = (
    "Loading legacy KernelProfile into ea_profile.v2 is deprecated and will be removed "
    "in a future release. Migrate to TypeSystemSpec (see packages/ea-profile/docs/"
    "v2-cutover-guide.md)."
)

_LAYER_ROLE_BY_NAME: dict[str, LayerRole] = {
    "infra": LayerRole.RUNTIME_SUBSTRATE,
    "governance": LayerRole.SYSTEM_LEDGER,
    "decision": LayerRole.CAUSAL_MEMORY,
    "needs": LayerRole.CAUSAL_MEMORY,
    "kernel": LayerRole.BUSINESS_SKELETON,
    "flow": LayerRole.DATA_MODELING_MEMORY,
    "projection": LayerRole.SURFACE_MEMORY,
}


def legacy_profile_to_type_system(
    profile: KernelProfile,
    *,
    namespace: str | None = None,
    domain: str | None = None,
    role_by_layer: dict[str, LayerRole] | None = None,
    transition_layer: str | None = None,
    artifact_source_layers: tuple[str, ...] = ("projection",),
    warn_on_deprecated: bool = True,
) -> TypeSystemSpec:
    """Convert a legacy KernelProfile to a v2 TypeSystemSpec.

    The adapter preserves what exists in legacy metadata and maps unsupported
    areas to empty collections.
    """

    if warn_on_deprecated:
        warn_legacy_profile_deprecated(source="legacy_profile_to_type_system")

    profile_spec = profile_spec_from_legacy(
        profile,
        namespace=namespace,
        domain=domain,
    )
    layers = layer_specs_from_legacy(profile.layer_stack, role_by_layer=role_by_layer)
    flow_edges = flow_edges_from_legacy(profile.layer_stack)

    layer_id = _normalize_identifier(
        transition_layer or (layers[0].id if layers else "state"),
        prefix="layer",
    )
    transitions = transition_specs_from_legacy(
        profile.state_transitions,
        layer=layer_id,
    )
    state_tokens = state_token_specs_from_legacy(
        profile.state_transitions,
        layer=layer_id,
    )
    artifact_types = artifact_type_specs_from_legacy(
        profile.artifact_types,
        source_layers=artifact_source_layers,
    )

    return TypeSystemSpec(
        profile=profile_spec,
        layers=layers,
        flow_edges=flow_edges,
        state_tokens=state_tokens,
        transitions=transitions,
        artifact_types=artifact_types,
    )


def type_system_to_legacy_profile(
    spec: TypeSystemSpec,
    *,
    name: str | None = None,
) -> KernelProfile:
    """Convert v2 TypeSystemSpec to a legacy KernelProfile."""

    layer_stack = _build_legacy_layer_stack(spec.layers, spec.flow_edges)
    metadata = ProfileMetadata(
        standard="M2 v2",
        organization=spec.profile.namespace,
        extra={
            "namespace": spec.profile.namespace,
            "domain": spec.profile.domain,
        },
    )
    return KernelProfile(
        name=name or spec.profile.id,
        version=spec.profile.version,
        kernel_version=spec.profile.kernel_version,
        elements=(),
        relations=(),
        metadata=metadata,
        state_transitions=tuple(
            transition_spec_to_legacy(item) for item in spec.transitions
        ),
        artifact_types=tuple(
            artifact_type_spec_to_legacy(item) for item in spec.artifact_types
        ),
        layer_stack=layer_stack,
    )


def profile_spec_from_legacy(
    profile: KernelProfile,
    *,
    namespace: str | None = None,
    domain: str | None = None,
) -> ProfileSpec:
    """Build v2 ProfileSpec from legacy KernelProfile."""

    extra = profile.metadata.extra if profile.metadata and profile.metadata.extra else {}
    return ProfileSpec(
        id=_normalize_identifier(profile.name, prefix="profile"),
        version=profile.version,
        kernel_version=profile.kernel_version,
        namespace=_normalize_identifier(
            namespace or extra.get("namespace", "legacy"),
            prefix="namespace",
        ),
        domain=_normalize_identifier(
            domain or extra.get("domain", "legacy"),
            prefix="domain",
        ),
    )


def layer_specs_from_legacy(
    stack: LayerStack | None,
    *,
    role_by_layer: dict[str, LayerRole] | None = None,
    default_role: LayerRole = LayerRole.BUSINESS_SKELETON,
) -> tuple[LayerSpec, ...]:
    """Convert legacy LayerStack to v2 LayerSpec tuple."""

    if stack is None:
        return ()
    resolved_roles = dict(role_by_layer or {})
    result: list[LayerSpec] = []
    for layer in stack.layers:
        layer_id = _normalize_identifier(layer.name, prefix="layer")
        role = (
            resolved_roles.get(layer.name)
            or resolved_roles.get(layer_id)
            or _LAYER_ROLE_BY_NAME.get(layer_id, default_role)
        )
        responsibility = _as_text(layer.responsibility) or f"{layer.name} layer"
        result.append(
            LayerSpec(
                id=layer_id,
                order=layer.order,
                role=role,
                responsibility=responsibility,
            )
        )
    return tuple(result)


def flow_edges_from_legacy(stack: LayerStack | None) -> tuple[FlowEdgeSpec, ...]:
    """Convert legacy layer flow strings to v2 FlowEdgeSpec tuple."""

    if stack is None:
        return ()
    return flow_edges_from_legacy_flows(
        definition_flow=stack.definition_flow,
        runtime_flow=stack.runtime_flow,
        feedback_flow=stack.feedback_flow,
    )


def flow_edges_from_legacy_flows(
    *,
    definition_flow: str = "",
    runtime_flow: str = "",
    feedback_flow: str = "",
) -> tuple[FlowEdgeSpec, ...]:
    """Convert legacy LayerStack flow strings into canonical v2 flow edges."""

    channels = (
        ("definition", definition_flow, FlowEdgeKind.STRUCTURE_REQUEST),
        ("runtime", runtime_flow, FlowEdgeKind.EXECUTION_SPEC),
        ("feedback", feedback_flow, FlowEdgeKind.FEEDBACK_OBSERVATION),
    )
    edges: list[FlowEdgeSpec] = []
    for channel, flow, kind in channels:
        path = _parse_flow_path(flow)
        for idx, (source, target) in enumerate(zip(path, path[1:], strict=False), start=1):
            edges.append(
                FlowEdgeSpec(
                    id=f"{channel}_flow_{idx}",
                    from_layer=source,
                    to_layer=target,
                    kind=kind,
                    required=True,
                )
            )
    return tuple(edges)


def warn_legacy_profile_deprecated(*, source: str) -> None:
    """Emit compatibility deprecation diagnostics for legacy profile loading."""

    message = f"{_LEGACY_PROFILE_DEPRECATION} source={source}"
    _LOGGER.warning(message)
    warnings.warn(message, category=DeprecationWarning, stacklevel=3)


def state_token_specs_from_legacy(
    transitions: tuple[ProfileStateTransition, ...],
    *,
    layer: str,
) -> tuple[StateTokenSpec, ...]:
    """Derive v2 StateTokenSpec entries from legacy transitions."""

    layer_id = _normalize_identifier(layer, prefix="layer")
    aliases_by_canonical: dict[str, set[str]] = {}
    for transition in transitions:
        for state in (transition.from_state, transition.to_state):
            if state == "*":
                continue
            canonical = canonicalize_state_token(state)
            aliases_by_canonical.setdefault(canonical, set())
            original = state.strip()
            if original and original != canonical:
                aliases_by_canonical[canonical].add(original)

    result = [
        StateTokenSpec(
            id=f"{layer_id}.{canonical.lower()}",
            layer=layer_id,
            canonical=canonical,
            aliases=tuple(sorted(aliases)),
        )
        for canonical, aliases in sorted(aliases_by_canonical.items())
    ]
    return tuple(result)


def transition_specs_from_legacy(
    transitions: tuple[ProfileStateTransition, ...],
    *,
    layer: str,
    requires_trace: bool = False,
    requires_governance_event: str = "state.transitioned",
) -> tuple[TransitionSpec, ...]:
    """Convert legacy state transitions to v2 TransitionSpec entries."""

    layer_id = _normalize_identifier(layer, prefix="layer")
    result: list[TransitionSpec] = []
    for transition in transitions:
        from_state = layered_state_reference(layer_id, transition.from_state)
        to_state = layered_state_reference(layer_id, transition.to_state)
        from_slug = "any" if from_state == "*" else from_state.rsplit(".", 1)[-1]
        to_slug = "any" if to_state == "*" else to_state.rsplit(".", 1)[-1]
        result.append(
            TransitionSpec(
                id=f"{layer_id}.{from_slug}_to_{to_slug}",
                layer=layer_id,
                from_state=from_state,
                to_state=to_state,
                requires_trace=requires_trace,
                requires_governance_event=requires_governance_event,
            )
        )
    return tuple(result)


def artifact_type_specs_from_legacy(
    artifact_types: tuple[ProfileArtifactType, ...],
    *,
    source_layers: tuple[str, ...] = ("projection",),
) -> tuple[ArtifactTypeSpec, ...]:
    """Convert legacy ProfileArtifactType entries to v2 ArtifactTypeSpec."""

    return tuple(
        artifact_type_spec_from_legacy(item, source_layers=source_layers)
        for item in artifact_types
    )


def transition_spec_to_legacy(spec: TransitionSpec) -> ProfileStateTransition:
    """Convert a v2 TransitionSpec to legacy ProfileStateTransition."""

    return ProfileStateTransition(
        from_state=_legacy_state_token(spec.from_state),
        to_state=_legacy_state_token(spec.to_state),
        guard_condition="",
        description="",
    )


def artifact_type_spec_to_legacy(spec: ArtifactTypeSpec) -> ProfileArtifactType:
    """Convert a v2 ArtifactTypeSpec to legacy ProfileArtifactType."""

    return ProfileArtifactType(
        name=spec.id,
        tier=spec.tier.value,
        description="",
        kernel_element_pattern=spec.kernel_element_pattern,
    )


def artifact_type_spec_from_legacy(
    artifact_type: ProfileArtifactType,
    *,
    source_layers: tuple[str, ...] = ("projection",),
) -> ArtifactTypeSpec:
    """Convert a legacy artifact type into v2 ArtifactTypeSpec."""

    return ArtifactTypeSpec(
        id=_normalize_identifier(artifact_type.name, prefix="artifact"),
        tier=_to_artifact_tier(artifact_type.tier),
        source_layers=tuple(_normalize_identifier(layer, prefix="layer") for layer in source_layers),
        kernel_element_pattern=artifact_type.kernel_element_pattern or "*",
    )


def _to_artifact_tier(value: str) -> ArtifactTier:
    raw = value.strip().lower()
    alias: dict[str, ArtifactTier] = {
        "function": ArtifactTier.FUNCTION,
        "ui": ArtifactTier.UI,
        "data": ArtifactTier.DATA,
        "evidence": ArtifactTier.EVIDENCE,
    }
    if raw not in alias:
        raise ValueError(f"Unsupported legacy artifact tier: {value!r}")
    return alias[raw]


def _build_legacy_layer_stack(
    layers: tuple[LayerSpec, ...],
    edges: tuple[FlowEdgeSpec, ...],
) -> LayerStack | None:
    if not layers:
        return None
    ordered = sorted(layers, key=lambda item: item.order)
    legacy_layers = tuple(
        LayerDefinition(
            name=layer.id,
            order=layer.order,
            depends_on=(),
            responsibility=layer.responsibility,
            model_perspective="",
        )
        for layer in ordered
    )
    return LayerStack(
        layers=legacy_layers,
        definition_flow=_edge_chain_as_string(edges, FlowEdgeKind.STRUCTURE_REQUEST),
        runtime_flow=_edge_chain_as_string(edges, FlowEdgeKind.EXECUTION_SPEC),
        feedback_flow=_edge_chain_as_string(edges, FlowEdgeKind.FEEDBACK_OBSERVATION),
    )


def _edge_chain_as_string(
    edges: tuple[FlowEdgeSpec, ...],
    kind: FlowEdgeKind,
) -> str:
    chain = [edge for edge in edges if edge.kind == kind]
    if not chain:
        return ""
    parts = [chain[0].from_layer]
    parts.extend(edge.to_layer for edge in chain)
    return " -> ".join(parts)


def _normalize_identifier(value: str, *, prefix: str) -> str:
    base = value.strip().lower()
    base = re.sub(r"[^a-z0-9._-]+", "-", base)
    base = base.strip("._-")
    if not base:
        base = prefix
    if len(base) < 3:
        base = f"{prefix}-{base}"
    if len(base) > 64:
        base = base[:64]
    candidate = base if base[0].isalnum() else f"{prefix}-{base}"

    # Fall back to stable digest when normalization still violates pattern.
    from ea_profile.v2.types import ID_PATTERN

    if ID_PATTERN.fullmatch(candidate):
        return candidate
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def _parse_flow_path(raw: str) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        return ()
    parts = [part for part in _FLOW_SPLIT_RE.split(text) if part]
    if len(parts) < 2:
        return ()
    return tuple(_normalize_identifier(part, prefix="layer") for part in parts)


def _legacy_state_token(value: str) -> str:
    if value == "*":
        return value
    return canonicalize_state_token(value)


def _as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        preferred = value.get("en")
        if isinstance(preferred, str):
            return preferred
        for item in value.values():
            if isinstance(item, str):
                return item
    return ""
