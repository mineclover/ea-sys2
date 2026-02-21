"""Tests for ea_profile.v2 canonical type system."""

import json
import logging
from pathlib import Path

import pytest
from ea_profile.types import (
    KernelProfile,
    LayerDefinition,
    LayerStack,
    ProfileArtifactType,
    ProfileMetadata,
    ProfileStateTransition,
)
from ea_profile.v2.adapters import (
    flow_edges_from_legacy_flows,
    legacy_profile_to_type_system,
    type_system_to_legacy_profile,
)
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
from ea_profile.v2.validator import TypeSystemValidationError

_GOLDEN_FLOW_EDGES = (
    Path(__file__).parent / "golden" / "legacy_layer_stack_flow_edges.json"
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
                id="needs",
                order=20,
                role=LayerRole.CAUSAL_MEMORY,
                responsibility="Needs causal memory",
            ),
            LayerSpec(
                id="kernel",
                order=30,
                role=LayerRole.BUSINESS_SKELETON,
                responsibility="Kernel structure",
            ),
            LayerSpec(
                id="flow",
                order=40,
                role=LayerRole.DATA_MODELING_MEMORY,
                responsibility="Flow execution memory",
            ),
            LayerSpec(
                id="projection",
                order=50,
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
                id="infra_to_flow",
                from_layer="infra",
                to_layer="flow",
                kind=FlowEdgeKind.RUNTIME_CAPABILITY_BINDING,
                required=True,
            ),
            FlowEdgeSpec(
                id="decision_to_needs",
                from_layer="decision",
                to_layer="needs",
                kind=FlowEdgeKind.CAUSAL_HANDOFF,
                required=True,
            ),
            FlowEdgeSpec(
                id="needs_to_kernel",
                from_layer="needs",
                to_layer="kernel",
                kind=FlowEdgeKind.STRUCTURE_REQUEST,
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
                    "needs",
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


def test_v2_flow_loop_validation_accepts_required_paths_and_closed_loop() -> None:
    spec = _sample_type_system()
    assert spec.loop_contracts[0].path == (
        "projection",
        "decision",
        "needs",
        "kernel",
        "flow",
        "projection",
    )


def test_v2_flow_loop_validation_rejects_missing_required_path_with_code() -> None:
    base = _sample_type_system()
    missing_decision_to_needs = tuple(
        edge for edge in base.flow_edges if edge.id != "decision_to_needs"
    )

    with pytest.raises(TypeSystemValidationError) as exc_info:
        TypeSystemSpec(
            profile=base.profile,
            layers=base.layers,
            flow_edges=missing_decision_to_needs,
        )

    issues = exc_info.value.issues
    assert "FLOW_REQUIRED_PATH_MISSING" in {issue.code for issue in issues}
    assert any("decision->needs" in issue.message for issue in issues)


def test_v2_flow_loop_validation_rejects_disconnected_loop_path_with_code() -> None:
    base = _sample_type_system()

    with pytest.raises(TypeSystemValidationError) as exc_info:
        TypeSystemSpec(
            profile=base.profile,
            layers=base.layers,
            flow_edges=base.flow_edges,
            loop_contracts=(
                LoopContractSpec(
                    id="disconnected_loop",
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
        )

    issues = exc_info.value.issues
    assert "LOOP_PATH_DISCONNECTED" in {issue.code for issue in issues}
    assert any("decision->kernel" in issue.message for issue in issues)


def test_v2_flow_loop_validation_rejects_invalid_loop_path_with_code() -> None:
    base = _sample_type_system()

    with pytest.raises(TypeSystemValidationError) as exc_info:
        TypeSystemSpec(
            profile=base.profile,
            layers=base.layers,
            flow_edges=base.flow_edges,
            loop_contracts=(
                LoopContractSpec(
                    id="invalid_loop",
                    path=(
                        "projection",
                        "unknown-layer",
                        "projection",
                    ),
                    enforce_trace=True,
                    enforce_event_chain=True,
                ),
            ),
        )

    issues = exc_info.value.issues
    assert "LOOP_PATH_INVALID_LAYER" in {issue.code for issue in issues}
    assert any("unknown-layer" in issue.message for issue in issues)


def test_v2_transition_state_validation_accepts_alias_references() -> None:
    spec = TypeSystemSpec(
        profile=ProfileSpec(
            id="ea-m2-v2",
            version="2.0.0",
            kernel_version="2.5.0",
            namespace="ea_sys",
            domain="governance_core",
        ),
        layers=(
            LayerSpec(
                id="decision",
                order=10,
                role=LayerRole.CAUSAL_MEMORY,
                responsibility="Decision state transitions",
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
                id="decision.transition_alias",
                layer="decision",
                from_state="DecisionStatusProposed",
                to_state="decision.ACCEPTED",
                requires_trace=True,
                requires_governance_event="decision.transitioned",
            ),
        ),
    )

    assert len(spec.transitions) == 1


def test_v2_transition_state_validation_rejects_cross_layer_reference() -> None:
    with pytest.raises(ValueError, match="must reference layer 'decision'"):
        TypeSystemSpec(
            profile=ProfileSpec(
                id="ea-m2-v2",
                version="2.0.0",
                kernel_version="2.5.0",
                namespace="ea_sys",
                domain="governance_core",
            ),
            layers=(
                LayerSpec(
                    id="decision",
                    order=10,
                    role=LayerRole.CAUSAL_MEMORY,
                    responsibility="Decision state transitions",
                ),
                LayerSpec(
                    id="needs",
                    order=20,
                    role=LayerRole.CAUSAL_MEMORY,
                    responsibility="Needs state transitions",
                ),
            ),
            state_tokens=(
                StateTokenSpec(
                    id="decision.proposed",
                    layer="decision",
                    canonical="PROPOSED",
                    aliases=(),
                ),
                StateTokenSpec(
                    id="decision.accepted",
                    layer="decision",
                    canonical="ACCEPTED",
                    aliases=(),
                ),
                StateTokenSpec(
                    id="needs.expressed",
                    layer="needs",
                    canonical="EXPRESSED",
                    aliases=(),
                ),
            ),
            transitions=(
                TransitionSpec(
                    id="decision.invalid_transition",
                    layer="decision",
                    from_state="needs.EXPRESSED",
                    to_state="decision.accepted",
                    requires_trace=True,
                    requires_governance_event="decision.transitioned",
                ),
            ),
        )


def test_v2_trace_evidence_validation_accepts_connected_source_type() -> None:
    spec = TypeSystemSpec(
        profile=ProfileSpec(
            id="ea-m2-v2",
            version="2.0.0",
            kernel_version="2.5.0",
            namespace="ea_sys",
            domain="governance_core",
        ),
        trace_links=(
            TraceLinkSpec(
                id="decision_informed_by_surface",
                source_type="decision_record",
                target_type="surface_artifact",
                relation=TraceRelation.INFORMED_BY,
                required=True,
            ),
        ),
        evidence_bindings=(
            EvidenceBindingSpec(
                id="surface_to_deployment",
                source_type="surface_artifact",
                binds_to=EvidenceBindingTarget.DEPLOYMENT_RECORD,
                required_fields=("service_id", "deployment_id", "environment"),
            ),
        ),
    )

    assert spec.evidence_bindings[0].source_type == "surface_artifact"


def test_v2_trace_evidence_validation_rejects_unlinked_evidence_source_type() -> None:
    with pytest.raises(ValueError, match="source_type references unknown trace node type"):
        TypeSystemSpec(
            profile=ProfileSpec(
                id="ea-m2-v2",
                version="2.0.0",
                kernel_version="2.5.0",
                namespace="ea_sys",
                domain="governance_core",
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
            evidence_bindings=(
                EvidenceBindingSpec(
                    id="kernel_change_to_commit",
                    source_type="kernel_change",
                    binds_to=EvidenceBindingTarget.CODE_COMMIT,
                    required_fields=("repo", "commit_sha", "author"),
                ),
            ),
        )


def test_v2_trace_evidence_validation_enforces_surface_artifact_environment_rule() -> None:
    binding = EvidenceBindingSpec(
        id="surface_to_deployment",
        source_type="surface_artifact",
        binds_to=EvidenceBindingTarget.DEPLOYMENT_RECORD,
        required_fields=("service_id", "deployment_id", "environment"),
    )
    object.__setattr__(binding, "required_fields", ("service_id", "deployment_id", "region"))

    with pytest.raises(ValueError, match="required_fields must include environment"):
        TypeSystemSpec(
            profile=ProfileSpec(
                id="ea-m2-v2",
                version="2.0.0",
                kernel_version="2.5.0",
                namespace="ea_sys",
                domain="governance_core",
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
            evidence_bindings=(binding,),
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

    as_v2 = legacy_profile_to_type_system(legacy, warn_on_deprecated=False)
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


def test_v2_legacy_adapter_emits_deprecation_warning(caplog: pytest.LogCaptureFixture):
    legacy = _sample_legacy_profile()

    with (
        caplog.at_level(logging.WARNING, logger="ea_profile.v2.adapters"),
        pytest.warns(DeprecationWarning, match="Loading legacy KernelProfile"),
    ):
        legacy_profile_to_type_system(legacy)

    assert any(
        "Loading legacy KernelProfile into ea_profile.v2 is deprecated" in record.message
        for record in caplog.records
    )


def test_v2_legacy_flow_migration_matches_golden():
    actual = [
        {
            "id": edge.id,
            "from": edge.from_layer,
            "to": edge.to_layer,
            "kind": edge.kind.value,
            "required": edge.required,
        }
        for edge in flow_edges_from_legacy_flows(
            definition_flow="Infra -> Governance -> Decision -> Needs -> Flow -> Projection",
            runtime_flow="Infra > Kernel > Flow > Projection",
            feedback_flow="Projection, Decision, Needs",
        )
    ]

    expected = json.loads(_GOLDEN_FLOW_EDGES.read_text(encoding="utf-8"))
    assert actual == expected
