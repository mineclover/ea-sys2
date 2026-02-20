"""Tests for SDLC pipeline profile metadata."""

from ea_kernel.profiles.sdlc import profile_path
from ea_kernel.spec import KERNEL_SPEC
from ea_profile.loader import load_profile
from ea_profile.profile_validator import validate_profile
from ea_profile.types import KernelProfile


def _transition_edges(profile: KernelProfile) -> set[tuple[str, str]]:
    return {
        (transition.from_state.strip().upper(), transition.to_state.strip().upper())
        for transition in profile.state_transitions
    }


def _allow_edges(profile: KernelProfile, relation: str) -> set[tuple[str, str]]:
    return {
        (rule.source_pattern, rule.target_pattern)
        for rule in profile.validity_rules
        if rule.relationship_name == relation and rule.valid is True and rule.priority > 1
    }


def test_sdlc_pipeline_profile_defines_required_elements_and_transitions() -> None:
    profile = load_profile(profile_path("pipeline"), KERNEL_SPEC)

    element_names = {element.name for element in profile.elements}
    assert {
        "BuildStep",
        "TestSuite",
        "DeployTarget",
        "RollbackProcedure",
        "ApprovalGate",
    } <= element_names

    assert _transition_edges(profile) == {
        ("QUEUED", "BUILDING"),
        ("BUILDING", "TESTING"),
        ("TESTING", "STAGING"),
        ("STAGING", "PRODUCTION"),
        ("PRODUCTION", "ROLLED_BACK"),
    }


def test_sdlc_pipeline_profile_defines_build_test_stage_deploy_next_rules() -> None:
    profile = load_profile(profile_path("pipeline"), KERNEL_SPEC)

    next_edges = _allow_edges(profile, "next")
    assert ("BuildStep", "TestSuite") in next_edges
    assert ("TestSuite", "StageStep") in next_edges
    assert ("StageStep", "DeployTarget") in next_edges


def test_sdlc_pipeline_profile_passes_m2_validator() -> None:
    profile = load_profile(profile_path("pipeline"), KERNEL_SPEC)

    validation_result = validate_profile(profile)
    assert validation_result.passed is True, validation_result.errors
