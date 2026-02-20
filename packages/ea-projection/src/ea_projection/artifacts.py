"""Surface artifact extraction for projection outputs.

Projection exposes kernel/flow elements as concrete surface-level artifacts:
API endpoints, pages, repositories, pull requests, and other externally-visible
outputs. Artifact declarations are loaded from projection profiles at runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

# ═══════════════════════════════════════════════════════════════════════════════
# Artifact Types (Profile-driven)
# ═══════════════════════════════════════════════════════════════════════════════

def _normalize_artifact_type_name(value: str) -> str:
    return value.strip().lower()


def _normalize_tier_name(value: str) -> str:
    return str(value).strip().lower()


def _projection_artifact_profile_paths() -> tuple[Path, ...]:
    """Return projection profile paths that declare artifact types."""
    paths: list[Path] = []

    try:
        from ea_kernel.profiles.ea_sys import layer_path

        paths.append(layer_path("projection"))
    except Exception:
        pass

    try:
        from ea_kernel.profiles.sdlc import profile_path as sdlc_profile_path

        paths.append(sdlc_profile_path("projection"))
    except Exception:
        pass

    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        token = str(path)
        if token in seen:
            continue
        seen.add(token)
        deduped.append(path)
    return tuple(deduped)


@lru_cache(maxsize=32)
def _profile_artifact_type_entries(
    profile_path: str,
) -> tuple[tuple[str, str, str], ...]:
    """Load normalized artifact type entries from a projection profile path."""
    from ea_projection.profile_bridge import load_projection_profile

    profile = load_projection_profile(Path(profile_path), validate=False)
    if not profile.artifact_types:
        raise RuntimeError(
            f"Projection profile '{profile_path}' has no [[artifact_types]] entries."
        )

    entries: list[tuple[str, str, str]] = []
    seen_names: set[str] = set()
    for artifact_type in profile.artifact_types:
        name = _normalize_artifact_type_name(artifact_type.name)
        tier = _normalize_tier_name(artifact_type.tier)
        pattern = str(artifact_type.kernel_element_pattern).strip()

        if not name:
            raise RuntimeError(
                f"Projection profile '{profile_path}' artifact type name cannot be empty."
            )
        if name in seen_names:
            raise RuntimeError(
                f"Projection profile '{profile_path}' has duplicate artifact type "
                f"declaration: '{name}'."
            )
        seen_names.add(name)
        entries.append((name, tier, pattern))

    return tuple(entries)


@lru_cache(maxsize=1)
def _artifact_type_tier_registry() -> dict[str, str]:
    """Load artifact type declarations from all available projection profiles."""
    profile_paths = _projection_artifact_profile_paths()
    if not profile_paths:
        raise RuntimeError(
            "No projection profiles with artifact type declarations were found."
        )

    registry: dict[str, str] = {}
    for path in profile_paths:
        for name, tier, _pattern in _profile_artifact_type_entries(str(path)):
            existing_tier = registry.get(name)
            if existing_tier is not None and existing_tier != tier:
                raise RuntimeError(
                    "Conflicting artifact type tier declaration for "
                    f"'{name}': '{existing_tier}' vs '{tier}'."
                )
            registry[name] = tier
    return registry


class _ArtifactTypeMeta(type):
    """Enum-like metaclass facade backed by profile-driven registry."""

    def __iter__(cls) -> Iterator[ArtifactType]:
        del cls
        return iter(ArtifactType._registry.values())

    def __len__(cls) -> int:
        del cls
        return len(ArtifactType._registry)

    def __contains__(cls, value: object) -> bool:
        del cls
        if isinstance(value, ArtifactType):
            return str(value) in ArtifactType._registry
        if isinstance(value, str):
            return _normalize_artifact_type_name(value) in ArtifactType._registry
        return False

    def __getattr__(cls, name: str) -> ArtifactType:
        del cls
        token = ArtifactType._registry.get(name.lower())
        if token is not None:
            return token
        raise AttributeError(f"Unknown ArtifactType member: {name}")


class ArtifactType(str, metaclass=_ArtifactTypeMeta):
    """Profile-driven artifact type token."""

    _registry: ClassVar[dict[str, ArtifactType]] = {}

    @property
    def value(self) -> str:
        return str(self)

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(cls._registry.keys())

    @classmethod
    def values(cls) -> tuple[ArtifactType, ...]:
        return tuple(cls._registry.values())

    @classmethod
    def ensure(cls, value: str | ArtifactType) -> ArtifactType:
        token = cls._registry.get(_normalize_artifact_type_name(str(value)))
        if token is not None:
            return token
        allowed = ", ".join(sorted(cls._registry))
        raise ValueError(
            f"Unknown projection artifact type: '{value}'. "
            f"Allowed artifact types: [{allowed}]"
        )

    @classmethod
    def tier_of(cls, value: str | ArtifactType) -> str:
        token = cls.ensure(value)
        return _artifact_type_tier_registry()[token.value]

    def __new__(cls, value: str | ArtifactType) -> ArtifactType:
        return cls.ensure(value)


def _configure_artifact_type_registry() -> None:
    """Initialize enum-like ArtifactType members from profile registry."""
    registry: dict[str, ArtifactType] = {}
    for name in _artifact_type_tier_registry():
        registry[name] = str.__new__(ArtifactType, name)
    ArtifactType._registry = registry


_configure_artifact_type_registry()


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", ArtifactType.ensure(self.artifact_type))

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
    categories: tuple[str, ...]  # Optional category allow-list
    artifact_type: ArtifactType
    kernel_element_pattern: str = ""  # Optional profile pattern (@Category/#Layer/name)
    name_patterns: tuple[str, ...] = ()  # If non-empty, name must contain one
    name_exclude_patterns: tuple[str, ...] = ()  # Exclude names containing these

    def __post_init__(self) -> None:
        object.__setattr__(self, "tier", _normalize_tier_name(self.tier))
        object.__setattr__(self, "artifact_type", ArtifactType.ensure(self.artifact_type))


@lru_cache(maxsize=16)
def extraction_rules_from_profile(
    profile_path: Path,
) -> tuple[ArtifactExtractionRule, ...]:
    """Build extraction rules from profile [[artifact_types]] declarations."""
    rules: list[ArtifactExtractionRule] = []
    for name, tier, pattern in _profile_artifact_type_entries(str(profile_path)):
        categories: tuple[str, ...] = ()
        if pattern.startswith("@") and len(pattern) > 1:
            categories = (pattern[1:],)
        rules.append(
            ArtifactExtractionRule(
                tier=tier,
                categories=categories,
                artifact_type=ArtifactType.ensure(name),
                kernel_element_pattern=pattern,
            )
        )
    return tuple(rules)


DEFAULT_EXTRACTION_RULES: tuple[ArtifactExtractionRule, ...] = (
    # UI tier → pages and tools
    ArtifactExtractionRule(
        tier="ui",
        categories=("Page", "Interface"),
        artifact_type=ArtifactType.ensure("page"),
    ),
    ArtifactExtractionRule(
        tier="ui",
        categories=("Context",),
        artifact_type=ArtifactType.ensure("tool"),
    ),
    # Function tier → API endpoints and tools
    ArtifactExtractionRule(
        tier="function",
        categories=("ActiveStructure", "Behavior", "Executable"),
        artifact_type=ArtifactType.ensure("api_endpoint"),
    ),
    ArtifactExtractionRule(
        tier="function",
        categories=("Governance",),
        artifact_type=ArtifactType.ensure("tool"),
    ),
    # Data tier → data schemas and identifiers
    ArtifactExtractionRule(
        tier="data",
        categories=("PassiveStructure", "Composite"),
        artifact_type=ArtifactType.ensure("data_schema"),
    ),
    # Decision tier → contracts and events
    ArtifactExtractionRule(
        tier="decision",
        categories=("Assessment", "Goal"),
        artifact_type=ArtifactType.ensure("contract"),
    ),
    ArtifactExtractionRule(
        tier="decision",
        categories=("Event",),
        artifact_type=ArtifactType.ensure("event"),
    ),
    # Evidence tier → identifiers
    ArtifactExtractionRule(
        tier="evidence",
        categories=("PassiveStructure",),
        artifact_type=ArtifactType.ensure("identifier"),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Extraction Engine
# ═══════════════════════════════════════════════════════════════════════════════

def _matches_rule(
    node: dict[str, Any],
    tier: str,
    rule: ArtifactExtractionRule,
) -> bool:
    """Check if a node matches an extraction rule."""
    if rule.tier != _normalize_tier_name(tier):
        return False

    category = str(node.get("category", ""))
    if rule.categories and category not in rule.categories:
        return False
    if rule.kernel_element_pattern and not _matches_kernel_element_pattern(
        node,
        rule.kernel_element_pattern,
    ):
        return False

    name = str(node.get("name", ""))
    name_lower = name.lower()
    if rule.name_exclude_patterns and any(p.lower() in name_lower for p in rule.name_exclude_patterns):
        return False
    if rule.name_patterns:
        return any(p.lower() in name_lower for p in rule.name_patterns)
    return True


def _matches_kernel_element_pattern(node: dict[str, Any], pattern: str) -> bool:
    """Match node attributes against a profile kernel_element_pattern."""
    token = str(pattern).strip()
    if token == "" or token == "*":
        return True

    name = str(node.get("name", ""))
    category = str(node.get("category", ""))
    layer = str(node.get("layer", ""))
    kernel_type = str(node.get("kernel_type", ""))

    if token.startswith("@"):
        return category == token[1:]
    if token.startswith("#"):
        return layer == token[1:]
    if any(char in token for char in "*?["):
        return fnmatchcase(name, token) or fnmatchcase(kernel_type, token)
    return name == token or kernel_type == token


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
        if not name:
            continue

        tier = tier_classifications.get(name, "")
        if not tier:
            continue

        for rule in rules:
            if not _matches_rule(node, tier, rule):
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


def summary_to_dict(summary: ArtifactSummary) -> dict[str, Any]:
    """Convert ArtifactSummary into an API-friendly dict payload."""
    return {
        "total_artifacts": summary.total_artifacts,
        "by_type": dict(summary.by_type),
        "by_tier": dict(summary.by_tier),
    }
