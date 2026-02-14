"""Tests for Zachman Framework kernel profile mapping correctness."""

from ea_kernel.profiles.zachman import (
    ZACHMAN_PROFILE,
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
        assert len(ALL_ELEMENTS) == 36

    def test_relation_count(self):
        assert len(ALL_RELATIONS) == 12

    def test_profile_name(self):
        assert ZACHMAN_PROFILE.name == "Zachman"

    def test_profile_version(self):
        assert ZACHMAN_PROFILE.version == "6.0"

    def test_kernel_version(self):
        assert ZACHMAN_PROFILE.kernel_version == "2.5.0"

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
# 2. Perspective distribution (layers)
# ═════════════════════════════════════════════════════════════════════════════

class TestPerspectiveDistribution:
    """Each perspective (row) should have exactly 6 elements."""

    def test_scope_count(self):
        assert len(ZACHMAN_PROFILE.elements_in_layer("Scope")) == 6

    def test_enterprise_count(self):
        assert len(ZACHMAN_PROFILE.elements_in_layer("Enterprise")) == 6

    def test_system_count(self):
        assert len(ZACHMAN_PROFILE.elements_in_layer("System")) == 6

    def test_technology_count(self):
        assert len(ZACHMAN_PROFILE.elements_in_layer("Technology")) == 6

    def test_detail_count(self):
        assert len(ZACHMAN_PROFILE.elements_in_layer("Detail")) == 6

    def test_operational_count(self):
        assert len(ZACHMAN_PROFILE.elements_in_layer("Operational")) == 6

    def test_domain_layers(self):
        layers = ZACHMAN_PROFILE.domain_layers()
        assert len(layers) == 6


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
# 4. Category → kernel type consistency (interrogative homogeneity)
# ═════════════════════════════════════════════════════════════════════════════

class TestCategoryConsistency:
    """Each interrogative column maps to exactly one kernel type."""

    def test_what_maps_to_item(self):
        for e in ZACHMAN_PROFILE.elements_in_category("What"):
            assert e.kernel_type == "item", (
                f"{e.name} is What but maps to {e.kernel_type}"
            )

    def test_how_maps_to_step(self):
        for e in ZACHMAN_PROFILE.elements_in_category("How"):
            assert e.kernel_type == "step", (
                f"{e.name} is How but maps to {e.kernel_type}"
            )

    def test_where_maps_to_package(self):
        for e in ZACHMAN_PROFILE.elements_in_category("Where"):
            assert e.kernel_type == "package", (
                f"{e.name} is Where but maps to {e.kernel_type}"
            )

    def test_who_maps_to_structure(self):
        for e in ZACHMAN_PROFILE.elements_in_category("Who"):
            assert e.kernel_type == "structure", (
                f"{e.name} is Who but maps to {e.kernel_type}"
            )

    def test_when_maps_to_event(self):
        for e in ZACHMAN_PROFILE.elements_in_category("When"):
            assert e.kernel_type == "event", (
                f"{e.name} is When but maps to {e.kernel_type}"
            )

    def test_why_maps_to_state(self):
        for e in ZACHMAN_PROFILE.elements_in_category("Why"):
            assert e.kernel_type == "state", (
                f"{e.name} is Why but maps to {e.kernel_type}"
            )

    def test_six_elements_per_category(self):
        for cat in ("What", "How", "Where", "Who", "When", "Why"):
            elems = ZACHMAN_PROFILE.elements_in_category(cat)
            assert len(elems) == 6, f"{cat} has {len(elems)} elements, expected 6"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Relation mapping
# ═════════════════════════════════════════════════════════════════════════════

class TestRelationMapping:
    """Zachman relations map to correct kernel relations."""

    _EXPECTED = {
        "transforms_to": "specialization",
        "derives_from": "specialization",
        "composition": "ownership",
        "aggregation": "membership",
        "uses": "association",
        "located_at": "association",
        "performed_by": "association",
        "triggered_by": "succession",
        "motivated_by": "association",
        "flow": "flow",
        "triggers": "succession",
        "association": "association",
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
            if r.id.startswith("zf-fallback-")
        }
        for name in rel_names:
            assert name in fallback_rels, f"Missing fallback for {name}"

    def test_fallback_rules_are_deny(self):
        for rule in ALL_RULES:
            if rule.id.startswith("zf-fallback-"):
                assert rule.valid is False
                assert rule.priority == 1
                assert rule.source_pattern == "*"
                assert rule.target_pattern == "*"

    def test_allow_rules_have_medium_priority(self):
        for rule in ALL_RULES:
            if not rule.id.startswith("zf-fallback-"):
                assert 40 <= rule.priority <= 60, (
                    f"Rule {rule.id} priority {rule.priority} out of range"
                )

    def test_rule_count_reasonable(self):
        assert len(ALL_RULES) >= 40

    def test_all_rule_references_valid_relations(self):
        rel_names = {r.name for r in ALL_RELATIONS}
        for rule in ALL_RULES:
            assert rule.relationship_name in rel_names, (
                f"Rule {rule.id} references unknown relation: {rule.relationship_name}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 7. Specific element spot checks
# ═════════════════════════════════════════════════════════════════════════════

class TestSpecificElements:
    def test_scope_data(self):
        e = ZACHMAN_PROFILE.get_element("ScopeData")
        assert e is not None
        assert e.kernel_type == "item"
        assert e.layer == "Scope"
        assert e.category == "What"

    def test_enterprise_process(self):
        e = ZACHMAN_PROFILE.get_element("EnterpriseProcess")
        assert e is not None
        assert e.kernel_type == "step"
        assert e.layer == "Enterprise"
        assert e.category == "How"

    def test_system_network(self):
        e = ZACHMAN_PROFILE.get_element("SystemNetwork")
        assert e is not None
        assert e.kernel_type == "package"
        assert e.layer == "System"
        assert e.category == "Where"

    def test_technology_organization(self):
        e = ZACHMAN_PROFILE.get_element("TechnologyOrganization")
        assert e is not None
        assert e.kernel_type == "structure"
        assert e.layer == "Technology"
        assert e.category == "Who"

    def test_detail_schedule(self):
        e = ZACHMAN_PROFILE.get_element("DetailSchedule")
        assert e is not None
        assert e.kernel_type == "event"
        assert e.layer == "Detail"
        assert e.category == "When"

    def test_operational_strategy(self):
        e = ZACHMAN_PROFILE.get_element("OperationalStrategy")
        assert e is not None
        assert e.kernel_type == "state"
        assert e.layer == "Operational"
        assert e.category == "Why"


