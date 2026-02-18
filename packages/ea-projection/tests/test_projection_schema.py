"""Tests for ea_projection.projection_schema — ProjectionSchema SchemaPort compliance."""

from ea_projection.projection_schema import PROJECTION_SCHEMA, ProjectionEntity, ProjectionRelation, ProjectionSchema


class TestProjectionSchema:
    def test_schema_is_frozen(self):
        assert isinstance(PROJECTION_SCHEMA, ProjectionSchema)

    def test_has_entities(self):
        assert len(PROJECTION_SCHEMA.entities) == 18

    def test_has_relations(self):
        assert len(PROJECTION_SCHEMA.relations) == 10  # 10 shared relations

    def test_entities_are_projection_entity(self):
        for e in PROJECTION_SCHEMA.entities:
            assert isinstance(e, ProjectionEntity)

    def test_relations_are_projection_relation(self):
        for r in PROJECTION_SCHEMA.relations:
            assert isinstance(r, ProjectionRelation)

    def test_get_entity_found(self):
        e = PROJECTION_SCHEMA.get_entity("projection_service")
        assert e is not None
        assert e.name == "projection_service"

    def test_get_entity_not_found(self):
        assert PROJECTION_SCHEMA.get_entity("nonexistent") is None

    def test_get_relation_found(self):
        r = PROJECTION_SCHEMA.get_relation("contains")
        assert r is not None
        assert r.name == "contains"

    def test_get_relation_not_found(self):
        assert PROJECTION_SCHEMA.get_relation("nonexistent") is None

    def test_has_abstract_projection_layer(self):
        e = PROJECTION_SCHEMA.get_entity("projection_layer")
        assert e is not None
        assert e.is_abstract is True

    def test_satisfies_schema_port(self):
        from ea_profile.types import SchemaPort
        assert isinstance(PROJECTION_SCHEMA, SchemaPort)
