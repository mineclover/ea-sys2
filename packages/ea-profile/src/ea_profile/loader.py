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

import tomllib
from pathlib import Path

from ea_profile.builder import ProfileBuilder
from ea_profile.types import (
    ConditionRegistry,
    KernelProfile,
    RuleCondition,
    SchemaPort,
)


class ProfileLoadError(Exception):
    """Raised when a profile TOML file cannot be parsed."""


def load_profile(
    path: Path,
    kernel: SchemaPort | None = None,
    condition_registry: ConditionRegistry | None = None,
) -> KernelProfile:
    """Load a profile from a TOML file."""
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as err:
        raise ProfileLoadError(f"Profile file not found: {path}") from err
    return load_profile_from_content(content, kernel, condition_registry)


def load_profile_from_content(
    content: str,
    kernel: SchemaPort | None = None,
    condition_registry: ConditionRegistry | None = None,
) -> KernelProfile:
    """Load a profile from a TOML string."""
    if condition_registry is None:
        condition_registry = ConditionRegistry.kernel_default()

    try:
        doc = tomllib.loads(content)
    except tomllib.TOMLDecodeError as err:
        raise ProfileLoadError(f"Invalid TOML: {err}") from err

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
    # Projection overrides (optional [projection] section)
    projection = doc.get("projection", {})
    extra: dict[str, str] = {}
    for proj_key, proj_val in projection.items():
        extra[f"projection.{proj_key}"] = str(proj_val)
    if standard or organization or extra:
        builder.metadata(
            standard=standard, organization=organization,
            extra=extra or None,
        )

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

    # State transitions
    for transition in doc.get("state_transitions", []):
        if "from_state" not in transition:
            raise ProfileLoadError(
                "State transition missing required field: from_state"
            )
        if "to_state" not in transition:
            raise ProfileLoadError(
                "State transition missing required field: to_state"
            )
        builder.add_state_transition(
            transition["from_state"],
            transition["to_state"],
            guard_condition=transition.get("guard_condition", ""),
            description=transition.get("description", ""),
        )

    # Artifact types
    for artifact_type in doc.get("artifact_types", []):
        if "name" not in artifact_type:
            raise ProfileLoadError(
                "Artifact type missing required field: name"
            )
        if "tier" not in artifact_type:
            raise ProfileLoadError(
                f"Artifact type '{artifact_type['name']}' missing required field: tier"
            )
        builder.add_artifact_type(
            artifact_type["name"],
            artifact_type["tier"],
            description=artifact_type.get("description", ""),
            kernel_element_pattern=artifact_type.get("kernel_element_pattern", ""),
        )

    # Layer stack
    layer_stack = doc.get("layer_stack")
    if layer_stack:
        builder.set_layer_stack(
            definition_flow=layer_stack.get("definition_flow", ""),
            runtime_flow=layer_stack.get("runtime_flow", ""),
            feedback_flow=layer_stack.get("feedback_flow", ""),
        )

        for layer in layer_stack.get("layers", []):
            if "name" not in layer:
                raise ProfileLoadError("Layer definition missing required field: name")
            if "order" not in layer:
                raise ProfileLoadError(
                    f"Layer definition '{layer['name']}' missing required field: order"
                )

            depends_on_raw = layer.get("depends_on", [])
            depends_on: tuple[str, ...]
            if isinstance(depends_on_raw, str):
                depends_on = (depends_on_raw,)
            elif isinstance(depends_on_raw, list):
                depends_on = tuple(str(dep) for dep in depends_on_raw)
            else:
                raise ProfileLoadError(
                    f"Layer definition '{layer['name']}' has invalid depends_on type"
                )

            builder.add_layer_definition(
                layer["name"],
                int(layer["order"]),
                depends_on=depends_on,
                responsibility=layer.get("responsibility", ""),
                model_perspective=layer.get("model_perspective", ""),
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
        conditions: tuple[RuleCondition, ...] = ()
        if conditions_raw:
            parsed: list[RuleCondition] = []
            for c in conditions_raw:
                ct = condition_registry.resolve(c)
                if ct is None:
                    raise ProfileLoadError(f"Unknown condition: {c!r}")
                parsed.append(RuleCondition(ct))
            conditions = tuple(parsed)

        scope = rule.get("scope", "")

        if valid:
            builder.allow(
                source, target, relation,
                priority=priority, notes=notes, rule_id=rule_id,
                conditions=conditions, scope=scope,
            )
        else:
            builder.deny(
                source, target, relation,
                priority=priority, notes=notes, rule_id=rule_id,
                scope=scope,
            )

    return builder.build(kernel)
