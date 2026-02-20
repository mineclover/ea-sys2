"""Profile composition: extend and subset operations."""

from __future__ import annotations

from ea_profile.types import (
    KernelProfile,
    LayerStack,
    ProfileArtifactType,
    ProfileElement,
    ProfileProcessUnit,
    ProfileRelation,
    ProfileRule,
    ProfileStateTransition,
)


def extend(
    base: KernelProfile,
    *,
    name: str,
    version: str,
    add_elements: tuple[ProfileElement, ...] = (),
    add_relations: tuple[ProfileRelation, ...] = (),
    add_state_transitions: tuple[ProfileStateTransition, ...] = (),
    add_artifact_types: tuple[ProfileArtifactType, ...] = (),
    add_process_units: tuple[ProfileProcessUnit, ...] = (),
    layer_stack: LayerStack | None = None,
    add_rules: tuple[ProfileRule, ...] = (),
    override_rules: tuple[ProfileRule, ...] = (),
) -> KernelProfile:
    """Create a new profile extending a base profile.

    - add_elements/relations/rules: appended to base
    - override_rules: replaces rules with the same ID in base
    """
    # Merge elements (base + added)
    elements = base.elements + add_elements

    # Merge relations (base + added)
    relations = base.relations + add_relations

    # Merge state transitions (base + added)
    state_transitions = base.state_transitions + add_state_transitions

    # Merge artifact types (base + added)
    artifact_types = base.artifact_types + add_artifact_types

    # Merge process units (base + added)
    process_units = base.process_units + add_process_units

    merged_layer_stack = layer_stack if layer_stack is not None else base.layer_stack

    # Merge rules: override matching IDs, then add new
    override_ids = {r.id for r in override_rules}
    override_map = {r.id: r for r in override_rules}
    merged_rules: list[ProfileRule] = []
    for rule in base.validity_rules:
        if rule.id in override_ids:
            merged_rules.append(override_map[rule.id])
        else:
            merged_rules.append(rule)
    merged_rules.extend(add_rules)

    return KernelProfile(
        name=name,
        version=version,
        kernel_version=base.kernel_version,
        elements=elements,
        relations=relations,
        validity_rules=tuple(merged_rules),
        metadata=base.metadata,
        state_transitions=state_transitions,
        artifact_types=artifact_types,
        process_units=process_units,
        layer_stack=merged_layer_stack,
    )


def subset(
    profile: KernelProfile,
    *,
    name: str,
    version: str,
    layers: set[str] | None = None,
    categories: set[str] | None = None,
    relations: set[str] | None = None,
) -> KernelProfile:
    """Create a subset profile by filtering layers/categories/relations.

    Retains only elements matching the specified layers and/or categories,
    and only rules referencing the retained relations.
    """
    # Filter elements
    filtered_elements = list(profile.elements)
    if layers is not None:
        filtered_elements = [e for e in filtered_elements if e.layer in layers]
    if categories is not None:
        filtered_elements = [e for e in filtered_elements if e.category in categories]

    # Filter relations
    if relations is not None:
        filtered_relations = tuple(
            r for r in profile.relations if r.name in relations
        )
    else:
        filtered_relations = profile.relations

    # Filter rules: keep only those referencing retained relations
    retained_rel_names = {r.name for r in filtered_relations}
    filtered_rules = tuple(
        r for r in profile.validity_rules
        if r.relationship_name in retained_rel_names
    )

    return KernelProfile(
        name=name,
        version=version,
        kernel_version=profile.kernel_version,
        elements=tuple(filtered_elements),
        relations=filtered_relations,
        validity_rules=filtered_rules,
        metadata=profile.metadata,
        state_transitions=profile.state_transitions,
        artifact_types=profile.artifact_types,
        process_units=profile.process_units,
        layer_stack=profile.layer_stack,
    )
