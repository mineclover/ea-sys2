"""Tests for profile_bridge.py — Governance profile loading."""

import pytest

from ea_kernel.profile_types import KernelProfile, ProfileBuildError
from ea_governance.profile_bridge import load_governance_profile_from_content


VALID_TOML = """\
[profile]
name = "TestGovernance"
version = "1.0"
kernel_version = "0.1.0"

[categories]
RegistryType = "layer_registry"
PolicyType = "policy"

[[elements]]
name = "ModelRegistry"
layer = "Core"
category = "RegistryType"

[[elements]]
name = "VersionPolicy"
layer = "Core"
category = "PolicyType"

[[relations]]
name = "registers"
kernel_relation = "registers"

[[rules]]
source = "@RegistryType"
target = "@PolicyType"
relation = "registers"
priority = 40
"""


class TestLoadGovernanceProfile:
    """load_governance_profile_from_content loads valid TOML into KernelProfile."""

    def test_valid_toml(self):
        profile = load_governance_profile_from_content(VALID_TOML)
        assert isinstance(profile, KernelProfile)
        assert profile.name == "TestGovernance"
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
name = "registers"
kernel_relation = "registers"
"""
        with pytest.raises(ProfileBuildError):
            load_governance_profile_from_content(bad_toml)

    def test_invalid_kernel_relation(self):
        bad_toml = """\
[profile]
name = "Bad"
version = "1.0"
kernel_version = "0.1.0"

[categories]
RegistryType = "layer_registry"

[[elements]]
name = "SomeRegistry"
layer = "Core"
category = "RegistryType"

[[relations]]
name = "bad_rel"
kernel_relation = "nonexistent_relation"
"""
        with pytest.raises(ProfileBuildError):
            load_governance_profile_from_content(bad_toml)

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
        profile = load_governance_profile_from_content(bad_toml, validate=False)
        assert profile.name == "Unvalidated"

    def test_governance_condition_used(self):
        """Governance-specific conditions can be used in rules."""
        toml_with_condition = """\
[profile]
name = "CondTest"
version = "1.0"
kernel_version = "0.1.0"

[categories]
RegistryType = "layer_registry"

[[elements]]
name = "RegistryA"
layer = "Core"
category = "RegistryType"

[[relations]]
name = "registers"
kernel_relation = "registers"

[[rules]]
source = "*"
target = "*"
relation = "registers"
priority = 40
conditions = ["SAME_LIFECYCLE"]
"""
        profile = load_governance_profile_from_content(toml_with_condition)
        allow_rules = [r for r in profile.validity_rules if r.valid and r.priority > 1]
        assert len(allow_rules) == 1
        assert allow_rules[0].conditions[0].condition_type == "same_lifecycle"
