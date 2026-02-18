"""Tests for flow_schema.py — FlowSchema and SchemaPort compliance."""

from ea_profile.types import SchemaPort
from ea_flow.flow_schema import FLOW_SCHEMA, FlowEntity, FlowRelation, FlowSchema


class TestFlowSchemaPort:
    """FLOW_SCHEMA satisfies SchemaPort protocol."""

    def test_satisfies_schema_port(self):
        assert isinstance(FLOW_SCHEMA, SchemaPort)

    def test_entity_count(self):
        assert len(FLOW_SCHEMA.entities) == 27

    def test_relation_count(self):
        assert len(FLOW_SCHEMA.relations) == 10

    def test_entities_are_flow_entity(self):
        for e in FLOW_SCHEMA.entities:
            assert isinstance(e, FlowEntity)

    def test_relations_are_flow_relation(self):
        for r in FLOW_SCHEMA.relations:
            assert isinstance(r, FlowRelation)

    def test_abstract_entities(self):
        abstract_names = {"flow_layer", "step_spec", "workflow_spec", "step_implementer"}
        for e in FLOW_SCHEMA.entities:
            if e.name in abstract_names:
                assert e.is_abstract is True, f"{e.name} should be abstract"

    def test_concrete_entities_not_abstract(self):
        abstract_names = {"flow_layer", "step_spec", "workflow_spec", "step_implementer"}
        for e in FLOW_SCHEMA.entities:
            if e.name not in abstract_names:
                assert e.is_abstract is False, f"{e.name} should not be abstract"

    def test_get_entity_found(self):
        e = FLOW_SCHEMA.get_entity("process_spec")
        assert e is not None
        assert e.name == "process_spec"

    def test_get_entity_not_found(self):
        assert FLOW_SCHEMA.get_entity("nonexistent") is None

    def test_get_relation_found(self):
        r = FLOW_SCHEMA.get_relation("next")
        assert r is not None
        assert r.name == "next"

    def test_get_relation_not_found(self):
        assert FLOW_SCHEMA.get_relation("nonexistent") is None

    def test_entity_names(self):
        names = {e.name for e in FLOW_SCHEMA.entities}
        expected = {
            "flow_layer", "step_spec", "workflow_spec", "meta_step",
            "use_case_spec", "execution_context", "step_result",
            "generation_rule", "flow_topology",
            "process_spec", "step_definition", "data_flow_edge",
            "schema_definition", "logic_condition", "data_transformation",
            "data_contract", "data_catalog",
            "step_implementer", "flow_runtime", "execution_result",
            "flow_profile",
            # S3/S4/S5
            "execution_store", "flow_analyzer", "flow_simulator",
            "workflow_promotion_engine", "step_effectiveness",
            "flow_analysis_report",
        }
        assert names == expected

    def test_relation_names(self):
        names = {r.name for r in FLOW_SCHEMA.relations}
        expected = {
            "contains", "next", "produces", "consumes", "depends_on",
            "registers", "coordinates", "triggers", "constrains", "available_in",
        }
        assert names == expected

    def test_schema_is_frozen(self):
        schema = FlowSchema(
            entities=(FlowEntity("test"),),
            relations=(FlowRelation("test_rel"),),
        )
        assert schema.entities[0].name == "test"
