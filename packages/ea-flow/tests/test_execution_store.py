"""Tests for ExecutionStore — S3 Recording."""

from __future__ import annotations

import tempfile
from pathlib import Path

from ea_flow.execution_store import (
    ExecutionQueryOptions,
    ExecutionStore,
    InMemoryExecutionStore,
    SQLiteExecutionStore,
    StepResultSummary,
    StoredExecutionRecord,
    WorkflowStatistics,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_record(
    workflow_name: str = "validate-model",
    success: bool = True,
    total_steps: int = 3,
    completed_steps: int = 3,
    failed_step: str = "",
    rollback_occurred: bool = False,
    duration_ms: int = 150,
    executed_at: str = "2025-01-15T10:00:00Z",
    step_results: tuple[StepResultSummary, ...] = (),
    execution_id: str = "exec-001",
) -> StoredExecutionRecord:
    if not step_results:
        step_results = (
            StepResultSummary(step_name="step-a", accepted=True, kernel_anchor="element"),
            StepResultSummary(step_name="step-b", accepted=True, kernel_anchor="feature"),
            StepResultSummary(step_name="step-c", accepted=success, kernel_anchor="type"),
        )
    return StoredExecutionRecord(
        storage_id="",
        workflow_name=workflow_name,
        success=success,
        total_steps=total_steps,
        completed_steps=completed_steps,
        failed_step=failed_step,
        rollback_occurred=rollback_occurred,
        duration_ms=duration_ms,
        executed_at=executed_at,
        step_results=step_results,
        execution_id=execution_id,
    )


# ── Shared tests for both implementations ──────────────────────────────

class _ExecutionStoreTests:
    """Shared test suite for ExecutionStore implementations."""

    def _create_store(self) -> ExecutionStore:
        raise NotImplementedError

    def test_store_and_get(self):
        store = self._create_store()
        rec = _make_record()
        stored = store.store(rec)

        assert stored.storage_id != ""
        assert stored.stored_at != ""
        assert stored.workflow_name == "validate-model"

        got = store.get(stored.storage_id)
        assert got is not None
        assert got.workflow_name == "validate-model"
        assert got.success is True

    def test_get_nonexistent_returns_none(self):
        store = self._create_store()
        assert store.get("nonexistent") is None

    def test_query_all(self):
        store = self._create_store()
        store.store(_make_record(execution_id="e1"))
        store.store(_make_record(execution_id="e2"))

        results = store.query()
        assert len(results) == 2

    def test_query_by_workflow(self):
        store = self._create_store()
        store.store(_make_record(workflow_name="wf-a"))
        store.store(_make_record(workflow_name="wf-b"))
        store.store(_make_record(workflow_name="wf-a"))

        options = ExecutionQueryOptions(workflow_name="wf-a")
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_success(self):
        store = self._create_store()
        store.store(_make_record(success=True))
        store.store(_make_record(success=False))
        store.store(_make_record(success=True))

        options = ExecutionQueryOptions(success=True)
        results = store.query(options)
        assert len(results) == 2

    def test_query_by_rollback(self):
        store = self._create_store()
        store.store(_make_record(rollback_occurred=True))
        store.store(_make_record(rollback_occurred=False))

        options = ExecutionQueryOptions(rollback_occurred=True)
        results = store.query(options)
        assert len(results) == 1

    def test_query_by_time_range(self):
        store = self._create_store()
        store.store(_make_record(executed_at="2025-01-10T00:00:00Z"))
        store.store(_make_record(executed_at="2025-01-20T00:00:00Z"))
        store.store(_make_record(executed_at="2025-01-30T00:00:00Z"))

        options = ExecutionQueryOptions(
            start_time="2025-01-15T00:00:00Z",
            end_time="2025-01-25T00:00:00Z",
        )
        results = store.query(options)
        assert len(results) == 1

    def test_query_pagination(self):
        store = self._create_store()
        for i in range(5):
            store.store(_make_record(execution_id=f"e-{i}"))

        options = ExecutionQueryOptions(limit=2, offset=0)
        page1 = store.query(options)
        assert len(page1) == 2

    def test_count(self):
        store = self._create_store()
        store.store(_make_record(workflow_name="a"))
        store.store(_make_record(workflow_name="b"))
        store.store(_make_record(workflow_name="a"))

        assert store.count() == 3
        assert store.count(ExecutionQueryOptions(workflow_name="a")) == 2

    def test_statistics_by_workflow(self):
        store = self._create_store()
        store.store(_make_record(
            workflow_name="wf-a", success=True,
            rollback_occurred=False, duration_ms=100,
        ))
        store.store(_make_record(
            workflow_name="wf-a", success=False,
            rollback_occurred=True, duration_ms=200,
        ))
        store.store(_make_record(
            workflow_name="wf-b", success=True,
            rollback_occurred=False, duration_ms=50,
        ))

        stats = store.statistics_by_workflow()
        assert len(stats) == 2

        wf_a = next(s for s in stats if s.workflow_name == "wf-a")
        assert wf_a.total_executions == 2
        assert wf_a.success_count == 1
        assert wf_a.rollback_count == 1
        assert wf_a.avg_duration_ms == 150.0
        assert wf_a.success_rate == 0.5
        assert wf_a.rollback_rate == 0.5

    def test_step_results_preserved(self):
        store = self._create_store()
        steps = (
            StepResultSummary(step_name="s1", accepted=True, kernel_anchor="el"),
            StepResultSummary(step_name="s2", accepted=False, kernel_anchor="ft"),
        )
        rec = _make_record(step_results=steps, total_steps=2, completed_steps=1)
        stored = store.store(rec)
        got = store.get(stored.storage_id)
        assert got is not None
        assert len(got.step_results) == 2
        assert got.step_results[0].step_name == "s1"
        assert got.step_results[1].accepted is False

    def test_metadata_preserved(self):
        store = self._create_store()
        rec = StoredExecutionRecord(
            storage_id="",
            workflow_name="meta-wf",
            success=True,
            total_steps=1,
            completed_steps=1,
            failed_step="",
            rollback_occurred=False,
            duration_ms=10,
            executed_at="2025-01-01T00:00:00Z",
            metadata=(("env", "test"), ("version", "1.0")),
        )
        stored = store.store(rec)
        got = store.get(stored.storage_id)
        assert got is not None
        assert dict(got.metadata) == {"env": "test", "version": "1.0"}


# ── InMemory Tests ──────────────────────────────────────────────────────

class TestInMemoryExecutionStore(_ExecutionStoreTests):
    def _create_store(self) -> ExecutionStore:
        return InMemoryExecutionStore()


# ── SQLite Tests ────────────────────────────────────────────────────────

class TestSQLiteExecutionStore(_ExecutionStoreTests):
    def _create_store(self) -> ExecutionStore:
        self._tmpdir = tempfile.mkdtemp()
        return SQLiteExecutionStore(Path(self._tmpdir) / "exec.db")

    def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "persist.db"
            store1 = SQLiteExecutionStore(db_path)
            store1.store(_make_record(workflow_name="persist-wf"))

            store2 = SQLiteExecutionStore(db_path)
            assert store2.count() == 1
            results = store2.query()
            assert results[0].workflow_name == "persist-wf"
