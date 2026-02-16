"""Tests for ea_infra.profile_bridge — infra profile loading."""

import pytest

from ea_infra.profile_bridge import load_infra_profile, load_infra_profile_from_content


VALID_INFRA_TOML = """\
[profile]
name = "TestInfra"
version = "1.0"
kernel_version = "2.0"

[categories]
ActiveStructure = "data_platform_service"

[[elements]]
name = "Svc"
layer = "Infra"
category = "ActiveStructure"

[[relations]]
name = "contains"
kernel_relation = "contains"
"""


class TestLoadFromContent:
    def test_load_valid_content_no_validate(self):
        p = load_infra_profile_from_content(VALID_INFRA_TOML, validate=False)
        assert p.name == "TestInfra"
        assert len(p.elements) == 1

    def test_load_valid_content_with_validate(self):
        p = load_infra_profile_from_content(VALID_INFRA_TOML, validate=True)
        assert p.name == "TestInfra"


class TestLoadFromFile:
    def test_load_valid_file(self, tmp_path):
        f = tmp_path / "infra.toml"
        f.write_text(VALID_INFRA_TOML, encoding="utf-8")
        p = load_infra_profile(f, validate=False)
        assert p.name == "TestInfra"

    def test_load_valid_file_with_validate(self, tmp_path):
        f = tmp_path / "infra.toml"
        f.write_text(VALID_INFRA_TOML, encoding="utf-8")
        p = load_infra_profile(f, validate=True)
        assert p.name == "TestInfra"


class TestConditionRegistryIntegration:
    def test_infra_conditions_resolved(self):
        toml = """\
[profile]
name = "InfraCond"
version = "1.0"
kernel_version = "2.0"

[[elements]]
name = "A"
layer = "Infra"
category = "Store"
kernel_type = "version_store"

[[relations]]
name = "contains"
kernel_relation = "contains"

[[rules]]
source = "A"
target = "A"
relation = "contains"
conditions = ["SAME_STORAGE_TIER"]
"""
        p = load_infra_profile_from_content(toml, validate=False)
        cond_rules = [r for r in p.validity_rules if r.conditions]
        assert len(cond_rules) == 1
        assert cond_rules[0].conditions[0].condition_type == "same_storage_tier"
