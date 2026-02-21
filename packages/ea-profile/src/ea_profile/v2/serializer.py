"""Serialization helpers for the M2 v2 type system."""

from __future__ import annotations

import json
from typing import Any

from ea_profile.v2.types import (
    ArtifactTier,
    ArtifactTypeSpec,
    EvidenceBindingSpec,
    EvidenceBindingTarget,
    FeedbackLayer,
    FlowEdgeKind,
    FlowEdgeSpec,
    GovernanceEventSpec,
    GovernanceRetentionPolicy,
    InfraAssetSpec,
    InfraAssetType,
    InfraCriticality,
    InfraEnvironment,
    LayerRole,
    LayerSpec,
    LoopContractSpec,
    ProfileSpec,
    ServiceOpsEventSpec,
    ServiceOpsSeverity,
    StateTokenSpec,
    TraceLinkSpec,
    TraceRelation,
    TransitionSpec,
    TypeSystemSpec,
)


def type_system_to_dict(spec: TypeSystemSpec) -> dict[str, Any]:
    """Convert TypeSystemSpec to a JSON-safe dict."""

    return {
        "profile": _profile_to_dict(spec.profile),
        "layers": [_layer_to_dict(item) for item in spec.layers],
        "flow_edges": [_flow_edge_to_dict(item) for item in spec.flow_edges],
        "state_tokens": [_state_token_to_dict(item) for item in spec.state_tokens],
        "transitions": [_transition_to_dict(item) for item in spec.transitions],
        "artifact_types": [_artifact_type_to_dict(item) for item in spec.artifact_types],
        "trace_links": [_trace_link_to_dict(item) for item in spec.trace_links],
        "governance_events": [_governance_event_to_dict(item) for item in spec.governance_events],
        "loop_contracts": [_loop_contract_to_dict(item) for item in spec.loop_contracts],
        "infra_assets": [_infra_asset_to_dict(item) for item in spec.infra_assets],
        "service_ops_events": [_service_ops_event_to_dict(item) for item in spec.service_ops_events],
        "evidence_bindings": [_evidence_binding_to_dict(item) for item in spec.evidence_bindings],
    }


def dict_to_type_system(data: dict[str, Any]) -> TypeSystemSpec:
    """Convert a dict payload to TypeSystemSpec."""

    return TypeSystemSpec(
        profile=_dict_to_profile(data["profile"]),
        layers=tuple(_dict_to_layer(item) for item in data.get("layers", [])),
        flow_edges=tuple(_dict_to_flow_edge(item) for item in data.get("flow_edges", [])),
        state_tokens=tuple(_dict_to_state_token(item) for item in data.get("state_tokens", [])),
        transitions=tuple(_dict_to_transition(item) for item in data.get("transitions", [])),
        artifact_types=tuple(
            _dict_to_artifact_type(item) for item in data.get("artifact_types", [])
        ),
        trace_links=tuple(_dict_to_trace_link(item) for item in data.get("trace_links", [])),
        governance_events=tuple(
            _dict_to_governance_event(item) for item in data.get("governance_events", [])
        ),
        loop_contracts=tuple(
            _dict_to_loop_contract(item) for item in data.get("loop_contracts", [])
        ),
        infra_assets=tuple(_dict_to_infra_asset(item) for item in data.get("infra_assets", [])),
        service_ops_events=tuple(
            _dict_to_service_ops_event(item) for item in data.get("service_ops_events", [])
        ),
        evidence_bindings=tuple(
            _dict_to_evidence_binding(item) for item in data.get("evidence_bindings", [])
        ),
    )


def type_system_to_json(spec: TypeSystemSpec, *, indent: int = 2) -> str:
    """Serialize TypeSystemSpec as JSON."""

    return json.dumps(type_system_to_dict(spec), indent=indent, ensure_ascii=False)


def json_to_type_system(raw: str) -> TypeSystemSpec:
    """Deserialize TypeSystemSpec from JSON."""

    return dict_to_type_system(json.loads(raw))


def _profile_to_dict(spec: ProfileSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "version": spec.version,
        "kernel_version": spec.kernel_version,
        "namespace": spec.namespace,
        "domain": spec.domain,
    }


def _dict_to_profile(data: dict[str, Any]) -> ProfileSpec:
    return ProfileSpec(
        id=data["id"],
        version=data["version"],
        kernel_version=data["kernel_version"],
        namespace=data["namespace"],
        domain=data["domain"],
    )


def _layer_to_dict(spec: LayerSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "order": spec.order,
        "role": spec.role.value,
        "responsibility": spec.responsibility,
    }


def _dict_to_layer(data: dict[str, Any]) -> LayerSpec:
    return LayerSpec(
        id=data["id"],
        order=data["order"],
        role=LayerRole(data["role"]),
        responsibility=data["responsibility"],
    )


def _flow_edge_to_dict(spec: FlowEdgeSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "from": spec.from_layer,
        "to": spec.to_layer,
        "kind": spec.kind.value,
        "required": spec.required,
    }


def _dict_to_flow_edge(data: dict[str, Any]) -> FlowEdgeSpec:
    return FlowEdgeSpec(
        id=data["id"],
        from_layer=data["from"],
        to_layer=data["to"],
        kind=FlowEdgeKind(data["kind"]),
        required=data["required"],
    )


def _state_token_to_dict(spec: StateTokenSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "layer": spec.layer,
        "canonical": spec.canonical,
        "aliases": list(spec.aliases),
    }


def _dict_to_state_token(data: dict[str, Any]) -> StateTokenSpec:
    return StateTokenSpec(
        id=data["id"],
        layer=data["layer"],
        canonical=data["canonical"],
        aliases=tuple(data.get("aliases", [])),
    )


def _transition_to_dict(spec: TransitionSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "layer": spec.layer,
        "from": spec.from_state,
        "to": spec.to_state,
        "requires_trace": spec.requires_trace,
        "requires_governance_event": spec.requires_governance_event,
    }


def _dict_to_transition(data: dict[str, Any]) -> TransitionSpec:
    return TransitionSpec(
        id=data["id"],
        layer=data["layer"],
        from_state=data["from"],
        to_state=data["to"],
        requires_trace=data["requires_trace"],
        requires_governance_event=data["requires_governance_event"],
    )


def _artifact_type_to_dict(spec: ArtifactTypeSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "tier": spec.tier.value,
        "source_layers": list(spec.source_layers),
        "kernel_element_pattern": spec.kernel_element_pattern,
    }


def _dict_to_artifact_type(data: dict[str, Any]) -> ArtifactTypeSpec:
    return ArtifactTypeSpec(
        id=data["id"],
        tier=ArtifactTier(data["tier"]),
        source_layers=tuple(data["source_layers"]),
        kernel_element_pattern=data["kernel_element_pattern"],
    )


def _trace_link_to_dict(spec: TraceLinkSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "source_type": spec.source_type,
        "target_type": spec.target_type,
        "relation": spec.relation.value,
        "required": spec.required,
    }


def _dict_to_trace_link(data: dict[str, Any]) -> TraceLinkSpec:
    return TraceLinkSpec(
        id=data["id"],
        source_type=data["source_type"],
        target_type=data["target_type"],
        relation=TraceRelation(data["relation"]),
        required=data["required"],
    )


def _governance_event_to_dict(spec: GovernanceEventSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "must_include": list(spec.must_include),
        "retention_policy": spec.retention_policy.value,
    }


def _dict_to_governance_event(data: dict[str, Any]) -> GovernanceEventSpec:
    return GovernanceEventSpec(
        name=data["name"],
        must_include=tuple(data["must_include"]),
        retention_policy=GovernanceRetentionPolicy(data["retention_policy"]),
    )


def _loop_contract_to_dict(spec: LoopContractSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "path": list(spec.path),
        "enforce_trace": spec.enforce_trace,
        "enforce_event_chain": spec.enforce_event_chain,
    }


def _dict_to_loop_contract(data: dict[str, Any]) -> LoopContractSpec:
    return LoopContractSpec(
        id=data["id"],
        path=tuple(data["path"]),
        enforce_trace=data["enforce_trace"],
        enforce_event_chain=data["enforce_event_chain"],
    )


def _infra_asset_to_dict(spec: InfraAssetSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "asset_type": spec.asset_type.value,
        "owner": spec.owner,
        "environment": spec.environment.value,
        "criticality": spec.criticality.value,
        "exposure_refs": list(spec.exposure_refs),
    }


def _dict_to_infra_asset(data: dict[str, Any]) -> InfraAssetSpec:
    return InfraAssetSpec(
        id=data["id"],
        asset_type=InfraAssetType(data["asset_type"]),
        owner=data["owner"],
        environment=InfraEnvironment(data["environment"]),
        criticality=InfraCriticality(data["criticality"]),
        exposure_refs=tuple(data["exposure_refs"]),
    )


def _service_ops_event_to_dict(spec: ServiceOpsEventSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "severity": spec.severity.value,
        "must_include": list(spec.must_include),
        "feeds_back_to": spec.feeds_back_to.value,
    }


def _dict_to_service_ops_event(data: dict[str, Any]) -> ServiceOpsEventSpec:
    return ServiceOpsEventSpec(
        name=data["name"],
        severity=ServiceOpsSeverity(data["severity"]),
        must_include=tuple(data["must_include"]),
        feeds_back_to=FeedbackLayer(data["feeds_back_to"]),
    )


def _evidence_binding_to_dict(spec: EvidenceBindingSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "source_type": spec.source_type,
        "binds_to": spec.binds_to.value,
        "required_fields": list(spec.required_fields),
    }


def _dict_to_evidence_binding(data: dict[str, Any]) -> EvidenceBindingSpec:
    return EvidenceBindingSpec(
        id=data["id"],
        source_type=data["source_type"],
        binds_to=EvidenceBindingTarget(data["binds_to"]),
        required_fields=tuple(data["required_fields"]),
    )
