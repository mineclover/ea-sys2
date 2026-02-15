"""Tests for profile_bridge.py — Needs profile loading."""

import pytest

from ea_kernel.profile_types import KernelProfile, ProfileBuildError
from ea_needs.profile_bridge import load_needs_profile_from_content


VALID_TOML = """\
[profile]
name = "TestNeeds"
version = "1.0"
kernel_version = "0.1.0"

[categories]
NeedType = "need"
ActorType = "stakeholder"

[[elements]]
name = "FunctionalNeed"
layer = "Core"
category = "NeedType"

[[elements]]
name = "ProjectOwner"
layer = "Core"
category = "ActorType"

[[relations]]
name = "depends_on"
kernel_relation = "depends_on"

[[rules]]
source = "@NeedType"
target = "@NeedType"
relation = "depends_on"
priority = 40
"""


class TestLoadNeedsProfile:
    """load_needs_profile_from_content loads valid TOML into KernelProfile."""

    def test_valid_toml(self):
        profile = load_needs_profile_from_content(VALID_TOML)
        assert isinstance(profile, KernelProfile)
        assert profile.name == "TestNeeds"
        assert len(profile.elements) == 2
        assert len(profile.relations) == 1

    def test_invalid_kernel_type(self):
        bad_toml = """\
[profile]
name = "Bad"
version = "1.0"
kernel_version = "0.1.0"

[categories]
BadCategory = "nonexistent_type"

[[elements]]
name = "BadElement"
layer = "Core"
category = "BadCategory"

[[relations]]
name = "depends_on"
kernel_relation = "depends_on"
"""
        with pytest.raises(ProfileBuildError):
            load_needs_profile_from_content(bad_toml)

    def test_invalid_kernel_relation(self):
        bad_toml = """\
[profile]
name = "Bad"
version = "1.0"
kernel_version = "0.1.0"

[categories]
NeedType = "need"

[[elements]]
name = "SomeNeed"
layer = "Core"
category = "NeedType"

[[relations]]
name = "bad_rel"
kernel_relation = "nonexistent_relation"
"""
        with pytest.raises(ProfileBuildError):
            load_needs_profile_from_content(bad_toml)

    def test_skip_validation(self):
        """When validate=False, unknown kernel types are allowed."""
        bad_toml = """\
[profile]
name = "Unvalidated"
version = "1.0"
kernel_version = "0.1.0"

[categories]
BadCategory = "nonexistent_type"

[[elements]]
name = "BadElement"
layer = "Core"
category = "BadCategory"

[[relations]]
name = "bad_rel"
kernel_relation = "nonexistent_relation"
"""
        profile = load_needs_profile_from_content(bad_toml, validate=False)
        assert profile.name == "Unvalidated"

    def test_needs_condition_used(self):
        """Needs-specific conditions can be used in rules."""
        toml_with_condition = """\
[profile]
name = "CondTest"
version = "1.0"
kernel_version = "0.1.0"

[categories]
NeedType = "need"

[[elements]]
name = "NeedA"
layer = "Core"
category = "NeedType"

[[relations]]
name = "supports"
kernel_relation = "supports"

[[rules]]
source = "*"
target = "*"
relation = "supports"
priority = 40
conditions = ["SAME_STATUS"]
"""
        profile = load_needs_profile_from_content(toml_with_condition)
        allow_rules = [r for r in profile.validity_rules if r.valid and r.priority > 1]
        assert len(allow_rules) == 1
        assert allow_rules[0].conditions[0].condition_type == "same_status"
