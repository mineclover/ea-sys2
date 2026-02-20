"""Tests for ea_profile.builder — ProfileBuilder fluent API."""

import pytest

from ea_profile.builder import ProfileBuilder
from ea_profile.types import (
    KernelProfile,
    ProfileBuildError,
    ProfileMetadata,
    RuleCondition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_builder() -> ProfileBuilder:
    """Builder with minimal valid content."""
    return (
        ProfileBuilder("Test", version="1.0", kernel_version="2.0")
        .element("A", layer="L1", category="Cat", kernel_type="structure")
        .relation("rel", kernel_relation="association")
    )


# ---------------------------------------------------------------------------
# Basic build
# ---------------------------------------------------------------------------

class TestBasicBuild:
    def test_build_returns_kernel_profile(self):
        p = _minimal_builder().build()
        assert isinstance(p, KernelProfile)
        assert p.name == "Test"
        assert p.version == "1.0"
        assert p.kernel_version == "2.0"

    def test_elements_and_relations(self):
        p = _minimal_builder().build()
        assert len(p.elements) == 1
        assert len(p.relations) == 1
        assert p.elements[0].name == "A"
        assert p.relations[0].name == "rel"


# ---------------------------------------------------------------------------
# Fluent API
# ---------------------------------------------------------------------------

class TestFluentAPI:
    def test_id_prefix(self):
        p = (
            ProfileBuilder("PFX", version="1.0", kernel_version="2.0")
            .id_prefix("pfx")
            .element("E", layer="L", category="C", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .allow("E", "E", "r")
            .build()
        )
        allow_rules = [r for r in p.validity_rules if r.valid and r.priority > 1]
        assert allow_rules[0].id.startswith("pfx-")

    def test_metadata(self):
        p = (
            _minimal_builder()
            .metadata(standard="S1", organization="O1")
            .build()
        )
        assert p.metadata is not None
        assert isinstance(p.metadata, ProfileMetadata)
        assert p.metadata.standard == "S1"
        assert p.metadata.organization == "O1"

    def test_metadata_with_extra(self):
        p = (
            _minimal_builder()
            .metadata(standard="S", organization="O", extra={"k": "v"})
            .build()
        )
        assert p.metadata.extra == {"k": "v"}

    def test_category_mapping_auto_inference(self):
        p = (
            ProfileBuilder("CM", version="1.0", kernel_version="2.0")
            .category_mapping({"Behavior": "step"})
            .element("Act", layer="L", category="Behavior")
            .relation("r", kernel_relation="association")
            .build()
        )
        assert p.elements[0].kernel_type == "step"

    def test_category_mapping_no_match_raises(self):
        with pytest.raises(ProfileBuildError, match="not in category_mapping"):
            (
                ProfileBuilder("CM", version="1.0", kernel_version="2.0")
                .element("X", layer="L", category="Unknown")
            )

    def test_add_state_transition(self):
        p = (
            _minimal_builder()
            .add_state_transition(
                "draft",
                "approved",
                guard_condition="has_review",
                description="Review complete",
            )
            .build()
        )
        assert len(p.state_transitions) == 1
        transition = p.state_transitions[0]
        assert transition.from_state == "draft"
        assert transition.to_state == "approved"
        assert transition.guard_condition == "has_review"
        assert transition.description == "Review complete"


# ---------------------------------------------------------------------------
# Element / Relation
# ---------------------------------------------------------------------------

class TestElementRelation:
    def test_element_explicit_kernel_type(self):
        p = (
            ProfileBuilder("E", version="1.0", kernel_version="2.0")
            .element("X", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .build()
        )
        assert p.elements[0].kernel_type == "item"

    def test_relation_with_direction(self):
        p = (
            ProfileBuilder("R", version="1.0", kernel_version="2.0")
            .element("X", layer="L", category="C", kernel_type="structure")
            .relation("flow_out", kernel_relation="flow", direction="out")
            .build()
        )
        assert p.relations[0].direction == "out"

    def test_relations_bulk(self):
        p = (
            ProfileBuilder("RB", version="1.0", kernel_version="2.0")
            .element("X", layer="L", category="C", kernel_type="structure")
            .relations(
                ("r1", "association"),
                ("r2", "flow", "data flow"),
                ("r3", "succession", "seq", "out"),
            )
            .build()
        )
        assert len(p.relations) == 3
        assert p.relations[1].description == "data flow"
        assert p.relations[2].direction == "out"


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

class TestRules:
    def test_allow_and_deny(self):
        p = (
            _minimal_builder()
            .allow("A", "A", "rel", priority=50)
            .deny("A", "A", "rel", priority=80)
            .build()
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        allows = [r for r in explicit if r.valid]
        denies = [r for r in explicit if not r.valid]
        assert len(allows) == 1
        assert len(denies) == 1

    def test_allow_same_category(self):
        p = (
            _minimal_builder()
            .allow_same_category("rel")
            .build()
        )
        cond_rules = [r for r in p.validity_rules if r.conditions]
        assert len(cond_rules) == 1
        assert cond_rules[0].conditions[0].condition_type == "same_category"

    def test_allow_same_layer(self):
        p = (
            _minimal_builder()
            .allow_same_layer("rel")
            .build()
        )
        cond_rules = [r for r in p.validity_rules if r.conditions]
        assert len(cond_rules) == 1
        assert cond_rules[0].conditions[0].condition_type == "same_layer"

    def test_rule_group(self):
        b = (
            ProfileBuilder("RG", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="C1", kernel_type="structure")
            .element("B", layer="L", category="C2", kernel_type="item")
            .relation("r", kernel_relation="association")
        )
        b.rule_group("r", [("A", "B"), ("B", "A")])
        p = b.build()
        explicit = [r for r in p.validity_rules if r.valid and r.priority > 1]
        assert len(explicit) == 2

    def test_allow_with_scope(self):
        p = (
            _minimal_builder()
            .allow("A", "A", "rel", scope="sibling")
            .build()
        )
        scoped = [r for r in p.validity_rules if r.scope == "sibling"]
        assert len(scoped) == 1

    def test_deny_with_scope(self):
        p = (
            _minimal_builder()
            .deny("A", "A", "rel", scope="subtree")
            .build()
        )
        scoped = [r for r in p.validity_rules if r.scope == "subtree"]
        assert len(scoped) == 1


# ---------------------------------------------------------------------------
# Build options
# ---------------------------------------------------------------------------

class TestBuildOptions:
    def test_auto_fallback_generates_deny_rules(self):
        p = _minimal_builder().build(auto_fallback=True)
        fallbacks = [r for r in p.validity_rules if r.priority == 1 and not r.valid]
        assert len(fallbacks) == 1  # one per relation

    def test_auto_fallback_false(self):
        p = _minimal_builder().build(auto_fallback=False)
        fallbacks = [r for r in p.validity_rules if r.priority == 1]
        assert len(fallbacks) == 0

    def test_validate_false_skips_validation(self):
        # Build with unknown element ref in rule — should not raise with validate=False
        b = (
            ProfileBuilder("V", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="C", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .allow("A", "NONEXISTENT", "r")
        )
        p = b.build(validate=False)
        assert isinstance(p, KernelProfile)


# ---------------------------------------------------------------------------
# Build errors
# ---------------------------------------------------------------------------

class TestBuildErrors:
    def test_duplicate_element_names(self):
        with pytest.raises(ProfileBuildError, match="Duplicate element"):
            (
                ProfileBuilder("D", version="1.0", kernel_version="2.0")
                .element("A", layer="L", category="C", kernel_type="structure")
                .element("A", layer="L", category="C", kernel_type="structure")
                .relation("r", kernel_relation="association")
                .build()
            )

    def test_invalid_kernel_type_with_schema(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _Ent:
            name: str
            is_abstract: bool = False

        @dataclass(frozen=True)
        class _Rel:
            name: str

        @dataclass(frozen=True)
        class _Schema:
            entities: tuple[_Ent, ...] = ()
            relations: tuple[_Rel, ...] = ()

        schema = _Schema(
            entities=(_Ent("structure"),),
            relations=(_Rel("association"),),
        )
        with pytest.raises(ProfileBuildError, match="unknown kernel type"):
            (
                ProfileBuilder("K", version="1.0", kernel_version="2.0")
                .element("A", layer="L", category="C", kernel_type="bogus")
                .relation("r", kernel_relation="association")
                .build(schema)
            )

    def test_unknown_pattern_ref(self):
        with pytest.raises(ProfileBuildError, match="unknown element"):
            (
                ProfileBuilder("P", version="1.0", kernel_version="2.0")
                .element("A", layer="L", category="C", kernel_type="structure")
                .relation("r", kernel_relation="association")
                .allow("A", "MISSING", "r")
                .build()
            )

    def test_unknown_relation_in_rule(self):
        with pytest.raises(ProfileBuildError, match="unknown relation"):
            (
                ProfileBuilder("P", version="1.0", kernel_version="2.0")
                .element("A", layer="L", category="C", kernel_type="structure")
                .relation("r", kernel_relation="association")
                .allow("A", "A", "nonexistent")
                .build()
            )
