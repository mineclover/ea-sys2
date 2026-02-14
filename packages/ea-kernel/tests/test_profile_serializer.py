"""Tests for profile_serializer — Dict/JSON round-trip + content hash."""

from __future__ import annotations

import json

import pytest
from ea_kernel.profile_serializer import (
    compute_content_hash,
    dict_to_profile,
    json_to_profile,
    profile_to_dict,
    profile_to_json,
)
from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileMetadata, ProfileRelation
from ea_kernel.types import KernelConditionType, KernelRuleCondition, KernelValidityRule

# ── Helpers ──────────────────────────────────────────────────────

def _make_profile(name: str = "TestProfile") -> KernelProfile:
    return KernelProfile(
        name=name,
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("Elem1", "structure", "Layer1", "Cat1", "desc1"),
            ProfileElement("Elem2", "step", "Layer2", "Cat2", ""),
        ),
        relations=(
            ProfileRelation("rel1", "association", "desc-rel"),
            ProfileRelation("rel2", "composition", ""),
        ),
        validity_rules=(
            KernelValidityRule(
                id="r1",
                source_pattern="@Cat1",
                target_pattern="@Cat2",
                relationship_name="rel1",
                valid=True,
                priority=40,
                conditions=(
                    KernelRuleCondition(
                        KernelConditionType.SAME_LAYER,
                        parameters=(("direction", "forward"),),
                    ),
                ),
                notes="allow note",
            ),
            KernelValidityRule(
                id="r2",
                source_pattern="*",
                target_pattern="*",
                relationship_name="rel1",
                valid=False,
                priority=1,
                notes="fallback",
            ),
        ),
        metadata=ProfileMetadata(
            standard="Test 1.0",
            organization="TestOrg",
            extra={"key": "val"},
        ),
    )


# ── Round-trip tests ─────────────────────────────────────────────

class TestDictRoundTrip:
    def test_full_profile_roundtrip(self):
        p = _make_profile()
        d = profile_to_dict(p)
        restored = dict_to_profile(d)
        assert restored == p

    def test_no_metadata_roundtrip(self):
        p = KernelProfile(
            name="Bare",
            version="0.1",
            kernel_version="2.5.0",
            elements=(ProfileElement("E1", "item", "L1", "C1"),),
            relations=(ProfileRelation("r1", "association"),),
        )
        assert dict_to_profile(profile_to_dict(p)) == p

    def test_empty_rules_roundtrip(self):
        p = KernelProfile(
            name="NoRules",
            version="0.1",
            kernel_version="2.5.0",
            elements=(ProfileElement("E1", "item", "L1", "C1"),),
            relations=(),
        )
        assert dict_to_profile(profile_to_dict(p)) == p

    def test_conditions_preserved(self):
        p = _make_profile()
        d = profile_to_dict(p)
        # Verify conditions serialized correctly
        conds = d["validity_rules"][0]["conditions"]
        assert len(conds) == 1
        assert conds[0]["condition_type"] == "same_layer"
        assert conds[0]["parameters"] == [["direction", "forward"]]
        # And round-trips back
        restored = dict_to_profile(d)
        assert restored.validity_rules[0].conditions == p.validity_rules[0].conditions


class TestJsonRoundTrip:
    def test_json_roundtrip(self):
        p = _make_profile()
        j = profile_to_json(p)
        restored = json_to_profile(j)
        assert restored == p

    def test_json_is_valid_json(self):
        p = _make_profile()
        j = profile_to_json(p)
        parsed = json.loads(j)
        assert parsed["name"] == "TestProfile"


class TestContentHash:
    def test_same_profile_same_hash(self):
        p = _make_profile()
        h1 = compute_content_hash(p)
        h2 = compute_content_hash(p)
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_different_profile_different_hash(self):
        p1 = _make_profile("A")
        p2 = _make_profile("B")
        assert compute_content_hash(p1) != compute_content_hash(p2)


# ── Builtin profile round-trip ───────────────────────────────────

class TestBuiltinProfileRoundTrip:
    @pytest.mark.parametrize("profile_name,module_path,var_name", [
        ("ArchiMate", "ea_kernel.profiles.archimate", "ARCHIMATE_PROFILE"),
        ("TOGAF", "ea_kernel.profiles.togaf", "TOGAF_PROFILE"),
        ("Zachman", "ea_kernel.profiles.zachman", "ZACHMAN_PROFILE"),
        ("BPMN", "ea_kernel.profiles.bpmn", "BPMN_PROFILE"),
        ("SysML2", "ea_kernel.profiles.sysml2", "SYSML2_PROFILE"),
    ])
    def test_builtin_roundtrip(self, profile_name, module_path, var_name):
        import importlib
        mod = importlib.import_module(module_path)
        profile = getattr(mod, var_name)
        d = profile_to_dict(profile)
        restored = dict_to_profile(d)
        assert restored == profile, f"{profile_name} dict round-trip failed"

    @pytest.mark.parametrize("profile_name,module_path,var_name", [
        ("ArchiMate", "ea_kernel.profiles.archimate", "ARCHIMATE_PROFILE"),
        ("TOGAF", "ea_kernel.profiles.togaf", "TOGAF_PROFILE"),
        ("Zachman", "ea_kernel.profiles.zachman", "ZACHMAN_PROFILE"),
        ("BPMN", "ea_kernel.profiles.bpmn", "BPMN_PROFILE"),
        ("SysML2", "ea_kernel.profiles.sysml2", "SYSML2_PROFILE"),
    ])
    def test_builtin_json_roundtrip(self, profile_name, module_path, var_name):
        import importlib
        mod = importlib.import_module(module_path)
        profile = getattr(mod, var_name)
        j = profile_to_json(profile)
        restored = json_to_profile(j)
        assert restored == profile, f"{profile_name} JSON round-trip failed"
