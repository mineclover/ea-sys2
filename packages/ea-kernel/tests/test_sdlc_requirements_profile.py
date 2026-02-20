"""Tests for SDLC requirements profile metadata."""

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


def _transition_states(profile: KernelProfile) -> set[str]:
    states: set[str] = set()
    for source, target in _transition_edges(profile):
        states.add(source)
        states.add(target)
    return states


def test_sdlc_requirements_profile_defines_required_elements_and_transitions() -> None:
    profile = load_profile(profile_path("requirements"), KERNEL_SPEC)

    element_names = {element.name for element in profile.elements}
    assert {
        "UserStory",
        "AcceptanceCriteria",
        "Epic",
        "TechnicalDebt",
        "BugReport",
    } <= element_names
    assert _transition_edges(profile) == {
        ("BACKLOG", "GROOMED"),
        ("GROOMED", "SPRINT"),
        ("SPRINT", "IN_PROGRESS"),
        ("IN_PROGRESS", "REVIEW"),
        ("REVIEW", "DONE"),
        ("DONE", "CLOSED"),
    }


def test_sdlc_requirements_profile_differs_from_governance_needs_state_model() -> None:
    sdlc_profile = load_profile(profile_path("requirements"), KERNEL_SPEC)
    governance_profile = load_profile(layer_path("needs"), KERNEL_SPEC)

    sdlc_states = _transition_states(sdlc_profile)
    governance_states = _transition_states(governance_profile)

    assert len(sdlc_states) == 7
    assert len(governance_states) == 5
    assert _transition_edges(sdlc_profile) != _transition_edges(governance_profile)


def test_sdlc_and_governance_needs_profiles_pass_same_m2_validator() -> None:
    sdlc_profile = load_profile(profile_path("requirements"), KERNEL_SPEC)
    governance_profile = load_profile(layer_path("needs"), KERNEL_SPEC)

    sdlc_result = validate_profile(sdlc_profile)
    governance_result = validate_profile(governance_profile)

    assert sdlc_result.passed is True, sdlc_result.errors
    assert governance_result.passed is True, governance_result.errors
