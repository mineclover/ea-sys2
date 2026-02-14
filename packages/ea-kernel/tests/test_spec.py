"""Tests for kernel validation engine and specification."""

import pytest

from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.spec import (
    KERNEL_LAYER_CONSTRAINTS,
    KERNEL_SPEC,
    KERNEL_VALIDITY_RULES,
    build_validated_schema,
)
from ea_kernel.types import (
    KernelConditionType,
    KernelRuleCondition,
    KernelValidationResult,
    KernelValidityRule,
    LayerConstraint,
)


# ═════════════════════════════════════════════════════════════════════════════
# 1. Rule Structure
# ═════════════════════════════════════════════════════════════════════════════

class TestValidityRuleStructure:
    """Verify structural integrity of the rule set."""

    def test_all_rule_ids_unique(self):
        ids = [r.id for r in KERNEL_VALIDITY_RULES]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[x for x in ids if ids.count(x) > 1]}"

    def test_all_relations_referenced(self):
        """Every relation in the schema must appear in at least one rule."""
        relation_names = {r.name for r in KERNEL_SCHEMA.relations}
        rule_relations = {r.relationship_name for r in KERNEL_VALIDITY_RULES}
        assert relation_names <= rule_relations, f"Missing: {relation_names - rule_relations}"

    def test_all_relations_have_fallback(self):
        """Every relation has a deny-by-default fallback rule."""
        relation_names = {r.name for r in KERNEL_SCHEMA.relations}
        fallback_relations = {
            r.relationship_name for r in KERNEL_VALIDITY_RULES
            if r.id.startswith("fallback-")
        }
        assert relation_names <= fallback_relations

    def test_fallback_rules_are_deny(self):
        for rule in KERNEL_VALIDITY_RULES:
            if rule.id.startswith("fallback-"):
                assert rule.valid is False
                assert rule.priority == 1
                assert rule.source_pattern == "*"
                assert rule.target_pattern == "*"

    def test_rule_references_valid_relations(self):
        """Every rule references a relation that exists in the schema."""
        relation_names = {r.name for r in KERNEL_SCHEMA.relations}
        for rule in KERNEL_VALIDITY_RULES:
            assert rule.relationship_name in relation_names, (
                f"Rule {rule.id} references unknown relation: {rule.relationship_name}"
            )

    def test_non_fallback_rules_have_notes(self):
        """Non-fallback rules should have explanatory notes."""
        for rule in KERNEL_VALIDITY_RULES:
            if not rule.id.startswith("fallback-"):
                assert rule.notes, f"Rule {rule.id} has no notes"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Pattern Matching
# ═════════════════════════════════════════════════════════════════════════════

class TestPatternMatching:
    """Test entity_matches() with various pattern types."""

    def test_exact_match(self):
        assert KERNEL_SPEC.entity_matches("feature", "feature") is True
        assert KERNEL_SPEC.entity_matches("feature", "step") is False

    def test_wildcard_all(self):
        assert KERNEL_SPEC.entity_matches("feature", "*") is True
        assert KERNEL_SPEC.entity_matches("package", "*") is True
        assert KERNEL_SPEC.entity_matches("nonexistent", "*") is False

    def test_prefix_wildcard_exact_base(self):
        """'metatype*' matches 'metatype' itself."""
        assert KERNEL_SPEC.entity_matches("metatype", "metatype*") is True

    def test_prefix_wildcard_descendants(self):
        """'metatype*' matches all descendants of metatype."""
        assert KERNEL_SPEC.entity_matches("feature", "metatype*") is True
        assert KERNEL_SPEC.entity_matches("classifier", "metatype*") is True
        assert KERNEL_SPEC.entity_matches("structure", "metatype*") is True
        assert KERNEL_SPEC.entity_matches("item", "metatype*") is True
        assert KERNEL_SPEC.entity_matches("datatype", "metatype*") is True
        assert KERNEL_SPEC.entity_matches("port", "metatype*") is True  # port → feature → metatype
        assert KERNEL_SPEC.entity_matches("step", "metatype*") is True  # step → feature → metatype
        assert KERNEL_SPEC.entity_matches("action", "metatype*") is True  # action → step → feature → metatype
        assert KERNEL_SPEC.entity_matches("event", "metatype*") is True  # event → feature → metatype
        assert KERNEL_SPEC.entity_matches("state", "metatype*") is True  # state → metatype

    def test_prefix_wildcard_non_descendants(self):
        """'classifier*' should NOT match non-descendants."""
        assert KERNEL_SPEC.entity_matches("feature", "classifier*") is False
        assert KERNEL_SPEC.entity_matches("package", "classifier*") is False
        assert KERNEL_SPEC.entity_matches("element", "classifier*") is False

    def test_element_wildcard(self):
        """'element*' matches everything that descends from element."""
        assert KERNEL_SPEC.entity_matches("namespace", "element*") is True
        assert KERNEL_SPEC.entity_matches("package", "element*") is True
        assert KERNEL_SPEC.entity_matches("feature", "element*") is True
        assert KERNEL_SPEC.entity_matches("action", "element*") is True

    def test_namespace_wildcard(self):
        """'namespace*' matches namespace descendants."""
        assert KERNEL_SPEC.entity_matches("package", "namespace*") is True
        assert KERNEL_SPEC.entity_matches("metatype", "namespace*") is True
        assert KERNEL_SPEC.entity_matches("feature", "namespace*") is True
        # element is parent of namespace, not descendant
        assert KERNEL_SPEC.entity_matches("element", "namespace*") is False

    def test_feature_wildcard(self):
        """'feature*' matches feature and its subtypes."""
        assert KERNEL_SPEC.entity_matches("feature", "feature*") is True
        assert KERNEL_SPEC.entity_matches("step", "feature*") is True
        assert KERNEL_SPEC.entity_matches("action", "feature*") is True
        assert KERNEL_SPEC.entity_matches("expression", "feature*") is True
        assert KERNEL_SPEC.entity_matches("port", "feature*") is True
        assert KERNEL_SPEC.entity_matches("event", "feature*") is True
        assert KERNEL_SPEC.entity_matches("classifier", "feature*") is False

    def test_classifier_wildcard_with_item(self):
        """'classifier*' matches item (new in v1.1)."""
        assert KERNEL_SPEC.entity_matches("item", "classifier*") is True
        assert KERNEL_SPEC.entity_matches("structure", "classifier*") is True
        assert KERNEL_SPEC.entity_matches("datatype", "classifier*") is True


# ═════════════════════════════════════════════════════════════════════════════
# 3. Condition Checking
# ═════════════════════════════════════════════════════════════════════════════

class TestConditionChecking:
    """Test _check_condition() with kernel entities."""

    def test_same_layer_passes(self):
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_LAYER),
            "feature", "classifier",  # both L1
        )
        assert ok is True

    def test_same_layer_fails(self):
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_LAYER),
            "feature", "step",  # L1 vs L4
        )
        assert ok is False

    def test_layer_order_passes(self):
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.LAYER_ORDER),
            "package", "step",  # L1 <= L4
        )
        assert ok is True

    def test_layer_order_equal(self):
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.LAYER_ORDER),
            "feature", "classifier",  # L1 == L1
        )
        assert ok is True

    def test_layer_order_fails(self):
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.LAYER_ORDER),
            "step", "package",  # L4 > L1
        )
        assert ok is False

    def test_same_branch_feature_step(self):
        """step descends from feature — they share non-root ancestors."""
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_ENTITY_BRANCH),
            "feature", "step",
        )
        assert ok is True

    def test_same_branch_step_action(self):
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_ENTITY_BRANCH),
            "step", "action",
        )
        assert ok is True

    def test_same_branch_classifier_feature_fails(self):
        """classifier and feature are siblings under metatype — share metatype (non-root)."""
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_ENTITY_BRANCH),
            "classifier", "feature",
        )
        # Both have metatype as ancestor, which has parent=namespace → non-root
        assert ok is True

    def test_same_branch_package_feature_fails(self):
        """package and feature diverge at namespace — namespace has parent=element (non-root)."""
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_ENTITY_BRANCH),
            "package", "feature",
        )
        # Both descend from namespace which has parent=element (non-root)
        assert ok is True

    def test_same_branch_state_expression(self):
        """state(→metatype) and expression(→feature→metatype) share metatype."""
        ok, _ = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_ENTITY_BRANCH),
            "state", "expression",
        )
        assert ok is True


# ═════════════════════════════════════════════════════════════════════════════
# 4. Allowed Relationships
# ═════════════════════════════════════════════════════════════════════════════

class TestAllowedRelationships:
    """Verify that valid relationship patterns are accepted."""

    def test_membership_namespace_to_element(self):
        r = KERNEL_SPEC.validate_relationship("package", "feature", "membership")
        assert r.valid is True

    def test_membership_package_nesting(self):
        r = KERNEL_SPEC.validate_relationship("package", "package", "membership")
        assert r.valid is True

    def test_ownership_metatype_to_feature(self):
        r = KERNEL_SPEC.validate_relationship("metatype", "feature", "ownership")
        assert r.valid is True

    def test_ownership_classifier_to_feature(self):
        r = KERNEL_SPEC.validate_relationship("structure", "feature", "ownership")
        assert r.valid is True

    def test_specialization_metatype(self):
        r = KERNEL_SPEC.validate_relationship("metatype", "metatype", "specialization")
        assert r.valid is True

    def test_specialization_classifier(self):
        r = KERNEL_SPEC.validate_relationship("structure", "datatype", "specialization")
        assert r.valid is True

    def test_feature_typing_feature_to_classifier(self):
        r = KERNEL_SPEC.validate_relationship("feature", "structure", "feature_typing")
        assert r.valid is True

    def test_feature_typing_feature_to_datatype(self):
        r = KERNEL_SPEC.validate_relationship("feature", "datatype", "feature_typing")
        assert r.valid is True

    def test_association_metatype(self):
        r = KERNEL_SPEC.validate_relationship("structure", "datatype", "association")
        assert r.valid is True

    def test_connector_feature_to_feature(self):
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "connector")
        assert r.valid is True

    def test_redefinition_feature_to_feature(self):
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "redefinition")
        assert r.valid is True

    def test_subsetting_feature_to_feature(self):
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "subsetting")
        assert r.valid is True

    def test_flow_feature_to_feature(self):
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "flow")
        assert r.valid is True

    def test_succession_step_to_step(self):
        r = KERNEL_SPEC.validate_relationship("step", "step", "succession")
        assert r.valid is True

    def test_succession_action_to_action(self):
        r = KERNEL_SPEC.validate_relationship("action", "action", "succession")
        assert r.valid is True

    def test_interaction_port_to_event(self):
        """Port→event interaction allowed (inter-01: feature*→feature*)."""
        r = KERNEL_SPEC.validate_relationship("port", "event", "interaction")
        assert r.valid is True

    def test_triggering_event_to_step_v15(self):
        """v1.5: Only event can trigger step (trig-01 tightened)."""
        r = KERNEL_SPEC.validate_relationship("event", "step", "triggering")
        assert r.valid is True

    def test_triggering_event_to_action_v15(self):
        """v1.5: Only event can trigger action (trig-02 tightened)."""
        r = KERNEL_SPEC.validate_relationship("event", "action", "triggering")
        assert r.valid is True

    def test_guarding_state_to_expression(self):
        r = KERNEL_SPEC.validate_relationship("state", "expression", "guarding")
        assert r.valid is True

    def test_specialization_state_to_state(self):
        r = KERNEL_SPEC.validate_relationship("state", "state", "specialization")
        assert r.valid is True

    # ── v1.1 new entity relationships ─────────────────────────────────

    def test_ownership_structure_to_port(self):
        """Structure owns port (classifier* → feature*)."""
        r = KERNEL_SPEC.validate_relationship("structure", "port", "ownership")
        assert r.valid is True

    def test_connector_port_to_port(self):
        """Port-to-port connector (feature* → feature*)."""
        r = KERNEL_SPEC.validate_relationship("port", "port", "connector")
        assert r.valid is True

    def test_triggering_event_to_step(self):
        """Event triggers step (feature* → step)."""
        r = KERNEL_SPEC.validate_relationship("event", "step", "triggering")
        assert r.valid is True

    def test_triggering_event_to_action(self):
        """Event triggers action (feature* → action)."""
        r = KERNEL_SPEC.validate_relationship("event", "action", "triggering")
        assert r.valid is True

    def test_succession_event_to_step(self):
        """Event → step via succession (succ-02)."""
        r = KERNEL_SPEC.validate_relationship("event", "step", "succession")
        assert r.valid is True

    # ── v1.2 succession broadening ─────────────────────────────────

    def test_succession_action_to_step(self):
        """Action → step via succession (succ-01: step*→step*)."""
        r = KERNEL_SPEC.validate_relationship("action", "step", "succession")
        assert r.valid is True

    def test_succession_step_to_event(self):
        """Step → event (succ-03: step*→event)."""
        r = KERNEL_SPEC.validate_relationship("step", "event", "succession")
        assert r.valid is True

    def test_succession_event_to_event(self):
        """Event chain (succ-04: event→event)."""
        r = KERNEL_SPEC.validate_relationship("event", "event", "succession")
        assert r.valid is True

    def test_succession_event_to_action(self):
        """Event → action (succ-02: event→step*)."""
        r = KERNEL_SPEC.validate_relationship("event", "action", "succession")
        assert r.valid is True

    def test_succession_action_to_event(self):
        """Action → event (succ-03: step*→event)."""
        r = KERNEL_SPEC.validate_relationship("action", "event", "succession")
        assert r.valid is True

    # ── v1.2 step→state specialization allowed ─────────────────────

    def test_specialization_step_to_state_allowed(self):
        """Step → state specialization (used by TOGAF Realization)."""
        r = KERNEL_SPEC.validate_relationship("step", "state", "specialization")
        assert r.valid is True

    def test_association_item_to_item(self):
        """Item associates with item (classifier* → classifier*)."""
        r = KERNEL_SPEC.validate_relationship("item", "item", "association")
        assert r.valid is True

    def test_association_structure_to_item(self):
        """Structure associates with item (classifier* → classifier*)."""
        r = KERNEL_SPEC.validate_relationship("structure", "item", "association")
        assert r.valid is True

    def test_feature_typing_port_to_structure(self):
        """Port typed by structure (feature* → classifier*)."""
        r = KERNEL_SPEC.validate_relationship("port", "structure", "feature_typing")
        assert r.valid is True

    # ── v1.5: Expression succession ─────────────────────────────────

    def test_succession_expression_to_step(self):
        """Expression → step via succession (succ-05)."""
        r = KERNEL_SPEC.validate_relationship("expression", "step", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-05"

    def test_succession_expression_to_action(self):
        """Expression → action via succession (succ-05: expression→step*)."""
        r = KERNEL_SPEC.validate_relationship("expression", "action", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-05"

    def test_succession_step_to_expression(self):
        """Step → expression via succession (succ-06)."""
        r = KERNEL_SPEC.validate_relationship("step", "expression", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-06"

    def test_succession_action_to_expression(self):
        """Action → expression via succession (succ-06: step*→expression)."""
        r = KERNEL_SPEC.validate_relationship("action", "expression", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-06"

    def test_succession_expression_to_event(self):
        """Expression → event via succession (succ-07)."""
        r = KERNEL_SPEC.validate_relationship("expression", "event", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-07"

    def test_succession_event_to_expression(self):
        """Event → expression via succession (succ-08)."""
        r = KERNEL_SPEC.validate_relationship("event", "expression", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-08"

    def test_succession_expression_to_expression(self):
        """Expression → expression via succession (succ-09)."""
        r = KERNEL_SPEC.validate_relationship("expression", "expression", "succession")
        assert r.valid is True
        assert r.rule_id == "succ-09"

    # ── v1.5: Item↔Feature flow ─────────────────────────────────────

    def test_flow_item_to_feature(self):
        """Item → feature via flow (flow-02)."""
        r = KERNEL_SPEC.validate_relationship("item", "feature", "flow")
        assert r.valid is True
        assert r.rule_id == "flow-02"

    def test_flow_item_to_step(self):
        """Item → step via flow (flow-02: item→feature*)."""
        r = KERNEL_SPEC.validate_relationship("item", "step", "flow")
        assert r.valid is True
        assert r.rule_id == "flow-02"

    def test_flow_feature_to_item(self):
        """Feature → item via flow (flow-03)."""
        r = KERNEL_SPEC.validate_relationship("feature", "item", "flow")
        assert r.valid is True
        assert r.rule_id == "flow-03"

    def test_flow_step_to_item(self):
        """Step → item via flow (flow-03: feature*→item)."""
        r = KERNEL_SPEC.validate_relationship("step", "item", "flow")
        assert r.valid is True
        assert r.rule_id == "flow-03"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Forbidden Relationships
# ═════════════════════════════════════════════════════════════════════════════

class TestForbiddenRelationships:
    """Verify that invalid relationship patterns are rejected."""

    def test_specialization_classifier_to_feature_denied(self):
        r = KERNEL_SPEC.validate_relationship("structure", "feature", "specialization")
        assert r.valid is False

    def test_specialization_feature_to_classifier_denied(self):
        r = KERNEL_SPEC.validate_relationship("feature", "structure", "specialization")
        assert r.valid is False

    def test_triggering_classifier_to_step_denied(self):
        r = KERNEL_SPEC.validate_relationship("structure", "step", "triggering")
        assert r.valid is False

    def test_triggering_package_to_step_denied(self):
        r = KERNEL_SPEC.validate_relationship("package", "step", "triggering")
        assert r.valid is False

    def test_guarding_state_to_feature_denied(self):
        r = KERNEL_SPEC.validate_relationship("state", "feature", "guarding")
        assert r.valid is False

    def test_guarding_feature_to_expression_denied(self):
        r = KERNEL_SPEC.validate_relationship("feature", "expression", "guarding")
        assert r.valid is False

    def test_association_state_state_denied(self):
        """L4 entities should not form L2 associations."""
        r = KERNEL_SPEC.validate_relationship("state", "state", "association")
        assert r.valid is False

    def test_association_step_step_denied(self):
        r = KERNEL_SPEC.validate_relationship("step", "step", "association")
        assert r.valid is False

    def test_association_action_action_denied(self):
        r = KERNEL_SPEC.validate_relationship("action", "action", "association")
        assert r.valid is False

    def test_association_event_event_denied(self):
        """L4 event cannot form L2 association (cross-03)."""
        r = KERNEL_SPEC.validate_relationship("event", "event", "association")
        assert r.valid is False

    # ── v1.2 new denials ──────────────────────────────────────────

    def test_association_expression_expression_denied(self):
        """L4 expression cannot form L2 association (cross-04)."""
        r = KERNEL_SPEC.validate_relationship("expression", "expression", "association")
        assert r.valid is False

    def test_association_step_event_denied(self):
        """L4 cross-type: step→event association denied (cross-05)."""
        r = KERNEL_SPEC.validate_relationship("step", "event", "association")
        assert r.valid is False

    def test_association_event_expression_denied(self):
        """L4 cross-type: event→expression association denied (cross-11)."""
        r = KERNEL_SPEC.validate_relationship("event", "expression", "association")
        assert r.valid is False

    def test_association_expression_state_denied(self):
        """L4 cross-type: expression→state association denied (cross-13)."""
        r = KERNEL_SPEC.validate_relationship("expression", "state", "association")
        assert r.valid is False

    def test_association_action_expression_denied(self):
        """L4 cross-type: action→expression association denied (cross-06, via step*)."""
        r = KERNEL_SPEC.validate_relationship("action", "expression", "association")
        assert r.valid is False

    def test_association_state_event_denied(self):
        """L4 cross-type: state→event association denied (cross-07)."""
        r = KERNEL_SPEC.validate_relationship("state", "event", "association")
        assert r.valid is False

    def test_specialization_state_feature_denied(self):
        """State cannot specialize plain feature (spec-07)."""
        r = KERNEL_SPEC.validate_relationship("state", "feature", "specialization")
        assert r.valid is False

    def test_specialization_feature_state_denied(self):
        """Plain feature cannot specialize state (spec-08)."""
        r = KERNEL_SPEC.validate_relationship("feature", "state", "specialization")
        assert r.valid is False

    def test_ownership_item_structure_denied(self):
        """Item(passive) cannot own Structure(active) (own-05)."""
        r = KERNEL_SPEC.validate_relationship("item", "structure", "ownership")
        assert r.valid is False

    def test_succession_port_port_denied(self):
        """Port→port succession denied (succ-01 removed, no allow for port)."""
        r = KERNEL_SPEC.validate_relationship("port", "port", "succession")
        assert r.valid is False

    def test_succession_expression_port_denied(self):
        """Expression→port succession denied (no allow rule)."""
        r = KERNEL_SPEC.validate_relationship("expression", "port", "succession")
        assert r.valid is False

    def test_unknown_entity_denied(self):
        r = KERNEL_SPEC.validate_relationship("nonexistent", "feature", "membership")
        assert r.valid is False
        assert "Unknown entity" in (r.notes or "")

    def test_unknown_relation_denied(self):
        """No rules match an unknown relation → deny-by-default."""
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "nonexistent_rel")
        assert r.valid is False

    def test_membership_layer_violation(self):
        """L4 entity cannot contain L1 entity (layer order violated)."""
        r = KERNEL_SPEC.validate_relationship("step", "package", "membership")
        assert r.valid is False

    # ── v1.3 cross-category specialization denials ────────────────

    def test_item_cannot_specialize_structure(self):
        """Item(passive) cannot specialize Structure(active) (spec-09)."""
        r = KERNEL_SPEC.validate_relationship("item", "structure", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-09"

    def test_state_cannot_specialize_step(self):
        """State cannot specialize step/action (spec-10)."""
        r = KERNEL_SPEC.validate_relationship("state", "step", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-10"

    def test_state_cannot_specialize_action(self):
        """State cannot specialize action (spec-10 via step*)."""
        r = KERNEL_SPEC.validate_relationship("state", "action", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-10"

    def test_state_cannot_specialize_item(self):
        """State cannot specialize item (spec-11)."""
        r = KERNEL_SPEC.validate_relationship("state", "item", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-11"

    def test_event_cannot_specialize_state(self):
        """Event cannot specialize state (spec-12)."""
        r = KERNEL_SPEC.validate_relationship("event", "state", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-12"

    def test_expression_cannot_specialize_step(self):
        """Expression cannot specialize step/action (spec-13)."""
        r = KERNEL_SPEC.validate_relationship("expression", "step", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-13"

    def test_expression_cannot_specialize_action(self):
        """Expression cannot specialize action (spec-13 via step*)."""
        r = KERNEL_SPEC.validate_relationship("expression", "action", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-13"

    def test_state_cannot_specialize_structure(self):
        """State cannot specialize structure (spec-14)."""
        r = KERNEL_SPEC.validate_relationship("state", "structure", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-14"

    def test_state_cannot_specialize_datatype(self):
        """State cannot specialize datatype (spec-15)."""
        r = KERNEL_SPEC.validate_relationship("state", "datatype", "specialization")
        assert r.valid is False
        assert r.rule_id == "spec-15"

    # ── v1.4 association hotspot denials ─────────────────────────────

    def test_item_cannot_associate_step(self):
        """Item(passive) cannot associate with step (assoc-03)."""
        r = KERNEL_SPEC.validate_relationship("item", "step", "association")
        assert r.valid is False
        assert r.rule_id == "assoc-03"

    def test_item_cannot_associate_action(self):
        """Item(passive) cannot associate with action (assoc-03 via step*)."""
        r = KERNEL_SPEC.validate_relationship("item", "action", "association")
        assert r.valid is False
        assert r.rule_id == "assoc-03"

    def test_item_cannot_associate_structure(self):
        """Item(passive) cannot associate with structure (assoc-04)."""
        r = KERNEL_SPEC.validate_relationship("item", "structure", "association")
        assert r.valid is False
        assert r.rule_id == "assoc-04"

    def test_structure_to_item_still_allowed(self):
        """Reverse direction (structure→item) is still allowed via assoc-02."""
        r = KERNEL_SPEC.validate_relationship("structure", "item", "association")
        assert r.valid is True
        assert r.rule_id == "assoc-02"

    # ── v1.5: Triggering tightening denials ─────────────────────────

    def test_port_cannot_trigger_step(self):
        """Port cannot trigger step (trig-01 tightened to event only)."""
        r = KERNEL_SPEC.validate_relationship("port", "step", "triggering")
        assert r.valid is False

    def test_port_cannot_trigger_action(self):
        """Port cannot trigger action (trig-02 tightened to event only)."""
        r = KERNEL_SPEC.validate_relationship("port", "action", "triggering")
        assert r.valid is False

    def test_feature_cannot_trigger_step(self):
        """Plain feature cannot trigger step (v1.5: trig-01 narrowed to event)."""
        r = KERNEL_SPEC.validate_relationship("feature", "step", "triggering")
        assert r.valid is False

    def test_feature_cannot_trigger_action(self):
        """Plain feature cannot trigger action (v1.5: trig-02 narrowed to event)."""
        r = KERNEL_SPEC.validate_relationship("feature", "action", "triggering")
        assert r.valid is False

    # ── v1.5: Interaction denials ───────────────────────────────────

    def test_port_port_interaction_denied(self):
        """Port↔port interaction denied (inter-02)."""
        r = KERNEL_SPEC.validate_relationship("port", "port", "interaction")
        assert r.valid is False
        assert r.rule_id == "inter-02"

    def test_step_step_interaction_denied(self):
        """Step↔step interaction denied (inter-03)."""
        r = KERNEL_SPEC.validate_relationship("step", "step", "interaction")
        assert r.valid is False
        assert r.rule_id == "inter-03"

    def test_action_action_interaction_denied(self):
        """Action↔action interaction denied (inter-03 via step*)."""
        r = KERNEL_SPEC.validate_relationship("action", "action", "interaction")
        assert r.valid is False
        assert r.rule_id == "inter-03"

    def test_step_action_interaction_denied(self):
        """Step↔action interaction denied (inter-03 via step*)."""
        r = KERNEL_SPEC.validate_relationship("step", "action", "interaction")
        assert r.valid is False
        assert r.rule_id == "inter-03"

    # ── v1.6: Feature typing denials ────────────────────────────────

    def test_event_cannot_be_typed_by_structure(self):
        """Event cannot be typed (ftyp-05: event→metatype* DENY)."""
        r = KERNEL_SPEC.validate_relationship("event", "structure", "feature_typing")
        assert r.valid is False
        assert r.rule_id == "ftyp-05"

    def test_event_cannot_be_typed_by_datatype(self):
        """Event cannot be typed by datatype (ftyp-05)."""
        r = KERNEL_SPEC.validate_relationship("event", "datatype", "feature_typing")
        assert r.valid is False
        assert r.rule_id == "ftyp-05"

    def test_expression_cannot_be_typed_by_structure(self):
        """Expression cannot be typed (ftyp-06: expression→metatype* DENY)."""
        r = KERNEL_SPEC.validate_relationship("expression", "structure", "feature_typing")
        assert r.valid is False
        assert r.rule_id == "ftyp-06"

    def test_expression_cannot_be_typed_by_datatype(self):
        """Expression cannot be typed by datatype (ftyp-06)."""
        r = KERNEL_SPEC.validate_relationship("expression", "datatype", "feature_typing")
        assert r.valid is False
        assert r.rule_id == "ftyp-06"

    def test_port_cannot_be_typed_by_datatype(self):
        """Port cannot be typed by value type (ftyp-07)."""
        r = KERNEL_SPEC.validate_relationship("port", "datatype", "feature_typing")
        assert r.valid is False
        assert r.rule_id == "ftyp-07"

    def test_port_can_still_be_typed_by_structure(self):
        """Port→structure typing still allowed (ftyp-02)."""
        r = KERNEL_SPEC.validate_relationship("port", "structure", "feature_typing")
        assert r.valid is True
        assert r.rule_id == "ftyp-02"

    def test_feature_can_still_be_typed_by_datatype(self):
        """Plain feature→datatype typing still allowed (ftyp-03)."""
        r = KERNEL_SPEC.validate_relationship("feature", "datatype", "feature_typing")
        assert r.valid is True
        assert r.rule_id == "ftyp-03"

    # ── v1.6: Redefinition denials ──────────────────────────────────

    def test_action_cannot_redefine_feature(self):
        """Action cannot redefine plain feature (redef-02: step*→feature DENY)."""
        r = KERNEL_SPEC.validate_relationship("action", "feature", "redefinition")
        assert r.valid is False
        assert r.rule_id == "redef-02"

    def test_step_cannot_redefine_feature(self):
        """Step cannot redefine plain feature (redef-02)."""
        r = KERNEL_SPEC.validate_relationship("step", "feature", "redefinition")
        assert r.valid is False
        assert r.rule_id == "redef-02"

    def test_event_cannot_redefine_feature(self):
        """Event cannot redefine plain feature (redef-03)."""
        r = KERNEL_SPEC.validate_relationship("event", "feature", "redefinition")
        assert r.valid is False
        assert r.rule_id == "redef-03"

    def test_feature_can_still_redefine_feature(self):
        """Plain feature→feature redefinition still allowed (redef-01)."""
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "redefinition")
        assert r.valid is True
        assert r.rule_id == "redef-01"

    def test_port_can_still_redefine_port(self):
        """Port→port redefinition still allowed (redef-01)."""
        r = KERNEL_SPEC.validate_relationship("port", "port", "redefinition")
        assert r.valid is True
        assert r.rule_id == "redef-01"

    # ── v1.6: Interaction denial (feature→feature) ──────────────────

    def test_feature_feature_interaction_denied(self):
        """Plain feature↔feature interaction denied (inter-04)."""
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "interaction")
        assert r.valid is False
        assert r.rule_id == "inter-04"

    def test_port_feature_interaction_still_allowed(self):
        """Port→feature interaction still allowed (inter-01)."""
        r = KERNEL_SPEC.validate_relationship("port", "feature", "interaction")
        assert r.valid is True
        assert r.rule_id == "inter-01"

    def test_event_feature_interaction_still_allowed(self):
        """Event→feature interaction still allowed (inter-01)."""
        r = KERNEL_SPEC.validate_relationship("event", "feature", "interaction")
        assert r.valid is True
        assert r.rule_id == "inter-01"

    # ── v1.8: Connector L4 behavioral denials (via LayerConstraint) ──

    def test_connector_step_step_denied(self):
        """Step↔step connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("step", "step", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_action_action_denied(self):
        """Action↔action connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("action", "action", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_step_action_denied(self):
        """Step↔action connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("step", "action", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_event_event_denied(self):
        """Event↔event connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("event", "event", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_expression_expression_denied(self):
        """Expression↔expression connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("expression", "expression", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_step_event_denied(self):
        """Step↔event connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("step", "event", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_step_expression_denied(self):
        """Step↔expression connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("step", "expression", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_event_step_denied(self):
        """Event↔step connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("event", "step", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_event_expression_denied(self):
        """Event↔expression connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("event", "expression", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_expression_step_denied(self):
        """Expression↔step connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("expression", "step", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_expression_event_denied(self):
        """Expression↔event connector denied (layer constraint)."""
        r = KERNEL_SPEC.validate_relationship("expression", "event", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_feature_feature_still_allowed(self):
        """Feature↔feature connector still allowed (conn-01)."""
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "connector")
        assert r.valid is True
        assert r.rule_id == "conn-01"

    def test_connector_port_port_still_allowed(self):
        """Port↔port connector still allowed (conn-01)."""
        r = KERNEL_SPEC.validate_relationship("port", "port", "connector")
        assert r.valid is True
        assert r.rule_id == "conn-01"

    def test_connector_port_feature_still_allowed(self):
        """Port↔feature connector still allowed (conn-01)."""
        r = KERNEL_SPEC.validate_relationship("port", "feature", "connector")
        assert r.valid is True
        assert r.rule_id == "conn-01"

    # ── v1.7: Guarding explicit denials ────────────────────────────

    def test_guarding_state_step_denied(self):
        """State cannot be guarded by step (guard-04)."""
        r = KERNEL_SPEC.validate_relationship("state", "step", "guarding")
        assert r.valid is False
        assert r.rule_id == "guard-04"

    def test_guarding_state_action_denied(self):
        """State cannot be guarded by action (guard-04 via step*)."""
        r = KERNEL_SPEC.validate_relationship("state", "action", "guarding")
        assert r.valid is False
        assert r.rule_id == "guard-04"

    def test_guarding_state_event_denied(self):
        """State cannot be guarded by event (guard-05)."""
        r = KERNEL_SPEC.validate_relationship("state", "event", "guarding")
        assert r.valid is False
        assert r.rule_id == "guard-05"

    def test_guarding_state_port_denied(self):
        """State cannot be guarded by port (guard-06)."""
        r = KERNEL_SPEC.validate_relationship("state", "port", "guarding")
        assert r.valid is False
        assert r.rule_id == "guard-06"

    def test_guarding_state_expression_still_allowed(self):
        """State→expression guarding still allowed (guard-01)."""
        r = KERNEL_SPEC.validate_relationship("state", "expression", "guarding")
        assert r.valid is True
        assert r.rule_id == "guard-01"


# ═════════════════════════════════════════════════════════════════════════════
# 6. Self-Description / Coverage
# ═════════════════════════════════════════════════════════════════════════════

class TestSelfDescription:
    """Verify completeness and consistency of the spec."""

    def test_rule_count(self):
        """v2.0: 81 rules (67 explicit + 14 fallback)."""
        assert len(KERNEL_VALIDITY_RULES) == 81

    def test_relation_coverage_complete(self):
        """All 14 relations are covered by at least one non-fallback rule."""
        relation_names = {r.name for r in KERNEL_SCHEMA.relations}
        non_fallback_relations = {
            r.relationship_name for r in KERNEL_VALIDITY_RULES
            if not r.id.startswith("fallback-")
        }
        assert relation_names <= non_fallback_relations

    def test_spec_matches_definition_entities(self):
        """KERNEL_SPEC has same entities as KERNEL_SCHEMA."""
        assert KERNEL_SPEC.entities == KERNEL_SCHEMA.entities

    def test_spec_matches_definition_relations(self):
        """KERNEL_SPEC has same relations as KERNEL_SCHEMA."""
        assert KERNEL_SPEC.relations == KERNEL_SCHEMA.relations

    def test_spec_has_rules(self):
        """KERNEL_SPEC has rules, including those from KERNEL_SCHEMA."""
        assert len(KERNEL_SPEC.validity_rules) > 0
        # KERNEL_SCHEMA now loads explicit rules (67 in v2.0)
        assert len(KERNEL_SCHEMA.validity_rules) > 0
        assert len(KERNEL_SPEC.validity_rules) >= len(KERNEL_SCHEMA.validity_rules)

    def test_build_validated_schema(self):
        """build_validated_schema() produces equivalent to KERNEL_SPEC."""
        built = build_validated_schema()
        assert built.validity_rules == KERNEL_SPEC.validity_rules
        assert built.entities == KERNEL_SPEC.entities
        assert built.layer_constraints == KERNEL_SPEC.layer_constraints

    def test_layer_constraint_count(self):
        """v1.8: 2 layer constraints (association L4→L4, connector L4→L4)."""
        assert len(KERNEL_LAYER_CONSTRAINTS) == 2
        assert len(KERNEL_SPEC.layer_constraints) == 2

    def test_rule_coverage_analysis(self):
        """rule_coverage() returns meaningful metrics."""
        cov = KERNEL_SPEC.rule_coverage()
        assert cov["total_rules"] == len(KERNEL_VALIDITY_RULES)
        assert cov["relation_coverage"] == 1.0  # all relations covered
        assert isinstance(cov["covered_entities"], list)
        assert isinstance(cov["uncovered_entities"], list)

    def test_priority_bands(self):
        """Rules follow the documented priority band structure."""
        for rule in KERNEL_VALIDITY_RULES:
            if rule.id.startswith("fallback-"):
                assert rule.priority == 1
            else:
                assert rule.priority >= 40


# ═════════════════════════════════════════════════════════════════════════════
# 7. Effective Plays / Roles (v1.2)
# ═════════════════════════════════════════════════════════════════════════════

class TestEffectivePlays:
    """Test effective_plays() — inherited plays from ancestors."""

    def test_action_inherits_step_plays(self):
        """Action should inherit succession and triggering plays from step."""
        plays = KERNEL_SPEC.effective_plays("action")
        assert "succession:predecessor" in plays
        assert "succession:successor" in plays
        assert "triggering:responding" in plays

    def test_action_inherits_feature_plays(self):
        """Action should inherit connector plays from feature."""
        plays = KERNEL_SPEC.effective_plays("action")
        assert "connector:source" in plays
        assert "connector:target" in plays

    def test_action_inherits_metatype_plays(self):
        """Action should inherit specialization and association plays from metatype."""
        plays = KERNEL_SPEC.effective_plays("action")
        assert "specialization:supertype" in plays
        assert "specialization:subtype" in plays

    def test_action_own_plays_empty(self):
        """Action has no own plays — all inherited."""
        entity = KERNEL_SPEC.get_entity("action")
        assert entity.plays == ()

    def test_event_inherits_trigger_source(self):
        """Event should have triggering:trigger_source (v1.2 rename)."""
        plays = KERNEL_SPEC.effective_plays("event")
        assert "triggering:trigger_source" in plays

    def test_feature_own_plays(self):
        """Feature has its own plays."""
        plays = KERNEL_SPEC.effective_plays("feature")
        assert "connector:source" in plays
        assert "feature_typing:typed_feature" in plays

    def test_nonexistent_entity_returns_empty(self):
        plays = KERNEL_SPEC.effective_plays("nonexistent")
        assert plays == ()

    def test_effective_plays_sorted(self):
        """Returned plays should be sorted."""
        plays = KERNEL_SPEC.effective_plays("action")
        assert list(plays) == sorted(plays)


class TestEffectiveRoles:
    """Test effective_roles() — inherited roles from parent relations."""

    def test_flow_inherits_connector_roles(self):
        """Flow should inherit source/target from connector."""
        roles = KERNEL_SPEC.effective_roles("flow")
        role_names = {r.name for r in roles}
        assert "source" in role_names
        assert "target" in role_names

    def test_succession_has_own_and_inherited_roles(self):
        """Succession defines predecessor/successor and inherits source/target."""
        roles = KERNEL_SPEC.effective_roles("succession")
        role_map = {r.name: r for r in roles}
        assert "predecessor" in role_map
        assert "successor" in role_map
        # Also inherits source/target from connector (different names, so both present)
        assert "source" in role_map
        assert "target" in role_map

    def test_interaction_inherits_connector_roles(self):
        """Interaction has no own roles — inherits from connector."""
        roles = KERNEL_SPEC.effective_roles("interaction")
        role_names = {r.name for r in roles}
        assert "source" in role_names
        assert "target" in role_names

    def test_triggering_own_roles(self):
        """Triggering has its own roles (no parent)."""
        roles = KERNEL_SPEC.effective_roles("triggering")
        role_names = {r.name for r in roles}
        assert "trigger_source" in role_names
        assert "responding" in role_names

    def test_nonexistent_relation_returns_empty(self):
        roles = KERNEL_SPEC.effective_roles("nonexistent")
        assert roles == ()

    def test_effective_roles_sorted_by_name(self):
        """Returned roles should be sorted by name."""
        roles = KERNEL_SPEC.effective_roles("succession")
        names = [r.name for r in roles]
        assert names == sorted(names)


# ═════════════════════════════════════════════════════════════════════════════
# 8. Layer Constraints (v1.8)
# ═════════════════════════════════════════════════════════════════════════════

class TestLayerConstraints:
    """Verify LayerConstraint replaces cartesian cross-layer/connector rules."""

    def test_association_constraint_denies_l4_l4(self):
        """L4→L4 association denied by constraint (replaces cross-01~14)."""
        r = KERNEL_SPEC.validate_relationship("event", "expression", "association")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:association"

    def test_association_constraint_allows_step_state(self):
        """step*↔state association is exempt from constraint."""
        r = KERNEL_SPEC.validate_relationship("step", "state", "association")
        assert r.valid is True

    def test_association_constraint_allows_action_state(self):
        """action↔state association is exempt (action matches step*)."""
        r = KERNEL_SPEC.validate_relationship("action", "state", "association")
        assert r.valid is True

    def test_association_constraint_allows_state_step(self):
        """state→step association is exempt (reverse direction)."""
        r = KERNEL_SPEC.validate_relationship("state", "step", "association")
        assert r.valid is True

    def test_association_constraint_allows_state_action(self):
        """state→action association is exempt (action matches step*)."""
        r = KERNEL_SPEC.validate_relationship("state", "action", "association")
        assert r.valid is True

    def test_connector_constraint_denies_l4_l4(self):
        """L4→L4 connector denied by constraint (replaces conn-02~10)."""
        r = KERNEL_SPEC.validate_relationship("step", "event", "connector")
        assert r.valid is False
        assert r.rule_id == "constraint:L4→L4:connector"

    def test_connector_constraint_no_state_exception(self):
        """state→state connector also denied (state is L4, no exception)."""
        r = KERNEL_SPEC.validate_relationship("state", "state", "connector")
        assert r.valid is False

    def test_constraint_does_not_affect_l1_l1(self):
        """L1→L1 connector still allowed (not L4→L4)."""
        r = KERNEL_SPEC.validate_relationship("feature", "feature", "connector")
        assert r.valid is True
        assert r.rule_id == "conn-01"

    def test_constraint_does_not_affect_l1_l4(self):
        """L1→L4 connector still allowed (not L4→L4)."""
        r = KERNEL_SPEC.validate_relationship("port", "step", "connector")
        assert r.valid is True
        assert r.rule_id == "conn-01"

    def test_constraint_does_not_affect_l1_l4_association(self):
        """L1→L4 association (classifier*→state) still uses rules, not constraint."""
        r = KERNEL_SPEC.validate_relationship("structure", "state", "association")
        assert r.valid is True


# ═════════════════════════════════════════════════════════════════════════════
# 9. Package Association (v1.9)
# ═════════════════════════════════════════════════════════════════════════════

class TestPackageAssociation:
    """v1.9: Package can participate in associations."""

    def test_package_to_structure_allowed(self):
        """Package → structure via association (assoc-05: package→metatype*)."""
        r = KERNEL_SPEC.validate_relationship("package", "structure", "association")
        assert r.valid is True
        assert r.rule_id == "assoc-05"

    def test_package_to_item_allowed(self):
        """Package → item via association (assoc-05: package→metatype*)."""
        r = KERNEL_SPEC.validate_relationship("package", "item", "association")
        assert r.valid is True
        assert r.rule_id == "assoc-05"

    def test_structure_to_package_allowed(self):
        """Structure → package via association (assoc-06: metatype*→package)."""
        r = KERNEL_SPEC.validate_relationship("structure", "package", "association")
        assert r.valid is True
        assert r.rule_id == "assoc-06"

    def test_package_to_package_allowed(self):
        """Package → package via association (assoc-07)."""
        r = KERNEL_SPEC.validate_relationship("package", "package", "association")
        assert r.valid is True
        assert r.rule_id == "assoc-07"

    def test_package_has_association_plays(self):
        """Package entity declares association plays (v1.9)."""
        pkg = KERNEL_SPEC.get_entity("package")
        assert "association:source_end" in pkg.plays
        assert "association:target_end" in pkg.plays


# ═════════════════════════════════════════════════════════════════════════════
# 10. Transition (v2.0)
# ═════════════════════════════════════════════════════════════════════════════

class TestTransition:
    """v2.0: State transition relation."""

    def test_transition_state_to_state_allowed(self):
        """State → state via transition (trans-01)."""
        r = KERNEL_SPEC.validate_relationship("state", "state", "transition")
        assert r.valid is True
        assert r.rule_id == "trans-01"

    def test_transition_feature_to_state_denied(self):
        """Feature → state transition denied (fallback)."""
        r = KERNEL_SPEC.validate_relationship("feature", "state", "transition")
        assert r.valid is False

    def test_transition_state_to_feature_denied(self):
        """State → feature transition denied (fallback)."""
        r = KERNEL_SPEC.validate_relationship("state", "feature", "transition")
        assert r.valid is False

    def test_transition_step_to_state_denied(self):
        """Step → state transition denied (fallback)."""
        r = KERNEL_SPEC.validate_relationship("step", "state", "transition")
        assert r.valid is False

    def test_transition_state_to_step_denied(self):
        """State → step transition denied (fallback)."""
        r = KERNEL_SPEC.validate_relationship("state", "step", "transition")
        assert r.valid is False

    def test_transition_has_fallback_rule(self):
        """Transition has a deny-by-default fallback rule."""
        fallback = [r for r in KERNEL_VALIDITY_RULES if r.id == "fallback-transition"]
        assert len(fallback) == 1
        assert fallback[0].valid is False
        assert fallback[0].priority == 1


# ═════════════════════════════════════════════════════════════════════════════
# 11. Effective Rule Coverage (v1.9)
# ═════════════════════════════════════════════════════════════════════════════

class TestEffectiveRuleCoverage:
    """v1.9: rule_coverage() includes effective_entity_coverage."""

    def test_effective_coverage_higher_than_literal(self):
        """Effective coverage should be >= literal coverage."""
        cov = KERNEL_SPEC.rule_coverage()
        assert cov["effective_entity_coverage"] >= cov["entity_coverage"]

    def test_effective_coverage_includes_wildcarded_entities(self):
        """Entities only referenced by wildcard patterns should appear in effective coverage."""
        cov = KERNEL_SPEC.rule_coverage()
        effective = set(cov["effective_covered_entities"])
        literal = set(cov["covered_entities"])
        # action is reachable via step* but never literal
        assert "action" in effective
        assert len(effective) >= len(literal)

    def test_effective_uncovered_is_complement(self):
        """effective_uncovered + effective_covered = all entities."""
        cov = KERNEL_SPEC.rule_coverage()
        entity_names = {e.name for e in KERNEL_SPEC.entities}
        effective = set(cov["effective_covered_entities"])
        uncovered = set(cov["effective_uncovered_entities"])
        assert effective | uncovered == entity_names
        assert effective & uncovered == set()

    def test_same_category_condition_skip_at_kernel(self):
        """SAME_CATEGORY condition passes at kernel level (profile-only)."""
        from ea_kernel.types import KernelConditionType, KernelRuleCondition
        ok, msg = KERNEL_SPEC._check_condition(
            KernelRuleCondition(KernelConditionType.SAME_CATEGORY),
            "structure", "item",
        )
        assert ok is True
        assert "profile-level" in msg
