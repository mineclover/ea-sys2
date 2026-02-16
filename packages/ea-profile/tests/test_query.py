"""Test suite for ea_profile.query module."""

import pytest
from ea_profile.builder import ProfileBuilder
from ea_profile.query import ProfileQuery, ElementQuery, RuleQuery


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


class TestElementQuery:
    """Test ElementQuery filtering and retrieval methods."""

    def test_in_layer(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).in_layer("Business")
        assert q.count() == 2
        assert set(q.names()) == {"ElemA", "ElemB"}

    def test_in_category(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).in_category("Structure")
        assert q.count() == 2
        assert set(q.names()) == {"ElemA", "ElemB"}

    def test_with_kernel_type(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).with_kernel_type("structure")
        assert q.count() == 1
        assert q.names() == ("ElemA",)

    def test_matching_exact(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).matching("ElemA")
        assert q.count() == 1
        assert q.names() == ("ElemA",)

    def test_matching_wildcard(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).matching("*")
        assert q.count() == 3
        assert set(q.names()) == {"ElemA", "ElemB", "ElemC"}

    def test_matching_category(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).matching("@Structure")
        assert q.count() == 2
        assert set(q.names()) == {"ElemA", "ElemB"}

    def test_matching_layer(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).matching("#Business")
        assert q.count() == 2
        assert set(q.names()) == {"ElemA", "ElemB"}

    def test_names(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements)
        names = q.names()
        assert isinstance(names, tuple)
        assert len(names) == 3
        assert set(names) == {"ElemA", "ElemB", "ElemC"}

    def test_count(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements)
        assert q.count() == 3

    def test_first_found(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).matching("ElemA")
        elem = q.first()
        assert elem is not None
        assert elem.name == "ElemA"

    def test_first_empty(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).matching("NonExistent")
        elem = q.first()
        assert elem is None

    def test_all(self):
        profile = _make_profile()
        q = ElementQuery(profile.elements).in_layer("Business")
        elems = q.all()
        assert isinstance(elems, tuple)
        assert len(elems) == 2
        assert set(e.name for e in elems) == {"ElemA", "ElemB"}

    def test_chaining_multiple_filters(self):
        profile = _make_profile()
        q = (ElementQuery(profile.elements)
             .in_layer("Business")
             .in_category("Structure")
             .with_kernel_type("structure"))
        assert q.count() == 1
        assert q.names() == ("ElemA",)


class TestRuleQuery:
    """Test RuleQuery filtering and retrieval methods."""

    def test_for_relation(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).for_relation("Rel1")
        assert q.count() == 3

    def test_allow_only(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).allow_only()
        assert q.count() == 1
        assert q.ids() == ("r-01",)

    def test_deny_only(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).deny_only()
        assert q.count() == 2
        assert set(q.ids()) == {"r-02", "fb-Rel1-deny"}

    def test_with_priority_above(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).with_priority_above(30)
        assert q.count() == 2
        assert set(q.ids()) == {"r-01", "r-02"}

    def test_with_priority_below(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).with_priority_below(30)
        assert q.count() == 1
        assert q.ids() == ("fb-Rel1-deny",)

    def test_with_source(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).with_source("@Structure")
        assert q.count() == 1
        assert q.ids() == ("r-01",)

    def test_with_target(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).with_target("@Structure")
        assert q.count() == 2
        assert set(q.ids()) == {"r-01", "r-02"}

    def test_count(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules)
        assert q.count() == 3

    def test_first_found(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).allow_only()
        rule = q.first()
        assert rule is not None
        assert rule.id == "r-01"

    def test_first_empty(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).for_relation("nonexistent")
        rule = q.first()
        assert rule is None

    def test_all(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules).deny_only()
        rules = q.all()
        assert isinstance(rules, tuple)
        assert len(rules) == 2
        assert set(r.id for r in rules) == {"r-02", "fb-Rel1-deny"}

    def test_ids(self):
        profile = _make_profile()
        q = RuleQuery(profile.validity_rules)
        ids = q.ids()
        assert isinstance(ids, tuple)
        assert len(ids) == 3
        assert set(ids) == {"r-01", "r-02", "fb-Rel1-deny"}

    def test_chaining_multiple_filters(self):
        profile = _make_profile()
        q = (RuleQuery(profile.validity_rules)
             .for_relation("Rel1")
             .deny_only()
             .with_priority_above(10))
        assert q.count() == 1
        assert q.ids() == ("r-02",)


class TestProfileQuery:
    """Test ProfileQuery integration with ElementQuery and RuleQuery."""

    def test_elements_returns_element_query(self):
        profile = _make_profile()
        pq = ProfileQuery(profile)
        eq = pq.elements()
        assert isinstance(eq, ElementQuery)
        assert eq.count() == 3

    def test_rules_returns_rule_query(self):
        profile = _make_profile()
        pq = ProfileQuery(profile)
        rq = pq.rules()
        assert isinstance(rq, RuleQuery)
        assert rq.count() == 3

    def test_elements_chaining(self):
        profile = _make_profile()
        pq = ProfileQuery(profile)
        names = pq.elements().in_layer("Business").names()
        assert set(names) == {"ElemA", "ElemB"}

    def test_rules_chaining(self):
        profile = _make_profile()
        pq = ProfileQuery(profile)
        ids = pq.rules().allow_only().ids()
        assert ids == ("r-01",)
