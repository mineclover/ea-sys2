"""Policy resolution — load, validate, and merge projection policy from TOML.

Extracted from kernel_service.py lines 908-1394.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from ea_projection.depth import (
    PROJECTION_DEFAULT_ACTOR_DEPTH,
    PROJECTION_LENS_TO_LEVEL,
    DepthLevelRegistry,
)
from ea_projection.policy.constants import TOPIC_QUERY_POLICY_DEFAULT
from ea_projection.policy.normalizer import (
    _safe_positive_int,
    _to_string_tuple,
    fallback_projection_ui_policy,
    normalize_projection_level_spec,
    normalize_projection_ui_policy,
    normalize_topic_query_policy,
)
from ea_projection.policy.validator import validate_projection_policy_document


def load_projection_policy_document(policy_path: Path) -> dict[str, Any]:
    """Load and parse a projection policy TOML document.

    Unlike the original kernel_service version, this does NOT use lru_cache
    because the path is injected from outside. Callers should cache as needed.
    """
    payload: dict[str, Any] = {
        "status": "missing",
        "path": str(policy_path),
        "document": {},
    }
    if not policy_path.exists():
        return payload
    try:
        with policy_path.open("rb") as handle:
            loaded = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        payload["status"] = "invalid_toml"
        payload["error"] = str(exc)
        return payload
    if not isinstance(loaded, dict):
        payload["status"] = "invalid_document"
        payload["error"] = "Root TOML document must be a table/object."
        return payload
    payload["status"] = "ok"
    payload["document"] = loaded
    return payload


@lru_cache(maxsize=64)
def resolve_projection_policy(
    profile_name: str,
    *,
    policy_path: Path | None = None,
    layer_key: str | None = None,
) -> dict[str, Any]:
    """Resolve merged projection policy for a profile.

    Args:
        profile_name: Profile name for cache keying.
        policy_path: Path to projection_policy.toml. If None, returns fallback policy.
        layer_key: Resolved layer key (e.g. "kernel", "flow"). If None, no layer override.
    """
    registry = DepthLevelRegistry.from_hardcoded()
    level_specs: dict[str, dict[str, Any]] = registry.to_level_specs()
    lens_to_level = dict(PROJECTION_LENS_TO_LEVEL)
    actor_default_depth = PROJECTION_DEFAULT_ACTOR_DEPTH
    topic_policy = normalize_topic_query_policy(
        spec=None,
        fallback=TOPIC_QUERY_POLICY_DEFAULT,
    )
    ui_policy = fallback_projection_ui_policy(layer_key)
    policy_source = "fallback"
    policy_scope = "global"
    schema_contract: dict[str, Any] = {}

    if policy_path is None:
        return {
            "level_specs": level_specs,
            "lens_to_level": lens_to_level,
            "actor_default_depth": actor_default_depth,
            "topic_policy": topic_policy,
            "ui_policy": ui_policy,
            "source": policy_source,
            "scope": policy_scope,
            "layer_key": layer_key,
            "schema_contract": schema_contract,
        }

    policy_loaded = load_projection_policy_document(policy_path)
    policy_status = str(policy_loaded.get("status", "missing"))
    policy_path_str = str(policy_loaded.get("path", str(policy_path)))

    if policy_status == "missing":
        return {
            "level_specs": level_specs,
            "lens_to_level": lens_to_level,
            "actor_default_depth": actor_default_depth,
            "topic_policy": topic_policy,
            "ui_policy": ui_policy,
            "source": policy_source,
            "scope": policy_scope,
            "layer_key": layer_key,
            "schema_contract": schema_contract,
        }
    if policy_status != "ok":
        return {
            "error": "Projection policy parsing failed",
            "policy_error": {
                "status": policy_status,
                "path": policy_path_str,
                "detail": str(policy_loaded.get("error", "invalid projection policy document")),
            },
        }

    policy_doc = policy_loaded.get("document")
    if not isinstance(policy_doc, dict):
        return {
            "error": "Projection policy parsing failed",
            "policy_error": {
                "status": "invalid_document",
                "path": policy_path_str,
                "detail": "Projection policy document must be a table/object.",
            },
        }

    issues = validate_projection_policy_document(policy_doc)
    if issues:
        return {
            "error": "Projection policy contract validation failed",
            "policy_error": {
                "status": "invalid_contract",
                "path": policy_path_str,
                "issues": issues,
            },
        }

    policy_source = "toml"
    m2 = policy_doc.get("m2")
    if isinstance(m2, dict):
        schema = m2.get("schema")
        if isinstance(schema, dict):
            for field in (
                "levels",
                "lenses",
                "base_view_modes",
                "focus_modes",
                "required_level_fields",
            ):
                values = _to_string_tuple(schema.get(field))
                if values:
                    schema_contract[field] = list(values)

            lens_to_level_doc = schema.get("lens_to_level")
            if isinstance(lens_to_level_doc, dict):
                for lens_name, target_level in lens_to_level_doc.items():
                    lens = str(lens_name).strip().lower()
                    level = str(target_level).strip().lower()
                    if not lens or level not in level_specs:
                        continue
                    lens_to_level[lens] = level

        defaults = m2.get("defaults")
        if isinstance(defaults, dict):
            actor_default_depth = _safe_positive_int(
                defaults.get("actor_default_depth"),
                actor_default_depth,
            )
        topic_policy = normalize_topic_query_policy(
            spec=m2.get("topic"),
            fallback=topic_policy,
        )

    m1 = policy_doc.get("m1")
    global_levels: dict[str, Any] = {}
    layer_levels: dict[str, Any] = {}
    layer_topic_policy: dict[str, Any] = {}
    if isinstance(m1, dict):
        global_config = m1.get("global")
        if isinstance(global_config, dict):
            levels = global_config.get("levels")
            if isinstance(levels, dict):
                global_levels = levels

        if layer_key:
            layers = m1.get("layers")
            if isinstance(layers, dict):
                layer_config = layers.get(layer_key)
                if isinstance(layer_config, dict):
                    levels = layer_config.get("levels")
                    if isinstance(levels, dict):
                        layer_levels = levels
                    topic = layer_config.get("topic")
                    if isinstance(topic, dict):
                        layer_topic_policy = topic
                    if levels or layer_topic_policy:
                        policy_scope = f"layer:{layer_key}"
        ui_policy = normalize_projection_ui_policy(
            spec=m1.get("ui"),
            layer_key=layer_key,
            fallback=ui_policy,
        )

    hardcoded_specs = registry.to_level_specs()
    for level_key_iter, fallback in hardcoded_specs.items():
        merged = normalize_projection_level_spec(
            level_key=level_key_iter,
            spec=global_levels.get(level_key_iter),
            fallback=fallback,
        )
        merged = normalize_projection_level_spec(
            level_key=level_key_iter,
            spec=layer_levels.get(level_key_iter),
            fallback=merged,
        )
        level_specs[level_key_iter] = merged

    for level_key_iter, spec in level_specs.items():
        lens = str(spec.get("lens", "")).strip().lower()
        if lens:
            lens_to_level[lens] = level_key_iter

    topic_policy = normalize_topic_query_policy(
        spec=layer_topic_policy,
        fallback=topic_policy,
    )

    return {
        "level_specs": level_specs,
        "lens_to_level": lens_to_level,
        "actor_default_depth": actor_default_depth,
        "topic_policy": topic_policy,
        "ui_policy": ui_policy,
        "source": policy_source,
        "scope": policy_scope,
        "layer_key": layer_key,
        "schema_contract": schema_contract,
    }


def resolve_topic_query_policy(
    profile_name: str,
    *,
    policy_path: Path | None = None,
    layer_key: str | None = None,
) -> dict[str, Any]:
    fallback = normalize_topic_query_policy(
        spec=None,
        fallback=TOPIC_QUERY_POLICY_DEFAULT,
    )
    policy = resolve_projection_policy(profile_name, policy_path=policy_path, layer_key=layer_key)
    if "error" in policy:
        return fallback
    topic_policy = policy.get("topic_policy")
    if not isinstance(topic_policy, dict):
        return fallback
    return normalize_topic_query_policy(spec=topic_policy, fallback=fallback)


def projection_policy_snapshot(
    *,
    profile_name: str,
    policy_path: Path | None = None,
    layer_key: str | None = None,
) -> dict[str, Any]:
    """Expose resolved projection policy (M2 contract + M1 layer policy + UI policy)."""
    policy = resolve_projection_policy(profile_name, policy_path=policy_path, layer_key=layer_key)
    if "error" in policy:
        return {
            "error": str(policy.get("error", "Projection policy resolution failed")),
            "policy_error": policy.get("policy_error"),
            "profile_name": profile_name,
        }

    level_specs_raw = policy.get("level_specs")
    level_specs: dict[str, dict[str, Any]] = {}
    if isinstance(level_specs_raw, dict):
        for key, raw in level_specs_raw.items():
            if not isinstance(raw, dict):
                continue
            level_specs[str(key)] = {
                "level": str(raw.get("level", str(key).upper())),
                "lens": str(raw.get("lens", str(key))),
                "description": str(raw.get("description", "")),
                "base_view_mode": str(raw.get("base_view_mode", "summary")),
                "base_focus": raw.get("base_focus"),
                "allowed_relations": list(_to_string_tuple(raw.get("allowed_relations"))),
                "allowed_categories": list(_to_string_tuple(raw.get("allowed_categories"))),
                "default_max_edges": int(raw.get("default_max_edges", 600)),
                "next_levels": list(_to_string_tuple(raw.get("next_levels"))),
            }

    lens_to_level_raw = policy.get("lens_to_level")
    lens_to_level: dict[str, str] = {}
    if isinstance(lens_to_level_raw, dict):
        for lens_name, level_name in lens_to_level_raw.items():
            lens = str(lens_name).strip().lower()
            level = str(level_name).strip().lower()
            if not lens or not level:
                continue
            lens_to_level[lens] = level

    topic_policy = policy.get("topic_policy")
    ui_policy = policy.get("ui_policy")

    return {
        "profile_name": profile_name,
        "source": str(policy.get("source", "fallback")),
        "scope": str(policy.get("scope", "global")),
        "layer_key": policy.get("layer_key"),
        "schema_contract": dict(policy.get("schema_contract", {})),
        "actor_default_depth": int(policy.get("actor_default_depth", PROJECTION_DEFAULT_ACTOR_DEPTH)),
        "lens_to_level": lens_to_level,
        "levels": level_specs,
        "topic": dict(topic_policy) if isinstance(topic_policy, dict) else normalize_topic_query_policy(
            spec=None,
            fallback=TOPIC_QUERY_POLICY_DEFAULT,
        ),
        "ui": dict(ui_policy) if isinstance(ui_policy, dict) else fallback_projection_ui_policy(layer_key),
    }
