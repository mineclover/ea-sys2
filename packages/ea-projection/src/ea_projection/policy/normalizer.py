"""Policy normalization functions — safe parsing and merging of policy specs.

Extracted from kernel_service.py lines 477-801.
"""

from __future__ import annotations

from typing import Any

from ea_projection.depth import (
    PROJECTION_BASE_VIEW_MODES,
    PROJECTION_FOCUS_MODES,
    PROJECTION_DEFAULT_ACTOR_DEPTH,
)
from ea_projection.policy.constants import (
    PROJECTION_UI_DEFAULT,
    PROJECTION_UI_LAYER_TUNING,
)


def _to_string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        normalized = value.strip()
        return (normalized,) if normalized else ()
    if not isinstance(value, (list, tuple)):
        return ()
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
    return tuple(out)


def _safe_positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _safe_probability(value: Any, fallback: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if parsed < 0.0:
        return fallback
    if parsed > 1.0:
        return fallback
    return parsed


def normalized_projection_preset_key(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def copy_projection_ui_defaults() -> dict[str, Any]:
    return {
        "edge_budget_options": list(PROJECTION_UI_DEFAULT["edge_budget_options"]),
        "preset_order": list(PROJECTION_UI_DEFAULT["preset_order"]),
        "defaults": dict(PROJECTION_UI_DEFAULT["defaults"]),
        "safety_caps": {
            "topology": dict(PROJECTION_UI_DEFAULT["safety_caps"]["topology"]),
            "composed": dict(PROJECTION_UI_DEFAULT["safety_caps"]["composed"]),
            "projection": dict(PROJECTION_UI_DEFAULT["safety_caps"]["projection"]),
        },
        "presets": {
            key: dict(value)
            for key, value in PROJECTION_UI_DEFAULT["presets"].items()
        },
    }


def normalize_projection_ui_preset(
    *,
    spec: Any,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(fallback)
    if not isinstance(spec, dict):
        return normalized

    source_mode_raw = spec.get("source_mode")
    if isinstance(source_mode_raw, str):
        source_mode = source_mode_raw.strip().lower()
        if source_mode in {"topology", "projection", "composed"}:
            normalized["source_mode"] = source_mode

    view_mode_raw = spec.get("view_mode")
    if isinstance(view_mode_raw, str):
        view_mode = view_mode_raw.strip().lower()
        if view_mode in PROJECTION_BASE_VIEW_MODES:
            normalized["view_mode"] = view_mode

    # Import level specs keys for validation
    from ea_projection.depth import DepthLevelRegistry
    level_keys = set(DepthLevelRegistry.from_hardcoded().keys())

    projection_level_raw = spec.get("projection_level")
    if isinstance(projection_level_raw, str):
        projection_level = projection_level_raw.strip().lower()
        if projection_level in level_keys:
            normalized["projection_level"] = projection_level

    focus_mode_raw = spec.get("focus_mode")
    if isinstance(focus_mode_raw, str):
        focus_mode = focus_mode_raw.strip().lower()
        if focus_mode in PROJECTION_FOCUS_MODES:
            normalized["focus_mode"] = focus_mode

    if "focus_depth" in spec:
        normalized["focus_depth"] = _safe_positive_int(
            spec.get("focus_depth"),
            int(normalized.get("focus_depth", PROJECTION_DEFAULT_ACTOR_DEPTH)),
        )
    if "max_edges" in spec:
        normalized["max_edges"] = _safe_positive_int(
            spec.get("max_edges"),
            int(normalized.get("max_edges", 420)),
        )

    if "surface_only" in spec and isinstance(spec.get("surface_only"), bool):
        normalized["surface_only"] = bool(spec.get("surface_only"))

    domain_scope_raw = spec.get("domain_scope")
    if isinstance(domain_scope_raw, str):
        domain_scope = domain_scope_raw.strip().lower()
        if domain_scope in {"all", "owned", "bridge"}:
            normalized["domain_scope"] = domain_scope

    source_mode = str(normalized.get("source_mode", "topology"))
    if source_mode == "projection":
        projection_level = str(normalized.get("projection_level", "l1")).strip().lower()
        if projection_level not in level_keys:
            normalized["projection_level"] = "l1"
        normalized.pop("view_mode", None)
        normalized.pop("focus_mode", None)
    else:
        view_mode = str(normalized.get("view_mode", "summary")).strip().lower()
        if view_mode not in PROJECTION_BASE_VIEW_MODES:
            normalized["view_mode"] = "summary"
        normalized.pop("projection_level", None)
        if view_mode != "focus":
            normalized.pop("focus_mode", None)
            normalized.pop("focus_depth", None)

    return normalized


def normalize_projection_ui_policy(
    *,
    spec: Any,
    layer_key: str | None,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    normalized = {
        "edge_budget_options": list(fallback.get("edge_budget_options", [])),
        "preset_order": list(fallback.get("preset_order", [])),
        "defaults": dict(fallback.get("defaults", {})),
        "safety_caps": {
            "topology": dict(fallback.get("safety_caps", {}).get("topology", {})),
            "composed": dict(fallback.get("safety_caps", {}).get("composed", {})),
            "projection": dict(fallback.get("safety_caps", {}).get("projection", {})),
        },
        "presets": {
            key: dict(value)
            for key, value in dict(fallback.get("presets", {})).items()
        },
    }
    if not isinstance(spec, dict):
        return normalized

    raw_options = spec.get("edge_budget_options")
    if isinstance(raw_options, (list, tuple)):
        parsed_options: list[int] = []
        seen: set[int] = set()
        for item in raw_options:
            value = _safe_positive_int(item, -1)
            if value <= 0 or value in seen:
                continue
            parsed_options.append(value)
            seen.add(value)
        if parsed_options:
            normalized["edge_budget_options"] = sorted(parsed_options)

    raw_order = _to_string_tuple(spec.get("preset_order"))
    if raw_order:
        seen_order: set[str] = set()
        order: list[str] = []
        for item in raw_order:
            key = normalized_projection_preset_key(item)
            if key in normalized["presets"] and key not in seen_order:
                order.append(key)
                seen_order.add(key)
        if order:
            normalized["preset_order"] = order

    defaults = normalized["defaults"]
    if isinstance(spec.get("safety_mode_default"), bool):
        defaults["safety_mode"] = bool(spec.get("safety_mode_default"))
    if isinstance(spec.get("surface_only_default"), bool):
        defaults["surface_only"] = bool(spec.get("surface_only_default"))
    domain_scope_raw = spec.get("domain_scope_default")
    if isinstance(domain_scope_raw, str):
        domain_scope = domain_scope_raw.strip().lower()
        if domain_scope in {"all", "owned", "bridge"}:
            defaults["domain_scope"] = domain_scope

    # Import level specs keys for safety_caps validation
    from ea_projection.depth import DepthLevelRegistry
    level_keys = tuple(DepthLevelRegistry.from_hardcoded().keys())

    raw_caps = spec.get("safety_caps")
    if isinstance(raw_caps, dict):
        for mode, keys in (
            ("topology", ("raw", "summary", "focus")),
            ("composed", ("summary", "focus")),
            ("projection", level_keys),
        ):
            raw_mode = raw_caps.get(mode)
            if not isinstance(raw_mode, dict):
                continue
            target_mode = normalized["safety_caps"][mode]
            for key in keys:
                if key not in raw_mode:
                    continue
                target_mode[key] = _safe_positive_int(raw_mode.get(key), int(target_mode.get(key, 1)))

    raw_presets = spec.get("presets")
    if isinstance(raw_presets, dict):
        for raw_key, raw_value in raw_presets.items():
            key = normalized_projection_preset_key(str(raw_key))
            if key not in normalized["presets"]:
                continue
            normalized["presets"][key] = normalize_projection_ui_preset(
                spec=raw_value,
                fallback=normalized["presets"][key],
            )

    raw_layers = spec.get("layers")
    layer_spec: dict[str, Any] | None = None
    if isinstance(raw_layers, dict) and layer_key:
        candidate = raw_layers.get(layer_key)
        if isinstance(candidate, dict):
            layer_spec = candidate
    if layer_spec is None:
        return normalized

    layer_options = layer_spec.get("edge_budget_options")
    if isinstance(layer_options, (list, tuple)):
        parsed_layer_options: list[int] = []
        seen_layer_options: set[int] = set()
        for item in layer_options:
            value = _safe_positive_int(item, -1)
            if value <= 0 or value in seen_layer_options:
                continue
            parsed_layer_options.append(value)
            seen_layer_options.add(value)
        if parsed_layer_options:
            normalized["edge_budget_options"] = sorted(parsed_layer_options)

    layer_order = _to_string_tuple(layer_spec.get("preset_order"))
    if layer_order:
        seen_order_layer: set[str] = set()
        order_list: list[str] = []
        for item in layer_order:
            key = normalized_projection_preset_key(item)
            if key in normalized["presets"] and key not in seen_order_layer:
                order_list.append(key)
                seen_order_layer.add(key)
        if order_list:
            normalized["preset_order"] = order_list

    if isinstance(layer_spec.get("safety_mode_default"), bool):
        defaults["safety_mode"] = bool(layer_spec.get("safety_mode_default"))
    if isinstance(layer_spec.get("surface_only_default"), bool):
        defaults["surface_only"] = bool(layer_spec.get("surface_only_default"))
    layer_domain_scope_raw = layer_spec.get("domain_scope_default")
    if isinstance(layer_domain_scope_raw, str):
        layer_domain_scope = layer_domain_scope_raw.strip().lower()
        if layer_domain_scope in {"all", "owned", "bridge"}:
            defaults["domain_scope"] = layer_domain_scope

    layer_caps = layer_spec.get("safety_caps")
    if isinstance(layer_caps, dict):
        for mode, keys in (
            ("topology", ("raw", "summary", "focus")),
            ("composed", ("summary", "focus")),
            ("projection", level_keys),
        ):
            raw_mode = layer_caps.get(mode)
            if not isinstance(raw_mode, dict):
                continue
            target_mode = normalized["safety_caps"][mode]
            for key in keys:
                if key not in raw_mode:
                    continue
                target_mode[key] = _safe_positive_int(raw_mode.get(key), int(target_mode.get(key, 1)))

    layer_presets = layer_spec.get("presets")
    if isinstance(layer_presets, dict):
        for raw_key, raw_value in layer_presets.items():
            key = normalized_projection_preset_key(str(raw_key))
            if key not in normalized["presets"]:
                continue
            normalized["presets"][key] = normalize_projection_ui_preset(
                spec=raw_value,
                fallback=normalized["presets"][key],
            )

    return normalized


def fallback_projection_ui_policy(layer_key: str | None) -> dict[str, Any]:
    fallback = copy_projection_ui_defaults()
    if not layer_key:
        return fallback
    for preset_key, per_layer in PROJECTION_UI_LAYER_TUNING.items():
        override = per_layer.get(layer_key)
        if not isinstance(override, dict):
            continue
        preset_fallback = fallback["presets"].get(preset_key)
        if not isinstance(preset_fallback, dict):
            continue
        fallback["presets"][preset_key] = normalize_projection_ui_preset(
            spec=override,
            fallback=preset_fallback,
        )
    return fallback


def normalize_topic_query_policy(
    *,
    spec: Any,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "default_depth": int(fallback.get("default_depth", 2)),
        "max_scope_nodes_per_depth": int(fallback.get("max_scope_nodes_per_depth", 40)),
        "seed_score_ratio": float(fallback.get("seed_score_ratio", 0.72)),
        "seed_score_floor": int(fallback.get("seed_score_floor", 60)),
        "min_token_coverage": float(fallback.get("min_token_coverage", 0.5)),
        "max_seed_count": int(fallback.get("max_seed_count", 8)),
        "max_match_count": int(fallback.get("max_match_count", 16)),
        "max_available_topics": int(fallback.get("max_available_topics", 60)),
        "scoring": dict(fallback.get("scoring", {})),
    }
    if not isinstance(spec, dict):
        return normalized

    positive_int_fields = (
        "default_depth",
        "max_scope_nodes_per_depth",
        "seed_score_floor",
        "max_seed_count",
        "max_match_count",
        "max_available_topics",
    )
    for field in positive_int_fields:
        if field not in spec:
            continue
        normalized[field] = _safe_positive_int(spec.get(field), int(normalized[field]))

    if "seed_score_ratio" in spec:
        normalized["seed_score_ratio"] = _safe_probability(
            spec.get("seed_score_ratio"),
            float(normalized["seed_score_ratio"]),
        )
    if "min_token_coverage" in spec:
        normalized["min_token_coverage"] = _safe_probability(
            spec.get("min_token_coverage"),
            float(normalized["min_token_coverage"]),
        )

    scoring = normalized["scoring"]
    if not isinstance(scoring, dict):
        scoring = {}
        normalized["scoring"] = scoring
    raw_scoring = spec.get("scoring")
    if isinstance(raw_scoring, dict):
        for key, fallback_value in list(scoring.items()):
            if key not in raw_scoring:
                continue
            scoring[key] = _safe_positive_int(raw_scoring.get(key), int(fallback_value))

    return normalized


def normalize_projection_level_spec(
    *,
    level_key: str,
    spec: Any,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(fallback)
    if not isinstance(spec, dict):
        return normalized

    text_fields = ("level", "lens", "description")
    for field in text_fields:
        raw = spec.get(field)
        if isinstance(raw, str) and raw.strip():
            normalized[field] = raw.strip()

    raw_base_view = spec.get("base_view_mode")
    if isinstance(raw_base_view, str):
        base_view = raw_base_view.strip().lower()
        if base_view in PROJECTION_BASE_VIEW_MODES:
            normalized["base_view_mode"] = base_view

    if "base_focus" in spec:
        raw_focus = spec.get("base_focus")
        if raw_focus is None:
            normalized["base_focus"] = None
        elif isinstance(raw_focus, str):
            focus = raw_focus.strip().lower()
            if focus in {"", "none", "null"}:
                normalized["base_focus"] = None
            elif focus in PROJECTION_FOCUS_MODES:
                normalized["base_focus"] = focus

    if "allowed_relations" in spec:
        normalized["allowed_relations"] = _to_string_tuple(spec.get("allowed_relations"))
    if "allowed_categories" in spec:
        normalized["allowed_categories"] = _to_string_tuple(spec.get("allowed_categories"))
    if "next_levels" in spec:
        normalized["next_levels"] = _to_string_tuple(spec.get("next_levels"))
    if "default_max_edges" in spec:
        normalized["default_max_edges"] = _safe_positive_int(
            spec.get("default_max_edges"),
            int(fallback.get("default_max_edges", 600)),
        )

    if not normalized.get("lens"):
        normalized["lens"] = level_key
    if not normalized.get("level"):
        normalized["level"] = level_key.upper()

    return normalized


def validate_topic_query_policy(
    *,
    label: str,
    spec: Any,
    issues: list[str],
) -> None:
    if spec is None:
        return
    if not isinstance(spec, dict):
        issues.append(f"{label} must be a table")
        return

    positive_int_fields = (
        "default_depth",
        "max_scope_nodes_per_depth",
        "seed_score_floor",
        "max_seed_count",
        "max_match_count",
        "max_available_topics",
    )
    for field in positive_int_fields:
        if field not in spec:
            continue
        value = _safe_positive_int(spec.get(field), -1)
        if value <= 0:
            issues.append(f"{label}.{field} must be greater than zero")

    probability_fields = ("seed_score_ratio", "min_token_coverage")
    for field in probability_fields:
        if field not in spec:
            continue
        try:
            value = float(spec.get(field))
        except (TypeError, ValueError):
            issues.append(f"{label}.{field} must be a number between 0.0 and 1.0")
            continue
        if value < 0.0 or value > 1.0:
            issues.append(f"{label}.{field} must be between 0.0 and 1.0")

    scoring = spec.get("scoring")
    if scoring is not None:
        if not isinstance(scoring, dict):
            issues.append(f"{label}.scoring must be a table")
        else:
            for key, raw in scoring.items():
                value = _safe_positive_int(raw, -1)
                if value <= 0:
                    issues.append(f"{label}.scoring.{key} must be greater than zero")
