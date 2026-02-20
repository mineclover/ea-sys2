"""Tests for SDLC Projection — profile-driven surface generation."""

from __future__ import annotations

from ea_kernel.profiles.sdlc import profile_path as sdlc_profile_path
from ea_profile.loader import load_profile
from sdlc_domain.sdlc_projection import (
    project_governance_surface,
    project_sdlc_surface,
)


def test_sdlc_projection_loads_artifact_types_from_profile() -> None:
    report = project_sdlc_surface()
    summary = report.surface_summary

    projection_profile = load_profile(sdlc_profile_path("projection"))
    declared_types = {
        artifact_type.name for artifact_type in projection_profile.artifact_types
    }
    surfaced_types = set(summary["by_type"])

    assert surfaced_types
    assert surfaced_types <= declared_types
    assert "repository" in surfaced_types
    assert "pull_request" in surfaced_types
    assert "ci_pipeline" in surfaced_types


def test_sdlc_projection_generates_l0_to_l3_surfaces() -> None:
    report = project_sdlc_surface(levels=("l0", "l1", "l2", "l3"))

    assert tuple(level.level for level in report.levels) == ("L0", "L1", "L2", "L3")
    for level in report.levels:
        assert level.node_count > 0
        assert level.edge_count >= 0
        assert level.surface_summary["total_artifacts"] > 0


def test_sdlc_surface_summary_aggregates_by_tier_and_type() -> None:
    report = project_sdlc_surface()
    summary = report.surface_summary

    assert summary["total_artifacts"] > 0
    assert summary["by_type"]["repository"] >= 1
    assert summary["by_type"]["pull_request"] >= 1
    assert summary["by_tier"]["data"] >= 1
    assert summary["by_tier"]["decision"] >= 1


def test_governance_and_sdlc_projection_use_same_engine_but_emit_different_types() -> None:
    sdlc_report = project_sdlc_surface()
    governance_report = project_governance_surface()

    sdlc_types = set(sdlc_report.surface_summary["by_type"])
    governance_types = set(governance_report.surface_summary["by_type"])

    assert sdlc_types != governance_types
    assert "repository" in sdlc_types
    assert "pull_request" in sdlc_types
    assert "configuration" in governance_types
    assert "repository" not in governance_types
