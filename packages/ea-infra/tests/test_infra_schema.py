"""Tests for ea_infra.infra_schema — InfraSchema SchemaPort compliance."""

from ea_infra.infra_schema import INFRA_SCHEMA, InfraEntity, InfraRelation, InfraSchema


class TestInfraSchema:
    def test_schema_is_frozen(self):
        assert isinstance(INFRA_SCHEMA, InfraSchema)

    def test_has_entities(self):
        assert len(INFRA_SCHEMA.entities) > 0

    def test_has_relations(self):
        assert len(INFRA_SCHEMA.relations) == 10  # 10 shared relations

    def test_entities_are_infra_entity(self):
        for e in INFRA_SCHEMA.entities:
            assert isinstance(e, InfraEntity)

    def test_relations_are_infra_relation(self):
        for r in INFRA_SCHEMA.relations:
            assert isinstance(r, InfraRelation)

    def test_get_entity_found(self):
        e = INFRA_SCHEMA.get_entity("data_platform_service")
        assert e is not None
        assert e.name == "data_platform_service"

    def test_get_entity_not_found(self):
        assert INFRA_SCHEMA.get_entity("nonexistent") is None

    def test_get_relation_found(self):
        r = INFRA_SCHEMA.get_relation("contains")
        assert r is not None
        assert r.name == "contains"

    def test_get_relation_not_found(self):
        assert INFRA_SCHEMA.get_relation("nonexistent") is None

    def test_has_abstract_infra_layer(self):
        e = INFRA_SCHEMA.get_entity("infra_layer")
        assert e is not None
        assert e.is_abstract is True

    def test_satisfies_schema_port(self):
        from ea_profile.types import SchemaPort
        assert isinstance(INFRA_SCHEMA, SchemaPort)
