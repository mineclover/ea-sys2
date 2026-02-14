"""Load kernel schema from TOML specification.

Parses specs/kernel_schema.toml into the typed kernel schema objects.
Only depends on ea_kernel.types — no circular imports.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from ea_kernel.types import (
    KernelAttribute,
    KernelEntity,
    KernelRelation,
    KernelRole,
    KernelSchema,
    Layer,
)

SPECS_DIR = Path(__file__).parent / "specs"

_LAYER_MAP: dict[str, Layer] = {
    "L1": Layer.L1, "L2": Layer.L2, "L3": Layer.L3, "L4": Layer.L4,
}


class SchemaLoadError(Exception):
    """Raised when a schema TOML file cannot be parsed or validated."""


def _default_layer_constraint_id(
    *,
    index: int,
    source_layer: str,
    target_layer: str,
    forbidden_relations: list[str],
) -> str:
    forbidden: str = (
        "-".join(forbidden_relations)
        if len(forbidden_relations) > 0
        else "none"
    )
    return (
        f"lc-{index:02d}-"
        f"{source_layer.lower()}-"
        f"{target_layer.lower()}-"
        f"{forbidden}"
    )


def load_kernel_schema(
    path: Path | None = None,
) -> tuple[str, KernelSchema, tuple[KernelAttribute, ...],
           tuple[KernelEntity, ...], tuple[KernelRelation, ...],
           tuple[KernelRelation, ...], tuple[KernelEntity, ...]]:
    """Load kernel schema from TOML file.

    Returns:
        (version, schema, attributes, l1_entities, l2_relations, l3_relations, l4_entities)
    """
    path = path or (SPECS_DIR / "kernel_schema.toml")
    try:
        raw = path.read_bytes()
    except FileNotFoundError as err:
        raise SchemaLoadError(f"Schema file not found: {path}") from err

    doc = tomllib.loads(raw.decode())

    meta = doc.get("meta", {})
    version = meta.get("kernel_version", "0.0.0")

    # Parse attributes
    attributes = tuple(
        KernelAttribute(name=a["name"], value_type=a["value_type"])
        for a in doc.get("attributes", [])
    )

    # Self-verification
    expected_attrs = meta.get("total_attributes")
    if expected_attrs is not None and len(attributes) != expected_attrs:
        raise SchemaLoadError(
            f"Expected {expected_attrs} attributes, got {len(attributes)}"
        )

    # Parse entities
    all_entities: list[KernelEntity] = []
    for e in doc.get("entities", []):
        layer = _LAYER_MAP.get(e["layer"])
        if layer is None:
            raise SchemaLoadError(f"Entity '{e['name']}': invalid layer '{e['layer']}'")
        all_entities.append(KernelEntity(
            name=e["name"],
            layer=layer,
            parent=e.get("parent"),
            is_abstract=e.get("is_abstract", False),
            owns=tuple(e.get("owns", [])),
            owns_key=e.get("owns_key"),
            plays=tuple(e.get("plays", [])),
            description=e.get("description", ""),
        ))

    # Parse relations
    all_relations: list[KernelRelation] = []
    for r in doc.get("relations", []):
        layer = _LAYER_MAP.get(r["layer"])
        if layer is None:
            raise SchemaLoadError(f"Relation '{r['name']}': invalid layer '{r['layer']}'")
        roles = tuple(
            KernelRole(name=role["name"], player=role["player"])
            for role in r.get("roles", [])
        )
        all_relations.append(KernelRelation(
            name=r["name"],
            layer=layer,
            parent=r.get("parent"),
            roles=roles,
            owns=tuple(r.get("owns", [])),
            owns_key=r.get("owns_key"),
            description=r.get("description", ""),
        ))

    # Self-verification
    expected_entities = meta.get("total_entities")
    if expected_entities is not None and len(all_entities) != expected_entities:
        raise SchemaLoadError(
            f"Expected {expected_entities} entities, got {len(all_entities)}"
        )
    expected_relations = meta.get("total_relations")
    if expected_relations is not None and len(all_relations) != expected_relations:
        raise SchemaLoadError(
            f"Expected {expected_relations} relations, got {len(all_relations)}"
        )

    # Split by layer
    l1_entities = tuple(e for e in all_entities if e.layer == Layer.L1)
    l4_entities = tuple(e for e in all_entities if e.layer == Layer.L4)
    l2_relations = tuple(r for r in all_relations if r.layer == Layer.L2)
    l3_relations = tuple(r for r in all_relations if r.layer == Layer.L3)

    # Load rules and layer constraints
    import warnings

    from ea_kernel.types import (
        KernelConditionType,
        KernelRuleCondition,
        KernelValidityRule,
        LayerConstraint,
    )

    rules_path = path.parent / "kernel_rules.toml"
    validity_rules: list[KernelValidityRule] = []
    parsed_constraints: list[LayerConstraint] = []

    if rules_path.exists():
        rules_doc = tomllib.loads(rules_path.read_bytes().decode())

        # Parse layer constraints
        for i, lc_data in enumerate(rules_doc.get("layer_constraints", [])):
            src = lc_data.get("source_layer")
            tgt = lc_data.get("target_layer")
            if src not in _LAYER_MAP or tgt not in _LAYER_MAP:
                raise SchemaLoadError(
                    f"Layer constraint #{i}: invalid layer ({src!r} -> {tgt!r})"
                )
            forbidden_relations = list(lc_data.get("forbidden", []))
            raw_constraint_id = lc_data.get("id")
            if raw_constraint_id is None:
                constraint_id = _default_layer_constraint_id(
                    index=i,
                    source_layer=src,
                    target_layer=tgt,
                    forbidden_relations=forbidden_relations,
                )
            elif isinstance(raw_constraint_id, str) and raw_constraint_id.strip():
                constraint_id = raw_constraint_id.strip()
            else:
                raise SchemaLoadError(
                    f"Layer constraint #{i}: invalid id {raw_constraint_id!r}"
                )
            parsed_constraints.append(LayerConstraint(
                id=constraint_id,
                source_layer=_LAYER_MAP[src],
                target_layer=_LAYER_MAP[tgt],
                forbidden_relations=tuple(forbidden_relations),
                allowed_pairs=tuple(
                    tuple(pair) for pair in lc_data.get("allowed_pairs", [])
                ),
                priority=lc_data.get("priority", 90),
                notes=lc_data.get("notes", ""),
            ))
        ids = [constraint.id for constraint in parsed_constraints]
        if len(ids) != len(set(ids)):
            raise SchemaLoadError("Layer constraints must have unique id values")

        # Parse rules
        for rule_key, r_data in rules_doc.get("rules", {}).items():
            conditions = []
            for cond_name in r_data.get("conditions", []):
                try:
                    ct = KernelConditionType(cond_name.lower())
                    conditions.append(KernelRuleCondition(condition_type=ct))
                except ValueError:
                    warnings.warn(
                        f"Rule {rule_key}: unknown condition type {cond_name!r}, skipping",
                        stacklevel=2,
                    )

            rule = KernelValidityRule(
                id=rule_key,
                source_pattern=r_data["source"],
                target_pattern=r_data["target"],
                relationship_name=r_data["relation"],
                valid=r_data.get("valid", True),
                priority=r_data.get("priority", 0),
                conditions=tuple(conditions),
                notes=r_data.get("notes", ""),
            )
            validity_rules.append(rule)

    schema = KernelSchema(
        attributes=attributes,
        entities=tuple(all_entities),
        relations=tuple(all_relations),
        validity_rules=tuple(validity_rules),
        layer_constraints=tuple(parsed_constraints),
    )

    return version, schema, attributes, l1_entities, l2_relations, l3_relations, l4_entities


def load_kernel_schema_from_package() -> KernelSchema:
    """Convenience wrapper to return just the KernelSchema object."""
    _, schema, _, _, _, _, _ = load_kernel_schema()
    return schema
