"""Policy document validation — structural validation of projection_policy.toml.

Extracted from kernel_service.py lines 934-1154.
"""

from __future__ import annotations

from typing import Any

from ea_projection.depth import PROJECTION_BASE_VIEW_MODES, PROJECTION_FOCUS_MODES
from ea_projection.policy.normalizer import (
    _safe_positive_int,
    _to_string_tuple,
    validate_topic_query_policy,
)


def validate_projection_policy_document(policy_doc: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    m2 = policy_doc.get("m2")
    if not isinstance(m2, dict):
        return ["m2 section is required and must be a table"]
    schema = m2.get("schema")
    if not isinstance(schema, dict):
        return ["m2.schema section is required and must be a table"]

    levels = _to_string_tuple(schema.get("levels"))
    lenses = _to_string_tuple(schema.get("lenses"))
    base_view_modes = {value.lower() for value in _to_string_tuple(schema.get("base_view_modes"))}
    focus_modes = {value.lower() for value in _to_string_tuple(schema.get("focus_modes"))}
    required_level_fields = _to_string_tuple(schema.get("required_level_fields"))

    if not levels:
        issues.append("m2.schema.levels must define at least one level")
    if not lenses:
        issues.append("m2.schema.lenses must define at least one lens")
    if not required_level_fields:
        issues.append("m2.schema.required_level_fields must define required keys")
    if not base_view_modes:
        issues.append("m2.schema.base_view_modes must define allowed base_view_mode values")
    if not focus_modes:
        issues.append("m2.schema.focus_modes must define allowed focus values")

    allowed_base_view_modes = {value.lower() for value in PROJECTION_BASE_VIEW_MODES}
    invalid_base_modes = sorted(base_view_modes - allowed_base_view_modes)
    if invalid_base_modes:
        issues.append(f"m2.schema.base_view_modes has invalid values: {', '.join(invalid_base_modes)}")

    allowed_focus_modes = {value.lower() for value in PROJECTION_FOCUS_MODES}
    invalid_focus_modes = sorted(focus_modes - allowed_focus_modes)
    if invalid_focus_modes:
        issues.append(f"m2.schema.focus_modes has invalid values: {', '.join(invalid_focus_modes)}")

    level_set = {level.lower() for level in levels}
    lens_set = {lens.lower() for lens in lenses}

    lens_to_level_raw = schema.get("lens_to_level")
    if not isinstance(lens_to_level_raw, dict):
        issues.append("m2.schema.lens_to_level must be a table")
    else:
        mapped_lenses: set[str] = set()
        for lens_name, target_level in lens_to_level_raw.items():
            lens_name_norm = str(lens_name).strip().lower()
            target_level_norm = str(target_level).strip().lower()
            if not lens_name_norm:
                issues.append("m2.schema.lens_to_level contains an empty lens key")
                continue
            mapped_lenses.add(lens_name_norm)
            if target_level_norm not in level_set:
                issues.append(
                    f"m2.schema.lens_to_level.{lens_name_norm} points to unknown level {target_level}",
                )
        missing_lenses = sorted(lens_set - mapped_lenses)
        if missing_lenses:
            issues.append(f"m2.schema.lens_to_level is missing mappings for: {', '.join(missing_lenses)}")

    defaults = m2.get("defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            issues.append("m2.defaults must be a table when provided")
        else:
            if "actor_default_depth" in defaults:
                actor_depth = _safe_positive_int(defaults.get("actor_default_depth"), -1)
                if actor_depth <= 0:
                    issues.append("m2.defaults.actor_default_depth must be greater than zero")
    validate_topic_query_policy(
        label="m2.topic",
        spec=m2.get("topic"),
        issues=issues,
    )

    tiers = m2.get("tiers")
    if tiers is not None:
        if not isinstance(tiers, dict):
            issues.append("m2.tiers must be a table when provided")
        else:
            tier_names = tiers.get("names")
            if tier_names is not None:
                if not isinstance(tier_names, (list, tuple)) or not tier_names:
                    issues.append("m2.tiers.names must be a non-empty list")
            definitions = tiers.get("definitions")
            if definitions is not None:
                if not isinstance(definitions, dict):
                    issues.append("m2.tiers.definitions must be a table when provided")
                else:
                    valid_tier_names = set(str(n) for n in (tier_names or []))
                    for tier_key, tier_def in definitions.items():
                        if not isinstance(tier_def, dict):
                            issues.append(f"m2.tiers.definitions.{tier_key} must be a table")
                            continue
                        cats = tier_def.get("categories")
                        if not isinstance(cats, (list, tuple)) or not cats:
                            issues.append(
                                f"m2.tiers.definitions.{tier_key}.categories must be a non-empty list"
                            )
                        transitions = tier_def.get("transitions")
                        if isinstance(transitions, (list, tuple)):
                            for t in transitions:
                                t_str = str(t).strip()
                                if valid_tier_names and t_str not in valid_tier_names:
                                    issues.append(
                                        f"m2.tiers.definitions.{tier_key}.transitions references unknown tier: {t_str}"
                                    )

    m1 = policy_doc.get("m1")
    if not isinstance(m1, dict):
        issues.append("m1 section is required and must be a table")
        return issues

    global_section = m1.get("global")
    if not isinstance(global_section, dict):
        issues.append("m1.global section is required and must be a table")
        return issues
    global_levels = global_section.get("levels")
    if not isinstance(global_levels, dict):
        issues.append("m1.global.levels section is required and must be a table")
        return issues

    required_fields_set = set(required_level_fields)
    allowed_level_set = set(level_set)

    for level in level_set:
        level_spec = global_levels.get(level)
        if not isinstance(level_spec, dict):
            issues.append(f"m1.global.levels.{level} must exist and be a table")
            continue

        missing_fields = sorted(field for field in required_fields_set if field not in level_spec)
        if missing_fields:
            issues.append(
                f"m1.global.levels.{level} is missing required fields: {', '.join(missing_fields)}",
            )

        if "base_view_mode" in level_spec:
            mode = str(level_spec.get("base_view_mode", "")).strip().lower()
            if mode not in base_view_modes:
                issues.append(
                    f"m1.global.levels.{level}.base_view_mode={mode or '<empty>'} is not declared in m2.schema.base_view_modes",
                )

        if "base_focus" in level_spec:
            base_focus = level_spec.get("base_focus")
            if base_focus is not None:
                focus = str(base_focus).strip().lower()
                if focus and focus not in {"none", "null"} and focus not in focus_modes:
                    issues.append(
                        f"m1.global.levels.{level}.base_focus={focus} is not declared in m2.schema.focus_modes",
                    )

        if "default_max_edges" in level_spec:
            edge_cap = _safe_positive_int(level_spec.get("default_max_edges"), -1)
            if edge_cap <= 0:
                issues.append(f"m1.global.levels.{level}.default_max_edges must be greater than zero")

        next_levels = _to_string_tuple(level_spec.get("next_levels"))
        for next_level in next_levels:
            if next_level.strip().lower() not in allowed_level_set:
                issues.append(
                    f"m1.global.levels.{level}.next_levels contains unknown level {next_level}",
                )

    layer_overrides = m1.get("layers")
    if layer_overrides is not None:
        if not isinstance(layer_overrides, dict):
            issues.append("m1.layers must be a table when provided")
        else:
            for layer_key, layer_config in layer_overrides.items():
                if not isinstance(layer_config, dict):
                    issues.append(f"m1.layers.{layer_key} must be a table")
                    continue
                validate_topic_query_policy(
                    label=f"m1.layers.{layer_key}.topic",
                    spec=layer_config.get("topic"),
                    issues=issues,
                )
                levels_table = layer_config.get("levels")
                if levels_table is None:
                    levels_table = {}
                if not isinstance(levels_table, dict):
                    issues.append(f"m1.layers.{layer_key}.levels must be a table when provided")
                    continue
                for level_name, override in levels_table.items():
                    level_norm = str(level_name).strip().lower()
                    if level_norm not in allowed_level_set:
                        issues.append(f"m1.layers.{layer_key}.levels.{level_name} is not a declared level")
                        continue
                    if not isinstance(override, dict):
                        issues.append(f"m1.layers.{layer_key}.levels.{level_name} must be a table")
                        continue

                    if "base_view_mode" in override:
                        mode = str(override.get("base_view_mode", "")).strip().lower()
                        if mode not in base_view_modes:
                            issues.append(
                                f"m1.layers.{layer_key}.levels.{level_name}.base_view_mode={mode or '<empty>'} is not declared in m2.schema.base_view_modes",
                            )
                    if "base_focus" in override:
                        base_focus = override.get("base_focus")
                        if base_focus is not None:
                            focus = str(base_focus).strip().lower()
                            if focus and focus not in {"none", "null"} and focus not in focus_modes:
                                issues.append(
                                    f"m1.layers.{layer_key}.levels.{level_name}.base_focus={focus} is not declared in m2.schema.focus_modes",
                                )
                    if "default_max_edges" in override:
                        edge_cap = _safe_positive_int(override.get("default_max_edges"), -1)
                        if edge_cap <= 0:
                            issues.append(
                                f"m1.layers.{layer_key}.levels.{level_name}.default_max_edges must be greater than zero",
                            )
                    if "next_levels" in override:
                        for next_level in _to_string_tuple(override.get("next_levels")):
                            if next_level.strip().lower() not in allowed_level_set:
                                issues.append(
                                    f"m1.layers.{layer_key}.levels.{level_name}.next_levels contains unknown level {next_level}",
                                )

    return issues
