"""Surface Artifact Definitions — identifiable externally-visible outputs.

Projection exposes kernel/flow elements as concrete surface-level artifacts:
API endpoints, pages, tools, identifiers, contracts, etc.

This module provides:
- ArtifactType: classification of surface artifact kinds
- SurfaceArtifact: frozen dataclass representing one identifiable surface output
- ArtifactExtractionRule: tier→artifact_type mapping rules
- extract_artifacts(): extract surface artifacts from projection nodes
- DEFAULT_EXTRACTION_RULES: built-in tier→artifact mappings

References:
- ea_projection/tier/resolver.py: tier classification
- ea_projection/surface.py: surface relation profile
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Artifact Types
# ═══════════════════════════════════════════════════════════════════════════════

class ArtifactType(StrEnum):
    """Classification of surface-level artifact kinds."""
    API_ENDPOINT = "api_endpoint"
    PAGE = "page"
    TOOL = "tool"
    IDENTIFIER = "identifier"
    CONTRACT = "contract"
    EVENT = "event"
    DATA_SCHEMA = "data_schema"
    CONFIGURATION = "configuration"


# ═══════════════════════════════════════════════════════════════════════════════
# Surface Artifact
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SurfaceArtifact:
    """An identifiable, externally-visible surface output.

    Represents a concrete element surfaced through projection —
    something that Decision layer can observe and reason about.
    """
    artifact_id: str
    artifact_type: ArtifactType
    name: str
    source_element: str  # Name of the projection node that produced this
    tier: str  # Tier from which this artifact was extracted
    description: str = ""
    qualified_name: str = ""  # Fully qualified identifier
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def qualified_id(self) -> str:
        """URI-style qualified identifier."""
        if self.qualified_name:
            return self.qualified_name
        return f"{self.tier}:{self.artifact_type.value}:{self.name}"


# ═══════════════════════════════════════════════════════════════════════════════
# Extraction Rules — Tier→Artifact mapping
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ArtifactExtractionRule:
    """Rule for extracting a surface artifact from a projection node.

    When a node's tier and category match, produce an artifact of the given type.
    """
    tier: str
    categories: tuple[str, ...]  # Profile categories that match
    artifact_type: ArtifactType
    name_patterns: tuple[str, ...] = ()  # If non-empty, name must contain one
    name_exclude_patterns: tuple[str, ...] = ()  # Exclude names containing these


DEFAULT_EXTRACTION_RULES: tuple[ArtifactExtractionRule, ...] = (
    # UI tier → pages and tools
    ArtifactExtractionRule(
        tier="ui",
        categories=("Page", "Interface"),
        artifact_type=ArtifactType.PAGE,
    ),
    ArtifactExtractionRule(
        tier="ui",
        categories=("Context",),
        artifact_type=ArtifactType.TOOL,
    ),
    # Function tier → API endpoints and tools
    ArtifactExtractionRule(
        tier="function",
        categories=("ActiveStructure", "Behavior", "Executable"),
        artifact_type=ArtifactType.API_ENDPOINT,
    ),
    ArtifactExtractionRule(
        tier="function",
        categories=("Governance",),
        artifact_type=ArtifactType.TOOL,
    ),
    # Data tier → data schemas and identifiers
    ArtifactExtractionRule(
        tier="data",
        categories=("PassiveStructure", "Composite"),
        artifact_type=ArtifactType.DATA_SCHEMA,
    ),
    # Decision tier → contracts and events
    ArtifactExtractionRule(
        tier="decision",
        categories=("Assessment", "Goal"),
        artifact_type=ArtifactType.CONTRACT,
    ),
    ArtifactExtractionRule(
        tier="decision",
        categories=("Event",),
        artifact_type=ArtifactType.EVENT,
    ),
    # Evidence tier → identifiers
    ArtifactExtractionRule(
        tier="evidence",
        categories=("PassiveStructure",),
        artifact_type=ArtifactType.IDENTIFIER,
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Extraction Engine
# ═══════════════════════════════════════════════════════════════════════════════

def _matches_rule(
    name: str,
    category: str,
    tier: str,
    rule: ArtifactExtractionRule,
) -> bool:
    """Check if a node matches an extraction rule."""
    if rule.tier != tier:
        return False
    if category not in rule.categories:
        return False

    name_lower = name.lower()
    if rule.name_exclude_patterns:
        if any(p.lower() in name_lower for p in rule.name_exclude_patterns):
            return False
    if rule.name_patterns:
        if not any(p.lower() in name_lower for p in rule.name_patterns):
            return False

    return True


def extract_artifacts(
    nodes: list[dict[str, Any]],
    tier_classifications: dict[str, str],
    *,
    rules: tuple[ArtifactExtractionRule, ...] = DEFAULT_EXTRACTION_RULES,
    profile_name: str = "",
) -> tuple[SurfaceArtifact, ...]:
    """Extract surface artifacts from projection nodes.

    Args:
        nodes: Projection node dicts (must have 'name', 'category').
        tier_classifications: {node_name: tier} mapping.
        rules: Extraction rules to apply.
        profile_name: Optional profile name for qualified identifiers.

    Returns:
        Tuple of extracted SurfaceArtifact instances.
    """
    artifacts: list[SurfaceArtifact] = []
    seen_ids: set[str] = set()

    for node in nodes:
        name = str(node.get("name", ""))
        category = str(node.get("category", ""))
        if not name:
            continue

        tier = tier_classifications.get(name, "")
        if not tier:
            continue

        for rule in rules:
            if not _matches_rule(name, category, tier, rule):
                continue

            artifact_id = f"{tier}:{rule.artifact_type.value}:{name}"
            if artifact_id in seen_ids:
                continue
            seen_ids.add(artifact_id)

            qualified = ""
            if profile_name:
                qualified = f"{profile_name}:{artifact_id}"

            description = str(node.get("description", ""))

            artifacts.append(SurfaceArtifact(
                artifact_id=artifact_id,
                artifact_type=rule.artifact_type,
                name=name,
                source_element=name,
                tier=tier,
                description=description,
                qualified_name=qualified,
            ))
            break  # One artifact per node (first matching rule wins)

    return tuple(artifacts)


@dataclass(frozen=True)
class ArtifactSummary:
    """Summary of extracted artifacts by type and tier."""
    total_artifacts: int = 0
    by_type: tuple[tuple[str, int], ...] = ()
    by_tier: tuple[tuple[str, int], ...] = ()


def summarize_artifacts(
    artifacts: tuple[SurfaceArtifact, ...],
) -> ArtifactSummary:
    """Summarize extracted artifacts by type and tier."""
    type_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}

    for a in artifacts:
        type_counts[a.artifact_type.value] = type_counts.get(a.artifact_type.value, 0) + 1
        tier_counts[a.tier] = tier_counts.get(a.tier, 0) + 1

    return ArtifactSummary(
        total_artifacts=len(artifacts),
        by_type=tuple(sorted(type_counts.items(), key=lambda x: -x[1])),
        by_tier=tuple(sorted(tier_counts.items(), key=lambda x: -x[1])),
    )
