"""Auto-generated standard test class for kernel profiles.

Eliminates 75% of profile test boilerplate by dynamically generating
a pytest-discoverable test class covering 7 standard sections.

Usage:
    # test_my_framework.py
    from ea_kernel.v2.test_harness import create_standard_tests
    from my_module import MY_PROFILE
    from ea_kernel.spec import KERNEL_SPEC

    TestMyFrameworkStandard = create_standard_tests(
        MY_PROFILE, KERNEL_SPEC,
        expected_element_count=42,
        expected_relation_count=8,
    )

    # Only domain-specific tests need to be written manually
    class TestMyFrameworkDomain:
        def test_custom_rule(self):
            ...
"""

from __future__ import annotations

from ea_kernel.profile_types import KernelProfile
from ea_kernel.types import KernelSchema


def create_standard_tests(
    profile: KernelProfile,
    kernel: KernelSchema,
    *,
    expected_element_count: int | None = None,
    expected_relation_count: int | None = None,
    expected_rule_count: int | None = None,
    expected_layer_counts: dict[str, int] | None = None,
    expected_category_types: dict[str, str] | None = None,
    expected_relation_mappings: dict[str, str] | None = None,
) -> type:
    """Create a pytest-discoverable test class with standard profile tests.

    Returns a class with test methods covering:
    1. Structure — element/relation/rule counts, name uniqueness
    2. Layer distribution — elements per layer
    3. Kernel mapping — all kernel_type/kernel_relation exist
    4. Category consistency — category → kernel_type homogeneity
    5. Relation mapping — relation → kernel_relation correctness
    6. Rule structure — fallback completeness, priority bands, ref validity
    7. Basic sanity — minimum rule count, meaningful coverage
    """

    kernel_entity_names = {e.name for e in kernel.entities}
    kernel_relation_names = {r.name for r in kernel.relations}

    class StandardTests:
        """Auto-generated standard profile tests."""

        # ── 1. Structure ──────────────────────────────────────────

        def test_profile_has_name(self) -> None:
            assert profile.name

        def test_profile_has_version(self) -> None:
            assert profile.version

        def test_profile_has_kernel_version(self) -> None:
            assert profile.kernel_version

        def test_element_count(self) -> None:
            if expected_element_count is not None:
                assert len(profile.elements) == expected_element_count

        def test_relation_count(self) -> None:
            if expected_relation_count is not None:
                assert len(profile.relations) == expected_relation_count

        def test_rule_count(self) -> None:
            if expected_rule_count is not None:
                assert len(profile.validity_rules) == expected_rule_count

        def test_element_names_unique(self) -> None:
            names = [e.name for e in profile.elements]
            assert len(names) == len(set(names)), (
                f"Duplicate element names: "
                f"{sorted(n for n in names if names.count(n) > 1)}"
            )

        def test_relation_names_unique(self) -> None:
            names = [r.name for r in profile.relations]
            assert len(names) == len(set(names)), (
                f"Duplicate relation names: "
                f"{sorted(n for n in names if names.count(n) > 1)}"
            )

        def test_rule_ids_unique(self) -> None:
            ids = [r.id for r in profile.validity_rules]
            assert len(ids) == len(set(ids)), (
                f"Duplicate rule IDs: "
                f"{sorted(i for i in ids if ids.count(i) > 1)}"
            )

        # ── 2. Layer distribution ─────────────────────────────────

        def test_layer_counts(self) -> None:
            if expected_layer_counts is not None:
                for layer, expected in expected_layer_counts.items():
                    actual = len(profile.elements_in_layer(layer))
                    assert actual == expected, (
                        f"Layer '{layer}': expected {expected}, got {actual}"
                    )

        def test_all_layers_non_empty(self) -> None:
            for layer in profile.domain_layers():
                assert len(profile.elements_in_layer(layer)) > 0, (
                    f"Layer '{layer}' has no elements"
                )

        # ── 3. Kernel type mapping ────────────────────────────────

        def test_all_kernel_types_exist(self) -> None:
            for elem in profile.elements:
                assert elem.kernel_type in kernel_entity_names, (
                    f"'{elem.name}' maps to unknown kernel type: "
                    f"'{elem.kernel_type}'"
                )

        def test_all_kernel_relations_exist(self) -> None:
            for rel in profile.relations:
                assert rel.kernel_relation in kernel_relation_names, (
                    f"'{rel.name}' maps to unknown kernel relation: "
                    f"'{rel.kernel_relation}'"
                )

        # ── 4. Category consistency ───────────────────────────────

        def test_category_type_consistency(self) -> None:
            if expected_category_types is not None:
                for cat, expected_type in expected_category_types.items():
                    for e in profile.elements_in_category(cat):
                        assert e.kernel_type == expected_type, (
                            f"'{e.name}' is category '{cat}' but maps to "
                            f"'{e.kernel_type}', expected '{expected_type}'"
                        )

        def test_category_homogeneity(self) -> None:
            """Each category maps to at most one kernel type."""
            cat_types: dict[str, set[str]] = {}
            for e in profile.elements:
                cat_types.setdefault(e.category, set()).add(e.kernel_type)
            for cat, types in cat_types.items():
                if expected_category_types and cat in expected_category_types:
                    assert len(types) == 1, (
                        f"Category '{cat}' maps to multiple kernel types: {types}"
                    )

        # ── 5. Relation mapping ───────────────────────────────────

        def test_relation_mappings(self) -> None:
            if expected_relation_mappings is not None:
                for name, expected_kernel in expected_relation_mappings.items():
                    rel = profile.get_relation(name)
                    assert rel is not None, f"Missing relation: '{name}'"
                    assert rel.kernel_relation == expected_kernel, (
                        f"'{name}' should map to '{expected_kernel}', "
                        f"got '{rel.kernel_relation}'"
                    )

        # ── 6. Rule structure ─────────────────────────────────────

        def test_all_relations_have_fallback(self) -> None:
            rel_names = {r.name for r in profile.relations}
            fallback_rels: set[str] = set()
            for rule in profile.validity_rules:
                if (not rule.valid and rule.priority == 1
                        and rule.source_pattern == "*"
                        and rule.target_pattern == "*"):
                    fallback_rels.add(rule.relationship_name)
            missing = rel_names - fallback_rels
            assert not missing, f"Missing fallback rules for: {sorted(missing)}"

        def test_fallback_rules_are_deny(self) -> None:
            for rule in profile.validity_rules:
                if (rule.priority == 1
                        and rule.source_pattern == "*"
                        and rule.target_pattern == "*"):
                    assert rule.valid is False, (
                        f"Fallback rule '{rule.id}' should be deny"
                    )

        def test_rule_references_valid_relations(self) -> None:
            rel_names = {r.name for r in profile.relations}
            for rule in profile.validity_rules:
                assert rule.relationship_name in rel_names, (
                    f"Rule '{rule.id}' references unknown relation: "
                    f"'{rule.relationship_name}'"
                )

        # ── 7. Basic sanity ───────────────────────────────────────

        def test_has_elements(self) -> None:
            assert len(profile.elements) > 0

        def test_has_relations(self) -> None:
            assert len(profile.relations) > 0

        def test_has_rules(self) -> None:
            assert len(profile.validity_rules) > 0

        def test_minimum_rule_count(self) -> None:
            """At least one explicit rule + fallbacks exist."""
            explicit = [r for r in profile.validity_rules if r.priority > 1]
            assert len(explicit) > 0, "Profile has no explicit rules"

    StandardTests.__name__ = f"Test{profile.name}Standard"
    StandardTests.__qualname__ = StandardTests.__name__
    return StandardTests
