"""SDLC Projection — profile-driven surface artifact generation.

This module instantiates the shared ``ea_projection`` engine for SDLC and
governance domains to verify domain-agnostic projection behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ea_kernel.profiles.ea_sys import layer_path as ea_sys_layer_path
from ea_kernel.profiles.sdlc import profile_path as sdlc_profile_path
from ea_profile.loader import load_profile
from ea_profile.types import KernelProfile, ProfileElement
from ea_projection.artifacts import (
    SurfaceArtifact,
    extract_artifacts,
    extraction_rules_from_profile,
    summarize_artifacts,
    summary_to_dict,
)
from ea_projection.depth import DepthLevelRegistry
from ea_projection.filter import apply_projection_filters
from ea_projection.tier import classify_element_tier, resolve_tier_definitions

_PROJECTION_RELATIONS = frozenset({
    "contains",
    "depends_on",
    "next",
    "triggers",
    "constrains",
    "produces",
    "consumes",
    "coordinates",
    "registers",
    "available_in",
})


def _normalize_relation_name(relation: str) -> str:
    token = str(relation).strip().lower()
    if token in _PROJECTION_RELATIONS:
        return token
    return "depends_on"


def _element_node(element: ProfileElement) -> dict[str, Any]:
    return {
        "name": element.name,
        "layer": element.layer,
        "category": element.category,
        "kernel_type": element.kernel_type,
        "description": str(element.description),
    }


def _append_edge(
    edges: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    *,
    source: str,
    target: str,
    relation: str,
    priority: int,
    synthetic: bool = False,
) -> None:
    key = (source, target, relation)
    if key in seen:
        return
    seen.add(key)
    payload: dict[str, Any] = {
        "source": source,
        "target": target,
        "relation": relation,
        "priority": priority,
    }
    if synthetic:
        payload["synthetic"] = True
    edges.append(payload)


def _combine_profiles(name: str, profiles: tuple[KernelProfile, ...]) -> KernelProfile:
    if not profiles:
        raise ValueError("At least one profile is required for projection composition.")

    elements: list[ProfileElement] = []
    seen_elements: set[str] = set()
    relations = []
    rules = []
    for profile in profiles:
        for element in profile.elements:
            if element.name in seen_elements:
                continue
            seen_elements.add(element.name)
            elements.append(element)
        relations.extend(profile.relations)
        rules.extend(profile.validity_rules)

    first = profiles[0]
    return KernelProfile(
        name=name,
        version=first.version,
        kernel_version=first.kernel_version,
        elements=tuple(elements),
        relations=tuple(relations),
        validity_rules=tuple(rules),
        metadata=first.metadata,
    )


def _profile_to_topology(profile: KernelProfile) -> dict[str, Any]:
    nodes = [_element_node(element) for element in profile.elements]
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for rule in profile.validity_rules:
        if not rule.valid:
            continue
        relation = _normalize_relation_name(rule.relationship_name)
        source_matches = profile.matching_elements(rule.source_pattern)
        target_matches = profile.matching_elements(rule.target_pattern)
        for source in source_matches:
            for target in target_matches:
                if source.name == target.name:
                    continue
                _append_edge(
                    edges,
                    seen_edges,
                    source=source.name,
                    target=target.name,
                    relation=relation,
                    priority=int(rule.priority),
                )

    by_layer: dict[str, list[ProfileElement]] = {}
    for element in profile.elements:
        by_layer.setdefault(element.layer, []).append(element)

    # Add containment anchors so low-depth levels can retain layer structure.
    for layer_elements in by_layer.values():
        roots = [element for element in layer_elements if element.category == "Composite"]
        if not roots:
            continue
        root = roots[0]
        for element in layer_elements:
            if element.name == root.name:
                continue
            _append_edge(
                edges,
                seen_edges,
                source=root.name,
                target=element.name,
                relation="contains",
                priority=1,
                synthetic=True,
            )

    # Keep passive structures reachable for L3 summaries.
    anchors = [
        element for element in profile.elements
        if element.category in {"Behavior", "Interface", "ActiveStructure"}
    ]
    passive = [
        element for element in profile.elements if element.category == "PassiveStructure"
    ]
    if anchors:
        anchor_names = [anchor.name for anchor in anchors]
        for index, element in enumerate(passive):
            source = anchor_names[index % len(anchor_names)]
            _append_edge(
                edges,
                seen_edges,
                source=source,
                target=element.name,
                relation="depends_on",
                priority=1,
                synthetic=True,
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def _classify_tiers(
    nodes: list[dict[str, Any]],
    tier_definitions: dict[str, dict[str, Any]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in nodes:
        name = str(node.get("name", ""))
        category = str(node.get("category", ""))
        if not name:
            continue
        tier = classify_element_tier(name, category, tier_definitions)
        if tier is None:
            continue
        result[name] = tier
    return result


@dataclass(frozen=True)
class SurfaceLevelProjection:
    """Projection result for one depth level."""

    level: str
    lens: str
    node_count: int
    edge_count: int
    artifacts: tuple[SurfaceArtifact, ...] = ()
    surface_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SurfaceProjectionReport:
    """Domain projection report with per-level and aggregate summaries."""

    source_profile: str
    projection_profile: str
    levels: tuple[SurfaceLevelProjection, ...] = ()
    artifacts: tuple[SurfaceArtifact, ...] = ()
    surface_summary: dict[str, Any] = field(default_factory=dict)


def _project_levels(
    *,
    source_profile: KernelProfile,
    projection_profile_path: Path,
    level_keys: tuple[str, ...],
) -> SurfaceProjectionReport:
    depth_registry = DepthLevelRegistry.from_hardcoded()
    tier_definitions = resolve_tier_definitions(None)
    extraction_rules = extraction_rules_from_profile(projection_profile_path)
    topology = _profile_to_topology(source_profile)

    level_results: list[SurfaceLevelProjection] = []
    unique_artifacts: dict[str, SurfaceArtifact] = {}

    for level_key in level_keys:
        spec = depth_registry.get(level_key)
        if spec is None:
            raise ValueError(f"Unknown projection level: {level_key}")

        filtered = apply_projection_filters(
            topology=topology,
            allowed_relations=tuple(spec.allowed_relations),
            allowed_categories=tuple(spec.allowed_categories),
            max_edges=spec.max_edges,
            preserve_nodes=set(),
            tier=None,
            tier_definitions=tier_definitions,
        )
        nodes = list(filtered.get("nodes", []))
        tier_classifications = _classify_tiers(nodes, tier_definitions)
        artifacts = extract_artifacts(
            nodes,
            tier_classifications,
            rules=extraction_rules,
            profile_name=source_profile.name,
        )
        for artifact in artifacts:
            unique_artifacts.setdefault(artifact.artifact_id, artifact)

        level_summary = summarize_artifacts(artifacts)
        level_results.append(
            SurfaceLevelProjection(
                level=spec.key.upper(),
                lens=spec.lens,
                node_count=int(filtered.get("node_count", 0)),
                edge_count=int(filtered.get("edge_count", 0)),
                artifacts=artifacts,
                surface_summary=summary_to_dict(level_summary),
            )
        )

    artifacts = tuple(unique_artifacts.values())
    surface_summary = summary_to_dict(summarize_artifacts(artifacts))
    return SurfaceProjectionReport(
        source_profile=source_profile.name,
        projection_profile=str(projection_profile_path),
        levels=tuple(level_results),
        artifacts=artifacts,
        surface_summary=surface_summary,
    )


@lru_cache(maxsize=1)
def _sdlc_source_profile() -> KernelProfile:
    domain_model = load_profile(sdlc_profile_path("domain-model"))
    projection_model = load_profile(sdlc_profile_path("projection"))
    return _combine_profiles("SDLC-SurfaceSource", (domain_model, projection_model))


@lru_cache(maxsize=1)
def _governance_source_profile() -> KernelProfile:
    kernel_profile = load_profile(ea_sys_layer_path("kernel"))
    projection_profile = load_profile(ea_sys_layer_path("projection"))
    return _combine_profiles(
        "Governance-SurfaceSource",
        (kernel_profile, projection_profile),
    )


def project_sdlc_surface(
    *,
    levels: tuple[str, ...] = ("l0", "l1", "l2", "l3"),
) -> SurfaceProjectionReport:
    """Project SDLC surfaces from composed SDLC source models."""
    return _project_levels(
        source_profile=_sdlc_source_profile(),
        projection_profile_path=sdlc_profile_path("projection"),
        level_keys=levels,
    )


def project_governance_surface(
    *,
    levels: tuple[str, ...] = ("l0", "l1", "l2", "l3"),
) -> SurfaceProjectionReport:
    """Project governance surfaces using the same shared projection engine."""
    return _project_levels(
        source_profile=_governance_source_profile(),
        projection_profile_path=ea_sys_layer_path("projection"),
        level_keys=levels,
    )
