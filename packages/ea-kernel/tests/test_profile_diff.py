"""Tests for profile_diff — Structural diff between profiles."""

from __future__ import annotations

from ea_kernel.profile_types import DiffChangeType, KernelProfile, ProfileElement, ProfileRelation
from ea_kernel.types import KernelValidityRule
from ea_kernel.profile_diff import diff_profiles, diff_summary


_DEFAULT_ELEMENTS = (
    ProfileElement("E1", "structure", "L1", "Cat1"),
    ProfileElement("E2", "step", "L2", "Cat2"),
)
_DEFAULT_RELATIONS = (ProfileRelation("r1", "association"),)
_DEFAULT_RULES = (
    KernelValidityRule(
        id="rule-1", source_pattern="@Cat1", target_pattern="@Cat2",
        relationship_name="r1", valid=True, priority=40,
    ),
)


def _base_profile(
    name: str = "A",
    version: str = "1.0",
    elements: tuple[ProfileElement, ...] | None = None,
    relations: tuple[ProfileRelation, ...] | None = None,
    rules: tuple[KernelValidityRule, ...] | None = None,
) -> KernelProfile:
    return KernelProfile(
        name=name,
        version=version,
        kernel_version="2.5.0",
        elements=_DEFAULT_ELEMENTS if elements is None else elements,
        relations=_DEFAULT_RELATIONS if relations is None else relations,
        validity_rules=_DEFAULT_RULES if rules is None else rules,
    )


class TestIdentical:
    def test_same_profile(self):
        p = _base_profile()
        d = diff_profiles(p, p)
        assert d.identical is True
        assert d.element_changes == ()
        assert d.relation_changes == ()
        assert d.rule_changes == ()

    def test_identical_summary(self):
        p = _base_profile()
        d = diff_profiles(p, p)
        s = diff_summary(d)
        assert "identical" in s


class TestElementChanges:
    def test_element_added(self):
        a = _base_profile()
        b = _base_profile(
            name="B",
            elements=a.elements + (ProfileElement("E3", "item", "L3", "Cat3"),),
        )
        d = diff_profiles(a, b)
        assert not d.identical
        added = [c for c in d.element_changes if c.change_type == DiffChangeType.ADDED]
        assert len(added) == 1
        assert added[0].element_name == "E3"

    def test_element_removed(self):
        a = _base_profile()
        b = _base_profile(name="B", elements=(a.elements[0],))
        d = diff_profiles(a, b)
        removed = [c for c in d.element_changes if c.change_type == DiffChangeType.REMOVED]
        assert len(removed) == 1
        assert removed[0].element_name == "E2"

    def test_element_modified(self):
        a = _base_profile()
        b = _base_profile(
            name="B",
            elements=(
                ProfileElement("E1", "item", "L1", "Cat1"),  # kernel_type changed
                ProfileElement("E2", "step", "L2", "Cat2"),
            ),
        )
        d = diff_profiles(a, b)
        mods = [c for c in d.element_changes if c.change_type == DiffChangeType.MODIFIED]
        assert len(mods) == 1
        assert mods[0].element_name == "E1"
        assert mods[0].field == "kernel_type"
        assert mods[0].old_value == "structure"
        assert mods[0].new_value == "item"


class TestRelationChanges:
    def test_relation_added(self):
        a = _base_profile()
        b = _base_profile(
            name="B",
            relations=a.relations + (ProfileRelation("r2", "composition"),),
        )
        d = diff_profiles(a, b)
        added = [c for c in d.relation_changes if c.change_type == DiffChangeType.ADDED]
        assert len(added) == 1
        assert added[0].relation_name == "r2"

    def test_relation_removed(self):
        a = _base_profile()
        b = _base_profile(name="B", relations=())
        d = diff_profiles(a, b)
        removed = [c for c in d.relation_changes if c.change_type == DiffChangeType.REMOVED]
        assert len(removed) == 1

    def test_relation_modified(self):
        a = _base_profile()
        b = _base_profile(
            name="B",
            relations=(ProfileRelation("r1", "composition"),),
        )
        d = diff_profiles(a, b)
        mods = [c for c in d.relation_changes if c.change_type == DiffChangeType.MODIFIED]
        assert len(mods) == 1
        assert mods[0].field == "kernel_relation"


class TestRuleChanges:
    def test_rule_added(self):
        a = _base_profile()
        b = _base_profile(
            name="B",
            rules=a.validity_rules + (
                KernelValidityRule(
                    id="rule-2", source_pattern="*", target_pattern="*",
                    relationship_name="r1", valid=False, priority=1,
                ),
            ),
        )
        d = diff_profiles(a, b)
        added = [c for c in d.rule_changes if c.change_type == DiffChangeType.ADDED]
        assert len(added) == 1
        assert added[0].rule_id == "rule-2"

    def test_rule_removed(self):
        a = _base_profile()
        b = _base_profile(name="B", rules=())
        d = diff_profiles(a, b)
        removed = [c for c in d.rule_changes if c.change_type == DiffChangeType.REMOVED]
        assert len(removed) == 1

    def test_rule_modified(self):
        a = _base_profile()
        b = _base_profile(
            name="B",
            rules=(
                KernelValidityRule(
                    id="rule-1", source_pattern="@Cat1", target_pattern="@Cat2",
                    relationship_name="r1", valid=False, priority=80,
                ),
            ),
        )
        d = diff_profiles(a, b)
        mods = [c for c in d.rule_changes if c.change_type == DiffChangeType.MODIFIED]
        # valid and priority changed
        fields = {m.field for m in mods}
        assert "valid" in fields
        assert "priority" in fields


class TestDiffSummary:
    def test_summary_with_changes(self):
        a = _base_profile()
        b = _base_profile(
            name="B", version="2.0",
            elements=a.elements + (ProfileElement("E3", "item", "L3", "Cat3"),),
        )
        d = diff_profiles(a, b)
        s = diff_summary(d)
        assert "Elements: +1" in s
        assert "A 1.0" in s
        assert "B 2.0" in s
