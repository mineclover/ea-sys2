"""Tests for profile diff and comparison."""

from __future__ import annotations

import pytest

from ea_profile.builder import ProfileBuilder
from ea_profile.diff import diff_profiles, diff_summary
from ea_profile.types import (
    DiffChangeType,
    KernelProfile,
    ProfileElement,
    ProfileRelation,
    ProfileRule,
    RuleCondition,
)


def _make_profile(name="TestProfile", version="1.0") -> KernelProfile:
    """Build a test profile with elements, relations, and rules."""
    b = ProfileBuilder(name, version=version, kernel_version="1.0")
    b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
    b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
    b.relation("Rel1", kernel_relation="association")
    b.relation("Rel2", kernel_relation="composition")
    b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
    b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
    return b.build()


class TestDiffProfiles:
    """Tests for diff_profiles() function."""

    def test_identical_profiles_no_changes(self):
        p1 = _make_profile()
        p2 = _make_profile()

        diff = diff_profiles(p1, p2)

        assert diff.identical is True
        assert len(diff.element_changes) == 0
        assert len(diff.relation_changes) == 0
        assert len(diff.rule_changes) == 0

    def test_added_element(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.element("ElemC", kernel_type="step", layer="Application", category="Behavior")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        assert len(diff.element_changes) == 1
        assert diff.element_changes[0].change_type == DiffChangeType.ADDED
        assert diff.element_changes[0].element_name == "ElemC"

    def test_removed_element(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        assert len(diff.element_changes) == 1
        assert diff.element_changes[0].change_type == DiffChangeType.REMOVED
        assert diff.element_changes[0].element_name == "ElemB"

    def test_modified_element_kernel_type_changed(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="step", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        assert len(diff.element_changes) == 1
        assert diff.element_changes[0].change_type == DiffChangeType.MODIFIED
        assert diff.element_changes[0].element_name == "ElemA"
        assert diff.element_changes[0].field == "kernel_type"
        assert diff.element_changes[0].old_value == "structure"
        assert diff.element_changes[0].new_value == "step"

    def test_added_relation(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.relation("Rel3", kernel_relation="dependency")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        assert len(diff.relation_changes) == 1
        assert diff.relation_changes[0].change_type == DiffChangeType.ADDED
        assert diff.relation_changes[0].relation_name == "Rel3"

    def test_removed_relation(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        # Should have 1 removed relation (Rel2)
        removed_rels = [c for c in diff.relation_changes if c.change_type == DiffChangeType.REMOVED]
        assert len(removed_rels) == 1
        assert removed_rels[0].relation_name == "Rel2"

    def test_modified_relation_kernel_relation_changed(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="dependency")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        modified_rel = next(
            c for c in diff.relation_changes
            if c.change_type == DiffChangeType.MODIFIED and c.relation_name == "Rel1"
        )
        assert modified_rel.field == "kernel_relation"
        assert modified_rel.old_value == "association"
        assert modified_rel.new_value == "dependency"

    def test_added_rule(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        b.allow("*", "*", "Rel1", priority=10, rule_id="r-03")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        assert len(diff.rule_changes) == 1
        assert diff.rule_changes[0].change_type == DiffChangeType.ADDED
        assert diff.rule_changes[0].rule_id == "r-03"

    def test_removed_rule(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        assert len(diff.rule_changes) == 1
        assert diff.rule_changes[0].change_type == DiffChangeType.REMOVED
        assert diff.rule_changes[0].rule_id == "r-02"

    def test_modified_rule_priority_changed(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        b.relation("Rel2", kernel_relation="composition")
        b.allow("@Structure", "@Structure", "Rel1", priority=100, rule_id="r-01")
        b.deny("@Structure", "@Structure", "Rel2", priority=40, rule_id="r-02")
        p2 = b.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        modified_rule = next(
            c for c in diff.rule_changes
            if c.change_type == DiffChangeType.MODIFIED and c.rule_id == "r-01"
        )
        assert modified_rule.field == "priority"
        assert modified_rule.old_value == "50"
        assert modified_rule.new_value == "100"

    def test_modified_rule_conditions_changed(self):
        b1 = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b1.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b1.relation("Rel1", kernel_relation="association")
        b1._rules.append(ProfileRule(
            id="r-01",
            source_pattern="@Structure",
            target_pattern="@Structure",
            relationship_name="Rel1",
            valid=True,
            priority=50,
            conditions=(
                RuleCondition(condition_type="same_layer", parameters=()),
            ),
        ))
        p1 = b1.build()

        b2 = ProfileBuilder("TestProfile", version="1.0", kernel_version="1.0")
        b2.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b2.relation("Rel1", kernel_relation="association")
        b2._rules.append(ProfileRule(
            id="r-01",
            source_pattern="@Structure",
            target_pattern="@Structure",
            relationship_name="Rel1",
            valid=True,
            priority=50,
            conditions=(
                RuleCondition(condition_type="layer_order", parameters=(("order", "Business>Application"),)),
            ),
        ))
        p2 = b2.build()

        diff = diff_profiles(p1, p2)

        assert diff.identical is False
        modified_rule = next(
            c for c in diff.rule_changes
            if c.change_type == DiffChangeType.MODIFIED and c.rule_id == "r-01"
        )
        assert modified_rule.field == "conditions"


class TestDiffSummary:
    """Tests for diff_summary() function."""

    def test_diff_summary_for_identical_profiles(self):
        p1 = _make_profile()
        p2 = _make_profile()
        diff = diff_profiles(p1, p2)

        summary = diff_summary(diff)

        assert "identical" in summary.lower()

    def test_diff_summary_contains_change_counts(self):
        p1 = _make_profile()

        b = ProfileBuilder("TestProfile", version="2.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="step", layer="Business", category="Structure")
        b.element("ElemC", kernel_type="step", layer="Application", category="Behavior")
        b.relation("Rel1", kernel_relation="dependency")
        b.relation("Rel3", kernel_relation="dependency")
        b.allow("*", "*", "Rel1", priority=10, rule_id="r-03")
        p2 = b.build()

        diff = diff_profiles(p1, p2)
        summary = diff_summary(diff)

        assert "Elements:" in summary
        assert "Relations:" in summary
        assert "Rules:" in summary
        # Check for presence of change indicators (may vary due to fallback rules)
        assert "+" in summary or "-" in summary or "~" in summary
