"""Compile profile rule patterns into executable kernel runtime rules.

Profile rules may use symbolic patterns:
- ``@Category``: profile category selector
- ``#Layer``: profile layer selector

These are expressive at profile design time but are not directly executable by
``KernelSchema.find_matching_rules``. This module compiles them into concrete
entity patterns usable by runtime judgment.
"""

from __future__ import annotations

from dataclasses import dataclass

from ea_kernel.profile_types import KernelProfile
from ea_kernel.types import (
    KernelEntity,
    KernelRelation,
    KernelSchema,
    KernelValidityRule,
    Layer,
)


@dataclass(frozen=True)
class ProfileRuleCompilationStats:
    """Compilation metrics for profile rule runtime materialization."""

    source_rule_count: int
    compiled_rule_count: int
    transformed_rule_count: int
    skipped_rule_count: int


@dataclass(frozen=True)
class ProfileRuleCompilationResult:
    """Compiled runtime rules plus compilation metadata."""

    rules: tuple[KernelValidityRule, ...]
    stats: ProfileRuleCompilationStats


@dataclass(frozen=True)
class ProfileSchemaOverlayStats:
    """Counts for profile-driven schema projection."""

    added_entity_count: int
    added_relation_count: int


@dataclass(frozen=True)
class ProfileRuntimeSchemaResult:
    """Runtime schema materialization output for a profile."""

    schema: KernelSchema
    compilation: ProfileRuleCompilationResult
    overlay: ProfileSchemaOverlayStats


def _expand_pattern(
    pattern: str,
    *,
    by_category: dict[str, tuple[str, ...]],
    category_wildcard: dict[str, str],
    by_layer: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    if pattern.startswith("@"):
        category = pattern[1:]
        wildcard = category_wildcard.get(category)
        if wildcard is not None:
            return (wildcard,)
        return by_category.get(category, ())
    if pattern.startswith("#"):
        return by_layer.get(pattern[1:], ())
    return (pattern,)


def compile_profile_rules_for_runtime(profile: KernelProfile) -> ProfileRuleCompilationResult:
    """Compile profile validity rules into runtime-executable kernel rules."""

    by_category: dict[str, tuple[str, ...]] = {}
    category_wildcard: dict[str, str] = {}
    by_layer: dict[str, tuple[str, ...]] = {}

    category_to_elements: dict[str, list[str]] = {}
    category_to_kernel_types: dict[str, set[str]] = {}
    layer_to_elements: dict[str, list[str]] = {}

    for element in profile.elements:
        category_to_elements.setdefault(element.category, []).append(element.name)
        category_to_kernel_types.setdefault(element.category, set()).add(element.kernel_type)
        layer_to_elements.setdefault(element.layer, []).append(element.name)

    for category, names in category_to_elements.items():
        by_category[category] = tuple(sorted(names))
        kernel_types = category_to_kernel_types.get(category, set())
        if len(kernel_types) == 1:
            only_kernel_type = next(iter(kernel_types))
            category_wildcard[category] = f"{only_kernel_type}*"

    for layer, names in layer_to_elements.items():
        by_layer[layer] = tuple(sorted(names))

    compiled_rules: list[KernelValidityRule] = []
    transformed_rule_count = 0
    skipped_rule_count = 0
    compiled_id_seq = 0

    for rule in profile.validity_rules:
        transformed = rule.source_pattern.startswith(("@", "#")) or rule.target_pattern.startswith(("@", "#"))
        if transformed:
            transformed_rule_count += 1

        source_patterns = _expand_pattern(
            rule.source_pattern,
            by_category=by_category,
            category_wildcard=category_wildcard,
            by_layer=by_layer,
        )
        target_patterns = _expand_pattern(
            rule.target_pattern,
            by_category=by_category,
            category_wildcard=category_wildcard,
            by_layer=by_layer,
        )

        if not source_patterns or not target_patterns:
            skipped_rule_count += 1
            continue

        for source in source_patterns:
            for target in target_patterns:
                compiled_id = rule.id
                if (
                    transformed
                    or source != rule.source_pattern
                    or target != rule.target_pattern
                ):
                    compiled_id_seq += 1
                    compiled_id = f"{rule.id}__c{compiled_id_seq:04d}"

                compiled_rules.append(
                    KernelValidityRule(
                        id=compiled_id,
                        source_pattern=source,
                        target_pattern=target,
                        relationship_name=rule.relationship_name,
                        valid=rule.valid,
                        priority=rule.priority,
                        conditions=rule.conditions,
                        description=rule.description,
                        notes=rule.notes,
                    )
                )

    stats = ProfileRuleCompilationStats(
        source_rule_count=len(profile.validity_rules),
        compiled_rule_count=len(compiled_rules),
        transformed_rule_count=transformed_rule_count,
        skipped_rule_count=skipped_rule_count,
    )
    return ProfileRuleCompilationResult(rules=tuple(compiled_rules), stats=stats)


def _fallback_layer(raw_layer: str) -> Layer:
    try:
        return Layer(raw_layer.strip().upper())
    except ValueError:
        return Layer.L4


def _resolve_profile_element_layer(
    *,
    base_schema: KernelSchema,
    kernel_type: str,
    profile_layer: str,
) -> Layer:
    kernel_entity = base_schema.get_entity(kernel_type)
    if kernel_entity is not None:
        return kernel_entity.layer
    return _fallback_layer(profile_layer)


def _resolve_profile_relation_layer(
    *,
    base_schema: KernelSchema,
    kernel_relation: str,
) -> Layer:
    base_relation = base_schema.get_relation(kernel_relation)
    if base_relation is not None:
        return base_relation.layer
    return Layer.L2


def _project_profile_structure(
    base_schema: KernelSchema,
    profile: KernelProfile,
    *,
    include_base_schema: bool,
) -> tuple[tuple[KernelEntity, ...], tuple[KernelRelation, ...], ProfileSchemaOverlayStats]:
    entities: list[KernelEntity] = list(base_schema.entities if include_base_schema else ())
    relations: list[KernelRelation] = list(base_schema.relations if include_base_schema else ())
    entity_names = {entity.name for entity in entities}
    relation_names = {relation.name for relation in relations}

    added_entity_count = 0
    added_relation_count = 0

    for element in profile.elements:
        if element.name in entity_names:
            continue
        entities.append(
            KernelEntity(
                name=element.name,
                layer=_resolve_profile_element_layer(
                    base_schema=base_schema,
                    kernel_type=element.kernel_type,
                    profile_layer=element.layer,
                ),
                parent=element.kernel_type if element.kernel_type else None,
                description=element.description,
                display_name=element.display_name,
                is_abstract=False,
            )
        )
        entity_names.add(element.name)
        added_entity_count += 1

    for relation in profile.relations:
        if relation.name in relation_names:
            continue
        relations.append(
            KernelRelation(
                name=relation.name,
                layer=_resolve_profile_relation_layer(
                    base_schema=base_schema,
                    kernel_relation=relation.kernel_relation,
                ),
                parent=relation.kernel_relation if relation.kernel_relation else None,
                description=relation.description,
                display_name=relation.display_name,
            )
        )
        relation_names.add(relation.name)
        added_relation_count += 1

    return (
        tuple(entities),
        tuple(relations),
        ProfileSchemaOverlayStats(
            added_entity_count=added_entity_count,
            added_relation_count=added_relation_count,
        ),
    )


def build_profile_structure_schema(
    base_schema: KernelSchema,
    profile: KernelProfile,
    *,
    include_base_schema: bool = True,
    include_base_rules: bool = True,
) -> tuple[KernelSchema, ProfileSchemaOverlayStats]:
    """Build a schema projected with profile elements/relations (without compiling profile rules)."""

    entities, relations, overlay = _project_profile_structure(
        base_schema,
        profile,
        include_base_schema=include_base_schema,
    )

    schema = KernelSchema(
        attributes=base_schema.attributes if include_base_schema else (),
        entities=entities,
        relations=relations,
        validity_rules=base_schema.validity_rules if include_base_rules else (),
        layer_constraints=base_schema.layer_constraints if include_base_schema else (),
    )
    return schema, overlay


def build_profile_runtime_schema(
    base_schema: KernelSchema,
    profile: KernelProfile,
    *,
    include_base_schema: bool = True,
    include_base_rules: bool = True,
) -> ProfileRuntimeSchemaResult:
    """Build executable runtime schema with compiled profile rules attached."""

    structure_schema, overlay = build_profile_structure_schema(
        base_schema,
        profile,
        include_base_schema=include_base_schema,
        include_base_rules=include_base_rules,
    )
    compilation = compile_profile_rules_for_runtime(profile)

    schema = KernelSchema(
        attributes=structure_schema.attributes,
        entities=structure_schema.entities,
        relations=structure_schema.relations,
        validity_rules=structure_schema.validity_rules + compilation.rules,
        layer_constraints=structure_schema.layer_constraints,
    )
    return ProfileRuntimeSchemaResult(
        schema=schema,
        compilation=compilation,
        overlay=overlay,
    )
