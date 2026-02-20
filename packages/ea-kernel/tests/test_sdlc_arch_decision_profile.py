"""Tests for SDLC architecture decision profile metadata."""

from ea_kernel.profiles.ea_sys import layer_path
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


def test_sdlc_arch_decision_profile_defines_required_elements_and_transitions() -> None:
    profile = load_profile(profile_path("arch-decision"), KERNEL_SPEC)

    element_names = {element.name for element in profile.elements}
    assert {"ArchDecisionRecord", "TechRadarEntry", "DesignReviewItem"} <= element_names
    assert _transition_edges(profile) == {
        ("PROPOSED", "REVIEW"),
        ("REVIEW", "ACCEPTED"),
        ("ACCEPTED", "SUPERSEDED"),
        ("SUPERSEDED", "DEPRECATED"),
    }


def test_sdlc_arch_decision_profile_adds_review_stage_vs_governance_decision() -> None:
    sdlc_profile = load_profile(profile_path("arch-decision"), KERNEL_SPEC)
    governance_profile = load_profile(layer_path("decision"), KERNEL_SPEC)

    sdlc_edges = _transition_edges(sdlc_profile)
    governance_edges = _transition_edges(governance_profile)

    assert ("PROPOSED", "REVIEW") in sdlc_edges
    assert ("PROPOSED", "REVIEW") not in governance_edges
    assert ("PROPOSED", "ACCEPTED") not in sdlc_edges
    assert ("PROPOSED", "ACCEPTED") in governance_edges


def test_sdlc_and_governance_decision_profiles_pass_same_m2_validator() -> None:
    sdlc_profile = load_profile(profile_path("arch-decision"), KERNEL_SPEC)
    governance_profile = load_profile(layer_path("decision"), KERNEL_SPEC)

    sdlc_result = validate_profile(sdlc_profile)
    governance_result = validate_profile(governance_profile)

    assert sdlc_result.passed is True, sdlc_result.errors
    assert governance_result.passed is True, governance_result.errors
