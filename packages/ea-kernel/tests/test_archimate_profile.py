"""Tests for ArchiMate 3.2 kernel profile mapping correctness."""

from ea_kernel.profiles.archimate import (
    ARCHIMATE_PROFILE,
    ALL_ELEMENTS,
    ALL_RELATIONS,
    ALL_RULES,
)
from ea_kernel.definition import KERNEL_SCHEMA


# ═════════════════════════════════════════════════════════════════════════════
# 1. Structural counts
# ═════════════════════════════════════════════════════════════════════════════

class TestProfileStructure:
    def test_element_count(self):
        assert len(ALL_ELEMENTS) == 61

    def test_relation_count(self):
        assert len(ALL_RELATIONS) == 11

    def test_profile_name(self):
        assert ARCHIMATE_PROFILE.name == "ArchiMate"

    def test_profile_version(self):
        assert ARCHIMATE_PROFILE.version == "3.2"

    def test_kernel_version(self):
        assert ARCHIMATE_PROFILE.kernel_version == "2.5.0"

    def test_all_element_names_unique(self):
        names = [e.name for e in ALL_ELEMENTS]
        assert len(names) == len(set(names)), f"Duplicates: {[n for n in names if names.count(n) > 1]}"

    def test_all_relation_names_unique(self):
        names = [r.name for r in ALL_RELATIONS]
        assert len(names) == len(set(names))

    def test_all_rule_ids_unique(self):
        ids = [r.id for r in ALL_RULES]
        assert len(ids) == len(set(ids)), f"Duplicates: {[i for i in ids if ids.count(i) > 1]}"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Layer distribution
# ═════════════════════════════════════════════════════════════════════════════

class TestLayerDistribution:
    def test_motivation_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Motivation")) == 10

    def test_strategy_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Strategy")) == 4

    def test_business_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Business")) == 13

    def test_application_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Application")) == 9

    def test_technology_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Technology")) == 13

    def test_physical_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Physical")) == 4

    def test_implementation_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Implementation")) == 5

    def test_cross_layer_count(self):
        assert len(ARCHIMATE_PROFILE.elements_in_layer("Cross-layer")) == 3

    def test_domain_layers(self):
        layers = ARCHIMATE_PROFILE.domain_layers()
        assert len(layers) == 8


# ═════════════════════════════════════════════════════════════════════════════
# 3. Kernel type mapping validity
# ═════════════════════════════════════════════════════════════════════════════

class TestKernelTypeMapping:
    """Every profile element must map to an existing kernel entity."""

    def test_all_kernel_types_exist(self):
        kernel_entity_names = {e.name for e in KERNEL_SCHEMA.entities}
        for elem in ALL_ELEMENTS:
            assert elem.kernel_type in kernel_entity_names, (
                f"{elem.name} maps to unknown kernel type: {elem.kernel_type}"
            )

    def test_all_kernel_relations_exist(self):
        kernel_relation_names = {r.name for r in KERNEL_SCHEMA.relations}
        for rel in ALL_RELATIONS:
            assert rel.kernel_relation in kernel_relation_names, (
                f"{rel.name} maps to unknown kernel relation: {rel.kernel_relation}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 4. Category → kernel type consistency
# ═════════════════════════════════════════════════════════════════════════════

class TestCategoryConsistency:
    """Category assignments should map to consistent kernel types."""

    def test_active_structure_maps_to_structure(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("ActiveStructure"):
            assert e.kernel_type == "structure", (
                f"{e.name} is ActiveStructure but maps to {e.kernel_type}"
            )

    def test_behavior_maps_to_step(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Behavior"):
            assert e.kernel_type == "step", (
                f"{e.name} is Behavior but maps to {e.kernel_type}"
            )

    def test_passive_structure_maps_to_item(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("PassiveStructure"):
            assert e.kernel_type == "item", (
                f"{e.name} is PassiveStructure but maps to {e.kernel_type}"
            )

    def test_event_maps_to_event(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Event"):
            assert e.kernel_type == "event", (
                f"{e.name} is Event but maps to {e.kernel_type}"
            )

    def test_interface_maps_to_port(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Interface"):
            assert e.kernel_type == "port", (
                f"{e.name} is Interface but maps to {e.kernel_type}"
            )

    def test_composite_maps_to_package(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Composite"):
            assert e.kernel_type == "package", (
                f"{e.name} is Composite but maps to {e.kernel_type}"
            )

    def test_executable_maps_to_action(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Executable"):
            assert e.kernel_type == "action", (
                f"{e.name} is Executable but maps to {e.kernel_type}"
            )

    def test_goal_maps_to_state(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Goal"):
            assert e.kernel_type == "state", (
                f"{e.name} is Goal but maps to {e.kernel_type}"
            )

    def test_outcome_maps_to_state(self):
        for e in ARCHIMATE_PROFILE.elements_in_category("Outcome"):
            assert e.kernel_type == "state", (
                f"{e.name} is Outcome but maps to {e.kernel_type}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 5. Relation mapping
# ═════════════════════════════════════════════════════════════════════════════

class TestRelationMapping:
    """ArchiMate relations map to correct kernel relations."""

    _EXPECTED = {
        "Composition": "ownership",
        "Aggregation": "membership",
        "Assignment": "association",
        "Realization": "specialization",
        "Serving": "association",
        "Access": "association",
        "Influence": "association",
        "Triggering": "succession",
        "Flow": "flow",
        "Specialization": "specialization",
        "Association": "association",
    }

    def test_all_mappings(self):
        for rel in ALL_RELATIONS:
            expected = self._EXPECTED.get(rel.name)
            assert expected is not None, f"Unexpected relation: {rel.name}"
            assert rel.kernel_relation == expected, (
                f"{rel.name} should map to {expected}, got {rel.kernel_relation}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 6. Rule structure
# ═════════════════════════════════════════════════════════════════════════════

class TestRuleStructure:
    def test_all_relations_have_fallback(self):
        rel_names = {r.name for r in ALL_RELATIONS}
        fallback_rels = {
            r.relationship_name for r in ALL_RULES
            if r.id.startswith("am-fallback-")
        }
        for name in rel_names:
            assert name in fallback_rels, f"Missing fallback for {name}"

    def test_fallback_rules_are_deny(self):
        for rule in ALL_RULES:
            if rule.id.startswith("am-fallback-"):
                assert rule.valid is False
                assert rule.priority == 1
                assert rule.source_pattern == "*"
                assert rule.target_pattern == "*"

    def test_deny_rules_have_high_priority(self):
        for rule in ALL_RULES:
            if rule.id.startswith("am-deny-"):
                assert rule.priority >= 80

    def test_allow_rules_have_medium_priority(self):
        for rule in ALL_RULES:
            if not rule.id.startswith(("am-deny-", "am-fallback-")):
                assert 40 <= rule.priority <= 60, (
                    f"Rule {rule.id} priority {rule.priority} out of range"
                )

    def test_rule_count_reasonable(self):
        """Profile should have a meaningful number of rules."""
        assert len(ALL_RULES) >= 40

    def test_all_rule_references_valid_relations(self):
        """Every rule references a relation that exists in the profile."""
        rel_names = {r.name for r in ALL_RELATIONS}
        for rule in ALL_RULES:
            assert rule.relationship_name in rel_names, (
                f"Rule {rule.id} references unknown relation: {rule.relationship_name}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 7. Specific element spot checks
# ═════════════════════════════════════════════════════════════════════════════

class TestSpecificElements:
    def test_business_process(self):
        bp = ARCHIMATE_PROFILE.get_element("BusinessProcess")
        assert bp is not None
        assert bp.kernel_type == "step"
        assert bp.layer == "Business"
        assert bp.category == "Behavior"

    def test_application_component(self):
        ac = ARCHIMATE_PROFILE.get_element("ApplicationComponent")
        assert ac is not None
        assert ac.kernel_type == "structure"
        assert ac.layer == "Application"
        assert ac.category == "ActiveStructure"

    def test_goal(self):
        g = ARCHIMATE_PROFILE.get_element("Goal")
        assert g is not None
        assert g.kernel_type == "state"
        assert g.layer == "Motivation"

    def test_node(self):
        n = ARCHIMATE_PROFILE.get_element("Node")
        assert n is not None
        assert n.kernel_type == "structure"
        assert n.layer == "Technology"

    def test_work_package(self):
        wp = ARCHIMATE_PROFILE.get_element("WorkPackage")
        assert wp is not None
        assert wp.kernel_type == "action"
        assert wp.layer == "Implementation"

    def test_grouping(self):
        g = ARCHIMATE_PROFILE.get_element("Grouping")
        assert g is not None
        assert g.kernel_type == "package"
        assert g.layer == "Cross-layer"

    def test_junction(self):
        j = ARCHIMATE_PROFILE.get_element("Junction")
        assert j is not None
        assert j.kernel_type == "feature"
        assert j.category == "Junction"

    def test_gap(self):
        g = ARCHIMATE_PROFILE.get_element("Gap")
        assert g is not None
        assert g.kernel_type == "expression"


