from ea_flow.topology import FlowOntology, ProcessSpec, SchemaDefinition, StepDefinition
from ea_flow.types import FlowStepCategory


def test_flow_ontology_describe_exposes_core_types() -> None:
    description = FlowOntology.describe()
    assert "ProcessSpec" in description
    assert "DataFlowEdge" in description
    assert "StepSchemaUsage" in description


def test_process_spec_defaults() -> None:
    schema = SchemaDefinition(id="schema-1", name="Input")
    step = StepDefinition(
        id="step-1",
        name="Start",
        category=FlowStepCategory.EVENT,
        description="start",
    )
    process = ProcessSpec(id="proc-1", name="Process", version="1.0.0", steps=[step], defined_schemas=[schema])

    assert process.trigger_event == "manual"
    assert len(process.steps) == 1
    assert process.steps[0].next_step_ids == []
    assert process.defined_schemas[0].id == "schema-1"
