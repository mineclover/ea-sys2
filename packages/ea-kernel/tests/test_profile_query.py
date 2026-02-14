"""Tests for profile_query — Chainable element/rule query."""

from __future__ import annotations

import pytest
from ea_kernel.profile_query import ProfileQuery
from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileRelation
from ea_kernel.types import KernelValidityRule


def _make_profile() -> KernelProfile:
    return KernelProfile(
        name="Test",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("A1", "structure", "LayerA", "Cat1"),
            ProfileElement("A2", "step", "LayerA", "Cat2"),
            ProfileElement("B1", "item", "LayerB", "Cat1"),
            ProfileElement("B2", "feature", "LayerB", "Cat2"),
        ),
        relations=(
            ProfileRelation("rel1", "association"),
            ProfileRelation("rel2", "composition"),
        ),
        validity_rules=(
            KernelValidityRule(
                id="allow-1", source_pattern="@Cat1", target_pattern="@Cat2",
                relationship_name="rel1", valid=True, priority=40,
            ),
            KernelValidityRule(
                id="allow-2", source_pattern="A1", target_pattern="B1",
                relationship_name="rel2", valid=True, priority=50,
            ),
            KernelValidityRule(
                id="deny-1", source_pattern="*", target_pattern="*",
                relationship_name="rel1", valid=False, priority=1,
            ),
        ),
    )


class TestElementQuery:
    def test_all(self):
        q = ProfileQuery(_make_profile())
        assert q.elements().count() == 4

    def test_in_layer(self):
        q = ProfileQuery(_make_profile())
        result = q.elements().in_layer("LayerA")
        assert result.count() == 2
        assert set(result.names()) == {"A1", "A2"}

    def test_in_category(self):
        q = ProfileQuery(_make_profile())
        result = q.elements().in_category("Cat1")
        assert result.count() == 2
        assert set(result.names()) == {"A1", "B1"}

    def test_with_kernel_type(self):
        q = ProfileQuery(_make_profile())
        result = q.elements().with_kernel_type("structure")
        assert result.count() == 1
        assert result.first().name == "A1"

    def test_chain(self):
        q = ProfileQuery(_make_profile())
        result = q.elements().in_layer("LayerA").in_category("Cat1")
        assert result.count() == 1
        assert result.first().name == "A1"

    def test_matching_wildcard(self):
        q = ProfileQuery(_make_profile())
        assert q.elements().matching("*").count() == 4

    def test_matching_category(self):
        q = ProfileQuery(_make_profile())
        assert q.elements().matching("@Cat2").count() == 2

    def test_matching_layer(self):
        q = ProfileQuery(_make_profile())
        assert q.elements().matching("#LayerB").count() == 2

    def test_matching_exact(self):
        q = ProfileQuery(_make_profile())
        assert q.elements().matching("B2").count() == 1

    def test_empty_result(self):
        q = ProfileQuery(_make_profile())
        result = q.elements().in_layer("Nonexistent")
        assert result.count() == 0
        assert result.first() is None
        assert result.names() == ()
        assert result.all() == ()


class TestRuleQuery:
    def test_all(self):
        q = ProfileQuery(_make_profile())
        assert q.rules().count() == 3

    def test_for_relation(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().for_relation("rel1")
        assert result.count() == 2  # allow-1 + deny-1

    def test_allow_only(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().allow_only()
        assert result.count() == 2
        assert all(r.valid for r in result.all())

    def test_deny_only(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().deny_only()
        assert result.count() == 1
        assert result.first().id == "deny-1"

    def test_with_priority_above(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().with_priority_above(10)
        assert result.count() == 2  # priority 40 and 50

    def test_with_priority_below(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().with_priority_below(45)
        assert result.count() == 2  # priority 40 and 1

    def test_with_source(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().with_source("@Cat1")
        assert result.count() == 1
        assert result.first().id == "allow-1"

    def test_with_target(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().with_target("*")
        assert result.count() == 1
        assert result.first().id == "deny-1"

    def test_chain(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().for_relation("rel1").allow_only()
        assert result.count() == 1
        assert result.first().id == "allow-1"

    def test_ids(self):
        q = ProfileQuery(_make_profile())
        ids = q.rules().ids()
        assert set(ids) == {"allow-1", "allow-2", "deny-1"}

    def test_empty_result(self):
        q = ProfileQuery(_make_profile())
        result = q.rules().for_relation("nonexistent")
        assert result.count() == 0
        assert result.first() is None
        assert result.all() == ()
        assert result.ids() == ()


class TestBuiltinProfiles:
    @pytest.mark.parametrize("module_path,var_name", [
        ("ea_kernel.profiles.archimate", "ARCHIMATE_PROFILE"),
        ("ea_kernel.profiles.togaf", "TOGAF_PROFILE"),
        ("ea_kernel.profiles.zachman", "ZACHMAN_PROFILE"),
        ("ea_kernel.profiles.bpmn", "BPMN_PROFILE"),
        ("ea_kernel.profiles.sysml2", "SYSML2_PROFILE"),
    ])
    def test_query_all_profiles(self, module_path, var_name):
        import importlib
        mod = importlib.import_module(module_path)
        profile = getattr(mod, var_name)
        q = ProfileQuery(profile)
        assert q.elements().count() == len(profile.elements)
        assert q.rules().count() == len(profile.validity_rules)
        # Chainable filters should not crash
        for layer in profile.domain_layers():
            q.elements().in_layer(layer).count()
