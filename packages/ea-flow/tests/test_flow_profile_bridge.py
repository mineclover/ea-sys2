"""Tests for profile_bridge.py — Flow profile loading."""

import pytest

from ea_kernel.profile_types import KernelProfile, ProfileBuildError
from ea_flow.profile_bridge import load_flow_profile_from_content


VALID_TOML = """\
[profile]
name = "TestFlow"
version = "1.0"
kernel_version = "0.1.0"

[categories]
StepType = "step_definition"
ProcessType = "process_spec"

[[elements]]
name = "IngestStep"
layer = "Core"
category = "StepType"

[[elements]]
name = "MainProcess"
layer = "Core"
category = "ProcessType"

[[relations]]
name = "contains"
kernel_relation = "contains"

[[rules]]
source = "@ProcessType"
target = "@StepType"
relation = "contains"
priority = 40
"""


class TestLoadFlowProfile:
    """load_flow_profile_from_content loads valid TOML into KernelProfile."""

    def test_valid_toml(self):
        profile = load_flow_profile_from_content(VALID_TOML)
        assert isinstance(profile, KernelProfile)
        assert profile.name == "TestFlow"
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
name = "contains"
kernel_relation = "contains"
"""
        with pytest.raises(ProfileBuildError):
            load_flow_profile_from_content(bad_toml)

    def test_invalid_kernel_relation(self):
        bad_toml = """\
[profile]
name = "Bad"
version = "1.0"
kernel_version = "0.1.0"

[categories]
StepType = "step_definition"

[[elements]]
name = "SomeStep"
layer = "Core"
category = "StepType"

[[relations]]
name = "bad_rel"
kernel_relation = "nonexistent_relation"
"""
        with pytest.raises(ProfileBuildError):
            load_flow_profile_from_content(bad_toml)

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
        profile = load_flow_profile_from_content(bad_toml, validate=False)
        assert profile.name == "Unvalidated"

    def test_flow_condition_used(self):
        """Flow-specific conditions can be used in rules."""
        toml_with_condition = """\
[profile]
name = "CondTest"
version = "1.0"
kernel_version = "0.1.0"

[categories]
StepType = "step_definition"

[[elements]]
name = "StepA"
layer = "Core"
category = "StepType"

[[relations]]
name = "next"
kernel_relation = "next"

[[rules]]
source = "*"
target = "*"
relation = "next"
priority = 40
conditions = ["SAME_PLANE"]
"""
        profile = load_flow_profile_from_content(toml_with_condition)
        allow_rules = [r for r in profile.validity_rules if r.valid and r.priority > 1]
        assert len(allow_rules) == 1
        assert allow_rules[0].conditions[0].condition_type == "same_plane"
