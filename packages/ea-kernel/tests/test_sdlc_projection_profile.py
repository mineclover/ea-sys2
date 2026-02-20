"""Tests for SDLC projection profile metadata."""

from ea_kernel.profiles.ea_sys import layer_path
from ea_kernel.profiles.sdlc import profile_path
from ea_kernel.spec import KERNEL_SPEC
from ea_profile.loader import load_profile
from ea_profile.profile_validator import validate_profile
from ea_profile.types import KernelProfile


def _artifact_tiers(profile: KernelProfile) -> dict[str, str]:
    return {artifact_type.name: artifact_type.tier for artifact_type in profile.artifact_types}


def test_sdlc_projection_profile_defines_required_artifact_types_and_tiers() -> None:
    profile = load_profile(profile_path("projection"), KERNEL_SPEC)

    assert _artifact_tiers(profile) == {
        "repository": "data",
        "pull_request": "decision",
        "ci_pipeline": "function",
        "deployment": "function",
        "api_doc": "evidence",
        "test_report": "evidence",
        "monitoring_dashboard": "ui",
    }


def test_sdlc_projection_artifact_set_is_disjoint_from_governance_projection() -> None:
    sdlc_profile = load_profile(profile_path("projection"), KERNEL_SPEC)
    governance_profile = load_profile(layer_path("projection"), KERNEL_SPEC)

    sdlc_artifacts = {artifact_type.name for artifact_type in sdlc_profile.artifact_types}
    governance_artifacts = {
        artifact_type.name for artifact_type in governance_profile.artifact_types
    }

    assert sdlc_artifacts == set(_artifact_tiers(sdlc_profile))
    assert governance_artifacts
    assert sdlc_artifacts.isdisjoint(governance_artifacts)


def test_sdlc_projection_profile_passes_m2_validator() -> None:
    profile = load_profile(profile_path("projection"), KERNEL_SPEC)

    validation_result = validate_profile(profile)
    assert validation_result.passed is True, validation_result.errors
