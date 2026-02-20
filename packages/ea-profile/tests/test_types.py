"""Tests for ea_profile.types — core types, patterns, and condition registry."""

import pytest

from ea_profile.types import (
    ConditionRegistry,
    KernelProfile,
    LayerDefinition,
    LayerStack,
    PatternType,
    ProfileArtifactType,
    ProfileBuildError,
    ProfileElement,
    ProfileRelation,
    ProfileRule,
    ProfileStateTransition,
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

    def test_profile_state_transition_creation(self):
        t = ProfileStateTransition(
            from_state="draft",
            to_state="approved",
            guard_condition="has_review",
            description="Review complete",
        )
        assert t.from_state == "draft"
        assert t.to_state == "approved"
        assert t.guard_condition == "has_review"
        assert t.description == "Review complete"

    def test_profile_artifact_type_creation(self):
        a = ProfileArtifactType(
            name="api_endpoint",
            tier="function",
            description="HTTP endpoint artifact",
            kernel_element_pattern="*Endpoint*",
        )
        assert a.name == "api_endpoint"
        assert a.tier == "function"
        assert a.description == "HTTP endpoint artifact"
        assert a.kernel_element_pattern == "*Endpoint*"

    def test_layer_definition_creation(self):
        layer = LayerDefinition(
            name="M1",
            order=1,
            depends_on=("M0",),
            responsibility="Modeling",
            model_perspective="Conceptual",
        )
        assert layer.name == "M1"
        assert layer.order == 1
        assert layer.depends_on == ("M0",)
        assert layer.responsibility == "Modeling"
        assert layer.model_perspective == "Conceptual"

    def test_layer_stack_creation(self):
        stack = LayerStack(
            layers=(LayerDefinition(name="M1", order=1),),
            definition_flow="top_down",
            runtime_flow="bottom_up",
            feedback_flow="closed_loop",
        )
        assert len(stack.layers) == 1
        assert stack.layers[0].name == "M1"
        assert stack.definition_flow == "top_down"
        assert stack.runtime_flow == "bottom_up"
        assert stack.feedback_flow == "closed_loop"

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
        assert rule.scope == ""

    def test_profile_rule_scope_default(self):
        rule = ProfileRule(id="r-s", source_pattern="A", target_pattern="B", relationship_name="rel")
        assert rule.scope == ""

    def test_profile_rule_scope_sibling(self):
        rule = ProfileRule(
            id="r-s", source_pattern="A", target_pattern="B",
            relationship_name="rel", scope="sibling",
        )
        assert rule.scope == "sibling"

    def test_profile_rule_scope_in_equality(self):
        r1 = ProfileRule(id="r", source_pattern="A", target_pattern="B", relationship_name="rel", scope="sibling")
        r2 = ProfileRule(id="r", source_pattern="A", target_pattern="B", relationship_name="rel", scope="sibling")
        r3 = ProfileRule(id="r", source_pattern="A", target_pattern="B", relationship_name="rel", scope="")
        assert r1 == r2
        assert r1 != r3

    def test_profile_rule_scope_in_hash(self):
        r1 = ProfileRule(id="r", source_pattern="A", target_pattern="B", relationship_name="rel", scope="sibling")
        r2 = ProfileRule(id="r", source_pattern="A", target_pattern="B", relationship_name="rel", scope="")
        assert hash(r1) != hash(r2)

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

    def test_state_transitions_default_empty(self, profile):
        assert profile.state_transitions == ()

    def test_artifact_types_default_empty(self, profile):
        assert profile.artifact_types == ()

    def test_layer_stack_default_none(self, profile):
        assert profile.layer_stack is None


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
