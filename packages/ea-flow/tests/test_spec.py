"""Tests for ea_flow.spec module."""

import pytest
from dataclasses import FrozenInstanceError

from ea_flow.spec import (
    ExecutionContext,
    FlowGenerationRule,
    FlowMetaStep,
    FlowTopology,
    KernelGroundedStepSpec,
    StepResultSpec,
    StepSpec,
    UseCaseSpec,
    _as_text,
)
from ea_flow.schema import DbSchemaSpec


class TestAsText:
    """Test _as_text helper."""

    def test_str_passthrough(self):
        assert _as_text("hello") == "hello"

    def test_dict_with_en(self):
        assert _as_text({"en": "English", "ko": "한국어"}) == "English"

    def test_dict_without_en(self):
        result = _as_text({"ko": "한국어", "ja": "日本語"})
        assert result in ("한국어", "日本語")

    def test_empty_dict(self):
        assert _as_text({}) == ""


class TestExecutionContext:
    """Test ExecutionContext frozen dataclass."""

    def test_creation(self):
        ctx = ExecutionContext(execution_id="exec-1", variables={"key": "val"})
        assert ctx.execution_id == "exec-1"
        assert ctx.variables == {"key": "val"}

    def test_frozen(self):
        ctx = ExecutionContext(execution_id="exec-1", variables={})
        with pytest.raises(FrozenInstanceError):
            ctx.execution_id = "changed"


class TestStepResultSpec:
    """Test StepResultSpec frozen dataclass."""

    def test_creation_defaults(self):
        s = StepResultSpec()
        assert s.output_schema is None
        assert s.expected_log_patterns == []

    def test_creation_with_patterns(self):
        s = StepResultSpec(expected_log_patterns=["SUCCESS", "DONE"])
        assert len(s.expected_log_patterns) == 2


class TestFlowMetaStep:
    """Test FlowMetaStep frozen dataclass."""

    def test_creation_minimal(self):
        m = FlowMetaStep(name="validate", description="Validate input")
        assert m.name == "validate"
        assert m.description == "Validate input"
        assert m.input_schema is None
        assert m.output_schema is None
        assert m.kernel_type_requirement is None

    def test_creation_full(self):
        m = FlowMetaStep(
            name={"en": "Validate", "ko": "검증"},
            description="Validate input",
            kernel_type_requirement="action",
        )
        assert m.kernel_type_requirement == "action"

    def test_frozen(self):
        m = FlowMetaStep(name="step", description="desc")
        with pytest.raises(FrozenInstanceError):
            m.name = "changed"


class TestKernelGroundedStepSpec:
    """Test KernelGroundedStepSpec concrete StepSpec."""

    def test_name_composition(self):
        meta = FlowMetaStep(name="validate", description="Validate")
        step = KernelGroundedStepSpec(anchor="BusinessProcess", meta_type=meta)
        assert step.name == "validate on BusinessProcess"

    def test_kernel_anchor(self):
        meta = FlowMetaStep(name="execute", description="Execute")
        step = KernelGroundedStepSpec(anchor="MyEntity", meta_type=meta)
        assert step.kernel_anchor == "MyEntity"

    def test_meta_type(self):
        meta = FlowMetaStep(name="step", description="desc")
        step = KernelGroundedStepSpec(anchor="anchor", meta_type=meta)
        assert step.meta_type is meta

    def test_input_schema_from_meta(self):
        schema = DbSchemaSpec(table_name="test", columns={"id": "int"})
        meta = FlowMetaStep(name="step", description="desc", input_schema=schema)
        step = KernelGroundedStepSpec(anchor="anchor", meta_type=meta)
        assert step.input_schema is schema

    def test_output_schema_from_meta(self):
        schema = DbSchemaSpec(table_name="test", columns={"id": "int"})
        meta = FlowMetaStep(name="step", description="desc", output_schema=schema)
        step = KernelGroundedStepSpec(anchor="anchor", meta_type=meta)
        assert step.output_schema is schema

    def test_is_step_spec(self):
        meta = FlowMetaStep(name="step", description="desc")
        step = KernelGroundedStepSpec(anchor="anchor", meta_type=meta)
        assert isinstance(step, StepSpec)


class TestUseCaseSpec:
    """Test UseCaseSpec concrete WorkflowSpec."""

    def _make_step(self):
        meta = FlowMetaStep(name="step", description="desc")
        return KernelGroundedStepSpec(anchor="Entity", meta_type=meta)

    def test_creation_minimal(self):
        step = self._make_step()
        uc = UseCaseSpec(
            name="Register User",
            description="User registration flow",
            primary_actor="Admin",
            success_criteria=["User created"],
            steps=[step],
        )
        assert uc.name == "Register User"
        assert uc.description == "User registration flow"
        assert uc.primary_actor == "Admin"
        assert uc.kernel_anchor is None
        assert uc.input_schema is None
        assert uc.output_schema is None

    def test_get_steps(self):
        step = self._make_step()
        uc = UseCaseSpec(
            name="Test",
            description="desc",
            primary_actor="Actor",
            success_criteria=[],
            steps=[step],
        )
        assert uc.get_steps() == [step]

    def test_i18n_name(self):
        uc = UseCaseSpec(
            name={"en": "English", "ko": "한국어"},
            description="desc",
            primary_actor="Actor",
            success_criteria=[],
            steps=[],
        )
        assert uc.name == "English"

    def test_success_criteria(self):
        uc = UseCaseSpec(
            name="Test",
            description="desc",
            primary_actor="Actor",
            success_criteria=["Criterion 1", "Criterion 2"],
            steps=[],
        )
        assert len(uc.success_criteria) == 2

    def test_with_kernel_anchor(self):
        uc = UseCaseSpec(
            name="Test",
            description="desc",
            primary_actor="Actor",
            success_criteria=[],
            steps=[],
            kernel_anchor="BusinessProcess",
        )
        assert uc.kernel_anchor == "BusinessProcess"


class TestFlowGenerationRule:
    """Test FlowGenerationRule frozen dataclass."""

    def test_creation_minimal(self):
        r = FlowGenerationRule(
            source_kernel_type="Entity",
            target_flow_type="ReviewFlow",
            naming_pattern="{target_flow_type} for {source_name}",
        )
        assert r.source_kernel_type == "Entity"
        assert r.required_steps == []
        assert r.logic_conditions == {}

    def test_creation_full(self):
        r = FlowGenerationRule(
            source_kernel_type="Entity",
            target_flow_type="ApprovalFlow",
            naming_pattern="{target_flow_type} for {source_name}",
            required_steps=["validate", "approve"],
            logic_conditions={"amount": {">=": 100000}},
        )
        assert len(r.required_steps) == 2
        assert r.logic_conditions["amount"][">="] == 100000

    def test_frozen(self):
        r = FlowGenerationRule(
            source_kernel_type="Entity",
            target_flow_type="Flow",
            naming_pattern="pattern",
        )
        with pytest.raises(FrozenInstanceError):
            r.source_kernel_type = "changed"


class TestFlowTopology:
    """Test FlowTopology frozen dataclass."""

    def test_creation_minimal(self):
        t = FlowTopology(name="simple")
        assert t.name == "simple"
        assert t.steps == []
        assert t.entry_point is None
        assert t.exit_points == []
        assert t.transition_rules == {}
        assert t.generation_rules == []

    def test_creation_with_transitions(self):
        t = FlowTopology(
            name="linear",
            entry_point="start",
            exit_points=["end"],
            transition_rules={"start": "process", "process": "end"},
        )
        assert t.entry_point == "start"
        assert t.exit_points == ["end"]
        assert t.transition_rules["start"] == "process"

    def test_frozen(self):
        t = FlowTopology(name="frozen")
        with pytest.raises(FrozenInstanceError):
            t.name = "changed"


class TestDbSchemaSpec:
    """Test DbSchemaSpec (schema.py) concrete SchemaSpec."""

    def test_creation(self):
        s = DbSchemaSpec(table_name="users", columns={"id": "int", "name": "varchar"})
        assert s.table_name == "users"
        assert s.format == "db-schema"
        assert s.ddl is None

    def test_validate_valid_data(self):
        s = DbSchemaSpec(table_name="users", columns={"id": "int", "name": "varchar"})
        assert s.validate({"id": 1, "name": "Alice"}) is True

    def test_validate_missing_column(self):
        s = DbSchemaSpec(table_name="users", columns={"id": "int", "name": "varchar"})
        assert s.validate({"id": 1}) is False

    def test_validate_non_dict(self):
        s = DbSchemaSpec(table_name="users", columns={"id": "int"})
        assert s.validate("not a dict") is False

    def test_to_dict(self):
        s = DbSchemaSpec(
            table_name="users",
            columns={"id": "int"},
            ddl="CREATE TABLE users (id INT)",
        )
        d = s.to_dict()
        assert d["format"] == "db-schema"
        assert d["table_name"] == "users"
        assert d["columns"] == {"id": "int"}
        assert d["ddl"] == "CREATE TABLE users (id INT)"

    def test_validate_extra_columns_ok(self):
        s = DbSchemaSpec(table_name="t", columns={"id": "int"})
        assert s.validate({"id": 1, "extra": "ok"}) is True
