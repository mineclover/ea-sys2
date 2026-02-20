"""Tests for kernel metamodel definitions."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ea_kernel.definition import (
    ATTRIBUTES,
    KERNEL_METADATA,
    KERNEL_SCHEMA,
    KERNEL_VERSION,
    L1_ENTITIES,
    L2_RELATIONS,
    L3_RELATIONS,
    L4_ENTITIES,
)
from ea_kernel.types import Layer


class TestVersionPin:
    """Verify kernel version 2.5.0 structural contract."""

    def test_kernel_version(self):
        assert KERNEL_VERSION == "2.5.0"

    def test_metadata_version(self):
        assert KERNEL_METADATA["version"] == "2.5.0"

    def test_metadata_entity_count(self):
        assert KERNEL_METADATA["entities"] == len(KERNEL_SCHEMA.entities)

    def test_metadata_relation_count(self):
        assert KERNEL_METADATA["relations"] == len(KERNEL_SCHEMA.relations)

    def test_metadata_attribute_count(self):
        assert KERNEL_METADATA["attributes"] == len(ATTRIBUTES)

    def test_init_version_matches(self):
        from ea_kernel import __version__
        assert __version__ == KERNEL_VERSION


class TestKernelCounts:
    """Verify the 31-element kernel structure."""

    def test_l1_entity_count(self):
        assert len(L1_ENTITIES) == 12

    def test_l2_relation_count(self):
        assert len(L2_RELATIONS) == 8

    def test_l3_relation_count(self):
        assert len(L3_RELATIONS) == 6

    def test_l4_entity_count(self):
        assert len(L4_ENTITIES) == 5

    def test_total_element_count(self):
        total = len(L1_ENTITIES) + len(L2_RELATIONS) + len(L3_RELATIONS) + len(L4_ENTITIES)
        assert total == 31

    def test_attribute_count(self):
        assert len(ATTRIBUTES) == 20


class TestEntityHierarchy:
    """Verify entity inheritance structure."""

    def test_element_is_root(self):
        element = KERNEL_SCHEMA.get_entity("element")
        assert element is not None
        assert element.parent is None
        assert element.is_abstract

    def test_namespace_extends_element(self):
        ns = KERNEL_SCHEMA.get_entity("namespace")
        assert ns is not None
        assert ns.parent == "element"
        assert ns.is_abstract  # abstract — use package for concrete namespace

    def test_metatype_extends_namespace(self):
        mt = KERNEL_SCHEMA.get_entity("metatype")
        assert mt is not None
        assert mt.parent == "namespace"
        assert mt.is_abstract

    def test_feature_extends_metatype(self):
        """KerML insight: Feature IS a Type."""
        feat = KERNEL_SCHEMA.get_entity("feature")
        assert feat is not None
        assert feat.parent == "metatype"
        assert not feat.is_abstract  # features are concrete

    def test_classifier_extends_metatype(self):
        cls = KERNEL_SCHEMA.get_entity("classifier")
        assert cls is not None
        assert cls.parent == "metatype"
        assert cls.is_abstract

    def test_structure_extends_classifier(self):
        struct = KERNEL_SCHEMA.get_entity("structure")
        assert struct is not None
        assert struct.parent == "classifier"

    def test_item_extends_classifier(self):
        item = KERNEL_SCHEMA.get_entity("item")
        assert item is not None
        assert item.parent == "classifier"

    def test_datatype_extends_classifier(self):
        dt = KERNEL_SCHEMA.get_entity("datatype")
        assert dt is not None
        assert dt.parent == "classifier"

    def test_port_extends_feature(self):
        port = KERNEL_SCHEMA.get_entity("port")
        assert port is not None
        assert port.parent == "feature"

    def test_step_extends_feature(self):
        step = KERNEL_SCHEMA.get_entity("step")
        assert step is not None
        assert step.parent == "feature"

    def test_action_extends_step(self):
        action = KERNEL_SCHEMA.get_entity("action")
        assert action is not None
        assert action.parent == "step"

    def test_state_extends_metatype(self):
        state = KERNEL_SCHEMA.get_entity("state")
        assert state is not None
        assert state.parent == "metatype"

    def test_event_extends_feature(self):
        event = KERNEL_SCHEMA.get_entity("event")
        assert event is not None
        assert event.parent == "feature"

    def test_expression_extends_feature(self):
        expr = KERNEL_SCHEMA.get_entity("expression")
        assert expr is not None
        assert expr.parent == "feature"

    def test_no_inheritance_cycles(self):
        for entity in KERNEL_SCHEMA.entities:
            ancestors = KERNEL_SCHEMA.all_entity_ancestors(entity.name)
            assert entity.name not in ancestors, (
                f"Cycle detected: {entity.name} → {ancestors}"
            )

    def test_all_parents_exist(self):
        names = {e.name for e in KERNEL_SCHEMA.entities}
        for entity in KERNEL_SCHEMA.entities:
            if entity.parent:
                assert entity.parent in names, (
                    f"{entity.name} has unknown parent '{entity.parent}'"
                )

    def test_max_depth(self):
        max_depth = max(
            KERNEL_SCHEMA.entity_depth(e.name)
            for e in KERNEL_SCHEMA.entities
        )
        # action: element → namespace → metatype → feature → step → action = 5
        assert max_depth == 5


class TestRelationHierarchy:
    """Verify relation inheritance and roles."""

    def test_flow_extends_connector(self):
        flow = KERNEL_SCHEMA.get_relation("flow")
        assert flow is not None
        assert flow.parent == "connector"

    def test_succession_extends_connector(self):
        succ = KERNEL_SCHEMA.get_relation("succession")
        assert succ is not None
        assert succ.parent == "connector"

    def test_interaction_extends_connector(self):
        inter = KERNEL_SCHEMA.get_relation("interaction")
        assert inter is not None
        assert inter.parent == "connector"

    def test_triggering_is_standalone(self):
        trig = KERNEL_SCHEMA.get_relation("triggering")
        assert trig is not None
        assert trig.parent is None

    def test_guarding_is_standalone(self):
        guard = KERNEL_SCHEMA.get_relation("guarding")
        assert guard is not None
        assert guard.parent is None

    def test_all_relation_parents_exist(self):
        rel_names = {r.name for r in KERNEL_SCHEMA.relations}
        for rel in KERNEL_SCHEMA.relations:
            if rel.parent:
                assert rel.parent in rel_names, (
                    f"{rel.name} has unknown parent '{rel.parent}'"
                )

    def test_connector_has_source_target_roles(self):
        conn = KERNEL_SCHEMA.get_relation("connector")
        assert conn is not None
        role_names = {r.name for r in conn.roles}
        assert "source" in role_names
        assert "target" in role_names

    def test_membership_roles(self):
        mem = KERNEL_SCHEMA.get_relation("membership")
        role_names = {r.name for r in mem.roles}
        assert "container" in role_names
        assert "member" in role_names

    def test_specialization_roles(self):
        spec = KERNEL_SCHEMA.get_relation("specialization")
        role_names = {r.name for r in spec.roles}
        assert "supertype" in role_names
        assert "subtype" in role_names


class TestLayerDistribution:
    """Verify elements are in correct layers."""

    def test_l1_entities(self):
        l1 = KERNEL_SCHEMA.entities_in_layer(Layer.L1)
        names = {e.name for e in l1}
        expected = {"element", "namespace", "metatype", "feature", "port", "input_port", "output_port", "classifier", "structure", "item", "datatype", "package"}
        assert names == expected

    def test_l2_relations(self):
        l2 = KERNEL_SCHEMA.relations_in_layer(Layer.L2)
        names = {r.name for r in l2}
        expected = {
            "membership", "ownership", "specialization", "feature_typing",
            "association", "connector", "redefinition", "subsetting",
        }
        assert names == expected

    def test_l3_relations(self):
        l3 = KERNEL_SCHEMA.relations_in_layer(Layer.L3)
        names = {r.name for r in l3}
        expected = {"flow", "succession", "interaction", "triggering", "guarding", "transition"}
        assert names == expected

    def test_l4_entities(self):
        l4 = KERNEL_SCHEMA.entities_in_layer(Layer.L4)
        names = {e.name for e in l4}
        expected = {"step", "action", "event", "expression", "state"}
        assert names == expected


class TestRolePlaying:
    """Verify that all roles mentioned in relations are played by entities."""

    def test_all_role_players_exist(self):
        entity_names = {e.name for e in KERNEL_SCHEMA.entities}
        for rel in KERNEL_SCHEMA.relations:
            for role in rel.roles:
                # Role player must be an entity or ancestor of an entity
                assert role.player in entity_names, (
                    f"Relation '{rel.name}' role '{role.name}' references "
                    f"unknown entity '{role.player}'"
                )

    def _collect_all_roles(self, rel_name: str) -> set[str]:
        """Collect roles defined on a relation and all its ancestors."""
        roles: set[str] = set()
        rel = KERNEL_SCHEMA.get_relation(rel_name)
        while rel:
            roles.update(r.name for r in rel.roles)
            rel = KERNEL_SCHEMA.get_relation(rel.parent) if rel.parent else None
        return roles

    def test_entity_plays_match_relations(self):
        """Every plays declaration on an entity should correspond to a relation role."""
        for entity in KERNEL_SCHEMA.entities:
            for play in entity.plays:
                rel_name, role_name = play.split(":")
                rel = KERNEL_SCHEMA.get_relation(rel_name)
                assert rel is not None, (
                    f"Entity '{entity.name}' plays role in unknown relation '{rel_name}'"
                )
                all_roles = self._collect_all_roles(rel_name)
                assert role_name in all_roles, (
                    f"Entity '{entity.name}' plays unknown role '{role_name}' "
                    f"in relation '{rel_name}' (available: {all_roles})"
                )


class TestL2L3Transition:
    """Verify the L2→L3 behavioral qualification pattern."""

    def test_l3_connector_subtypes_inherit_roles(self):
        """Flow, Succession, Interaction inherit source/target from Connector."""
        connector = KERNEL_SCHEMA.get_relation("connector")
        assert connector is not None

        for sub_name in ("flow", "succession", "interaction"):
            sub = KERNEL_SCHEMA.get_relation(sub_name)
            assert sub is not None
            assert sub.parent == "connector"
            # Subtypes don't redefine roles — they inherit from connector

    def test_flow_adds_direction(self):
        flow = KERNEL_SCHEMA.get_relation("flow")
        assert "direction" in flow.owns

    def test_succession_adds_guard(self):
        succ = KERNEL_SCHEMA.get_relation("succession")
        assert "guard_expr" in succ.owns

    def test_interaction_adds_kind(self):
        inter = KERNEL_SCHEMA.get_relation("interaction")
        assert "kind" in inter.owns

    def test_transition_relation_exists(self):
        trans = KERNEL_SCHEMA.get_relation("transition")
        assert trans is not None
        assert trans.layer == Layer.L3
        assert trans.parent is None  # standalone, not connector subtype

    def test_transition_roles(self):
        trans = KERNEL_SCHEMA.get_relation("transition")
        role_names = {r.name for r in trans.roles}
        assert "source_state" in role_names
        assert "target_state" in role_names

    def test_state_plays_transition(self):
        state = KERNEL_SCHEMA.get_entity("state")
        assert "transition:source_state" in state.plays
        assert "transition:target_state" in state.plays

    def test_expression_owns_kind(self):
        expr = KERNEL_SCHEMA.get_entity("expression")
        assert "kind" in expr.owns

    def test_succession_owns_execution_mode(self):
        succ = KERNEL_SCHEMA.get_relation("succession")
        assert "execution_mode" in succ.owns

    def test_succession_owns_join_mode(self):
        succ = KERNEL_SCHEMA.get_relation("succession")
        assert "join_mode" in succ.owns
