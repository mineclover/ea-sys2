"""Tests for BPMN 2.0 kernel profile.

Validates profile structure, kernel type mapping, validity rule coverage,
and 2-stage validation pipeline for process/execution modeling.
"""

from ea_kernel.profiles.bpmn import BPMN_PROFILE, ALL_ELEMENTS, ALL_RELATIONS, ALL_RULES


# ═════════════════════════════════════════════════════════════════════════════
# 1. Profile Structure
# ═════════════════════════════════════════════════════════════════════════════

class TestBpmnStructure:
    def test_element_count(self):
        assert len(ALL_ELEMENTS) == 27

    def test_relation_count(self):
        assert len(ALL_RELATIONS) == 8

    def test_rule_count(self):
        """41 allow + 8 deny + 8 fallback = 57 rules."""
        assert len(ALL_RULES) == 57

    def test_rule_breakdown(self):
        allow = [r for r in ALL_RULES if r.valid and r.priority > 1]
        deny = [r for r in ALL_RULES if not r.valid and r.priority > 1]
        fallback = [r for r in ALL_RULES if r.priority == 1]
        assert len(allow) == 41
        assert len(deny) == 8
        assert len(fallback) == 8

    def test_profile_metadata(self):
        assert BPMN_PROFILE.name == "BPMN"
        assert BPMN_PROFILE.version == "2.0"
        assert BPMN_PROFILE.kernel_version == "2.5.0"
        assert BPMN_PROFILE.metadata is not None
        assert BPMN_PROFILE.metadata.standard == "BPMN 2.0"
        assert BPMN_PROFILE.metadata.organization == "OMG"

    def test_all_rule_ids_unique(self):
        ids = [r.id for r in ALL_RULES]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_all_rules_reference_valid_relations(self):
        """Every rule references a relation that exists in the profile."""
        rel_names = {r.name for r in ALL_RELATIONS}
        for rule in ALL_RULES:
            assert rule.relationship_name in rel_names, (
                f"Rule {rule.id} references unknown relation: {rule.relationship_name}"
            )

    def test_fallback_per_relation(self):
        """Every relation has exactly one fallback rule."""
        rel_names = {r.name for r in ALL_RELATIONS}
        fallback_rels = {r.relationship_name for r in ALL_RULES if r.id.startswith("bp-fallback-")}
        assert rel_names == fallback_rels


# ═════════════════════════════════════════════════════════════════════════════
# 2. Kernel Type Mapping
# ═════════════════════════════════════════════════════════════════════════════

class TestBpmnKernelMapping:
    def test_8_categories(self):
        categories = sorted({e.category for e in ALL_ELEMENTS})
        assert categories == [
            "Activity", "Connector", "Container", "Data",
            "Event", "Gateway", "Participant", "Task",
        ]

    def test_3_layers(self):
        layers = BPMN_PROFILE.domain_layers()
        assert set(layers) == {"Orchestration", "Collaboration", "DataFlow"}


# ═════════════════════════════════════════════════════════════════════════════
# 3. Element counts by category
# ═════════════════════════════════════════════════════════════════════════════

class TestBpmnElementCounts:
    def test_activity_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Activity")) == 2

    def test_task_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Task")) == 5

    def test_event_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Event")) == 8

    def test_gateway_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Gateway")) == 4

    def test_participant_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Participant")) == 2

    def test_data_count(self):
        """Message + DataObject + DataStore = 3 Data elements."""
        assert len(BPMN_PROFILE.elements_in_category("Data")) == 3

    def test_container_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Container")) == 2

    def test_connector_count(self):
        assert len(BPMN_PROFILE.elements_in_category("Connector")) == 1


