"""Tests for ea_profile.loader — TOML → KernelProfile loading."""

import pytest

from ea_profile.loader import ProfileLoadError, load_profile, load_profile_from_content
from ea_profile.types import ConditionRegistry, KernelProfile


# ---------------------------------------------------------------------------
# Valid TOML loading
# ---------------------------------------------------------------------------

VALID_TOML = """\
[profile]
name = "TestProfile"
version = "1.0"
kernel_version = "2.0"
id_prefix = "tp"
standard = "TestStd"
organization = "TestOrg"

[categories]
Behavior = "step"
Structure = "structure"

[[elements]]
name = "Svc"
layer = "Core"
category = "Structure"

[[elements]]
name = "Act"
layer = "Core"
category = "Behavior"

[[relations]]
name = "uses"
kernel_relation = "association"

[[rules]]
source = "@Behavior"
target = "@Structure"
relation = "uses"
priority = 50
"""


class TestLoadFromContent:
    def test_valid_toml(self):
        p = load_profile_from_content(VALID_TOML)
        assert isinstance(p, KernelProfile)
        assert p.name == "TestProfile"
        assert p.version == "1.0"
        assert p.kernel_version == "2.0"
        assert len(p.elements) == 2
        assert len(p.relations) == 1
        assert p.metadata is not None
        assert p.metadata.standard == "TestStd"

    def test_rules_loaded(self):
        p = load_profile_from_content(VALID_TOML)
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 1
        assert explicit[0].source_pattern == "@Behavior"

    def test_state_transitions_loaded(self):
        toml = """\
[profile]
name = "StateProfile"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "Core"
category = "C"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[state_transitions]]
from_state = "draft"
to_state = "approved"
guard_condition = "has_review"
description = "Review complete"
"""
        p = load_profile_from_content(toml)
        assert len(p.state_transitions) == 1
        transition = p.state_transitions[0]
        assert transition.from_state == "draft"
        assert transition.to_state == "approved"
        assert transition.guard_condition == "has_review"
        assert transition.description == "Review complete"


class TestLoadFromFile:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "test.toml"
        f.write_text(VALID_TOML, encoding="utf-8")
        p = load_profile(f)
        assert isinstance(p, KernelProfile)
        assert p.name == "TestProfile"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(ProfileLoadError, match="not found"):
            load_profile(tmp_path / "missing.toml")


# ---------------------------------------------------------------------------
# Required field errors
# ---------------------------------------------------------------------------

class TestRequiredFields:
    def test_missing_profile_name(self):
        toml = """\
[profile]
version = "1.0"
kernel_version = "2.0"
"""
        with pytest.raises(ProfileLoadError, match="profile.name"):
            load_profile_from_content(toml)

    def test_missing_profile_version(self):
        toml = """\
[profile]
name = "X"
kernel_version = "2.0"
"""
        with pytest.raises(ProfileLoadError, match="profile.version"):
            load_profile_from_content(toml)

    def test_missing_kernel_version(self):
        toml = """\
[profile]
name = "X"
version = "1.0"
"""
        with pytest.raises(ProfileLoadError, match="profile.kernel_version"):
            load_profile_from_content(toml)

    def test_missing_element_name(self):
        toml = """\
[profile]
name = "X"
version = "1.0"
kernel_version = "2.0"

[[elements]]
layer = "L"
category = "C"
kernel_type = "structure"
"""
        with pytest.raises(ProfileLoadError, match="Element missing.*name"):
            load_profile_from_content(toml)

    def test_missing_element_layer(self):
        toml = """\
[profile]
name = "X"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "E"
category = "C"
kernel_type = "structure"
"""
        with pytest.raises(ProfileLoadError, match="missing.*layer"):
            load_profile_from_content(toml)

    def test_missing_relation_kernel_relation(self):
        toml = """\
[profile]
name = "X"
version = "1.0"
kernel_version = "2.0"

[[relations]]
name = "r"
"""
        with pytest.raises(ProfileLoadError, match="kernel_relation"):
            load_profile_from_content(toml)

    def test_missing_state_transition_from_state(self):
        toml = """\
[profile]
name = "X"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[state_transitions]]
to_state = "approved"
"""
        with pytest.raises(ProfileLoadError, match="from_state"):
            load_profile_from_content(toml)

    def test_missing_state_transition_to_state(self):
        toml = """\
[profile]
name = "X"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[state_transitions]]
from_state = "draft"
"""
        with pytest.raises(ProfileLoadError, match="to_state"):
            load_profile_from_content(toml)


# ---------------------------------------------------------------------------
# Condition resolution
# ---------------------------------------------------------------------------

class TestConditionResolution:
    def test_known_condition_resolves(self):
        toml = """\
[profile]
name = "C"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "L"
category = "Cat"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
source = "A"
target = "A"
relation = "r"
conditions = ["SAME_LAYER"]
"""
        p = load_profile_from_content(toml)
        cond_rules = [r for r in p.validity_rules if r.conditions]
        assert len(cond_rules) == 1
        assert cond_rules[0].conditions[0].condition_type == "same_layer"

    def test_unknown_condition_raises(self):
        toml = """\
[profile]
name = "C"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "L"
category = "Cat"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
source = "A"
target = "A"
relation = "r"
conditions = ["UNKNOWN_COND"]
"""
        with pytest.raises(ProfileLoadError, match="Unknown condition"):
            load_profile_from_content(toml)


# ---------------------------------------------------------------------------
# Category mapping inference from TOML
# ---------------------------------------------------------------------------

class TestScopeLoading:
    def test_scope_sibling_parsed(self):
        toml = """\
[profile]
name = "S"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
source = "A"
target = "A"
relation = "r"
scope = "sibling"
"""
        p = load_profile_from_content(toml)
        scoped_rules = [r for r in p.validity_rules if r.scope == "sibling"]
        assert len(scoped_rules) == 1

    def test_scope_default_empty(self):
        toml = """\
[profile]
name = "S"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "structure"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
source = "A"
target = "A"
relation = "r"
"""
        p = load_profile_from_content(toml)
        allow_rules = [r for r in p.validity_rules if r.valid and r.priority > 1]
        assert all(r.scope == "" for r in allow_rules)


class TestCategoryMapping:
    def test_category_mapping_infers_kernel_type(self):
        toml = """\
[profile]
name = "M"
version = "1.0"
kernel_version = "2.0"

[categories]
Active = "structure"

[[elements]]
name = "X"
layer = "L"
category = "Active"

[[relations]]
name = "r"
kernel_relation = "association"
"""
        p = load_profile_from_content(toml)
        assert p.elements[0].kernel_type == "structure"
