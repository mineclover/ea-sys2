"""Tests for decision_schema.py — DecisionSchema and SchemaPort compliance."""

from ea_profile.types import SchemaPort
from ea_decision.decision_schema import DECISION_SCHEMA, DecisionEntity, DecisionRelation, DecisionSchema


class TestDecisionSchemaPort:
    """DECISION_SCHEMA satisfies SchemaPort protocol."""

    def test_satisfies_schema_port(self):
        assert isinstance(DECISION_SCHEMA, SchemaPort)

    def test_entity_count(self):
        assert len(DECISION_SCHEMA.entities) == 14

    def test_relation_count(self):
        assert len(DECISION_SCHEMA.relations) == 10

    def test_entities_are_decision_entity(self):
        for e in DECISION_SCHEMA.entities:
            assert isinstance(e, DecisionEntity)

    def test_relations_are_decision_relation(self):
        for r in DECISION_SCHEMA.relations:
            assert isinstance(r, DecisionRelation)

    def test_abstract_entity(self):
        topic = DECISION_SCHEMA.get_entity("decision_topic")
        assert topic is not None
        assert topic.is_abstract is True

    def test_concrete_entities_not_abstract(self):
        for e in DECISION_SCHEMA.entities:
            if e.name != "decision_topic":
                assert e.is_abstract is False, f"{e.name} should not be abstract"

    def test_get_entity_found(self):
        e = DECISION_SCHEMA.get_entity("intent")
        assert e is not None
        assert e.name == "intent"

    def test_get_entity_not_found(self):
        assert DECISION_SCHEMA.get_entity("nonexistent") is None

    def test_get_relation_found(self):
        r = DECISION_SCHEMA.get_relation("evaluates")
        assert r is not None
        assert r.name == "evaluates"

    def test_get_relation_not_found(self):
        assert DECISION_SCHEMA.get_relation("nonexistent") is None

    def test_entity_names(self):
        names = {e.name for e in DECISION_SCHEMA.entities}
        expected = {
            "decision_topic", "topic", "intent", "choice_option", "choice",
            "decision_result", "evidence", "evidence_collection",
            "evaluation_dimension", "evaluation_result", "decision_pattern",
            "pattern_schema", "decision_lifecycle", "rationale",
        }
        assert names == expected

    def test_relation_names(self):
        names = {r.name for r in DECISION_SCHEMA.relations}
        expected = {
            "evaluates", "selects", "produces", "justifies", "contains",
            "supersedes", "applies", "refines", "depends_on", "transitions_to",
        }
        assert names == expected

    def test_schema_is_frozen(self):
        schema = DecisionSchema(
            entities=(DecisionEntity("test"),),
            relations=(DecisionRelation("test_rel"),),
        )
        assert schema.entities[0].name == "test"
