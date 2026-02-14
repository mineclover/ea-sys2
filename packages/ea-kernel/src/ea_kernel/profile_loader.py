"""TOML → KernelProfile loader.

Provides a declarative path to profile creation, built on ProfileBuilder.
Reuses the TOML parsing pattern established by spec_loader.py.

TOML format:
    [profile]
    name = "MyFramework"
    version = "1.0"
    kernel_version = "2.5.0"
    id_prefix = "mf"
    standard = "MyFramework Spec"
    organization = "ACME Corp"

    [categories]
    ActiveStructure = "structure"
    Behavior = "step"

    [[elements]]
    name = "Widget"
    layer = "Core"
    category = "ActiveStructure"

    [[relations]]
    name = "uses"
    kernel_relation = "association"

    [[rules]]
    source = "@ActiveStructure"
    target = "@Behavior"
    relation = "uses"
    priority = 40
"""

from __future__ import annotations

try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path

from ea_kernel.profile_types import KernelProfile
from ea_kernel.types import KernelConditionType, KernelRuleCondition, KernelSchema
from ea_kernel.profile_builder import ProfileBuilder

_CONDITION_MAP: dict[str, KernelConditionType] = {
    "LAYER_ORDER": KernelConditionType.LAYER_ORDER,
    "SAME_LAYER": KernelConditionType.SAME_LAYER,
    "SAME_BRANCH": KernelConditionType.SAME_ENTITY_BRANCH,
    "ANCESTOR_OF": KernelConditionType.ANCESTOR_OF,
    "SAME_CATEGORY": KernelConditionType.SAME_CATEGORY,
}


class ProfileLoadError(Exception):
    """Raised when a profile TOML file cannot be parsed."""


def load_profile(
    path: Path,
    kernel: KernelSchema | None = None,
) -> KernelProfile:
    """Load a profile from a TOML file."""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ProfileLoadError(f"Profile file not found: {path}")
    return load_profile_from_content(content, kernel)


def load_profile_from_content(
    content: str,
    kernel: KernelSchema | None = None,
) -> KernelProfile:
    """Load a profile from a TOML string."""
    try:
        doc = tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise ProfileLoadError(f"Invalid TOML: {e}")

    profile_section = doc.get("profile", {})
    name = profile_section.get("name")
    version = profile_section.get("version")
    kernel_version = profile_section.get("kernel_version")

    if not name:
        raise ProfileLoadError("Missing required field: profile.name")
    if not version:
        raise ProfileLoadError("Missing required field: profile.version")
    if not kernel_version:
        raise ProfileLoadError("Missing required field: profile.kernel_version")

    builder = ProfileBuilder(name, version=version, kernel_version=kernel_version)

    # ID prefix
    prefix = profile_section.get("id_prefix", "")
    if prefix:
        builder.id_prefix(prefix)

    # Metadata
    standard = profile_section.get("standard", "")
    organization = profile_section.get("organization", "")
    if standard or organization:
        builder.metadata(standard=standard, organization=organization)

    # Category mapping
    categories = doc.get("categories", {})
    if categories:
        builder.category_mapping(categories)

    # Elements
    for elem in doc.get("elements", []):
        if "name" not in elem:
            raise ProfileLoadError("Element missing required field: name")
        if "layer" not in elem:
            raise ProfileLoadError(f"Element '{elem['name']}' missing required field: layer")
        if "category" not in elem:
            raise ProfileLoadError(f"Element '{elem['name']}' missing required field: category")
        builder.element(
            elem["name"],
            layer=elem["layer"],
            category=elem["category"],
            kernel_type=elem.get("kernel_type"),
            description=elem.get("description", ""),
            display_name=elem.get("display_name", ""),
        )

    # Relations
    for rel in doc.get("relations", []):
        if "name" not in rel:
            raise ProfileLoadError("Relation missing required field: name")
        if "kernel_relation" not in rel:
            raise ProfileLoadError(f"Relation '{rel['name']}' missing required field: kernel_relation")
        builder.relation(
            rel["name"],
            kernel_relation=rel["kernel_relation"],
            description=rel.get("description", ""),
            display_name=rel.get("display_name", ""),
            direction=rel.get("direction", ""),
        )

    # Rules
    for rule in doc.get("rules", []):
        source = rule.get("source")
        target = rule.get("target")
        relation = rule.get("relation")
        if not source or not target or not relation:
            raise ProfileLoadError(
                f"Rule missing required fields (source, target, relation): {rule}"
            )
        valid = rule.get("valid", True)
        priority = rule.get("priority", 40 if valid else 80)
        notes = rule.get("notes", "")
        rule_id = rule.get("id")

        conditions_raw = rule.get("conditions", [])
        conditions: tuple[KernelRuleCondition, ...] = ()
        if conditions_raw:
            parsed: list[KernelRuleCondition] = []
            for c in conditions_raw:
                ct = _CONDITION_MAP.get(c)
                if ct is None:
                    raise ProfileLoadError(f"Unknown condition: {c!r}")
                parsed.append(KernelRuleCondition(ct))
            conditions = tuple(parsed)

        if valid:
            builder.allow(
                source, target, relation,
                priority=priority, notes=notes, rule_id=rule_id,
                conditions=conditions,
            )
        else:
            builder.deny(
                source, target, relation,
                priority=priority, notes=notes, rule_id=rule_id,
            )

    return builder.build(kernel)
