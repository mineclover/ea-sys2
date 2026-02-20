"""Tests for ea_profile.profile_validator."""

from ea_profile.builder import ProfileBuilder
from ea_profile.profile_validator import (
    ProfileValidationResult,
    validate_artifact_types,
    validate_layer_stack,
    validate_process_units,
    validate_profile,
    validate_state_transitions,
)


def _base_builder() -> ProfileBuilder:
    return (
        ProfileBuilder("Validator", version="1.0", kernel_version="2.0")
        .element("DraftState", layer="Domain", category="State", kernel_type="state")
        .element("ApprovedState", layer="Domain", category="State", kernel_type="state")
        .element("NeedArtifactModel", layer="Domain", category="Artifact", kernel_type="item")
        .relation("uses", kernel_relation="association")
    )


def test_validate_profile_passes_with_consistent_metadata() -> None:
    profile = (
        _base_builder()
        .add_state_transition("DraftState", "ApprovedState")
        .add_artifact_type(
            "need_statement",
            "function",
            kernel_element_pattern="NeedArtifact*",
        )
        .add_process_unit(
            "NeedDiscovery",
            "IDENTIFY",
            input_artifacts=("need_statement",),
            output_artifacts=("need_statement",),
        )
        .set_layer_stack(
            definition_flow="top_down",
            runtime_flow="bottom_up",
            feedback_flow="closed_loop",
        )
        .add_layer_definition("M2", 1)
        .add_layer_definition("M1", 2, depends_on=("M2",))
        .build()
    )

    result = validate_profile(profile)

    assert isinstance(result, ProfileValidationResult)
    assert result.passed is True
    assert result.errors == ()
    assert validate_state_transitions(profile) == ()
    assert validate_artifact_types(profile) == ()
    assert validate_layer_stack(profile) == ()
    assert validate_process_units(profile) == ()


def test_validate_profile_fails_on_layer_dependency_cycle() -> None:
    profile = (
        _base_builder()
        .set_layer_stack(
            definition_flow="top_down",
            runtime_flow="bottom_up",
            feedback_flow="closed_loop",
        )
        .add_layer_definition("Domain", 1, depends_on=("Application",))
        .add_layer_definition("Application", 2, depends_on=("Domain",))
        .build()
    )

    result = validate_profile(profile)

    assert result.passed is False
    assert any("cycle detected" in error for error in result.layer_stack_errors)


def test_validate_profile_fails_on_missing_state_reference() -> None:
    profile = (
        _base_builder()
        .add_state_transition("MissingState", "ApprovedState")
        .build()
    )

    result = validate_profile(profile)

    assert result.passed is False
    assert any("MissingState" in error for error in result.state_transition_errors)


def test_validate_state_transitions_accepts_status_alias_elements() -> None:
    profile = (
        _base_builder()
        .element("NeedStatusDraft", layer="Needs", category="Goal", kernel_type="state")
        .element("NeedStatusExpressed", layer="Needs", category="Goal", kernel_type="state")
        .add_state_transition("DRAFT", "EXPRESSED")
        .build()
    )

    errors = validate_state_transitions(profile)

    assert errors == ()


def test_validate_artifact_types_fails_on_unmatched_pattern() -> None:
    profile = (
        _base_builder()
        .add_artifact_type(
            "need_statement",
            "function",
            kernel_element_pattern="DoesNotExist*",
        )
        .build()
    )

    errors = validate_artifact_types(profile)

    assert len(errors) == 1
    assert "matches no profile elements" in errors[0]


def test_validate_process_units_fails_on_unknown_artifacts() -> None:
    profile = (
        _base_builder()
        .add_artifact_type(
            "need_statement",
            "function",
            kernel_element_pattern="NeedArtifact*",
        )
        .add_process_unit(
            "NeedDiscovery",
            "IDENTIFY",
            input_artifacts=("missing_input",),
            output_artifacts=("missing_output",),
        )
        .build()
    )

    errors = validate_process_units(profile)

    assert len(errors) == 2
    assert any("missing_input" in error for error in errors)
    assert any("missing_output" in error for error in errors)
