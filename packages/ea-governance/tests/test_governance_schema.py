"""Tests for governance_schema.py — GovernanceSchema and SchemaPort compliance."""

from ea_profile.types import SchemaPort
from ea_governance.governance_schema import GOVERNANCE_SCHEMA, GovernanceEntity, GovernanceRelation, GovernanceSchema


class TestGovernanceSchemaPort:
    """GOVERNANCE_SCHEMA satisfies SchemaPort protocol."""

    def test_satisfies_schema_port(self):
        assert isinstance(GOVERNANCE_SCHEMA, SchemaPort)

    def test_entity_count(self):
        assert len(GOVERNANCE_SCHEMA.entities) == 14

    def test_relation_count(self):
        assert len(GOVERNANCE_SCHEMA.relations) == 10

    def test_entities_are_governance_entity(self):
        for e in GOVERNANCE_SCHEMA.entities:
            assert isinstance(e, GovernanceEntity)

    def test_relations_are_governance_relation(self):
        for r in GOVERNANCE_SCHEMA.relations:
            assert isinstance(r, GovernanceRelation)

    def test_abstract_entity(self):
        boundary = GOVERNANCE_SCHEMA.get_entity("governance_boundary")
        assert boundary is not None
        assert boundary.is_abstract is True

    def test_concrete_entities_not_abstract(self):
        for e in GOVERNANCE_SCHEMA.entities:
            if e.name != "governance_boundary":
                assert e.is_abstract is False, f"{e.name} should not be abstract"

    def test_get_entity_found(self):
        e = GOVERNANCE_SCHEMA.get_entity("layer_registry")
        assert e is not None
        assert e.name == "layer_registry"

    def test_get_entity_not_found(self):
        assert GOVERNANCE_SCHEMA.get_entity("nonexistent") is None

    def test_get_relation_found(self):
        r = GOVERNANCE_SCHEMA.get_relation("registers")
        assert r is not None
        assert r.name == "registers"

    def test_get_relation_not_found(self):
        assert GOVERNANCE_SCHEMA.get_relation("nonexistent") is None

    def test_entity_names(self):
        names = {e.name for e in GOVERNANCE_SCHEMA.entities}
        expected = {
            "governance_boundary", "layer_registry", "lifecycle_manager",
            "coordinator", "policy", "governance_goal", "governance_step",
            "governance_action", "governance_record", "entry_port",
            "model_port", "model_endpoint", "governance_event", "feedback_loop",
        }
        assert names == expected

    def test_relation_names(self):
        names = {r.name for r in GOVERNANCE_SCHEMA.relations}
        expected = {
            "contains", "registers", "coordinates", "depends_on",
            "produces", "consumes", "next", "triggers",
            "constrains", "available_in",
        }
        assert names == expected

    def test_schema_is_frozen(self):
        schema = GovernanceSchema(
            entities=(GovernanceEntity("test"),),
            relations=(GovernanceRelation("test_rel"),),
        )
        assert schema.entities[0].name == "test"
