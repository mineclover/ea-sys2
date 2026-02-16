"""Tests for ea_profile.types — core types, patterns, and condition registry."""

import pytest

from ea_profile.types import (
    ConditionRegistry,
    KernelProfile,
    PatternType,
    ProfileBuildError,
    ProfileElement,
    ProfileRelation,
    ProfileRule,
    RuleCondition,
    SchemaPort,
    classify_pattern,
    match_pattern,
)


# ---------------------------------------------------------------------------
# Frozen dataclass creation
# ---------------------------------------------------------------------------

class TestFrozenTypes:
    def test_profile_element_creation(self):
        e = ProfileElement(name="Svc", kernel_type="structure", layer="Business", category="Active")
        assert e.name == "Svc"
        assert e.kernel_type == "structure"
        assert e.layer == "Business"
        assert e.category == "Active"

    def test_profile_relation_creation(self):
        r = ProfileRelation(name="uses", kernel_relation="association")
        assert r.name == "uses"
        assert r.kernel_relation == "association"
        assert r.direction == ""

    def test_profile_rule_creation(self):
        rule = ProfileRule(
            id="r-01",
            source_pattern="@Behavior",
            target_pattern="*",
            relationship_name="assoc",
            valid=True,
            priority=40,
        )
        assert rule.id == "r-01"
        assert rule.valid is True
        assert rule.conditions == ()

    def test_rule_condition_creation(self):
        c = RuleCondition(condition_type="same_layer")
        assert c.condition_type == "same_layer"
        assert c.parameters == ()

    def test_rule_condition_with_params(self):
        c = RuleCondition(condition_type="layer_order", parameters=(("direction", "up"),))
        assert c.parameters == (("direction", "up"),)


# ---------------------------------------------------------------------------
# KernelProfile
# ---------------------------------------------------------------------------

class TestKernelProfile:
    @pytest.fixture()
    def profile(self):
        return KernelProfile(
            name="Test",
            version="1.0",
            kernel_version="2.0",
            elements=(
                ProfileElement("A", "structure", "Business", "Active"),
                ProfileElement("B", "step", "Business", "Behavior"),
                ProfileElement("C", "item", "Tech", "Passive"),
            ),
            relations=(
                ProfileRelation("uses", "association"),
            ),
        )

    def test_get_element(self, profile):
        assert profile.get_element("A") is not None
        assert profile.get_element("A").kernel_type == "structure"
        assert profile.get_element("Z") is None

    def test_get_relation(self, profile):
        assert profile.get_relation("uses") is not None
        assert profile.get_relation("missing") is None

    def test_elements_in_layer(self, profile):
        biz = profile.elements_in_layer("Business")
        assert len(biz) == 2

    def test_elements_in_category(self, profile):
        active = profile.elements_in_category("Active")
        assert len(active) == 1

    def test_matching_elements_wildcard(self, profile):
        assert len(profile.matching_elements("*")) == 3

    def test_matching_elements_category(self, profile):
        assert len(profile.matching_elements("@Behavior")) == 1

    def test_matching_elements_layer(self, profile):
        assert len(profile.matching_elements("#Tech")) == 1

    def test_matching_elements_exact(self, profile):
        assert len(profile.matching_elements("A")) == 1
        assert len(profile.matching_elements("Z")) == 0


# ---------------------------------------------------------------------------
# ConditionRegistry
# ---------------------------------------------------------------------------

class TestConditionRegistry:
    def test_kernel_default(self):
        reg = ConditionRegistry.kernel_default()
        assert len(reg._map) == 5
        assert reg.resolve("SAME_LAYER") == "same_layer"
        assert reg.resolve("LAYER_ORDER") == "layer_order"

    def test_register_and_resolve(self):
        reg = ConditionRegistry()
        reg.register("MY_COND", "my_condition_type")
        assert reg.resolve("MY_COND") == "my_condition_type"
        assert reg.resolve("UNKNOWN") is None


# ---------------------------------------------------------------------------
# SchemaPort Protocol
# ---------------------------------------------------------------------------

class TestSchemaPort:
    def test_runtime_checkable(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _Entity:
            name: str
            is_abstract: bool = False

        @dataclass(frozen=True)
        class _Relation:
            name: str

        @dataclass(frozen=True)
        class _FakeSchema:
            entities: tuple[_Entity, ...] = ()
            relations: tuple[_Relation, ...] = ()

        schema = _FakeSchema(
            entities=(_Entity("e1"),),
            relations=(_Relation("r1"),),
        )
        assert isinstance(schema, SchemaPort)


# ---------------------------------------------------------------------------
# Pattern classification and matching
# ---------------------------------------------------------------------------

class TestPatternUtils:
    def test_classify_wildcard(self):
        assert classify_pattern("*") == PatternType.WILDCARD

    def test_classify_category(self):
        assert classify_pattern("@Behavior") == PatternType.CATEGORY

    def test_classify_layer(self):
        assert classify_pattern("#Business") == PatternType.LAYER

    def test_classify_exact(self):
        assert classify_pattern("MyElement") == PatternType.EXACT

    def test_match_pattern_wildcard(self):
        e = ProfileElement("X", "structure", "L1", "Cat1")
        assert match_pattern(e, "*") is True

    def test_match_pattern_category(self):
        e = ProfileElement("X", "structure", "L1", "Cat1")
        assert match_pattern(e, "@Cat1") is True
        assert match_pattern(e, "@Cat2") is False

    def test_match_pattern_layer(self):
        e = ProfileElement("X", "structure", "L1", "Cat1")
        assert match_pattern(e, "#L1") is True
        assert match_pattern(e, "#L2") is False

    def test_match_pattern_exact(self):
        e = ProfileElement("X", "structure", "L1", "Cat1")
        assert match_pattern(e, "X") is True
        assert match_pattern(e, "Y") is False


# ---------------------------------------------------------------------------
# ProfileBuildError
# ---------------------------------------------------------------------------

class TestProfileBuildError:
    def test_error_stores_list(self):
        err = ProfileBuildError(["err1", "err2"])
        assert err.errors == ["err1", "err2"]
        assert "2 build error" in str(err)
