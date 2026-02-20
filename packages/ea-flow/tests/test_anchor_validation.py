"""Tests for anchor_validation — Kernel↔Flow bidirectional awareness."""

from __future__ import annotations

from ea_flow.anchor_validation import (
    AnchorUsage,
    AnchorValidationResult,
    WorkflowAnchorReport,
    collect_anchors,
    find_anchor_usages,
    validate_kernel_anchor,
    validate_workflow_anchors,
)
from ea_flow.execution_store import (
    InMemoryExecutionStore,
    StepResultSummary,
    StoredExecutionRecord,
)
from ea_flow.spec import KernelGroundedStepSpec, FlowMetaStep, StepSpec, WorkflowSpec
from ea_flow.schema import SchemaSpec


# ── Test fixtures ─────────────────────────────────────────────────────

_ENTITY_NAMES = frozenset({
    "element", "namespace", "metatype", "feature", "port",
    "step", "action", "event", "expression",
    "classifier", "structure", "item", "datatype", "state", "package",
})

_RELATION_NAMES = frozenset({
    "membership", "ownership", "specialization", "feature_typing",
    "association", "connector", "redefinition", "subsetting",
    "flow", "succession", "interaction", "triggering", "guarding", "transition",
})


class _DummyStep(StepSpec):
    def __init__(self, name: str, anchor: str | None = None):
        self._name = name
        self._anchor = anchor

    @property
    def name(self) -> str:
        return self._name

    @property
    def kernel_anchor(self) -> str | None:
        return self._anchor


class _DummyWorkflow(WorkflowSpec):
    def __init__(self, name: str, steps: list[StepSpec]):
        self._name = name
        self._steps = steps

    @property
    def name(self) -> str:
        return self._name

    @property
    def kernel_anchor(self) -> str | None:
        return None

    @property
    def input_schema(self) -> SchemaSpec | None:
        return None

    @property
    def output_schema(self) -> SchemaSpec | None:
        return None

    def get_steps(self) -> list[StepSpec]:
        return self._steps


# ── validate_kernel_anchor ────────────────────────────────────────────

class TestValidateKernelAnchor:

    def test_empty_anchor_invalid(self):
        result = validate_kernel_anchor(
            "", entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is False
        assert "Empty" in result.message

    def test_direct_entity_match(self):
        result = validate_kernel_anchor(
            "element", entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is True
        assert result.match_type == "entity"
        assert result.resolved_name == "element"

    def test_direct_relation_match(self):
        result = validate_kernel_anchor(
            "connector", entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is True
        assert result.match_type == "relation"
        assert result.resolved_name == "connector"

    def test_uri_entity_match(self):
        result = validate_kernel_anchor(
            "ea:kernel:entity:feature",
            entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is True
        assert result.match_type == "uri_entity"
        assert result.resolved_name == "feature"

    def test_uri_relation_match(self):
        result = validate_kernel_anchor(
            "ea:kernel:relation:flow",
            entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is True
        assert result.match_type == "uri_relation"
        assert result.resolved_name == "flow"

    def test_uri_operation_match(self):
        result = validate_kernel_anchor(
            "ea:kernel:rule_creation",
            entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is True
        assert result.match_type == "uri_operation"

    def test_uri_rule_match(self):
        result = validate_kernel_anchor(
            "ea:kernel:rule:R1",
            entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is True
        assert result.match_type == "uri_rule"
        assert result.resolved_name == "R1"

    def test_unknown_anchor_invalid(self):
        result = validate_kernel_anchor(
            "nonexistent_thing",
            entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is False
        assert "not a known" in result.message

    def test_uri_unknown_entity_invalid(self):
        result = validate_kernel_anchor(
            "ea:kernel:entity:nonexistent",
            entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert result.valid is False
        assert "does not match" in result.message


# ── collect_anchors ───────────────────────────────────────────────────

class TestCollectAnchors:

    def test_collect_from_workflow(self):
        wf = _DummyWorkflow("test-wf", [
            _DummyStep("s1", "element"),
            _DummyStep("s2", None),
            _DummyStep("s3", "connector"),
        ])

        anchors = collect_anchors(wf)
        assert anchors == ["element", "connector"]

    def test_empty_workflow(self):
        wf = _DummyWorkflow("empty", [])
        assert collect_anchors(wf) == []


# ── validate_workflow_anchors ─────────────────────────────────────────

class TestValidateWorkflowAnchors:

    def test_all_valid(self):
        wf = _DummyWorkflow("test-wf", [
            _DummyStep("s1", "element"),
            _DummyStep("s2", "connector"),
        ])

        report = validate_workflow_anchors(
            wf, entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )

        assert report.workflow_name == "test-wf"
        assert report.total_steps == 2
        assert report.anchored_steps == 2
        assert report.unanchored_steps == 0
        assert report.valid_anchors == 2
        assert report.invalid_anchors == 0
        assert report.all_valid is True

    def test_mixed_valid_invalid(self):
        wf = _DummyWorkflow("mixed", [
            _DummyStep("s1", "element"),
            _DummyStep("s2", "nonexistent"),
            _DummyStep("s3", None),
        ])

        report = validate_workflow_anchors(
            wf, entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )

        assert report.total_steps == 3
        assert report.anchored_steps == 2
        assert report.unanchored_steps == 1
        assert report.valid_anchors == 1
        assert report.invalid_anchors == 1
        assert report.all_valid is False

    def test_empty_workflow(self):
        wf = _DummyWorkflow("empty", [])
        report = validate_workflow_anchors(
            wf, entity_names=_ENTITY_NAMES, relation_names=_RELATION_NAMES,
        )
        assert report.total_steps == 0
        assert report.all_valid is True


# ── find_anchor_usages (reverse lookup) ───────────────────────────────

def _exec_record(
    workflow_name: str = "wf-1",
    steps: tuple[StepResultSummary, ...] = (),
    execution_id: str = "exec-1",
) -> StoredExecutionRecord:
    return StoredExecutionRecord(
        storage_id="",
        workflow_name=workflow_name,
        success=True,
        total_steps=len(steps),
        completed_steps=len(steps),
        failed_step="",
        rollback_occurred=False,
        duration_ms=100,
        executed_at="2025-01-15T10:00:00Z",
        step_results=steps,
        execution_id=execution_id,
    )


class TestFindAnchorUsages:

    def test_direct_match(self):
        records = (
            _exec_record("wf-a", (
                StepResultSummary("s1", True, kernel_anchor="element"),
                StepResultSummary("s2", True, kernel_anchor="feature"),
            ), "exec-a"),
            _exec_record("wf-b", (
                StepResultSummary("s3", True, kernel_anchor="element"),
            ), "exec-b"),
        )

        usages = find_anchor_usages(records, "element")

        assert len(usages) == 2
        assert usages[0].workflow_name == "wf-a"
        assert usages[0].step_name == "s1"
        assert usages[1].workflow_name == "wf-b"

    def test_uri_match(self):
        records = (
            _exec_record("wf-a", (
                StepResultSummary("s1", True, kernel_anchor="ea:kernel:entity:feature"),
            ), "exec-a"),
        )

        usages = find_anchor_usages(records, "feature")

        assert len(usages) == 1
        assert usages[0].kernel_anchor == "ea:kernel:entity:feature"

    def test_no_match(self):
        records = (
            _exec_record("wf-a", (
                StepResultSummary("s1", True, kernel_anchor="element"),
            )),
        )

        usages = find_anchor_usages(records, "nonexistent")
        assert len(usages) == 0

    def test_empty_records(self):
        usages = find_anchor_usages((), "element")
        assert len(usages) == 0

    def test_empty_anchor(self):
        records = (
            _exec_record("wf-a", (
                StepResultSummary("s1", True, kernel_anchor=""),
            )),
        )

        usages = find_anchor_usages(records, "element")
        assert len(usages) == 0

    def test_rule_uri_match(self):
        records = (
            _exec_record("wf-a", (
                StepResultSummary("s1", True, kernel_anchor="ea:kernel:rule:R1"),
            )),
        )

        usages = find_anchor_usages(records, "R1")
        assert len(usages) == 1
