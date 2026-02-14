"""Tests for SysML 2.0 kernel profile — behavioral modeling stress test.

Validates full 13/14 kernel relation + 11/11 kernel type coverage,
with emphasis on L2/L3 behavioral relations (feature_typing, connector,
redefinition, subsetting, interaction, triggering, guarding).
"""

from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.profiles.sysml2 import (
    ALL_ELEMENTS,
    ALL_RELATIONS,
    ALL_RULES,
    SYSML2_PROFILE,
)

# ═════════════════════════════════════════════════════════════════════════════
# 1. Profile structure
# ═════════════════════════════════════════════════════════════════════════════

class TestProfileStructure:
    def test_element_count(self):
        assert len(ALL_ELEMENTS) == 25

    def test_relation_count(self):
        assert len(ALL_RELATIONS) == 13

    def test_rule_count(self):
        allow = [r for r in ALL_RULES if r.valid and r.priority > 1]
        deny = [r for r in ALL_RULES if not r.valid and r.priority >= 80]
        fallback = [r for r in ALL_RULES if r.priority == 1]
        assert len(allow) == 33
        assert len(deny) == 10
        assert len(fallback) == 13
        assert len(ALL_RULES) == 56  # 33 + 10 + 13

    def test_profile_name(self):
        assert SYSML2_PROFILE.name == "SysML"

    def test_profile_version(self):
        assert SYSML2_PROFILE.version == "2.0"

    def test_kernel_version(self):
        assert SYSML2_PROFILE.kernel_version == "2.5.0"

    def test_metadata(self):
        assert SYSML2_PROFILE.metadata is not None
        assert SYSML2_PROFILE.metadata.standard == "SysML 2.0 / KerML"
        assert SYSML2_PROFILE.metadata.organization == "OMG"

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
    def test_structure_count(self):
        assert len(SYSML2_PROFILE.elements_in_layer("Structure")) == 10

    def test_behavior_count(self):
        assert len(SYSML2_PROFILE.elements_in_layer("Behavior")) == 6

    def test_interaction_count(self):
        assert len(SYSML2_PROFILE.elements_in_layer("Interaction")) == 4

    def test_constraint_count(self):
        assert len(SYSML2_PROFILE.elements_in_layer("Constraint")) == 5

    def test_domain_layers(self):
        layers = SYSML2_PROFILE.domain_layers()
        assert len(layers) == 4
        assert set(layers) == {"Structure", "Behavior", "Interaction", "Constraint"}


# ═════════════════════════════════════════════════════════════════════════════
# 3. Kernel type mapping — 11/11 complete
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

    def test_all_11_kernel_types_used(self):
        """SysML 2.0 must use all 11 kernel entity types."""
        used_types = {e.kernel_type for e in ALL_ELEMENTS}
        expected_types = {
            "structure", "feature", "port", "datatype", "package",
            "step", "action", "state", "event", "item", "expression",
        }
        assert used_types == expected_types, (
            f"Missing kernel types: {expected_types - used_types}"
        )

    def test_all_13_kernel_relations_used(self):
        """SysML 2.0 must use all 13 kernel relation types."""
        used_relations = {r.kernel_relation for r in ALL_RELATIONS}
        expected_relations = {
            "ownership", "membership", "specialization", "feature_typing",
            "connector", "redefinition", "subsetting", "association",
            "flow", "succession", "interaction", "triggering", "guarding",
        }
        assert used_relations == expected_relations, (
            f"Missing kernel relations: {expected_relations - used_relations}"
        )


# ═════════════════════════════════════════════════════════════════════════════
# 4. Category → kernel type consistency (homogeneous)
# ═════════════════════════════════════════════════════════════════════════════

class TestCategoryConsistency:
    """11 categories, each mapping to exactly one kernel type."""

    def test_active_structure_maps_to_structure(self):
        for e in SYSML2_PROFILE.elements_in_category("ActiveStructure"):
            assert e.kernel_type == "structure", (
                f"{e.name} is ActiveStructure but maps to {e.kernel_type}"
            )

    def test_property_maps_to_feature(self):
        for e in SYSML2_PROFILE.elements_in_category("Property"):
            assert e.kernel_type == "feature", (
                f"{e.name} is Property but maps to {e.kernel_type}"
            )

    def test_port_maps_to_port(self):
        for e in SYSML2_PROFILE.elements_in_category("Port"):
            assert e.kernel_type == "port", (
                f"{e.name} is Port but maps to {e.kernel_type}"
            )

    def test_datatype_maps_to_datatype(self):
        for e in SYSML2_PROFILE.elements_in_category("DataType"):
            assert e.kernel_type == "datatype", (
                f"{e.name} is DataType but maps to {e.kernel_type}"
            )

    def test_container_maps_to_package(self):
        for e in SYSML2_PROFILE.elements_in_category("Container"):
            assert e.kernel_type == "package", (
                f"{e.name} is Container but maps to {e.kernel_type}"
            )

    def test_behavior_maps_to_step(self):
        for e in SYSML2_PROFILE.elements_in_category("Behavior"):
            assert e.kernel_type == "step", (
                f"{e.name} is Behavior but maps to {e.kernel_type}"
            )

    def test_execution_maps_to_action(self):
        for e in SYSML2_PROFILE.elements_in_category("Execution"):
            assert e.kernel_type == "action", (
                f"{e.name} is Execution but maps to {e.kernel_type}"
            )

    def test_state_machine_maps_to_state(self):
        for e in SYSML2_PROFILE.elements_in_category("StateMachine"):
            assert e.kernel_type == "state", (
                f"{e.name} is StateMachine but maps to {e.kernel_type}"
            )

    def test_event_maps_to_event(self):
        for e in SYSML2_PROFILE.elements_in_category("Event"):
            assert e.kernel_type == "event", (
                f"{e.name} is Event but maps to {e.kernel_type}"
            )

    def test_passive_structure_maps_to_item(self):
        for e in SYSML2_PROFILE.elements_in_category("PassiveStructure"):
            assert e.kernel_type == "item", (
                f"{e.name} is PassiveStructure but maps to {e.kernel_type}"
            )

    def test_constraint_maps_to_expression(self):
        for e in SYSML2_PROFILE.elements_in_category("Constraint"):
            assert e.kernel_type == "expression", (
                f"{e.name} is Constraint but maps to {e.kernel_type}"
            )

    def test_exactly_11_categories(self):
        categories = {e.category for e in ALL_ELEMENTS}
        assert len(categories) == 11


# ═════════════════════════════════════════════════════════════════════════════
# 5. Relation mapping — 13/13 complete
# ═════════════════════════════════════════════════════════════════════════════

class TestRelationMapping:
    """SysML relations map to correct kernel relations."""

    _EXPECTED = {
        "composition": "ownership",
        "containment": "membership",
        "generalization": "specialization",
        "typing": "feature_typing",
        "connection": "connector",
        "redefines": "redefinition",
        "subsets": "subsetting",
        "allocation": "association",
        "dataFlow": "flow",
        "controlFlow": "succession",
        "messaging": "interaction",
        "eventTrigger": "triggering",
        "guard": "guarding",
    }

    def test_all_mappings(self):
        for rel in ALL_RELATIONS:
            expected = self._EXPECTED.get(rel.name)
            assert expected is not None, f"Unexpected relation: {rel.name}"
            assert rel.kernel_relation == expected, (
                f"{rel.name} should map to {expected}, got {rel.kernel_relation}"
            )

    def test_mapping_count(self):
        assert len(self._EXPECTED) == 13


# ═════════════════════════════════════════════════════════════════════════════
# 6. Rule structure
# ═════════════════════════════════════════════════════════════════════════════

class TestRuleStructure:
    def test_all_relations_have_fallback(self):
        rel_names = {r.name for r in ALL_RELATIONS}
        fallback_rels = {
            r.relationship_name for r in ALL_RULES
            if r.id.startswith("sm-fallback-")
        }
        for name in rel_names:
            assert name in fallback_rels, f"Missing fallback for {name}"

    def test_fallback_rules_are_deny(self):
        for rule in ALL_RULES:
            if rule.id.startswith("sm-fallback-"):
                assert rule.valid is False
                assert rule.priority == 1
                assert rule.source_pattern == "*"
                assert rule.target_pattern == "*"

    def test_deny_rules_have_high_priority(self):
        for rule in ALL_RULES:
            if rule.id.startswith("sm-deny-"):
                assert rule.priority >= 80

    def test_allow_rules_have_medium_priority(self):
        for rule in ALL_RULES:
            if not rule.id.startswith(("sm-deny-", "sm-fallback-")):
                assert 40 <= rule.priority <= 60, (
                    f"Rule {rule.id} priority {rule.priority} out of range"
                )

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
    def test_part(self):
        e = SYSML2_PROFILE.get_element("Part")
        assert e is not None
        assert e.kernel_type == "structure"
        assert e.layer == "Structure"
        assert e.category == "ActiveStructure"

    def test_block(self):
        e = SYSML2_PROFILE.get_element("Block")
        assert e is not None
        assert e.kernel_type == "structure"
        assert e.category == "ActiveStructure"

    def test_interface_block(self):
        e = SYSML2_PROFILE.get_element("InterfaceBlock")
        assert e is not None
        assert e.kernel_type == "structure"
        assert e.category == "ActiveStructure"

    def test_part_property(self):
        e = SYSML2_PROFILE.get_element("PartProperty")
        assert e is not None
        assert e.kernel_type == "feature"
        assert e.category == "Property"

    def test_flow_port(self):
        e = SYSML2_PROFILE.get_element("FlowPort")
        assert e is not None
        assert e.kernel_type == "port"
        assert e.category == "Port"

    def test_value_type(self):
        e = SYSML2_PROFILE.get_element("ValueType")
        assert e is not None
        assert e.kernel_type == "datatype"
        assert e.category == "DataType"

    def test_model_package(self):
        e = SYSML2_PROFILE.get_element("ModelPackage")
        assert e is not None
        assert e.kernel_type == "package"
        assert e.category == "Container"

    def test_activity(self):
        e = SYSML2_PROFILE.get_element("Activity")
        assert e is not None
        assert e.kernel_type == "step"
        assert e.layer == "Behavior"
        assert e.category == "Behavior"

    def test_action(self):
        e = SYSML2_PROFILE.get_element("Action")
        assert e is not None
        assert e.kernel_type == "action"
        assert e.category == "Execution"

    def test_state(self):
        e = SYSML2_PROFILE.get_element("State")
        assert e is not None
        assert e.kernel_type == "state"
        assert e.category == "StateMachine"

    def test_event_occurrence(self):
        e = SYSML2_PROFILE.get_element("EventOccurrence")
        assert e is not None
        assert e.kernel_type == "event"
        assert e.layer == "Interaction"

    def test_signal(self):
        e = SYSML2_PROFILE.get_element("Signal")
        assert e is not None
        assert e.kernel_type == "item"
        assert e.category == "PassiveStructure"

    def test_guard_expression(self):
        e = SYSML2_PROFILE.get_element("GuardExpression")
        assert e is not None
        assert e.kernel_type == "expression"
        assert e.layer == "Constraint"
        assert e.category == "Constraint"

    def test_requirement(self):
        e = SYSML2_PROFILE.get_element("Requirement")
        assert e is not None
        assert e.kernel_type == "item"
        assert e.category == "PassiveStructure"


