"""Tests for profile_bridge.py — Decision profile loading."""

import pytest

from ea_kernel.profile_types import KernelProfile, ProfileBuildError
from ea_decision.profile_bridge import load_decision_profile_from_content


VALID_TOML = """\
[profile]
name = "TestDecision"
version = "1.0"
kernel_version = "0.1.0"

[categories]
TopicType = "topic"
EvidenceType = "evidence"

[[elements]]
name = "ArchDecisionTopic"
layer = "Core"
category = "TopicType"

[[elements]]
name = "DesignEvidence"
layer = "Core"
category = "EvidenceType"

[[relations]]
name = "justifies"
kernel_relation = "justifies"

[[rules]]
source = "@EvidenceType"
target = "@TopicType"
relation = "justifies"
priority = 40
"""


class TestLoadDecisionProfile:
    """load_decision_profile_from_content loads valid TOML into KernelProfile."""

    def test_valid_toml(self):
        profile = load_decision_profile_from_content(VALID_TOML)
        assert isinstance(profile, KernelProfile)
        assert profile.name == "TestDecision"
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
name = "justifies"
kernel_relation = "justifies"
"""
        with pytest.raises(ProfileBuildError):
            load_decision_profile_from_content(bad_toml)

    def test_invalid_kernel_relation(self):
        bad_toml = """\
[profile]
name = "Bad"
version = "1.0"
kernel_version = "0.1.0"

[categories]
TopicType = "topic"

[[elements]]
name = "SomeTopic"
layer = "Core"
category = "TopicType"

[[relations]]
name = "bad_rel"
kernel_relation = "nonexistent_relation"
"""
        with pytest.raises(ProfileBuildError):
            load_decision_profile_from_content(bad_toml)

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
        profile = load_decision_profile_from_content(bad_toml, validate=False)
        assert profile.name == "Unvalidated"

    def test_decision_condition_used(self):
        """Decision-specific conditions can be used in rules."""
        toml_with_condition = """\
[profile]
name = "CondTest"
version = "1.0"
kernel_version = "0.1.0"

[categories]
TopicType = "topic"

[[elements]]
name = "TopicA"
layer = "Core"
category = "TopicType"

[[relations]]
name = "depends_on"
kernel_relation = "depends_on"

[[rules]]
source = "*"
target = "*"
relation = "depends_on"
priority = 40
conditions = ["SAME_LIFECYCLE_STATE"]
"""
        profile = load_decision_profile_from_content(toml_with_condition)
        allow_rules = [r for r in profile.validity_rules if r.valid and r.priority > 1]
        assert len(allow_rules) == 1
        assert allow_rules[0].conditions[0].condition_type == "same_lifecycle_state"
