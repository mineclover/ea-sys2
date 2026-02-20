"""Tests for policy/ — resolver, validator, normalizer."""

from pathlib import Path

from ea_projection.policy import (
    resolve_projection_policy,
    resolve_topic_query_policy,
    projection_policy_snapshot,
)
from ea_projection.policy.constants import TOPIC_QUERY_POLICY_DEFAULT
from ea_projection.policy.normalizer import (
    fallback_projection_ui_policy,
    normalize_topic_query_policy,
    normalize_projection_level_spec,
)
from ea_projection.policy.validator import validate_projection_policy_document


class TestResolveProjectionPolicy:

    def test_resolve_fallback_when_no_path(self):
        # Clear cache for isolated test
        resolve_projection_policy.cache_clear()
        policy = resolve_projection_policy("test-profile")
        assert "error" not in policy
        assert policy["source"] == "fallback"
        assert "l0" in policy["level_specs"]
        assert "l4" in policy["level_specs"]
        assert policy["layer_key"] is None

    def test_resolve_fallback_when_missing_file(self):
        resolve_projection_policy.cache_clear()
        policy = resolve_projection_policy(
            "test-missing",
            policy_path=Path("/nonexistent/policy.toml"),
        )
        assert "error" not in policy
        assert policy["source"] == "fallback"

    def test_resolve_with_layer_key(self):
        resolve_projection_policy.cache_clear()
        policy = resolve_projection_policy(
            "test-layer",
            layer_key="kernel",
        )
        assert policy["layer_key"] == "kernel"


class TestResolveTopicQueryPolicy:

    def test_resolve_topic_fallback(self):
        resolve_projection_policy.cache_clear()
        topic = resolve_topic_query_policy("test-topic")
        assert topic["default_depth"] == 2
        assert topic["max_seed_count"] == 8
        assert "scoring" in topic


class TestValidatePolicyDocument:

    def test_valid_document(self):
        doc = _build_valid_policy_doc()
        issues = validate_projection_policy_document(doc)
        assert issues == []

    def test_missing_m2(self):
        issues = validate_projection_policy_document({})
        assert len(issues) == 1
        assert "m2" in issues[0]

    def test_missing_m1(self):
        doc = _build_valid_policy_doc()
        del doc["m1"]
        issues = validate_projection_policy_document(doc)
        assert any("m1" in i for i in issues)

    def test_invalid_base_view_mode(self):
        doc = _build_valid_policy_doc()
        doc["m2"]["schema"]["base_view_modes"] = ["invalid_mode"]
        issues = validate_projection_policy_document(doc)
        assert any("invalid" in i.lower() for i in issues)


class TestNormalizer:

    def test_normalize_topic_query_fallback(self):
        result = normalize_topic_query_policy(
            spec=None,
            fallback=TOPIC_QUERY_POLICY_DEFAULT,
        )
        assert result["default_depth"] == 2
        assert result["seed_score_ratio"] == 0.72

    def test_normalize_level_spec_preserves_fallback(self):
        fallback = {
            "level": "L0",
            "lens": "panorama",
            "description": "test",
            "base_view_mode": "focus",
            "default_max_edges": 180,
        }
        result = normalize_projection_level_spec(
            level_key="l0",
            spec=None,
            fallback=fallback,
        )
        assert result == fallback

    def test_normalize_level_spec_overrides(self):
        fallback = {
            "level": "L0",
            "lens": "panorama",
            "description": "test",
            "base_view_mode": "focus",
            "default_max_edges": 180,
        }
        result = normalize_projection_level_spec(
            level_key="l0",
            spec={"default_max_edges": 300},
            fallback=fallback,
        )
        assert result["default_max_edges"] == 300


class TestFallbackUIPolicy:

    def test_fallback_without_layer(self):
        result = fallback_projection_ui_policy(None)
        assert "presets" in result
        assert "overview" in result["presets"]

    def test_fallback_with_layer_tuning(self):
        result = fallback_projection_ui_policy("kernel")
        overview_preset = result["presets"]["overview"]
        assert overview_preset["max_edges"] == 420

    def test_policy_snapshot_fallback(self):
        resolve_projection_policy.cache_clear()
        snap = projection_policy_snapshot(profile_name="test-snap")
        assert snap["source"] == "fallback"
        assert "levels" in snap
        assert "ui" in snap


def _build_valid_policy_doc() -> dict:
    return {
        "m2": {
            "schema": {
                "levels": ["l0", "l1", "l2", "l3", "l4"],
                "lenses": ["panorama", "capability", "interaction", "execution", "trace"],
                "base_view_modes": ["raw", "summary", "focus"],
                "focus_modes": ["core", "relation", "layer", "actor", "topic", "seed"],
                "required_level_fields": ["lens", "description", "base_view_mode"],
                "lens_to_level": {
                    "panorama": "l0",
                    "capability": "l1",
                    "interaction": "l2",
                    "execution": "l3",
                    "trace": "l4",
                },
            },
        },
        "m1": {
            "global": {
                "levels": {
                    "l0": {
                        "lens": "panorama",
                        "description": "test",
                        "base_view_mode": "focus",
                    },
                    "l1": {
                        "lens": "capability",
                        "description": "test",
                        "base_view_mode": "summary",
                    },
                    "l2": {
                        "lens": "interaction",
                        "description": "test",
                        "base_view_mode": "focus",
                    },
                    "l3": {
                        "lens": "execution",
                        "description": "test",
                        "base_view_mode": "summary",
                    },
                    "l4": {
                        "lens": "trace",
                        "description": "test",
                        "base_view_mode": "summary",
                    },
                },
            },
        },
    }
