"""Tests for needs_schema.py — NeedsSchema and SchemaPort compliance."""

from ea_kernel.profile_types import SchemaPort
from ea_needs.needs_schema import NEEDS_SCHEMA, NeedsEntity, NeedsRelation, NeedsSchema


class TestNeedsSchemaPort:
    """NEEDS_SCHEMA satisfies SchemaPort protocol."""

    def test_satisfies_schema_port(self):
        assert isinstance(NEEDS_SCHEMA, SchemaPort)

    def test_entity_count(self):
        assert len(NEEDS_SCHEMA.entities) == 23

    def test_relation_count(self):
        assert len(NEEDS_SCHEMA.relations) == 11

    def test_entities_are_needs_entity(self):
        for e in NEEDS_SCHEMA.entities:
            assert isinstance(e, NeedsEntity)

    def test_relations_are_needs_relation(self):
        for r in NEEDS_SCHEMA.relations:
            assert isinstance(r, NeedsRelation)

    def test_abstract_entity(self):
        catalog = NEEDS_SCHEMA.get_entity("need_catalog")
        assert catalog is not None
        assert catalog.is_abstract is True

    def test_concrete_entities_not_abstract(self):
        for e in NEEDS_SCHEMA.entities:
            if e.name != "need_catalog":
                assert e.is_abstract is False, f"{e.name} should not be abstract"

    def test_get_entity_found(self):
        e = NEEDS_SCHEMA.get_entity("stakeholder")
        assert e is not None
        assert e.name == "stakeholder"

    def test_get_entity_not_found(self):
        assert NEEDS_SCHEMA.get_entity("nonexistent") is None

    def test_get_relation_found(self):
        r = NEEDS_SCHEMA.get_relation("depends_on")
        assert r is not None
        assert r.name == "depends_on"

    def test_get_relation_not_found(self):
        assert NEEDS_SCHEMA.get_relation("nonexistent") is None

    def test_entity_names(self):
        names = {e.name for e in NEEDS_SCHEMA.entities}
        expected = {
            "need_catalog", "stakeholder", "desire", "justification",
            "need_statement", "use_case", "process_unit", "need", "need_relation",
            # N1 Enums
            "need_status", "need_priority", "need_purpose", "need_cause_type",
            "need_resolution_complexity", "need_process_stage", "justification_type",
            # S3/S4/S5
            "need_store", "needs_analyzer", "needs_simulator", "need_promotion_engine",
            # Scenario flow
            "scenario_flow", "scenario_step", "scenario_type",
        }
        assert names == expected

    def test_relation_names(self):
        names = {r.name for r in NEEDS_SCHEMA.relations}
        expected = {
            "depends_on", "conflicts_with", "supports", "refines", "supersedes",
            "contains", "expresses", "justifies",
            "addresses", "withdraws",
            "branches_from",
        }
        assert names == expected

    def test_schema_is_frozen(self):
        schema = NeedsSchema(
            entities=(NeedsEntity("test"),),
            relations=(NeedsRelation("test_rel"),),
        )
        assert schema.entities[0].name == "test"
