"""Test suite for ea_profile.schema module."""

import pytest
from dataclasses import dataclass
from ea_profile.builder import ProfileBuilder
from ea_profile.schema import ProfileSchema


@dataclass(frozen=True)
class MockEntity:
    """Mock schema entity for coverage testing."""
    name: str
    is_abstract: bool = False


@dataclass(frozen=True)
class MockRelation:
    """Mock schema relation for coverage testing."""
    name: str


class MockSchema:
    """Mock schema implementation for testing."""

    def __init__(self, entities, relations):
        self._entities = entities
        self._relations = relations

    @property
    def entities(self):
        return self._entities

    @property
    def relations(self):
        return self._relations


def _make_profile(name="TestProfile", version="1.0"):
    """Build a test profile with elements and rules."""
    b = ProfileBuilder(name, version=version, kernel_version="1.0")
    b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
    b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
    b.element("ElemC", kernel_type="step", layer="Application", category="Behavior")
    b.relation("Rel1", kernel_relation="association")
    b.relation("Rel2", kernel_relation="composition")
    b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
    b.deny("@Behavior", "@Structure", "Rel1", priority=40, rule_id="r-02")
    b.deny("*", "*", "Rel1", priority=0, notes="fallback", rule_id="fb-Rel1-deny")
    return b.build(auto_fallback=False)


class TestProfileSchemaProperties:
    """Test ProfileSchema property accessors."""

    def test_profile_property(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        assert schema.profile is profile

    def test_layers(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        layers = schema.layers
        assert isinstance(layers, tuple)
        assert set(layers) == {"Business", "Application"}

    def test_categories(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        categories = schema.categories
        assert isinstance(categories, tuple)
        assert set(categories) == {"Structure", "Behavior"}

    def test_kernel_types_used(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        types = schema.kernel_types_used
        assert isinstance(types, tuple)
        assert set(types) == {"structure", "item", "step"}

    def test_kernel_relations_used(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        relations = schema.kernel_relations_used
        assert isinstance(relations, tuple)
        assert set(relations) == {"association", "composition"}


class TestResolvePattern:
    """Test ProfileSchema.resolve_pattern method."""

    def test_resolve_pattern_exact(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        elems = schema.resolve_pattern("ElemA")
        assert len(elems) == 1
        assert elems[0].name == "ElemA"

    def test_resolve_pattern_wildcard(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        elems = schema.resolve_pattern("*")
        assert len(elems) == 3
        assert set(e.name for e in elems) == {"ElemA", "ElemB", "ElemC"}

    def test_resolve_pattern_category(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        elems = schema.resolve_pattern("@Structure")
        assert len(elems) == 2
        assert set(e.name for e in elems) == {"ElemA", "ElemB"}

    def test_resolve_pattern_layer(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        elems = schema.resolve_pattern("#Business")
        assert len(elems) == 2
        assert set(e.name for e in elems) == {"ElemA", "ElemB"}

    def test_resolve_pattern_nonexistent(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        elems = schema.resolve_pattern("NonExistent")
        assert len(elems) == 0


class TestCoverage:
    """Test ProfileSchema coverage calculation methods."""

    def test_element_coverage_full(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        mock_schema = MockSchema(
            entities=[
                MockEntity("structure"),
                MockEntity("item"),
                MockEntity("step"),
            ],
            relations=[]
        )
        coverage = schema.element_coverage(mock_schema)
        assert coverage == 1.0

    def test_element_coverage_partial(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        mock_schema = MockSchema(
            entities=[
                MockEntity("structure"),
                MockEntity("item"),
                MockEntity("step"),
                MockEntity("unused_type"),
            ],
            relations=[]
        )
        coverage = schema.element_coverage(mock_schema)
        assert coverage == 0.75

    def test_element_coverage_empty_schema(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        mock_schema = MockSchema(entities=[], relations=[])
        coverage = schema.element_coverage(mock_schema)
        assert coverage == 0.0

    def test_relation_coverage_full(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        mock_schema = MockSchema(
            entities=[],
            relations=[
                MockRelation("association"),
                MockRelation("composition"),
            ]
        )
        coverage = schema.relation_coverage(mock_schema)
        assert coverage == 1.0

    def test_relation_coverage_partial(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        mock_schema = MockSchema(
            entities=[],
            relations=[
                MockRelation("association"),
                MockRelation("composition"),
                MockRelation("unused_relation"),
            ]
        )
        coverage = schema.relation_coverage(mock_schema)
        assert coverage == pytest.approx(0.666, rel=0.01)

    def test_relation_coverage_empty_schema(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        mock_schema = MockSchema(entities=[], relations=[])
        coverage = schema.relation_coverage(mock_schema)
        assert coverage == 0.0


class TestRulesForRelation:
    """Test ProfileSchema.rules_for_relation method."""

    def test_rules_for_relation_rel1(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        rules = schema.rules_for_relation("Rel1")
        assert len(rules) == 3
        assert set(r.id for r in rules) == {"r-01", "r-02", "fb-Rel1-deny"}

    def test_rules_for_relation_rel2(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        rules = schema.rules_for_relation("Rel2")
        assert len(rules) == 0

    def test_rules_for_relation_nonexistent(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        rules = schema.rules_for_relation("nonexistent")
        assert len(rules) == 0


class TestRulesBetween:
    """Test ProfileSchema.rules_between method."""

    def test_rules_between_exact_match(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        # Pass element names — both ElemA and ElemB are in @Structure
        rules = schema.rules_between("ElemA", "ElemB")
        assert len(rules) >= 1
        assert any(r.id == "r-01" for r in rules)

    def test_rules_between_wildcard(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        rules = schema.rules_between("*", "*")
        assert len(rules) >= 1
        assert any(r.id == "fb-Rel1-deny" for r in rules)

    def test_rules_between_category_pattern(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        # ElemC is in @Behavior, ElemA is in @Structure
        rules = schema.rules_between("ElemC", "ElemA")
        assert len(rules) >= 1
        assert any(r.id == "r-02" for r in rules)

    def test_rules_between_no_match(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        rules = schema.rules_between("NonExistent", "AlsoNonExistent")
        # Should still match wildcard rule
        assert any(r.id == "fb-Rel1-deny" for r in rules)


class TestEffectiveRule:
    """Test ProfileSchema.effective_rule method."""

    def test_effective_rule_highest_priority(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        # effective_rule takes element names as strings, relation as relationship_name
        rule = schema.effective_rule("ElemA", "ElemB", "Rel1")
        assert rule is not None
        assert rule.id == "r-01"
        assert rule.priority == 50

    def test_effective_rule_deny_wins_at_same_priority(self):
        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("X", kernel_type="item", layer="Business", category="Cat1")
        b.element("Y", kernel_type="item", layer="Business", category="Cat2")
        b.relation("Rel", kernel_relation="test_rel")
        b.allow("@Cat1", "@Cat2", "Rel", priority=50, rule_id="allow-rule")
        b.deny("@Cat1", "@Cat2", "Rel", priority=50, rule_id="deny-rule")
        profile = b.build(auto_fallback=False)
        schema = ProfileSchema(profile)

        rule = schema.effective_rule("X", "Y", "Rel")
        assert rule is not None
        assert rule.id == "deny-rule"
        assert rule.valid is False

    def test_effective_rule_returns_none_when_no_match(self):
        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("X", kernel_type="item", layer="Business", category="Cat1")
        b.element("Y", kernel_type="item", layer="Business", category="Cat2")
        b.relation("Rel", kernel_relation="test_rel")
        # No rules defined
        profile = b.build(auto_fallback=False)
        schema = ProfileSchema(profile)

        rule = schema.effective_rule("X", "Y", "Rel")
        assert rule is None

    def test_effective_rule_wildcard_fallback(self):
        profile = _make_profile()
        schema = ProfileSchema(profile)
        # ElemC is in Behavior, ElemB is in Structure
        # Should match r-02 (@Behavior→@Structure, priority 40) over fb-Rel1-deny (*, priority 0)
        rule = schema.effective_rule("ElemC", "ElemB", "Rel1")
        assert rule is not None
        assert rule.id == "r-02"
        assert rule.priority == 40
