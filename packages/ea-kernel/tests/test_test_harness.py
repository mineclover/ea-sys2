"""Tests for v2 test harness (auto-generated test class)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.profile_builder import ProfileBuilder
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.test_harness import create_standard_tests

# ═════════════════════════════════════════════════════════════════════════════
# 1. Harness generates a class
# ═════════════════════════════════════════════════════════════════════════════

class TestHarnessCreation:
    def _build_test_profile(self):
        return (
            ProfileBuilder("TestFW", version="1.0", kernel_version="2.5.0")
            .category_mapping({"Data": "item", "Process": "step"})
            .element("Widget", layer="Core", category="Data")
            .element("Task", layer="Core", category="Process")
            .relation("uses", kernel_relation="association")
            .allow("@Data", "@Process", "uses")
            .build(KERNEL_SCHEMA)
        )

    def test_creates_class(self):
        p = self._build_test_profile()
        cls = create_standard_tests(p, KERNEL_SPEC)
        assert isinstance(cls, type)

    def test_class_name_includes_profile(self):
        p = self._build_test_profile()
        cls = create_standard_tests(p, KERNEL_SPEC)
        assert "TestFW" in cls.__name__

    def test_has_structure_tests(self):
        p = self._build_test_profile()
        cls = create_standard_tests(p, KERNEL_SPEC)
        assert hasattr(cls, "test_profile_has_name")
        assert hasattr(cls, "test_element_names_unique")
        assert hasattr(cls, "test_rule_ids_unique")

    def test_has_kernel_mapping_tests(self):
        p = self._build_test_profile()
        cls = create_standard_tests(p, KERNEL_SPEC)
        assert hasattr(cls, "test_all_kernel_types_exist")
        assert hasattr(cls, "test_all_kernel_relations_exist")

    def test_has_rule_structure_tests(self):
        p = self._build_test_profile()
        cls = create_standard_tests(p, KERNEL_SPEC)
        assert hasattr(cls, "test_all_relations_have_fallback")
        assert hasattr(cls, "test_fallback_rules_are_deny")

    def test_has_sanity_tests(self):
        p = self._build_test_profile()
        cls = create_standard_tests(p, KERNEL_SPEC)
        assert hasattr(cls, "test_has_elements")
        assert hasattr(cls, "test_minimum_rule_count")


# ═════════════════════════════════════════════════════════════════════════════
# 2. Generated tests pass for well-formed profiles
# ═════════════════════════════════════════════════════════════════════════════

class TestHarnessExecution:
    def _build_test_profile(self):
        return (
            ProfileBuilder("TestFW", version="1.0", kernel_version="2.5.0")
            .category_mapping({"Data": "item", "Process": "step"})
            .element("Widget", layer="Core", category="Data")
            .element("Task", layer="Core", category="Process")
            .element("Other", layer="Extra", category="Data")
            .relation("uses", kernel_relation="association")
            .allow("@Data", "@Process", "uses")
            .build(KERNEL_SCHEMA)
        )

    def test_all_standard_tests_pass(self):
        p = self._build_test_profile()
        cls = create_standard_tests(
            p, KERNEL_SPEC,
            expected_element_count=3,
            expected_relation_count=1,
            expected_layer_counts={"Core": 2, "Extra": 1},
            expected_category_types={"Data": "item", "Process": "step"},
            expected_relation_mappings={"uses": "association"},
        )
        instance = cls()
        # Run all test methods
        for name in dir(instance):
            if name.startswith("test_"):
                getattr(instance, name)()


# ═════════════════════════════════════════════════════════════════════════════
# 3. Harness works with existing profiles
# ═════════════════════════════════════════════════════════════════════════════

class TestHarnessWithExistingProfiles:
    def test_zachman_standard_tests_pass(self):
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        cls = create_standard_tests(
            ZACHMAN_PROFILE, KERNEL_SPEC,
            expected_element_count=36,
            expected_relation_count=12,
            expected_layer_counts={
                "Scope": 6, "Enterprise": 6, "System": 6,
                "Technology": 6, "Detail": 6, "Operational": 6,
            },
            expected_category_types={
                "What": "item", "How": "step", "Where": "package",
                "Who": "structure", "When": "event", "Why": "state",
            },
            expected_relation_mappings={
                "transforms_to": "specialization",
                "derives_from": "specialization",
                "composition": "ownership",
                "aggregation": "membership",
                "uses": "association",
                "flow": "flow",
                "triggers": "succession",
            },
        )
        instance = cls()
        for name in dir(instance):
            if name.startswith("test_"):
                getattr(instance, name)()

    def test_archimate_standard_tests_pass(self):
        from ea_kernel.profiles.archimate import ARCHIMATE_PROFILE
        cls = create_standard_tests(ARCHIMATE_PROFILE, KERNEL_SPEC)
        instance = cls()
        for name in dir(instance):
            if name.startswith("test_"):
                getattr(instance, name)()

    def test_togaf_standard_tests_pass(self):
        from ea_kernel.profiles.togaf import TOGAF_PROFILE
        cls = create_standard_tests(TOGAF_PROFILE, KERNEL_SPEC)
        instance = cls()
        for name in dir(instance):
            if name.startswith("test_"):
                getattr(instance, name)()

    def test_sysml2_standard_tests_pass(self):
        from ea_kernel.profiles.sysml2 import SYSML2_PROFILE
        cls = create_standard_tests(SYSML2_PROFILE, KERNEL_SPEC)
        instance = cls()
        for name in dir(instance):
            if name.startswith("test_"):
                getattr(instance, name)()

    def test_bpmn_standard_tests_pass(self):
        from ea_kernel.profiles.bpmn import BPMN_PROFILE
        cls = create_standard_tests(BPMN_PROFILE, KERNEL_SPEC)
        instance = cls()
        for name in dir(instance):
            if name.startswith("test_"):
                getattr(instance, name)()
