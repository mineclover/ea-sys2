"""Tests for ea_profile.v2 canonical type system."""

import pytest
from ea_profile.types import (
    KernelProfile,
    LayerDefinition,
    LayerStack,
    ProfileArtifactType,
    ProfileMetadata,
    ProfileStateTransition,
)
from ea_profile.v2.adapters import legacy_profile_to_type_system, type_system_to_legacy_profile
from ea_profile.v2.serializer import (
    dict_to_type_system,
    json_to_type_system,
    type_system_to_dict,
    type_system_to_json,
)
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


def _sample_type_system() -> TypeSystemSpec:
    return TypeSystemSpec(
        profile=ProfileSpec(
            id="ea-m2-v2",
            version="2.0.0",
            kernel_version="2.5.0",
            namespace="ea_sys",
            domain="governance_core",
        ),
        layers=(
            LayerSpec(
                id="infra",
                order=0,
                role=LayerRole.RUNTIME_SUBSTRATE,
                responsibility="Runtime substrate contracts",
            ),
            LayerSpec(
                id="decision",
                order=10,
                role=LayerRole.CAUSAL_MEMORY,
                responsibility="Decision causal memory",
            ),
            LayerSpec(
                id="kernel",
                order=20,
                role=LayerRole.BUSINESS_SKELETON,
                responsibility="Kernel structure",
            ),
            LayerSpec(
                id="flow",
                order=30,
                role=LayerRole.DATA_MODELING_MEMORY,
                responsibility="Flow execution memory",
            ),
            LayerSpec(
                id="projection",
                order=40,
                role=LayerRole.SURFACE_MEMORY,
                responsibility="Surface artifact memory",
            ),
        ),
        flow_edges=(
            FlowEdgeSpec(
                id="infra_to_kernel",
                from_layer="infra",
                to_layer="kernel",
                kind=FlowEdgeKind.SUBSTRATE_CONSTRAINT,
                required=True,
            ),
            FlowEdgeSpec(
                id="kernel_to_flow",
                from_layer="kernel",
                to_layer="flow",
                kind=FlowEdgeKind.EXECUTION_SPEC,
                required=True,
            ),
            FlowEdgeSpec(
                id="flow_to_projection",
                from_layer="flow",
                to_layer="projection",
                kind=FlowEdgeKind.SURFACE_EXPOSURE,
                required=True,
            ),
            FlowEdgeSpec(
                id="projection_to_decision",
                from_layer="projection",
                to_layer="decision",
                kind=FlowEdgeKind.FEEDBACK_OBSERVATION,
                required=True,
            ),
        ),
        state_tokens=(
            StateTokenSpec(
                id="decision.proposed",
                layer="decision",
                canonical="PROPOSED",
                aliases=("DecisionStatusProposed",),
            ),
            StateTokenSpec(
                id="decision.accepted",
                layer="decision",
                canonical="ACCEPTED",
                aliases=("DecisionStatusAccepted",),
            ),
        ),
        transitions=(
            TransitionSpec(
                id="decision.proposed_to_accepted",
                layer="decision",
                from_state="decision.proposed",
                to_state="decision.accepted",
                requires_trace=True,
                requires_governance_event="decision.transitioned",
            ),
        ),
        artifact_types=(
            ArtifactTypeSpec(
                id="api_endpoint",
                tier=ArtifactTier.FUNCTION,
                source_layers=("flow", "projection"),
                kernel_element_pattern="@ActiveStructure",
            ),
        ),
        trace_links=(
            TraceLinkSpec(
                id="decision_informed_by_projection",
                source_type="decision_record",
                target_type="surface_artifact",
                relation=TraceRelation.INFORMED_BY,
                required=True,
            ),
        ),
        governance_events=(
            GovernanceEventSpec(
                name="decision.transitioned",
                must_include=("trace_id", "lineage_id", "actor"),
                retention_policy=GovernanceRetentionPolicy.IMMUTABLE,
            ),
        ),
        loop_contracts=(
            LoopContractSpec(
                id="continuous_refinement",
                path=(
                    "projection",
                    "decision",
                    "kernel",
                    "flow",
                    "projection",
                ),
                enforce_trace=True,
                enforce_event_chain=True,
            ),
        ),
        infra_assets=(
            InfraAssetSpec(
                id="orders-api-gateway-prod",
                asset_type=InfraAssetType.API_GATEWAY,
                owner="platform-network",
                environment=InfraEnvironment.PROD,
                criticality=InfraCriticality.TIER1,
                exposure_refs=(
                    "url:https://api.company.com/orders",
                    "file:infra/k8s/orders-gateway.yaml",
                ),
            ),
        ),
        service_ops_events=(
            ServiceOpsEventSpec(
                name="incident_opened",
                severity=ServiceOpsSeverity.HIGH,
                must_include=("trace_id", "lineage_id", "service_id", "incident_id"),
                feeds_back_to=FeedbackLayer.DECISION,
            ),
        ),
        evidence_bindings=(
            EvidenceBindingSpec(
                id="surface_artifact_to_deployment",
                source_type="surface_artifact",
                binds_to=EvidenceBindingTarget.DEPLOYMENT_RECORD,
                required_fields=("service_id", "deployment_id", "environment"),
            ),
        ),
    )


def _sample_legacy_profile() -> KernelProfile:
    return KernelProfile(
        name="Legacy Profile",
        version="1.0.0",
        kernel_version="2.5.0",
        elements=(),
        relations=(),
        metadata=ProfileMetadata(
            standard="Legacy",
            organization="EA",
            extra={"namespace": "ea_sys", "domain": "legacy_core"},
        ),
        state_transitions=(
            ProfileStateTransition(from_state="draft", to_state="approved"),
        ),
        artifact_types=(
            ProfileArtifactType(
                name="api_endpoint",
                tier="function",
                kernel_element_pattern="@ActiveStructure",
            ),
        ),
        layer_stack=LayerStack(
            layers=(
                LayerDefinition(
                    name="Decision",
                    order=10,
                    responsibility="Decision layer",
                ),
                LayerDefinition(
                    name="Kernel",
                    order=20,
                    depends_on=("Decision",),
                    responsibility="Kernel layer",
                ),
            ),
            definition_flow="Decision -> Kernel",
            runtime_flow="Kernel -> Decision",
            feedback_flow="Decision -> Kernel -> Decision",
        ),
    )


def test_v2_types_define_all_12_entities():
    spec = _sample_type_system()

    assert isinstance(spec.profile, ProfileSpec)
    assert isinstance(spec.layers[0], LayerSpec)
    assert isinstance(spec.flow_edges[0], FlowEdgeSpec)
    assert isinstance(spec.state_tokens[0], StateTokenSpec)
    assert isinstance(spec.transitions[0], TransitionSpec)
    assert isinstance(spec.artifact_types[0], ArtifactTypeSpec)
    assert isinstance(spec.trace_links[0], TraceLinkSpec)
    assert isinstance(spec.governance_events[0], GovernanceEventSpec)
    assert isinstance(spec.loop_contracts[0], LoopContractSpec)
    assert isinstance(spec.infra_assets[0], InfraAssetSpec)
    assert isinstance(spec.service_ops_events[0], ServiceOpsEventSpec)
    assert isinstance(spec.evidence_bindings[0], EvidenceBindingSpec)


def test_v2_types_enforce_required_fields_and_enums():
    with pytest.raises(TypeError):
        LayerSpec(  # type: ignore[arg-type]
            id="infra",
            order=0,
            role="runtime_substrate",
            responsibility="Runtime substrate",
        )

    with pytest.raises(ValueError):
        ProfileSpec(
            id="ea-m2-v2",
            version="2.0.0",
            kernel_version="2.5.0",
            namespace="ea_sys",
            domain="",
        )

    with pytest.raises(ValueError):
        ServiceOpsEventSpec(
            name="critical_incident",
            severity=ServiceOpsSeverity.CRITICAL,
            must_include=("trace_id", "lineage_id", "service_id"),
            feeds_back_to=FeedbackLayer.DECISION,
        )

    with pytest.raises(ValueError):
        InfraAssetSpec(
            id="api-gw-prod",
            asset_type=InfraAssetType.API_GATEWAY,
            owner="platform-network",
            environment=InfraEnvironment.PROD,
            criticality=InfraCriticality.TIER1,
            exposure_refs=("file:infra/k8s/api-gw.yaml",),
        )

    with pytest.raises(ValueError):
        EvidenceBindingSpec(
            id="surface_to_deployment",
            source_type="surface_artifact",
            binds_to=EvidenceBindingTarget.DEPLOYMENT_RECORD,
            required_fields=("service_id", "deployment_id", "dashboard_url"),
        )


def test_v2_serialization_round_trip_dict_json():
    original = _sample_type_system()

    as_dict = type_system_to_dict(original)
    restored_from_dict = dict_to_type_system(as_dict)
    assert restored_from_dict == original

    as_json = type_system_to_json(original)
    restored_from_json = json_to_type_system(as_json)
    assert restored_from_json == original


def test_v2_legacy_adapter_round_trip():
    legacy = _sample_legacy_profile()

    as_v2 = legacy_profile_to_type_system(legacy)
    assert as_v2.profile.namespace == "ea_sys"
    assert len(as_v2.layers) == 2
    assert len(as_v2.transitions) == 1
    assert len(as_v2.artifact_types) == 1

    restored = type_system_to_legacy_profile(as_v2, name="legacy-roundtrip")
    assert restored.name == "legacy-roundtrip"
    assert restored.version == legacy.version
    assert restored.kernel_version == legacy.kernel_version
    assert restored.state_transitions[0].from_state == "DRAFT"
    assert restored.state_transitions[0].to_state == "APPROVED"
    assert restored.artifact_types[0].name == "api_endpoint"
