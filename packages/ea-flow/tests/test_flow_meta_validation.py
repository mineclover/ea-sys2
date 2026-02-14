import pytest
from ea_flow.spec import FlowMetaStep, KernelGroundedStepSpec
from ea_flow.schema import JsonSchema2020Spec

def test_step_meta_conformance():
    # 1. Define a MetaStep (The Model)
    meta = FlowMetaStep(
        name="DataMappingStep",
        description="Maps raw input to structured output",
        input_schema=JsonSchema2020Spec({"type": "object", "properties": {"raw": {"type": "string"}}}),
        output_schema=JsonSchema2020Spec({"type": "object", "properties": {"mapped": {"type": "string"}}})
    )

    # 2. Create a Spec Instance (The Declarative Fact)
    step = KernelGroundedStepSpec(anchor="ea:kernel:schema", meta_type=meta)

    # 3. Verify Conformance
    assert step.meta_type == meta
    assert step.name == "DataMappingStep on ea:kernel:schema"
    assert step.input_schema == meta.input_schema
    assert step.output_schema == meta.output_schema

    # 4. Input validation (Simple test)
    valid_data = {"raw": "test"}
    assert step.input_schema.validate(valid_data) == True
