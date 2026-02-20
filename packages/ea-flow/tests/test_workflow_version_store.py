"""Tests for WorkflowVersionStore — Version Management."""

from __future__ import annotations

import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from ea_flow.workflow_version_store import (
    InMemoryWorkflowVersionStore,
    SQLiteWorkflowVersionStore,
    StoredStepEntry,
    WorkflowVersionQueryOptions,
    WorkflowVersionStore,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_entries(
    names: tuple[str, ...] = ("step-a", "step-b", "step-c"),
) -> tuple[StoredStepEntry, ...]:
    return tuple(
        StoredStepEntry(
            step_name=name,
            kernel_anchor=f"anchor-{name}",
            input_schema_hash=f"in-{name}",
            output_schema_hash=f"out-{name}",
            description=f"Step {name}",
        )
        for name in names
    )


# ── Shared Test Contract ────────────────────────────────────────────────

class _WorkflowVersionStoreTests(ABC):
    """Shared tests for WorkflowVersionStore implementations."""

    @abstractmethod
    def create_store(self) -> WorkflowVersionStore:
        ...

    def test_create_and_get(self):
        store = self.create_store()
        entries = _make_entries()
        info = store.create_version(
            workflow_name="validate-model",
            step_entries=entries,
            description="Initial version",
        )

        assert info.version_id != ""
        assert info.workflow_name == "validate-model"
        assert info.step_count == 3
        assert info.created_at != ""
        assert info.description == "Initial version"
        assert info.step_names == ("step-a", "step-b", "step-c")

        got = store.get(info.version_id)
        assert got is not None
        assert got.workflow_name == "validate-model"
        assert got.step_count == 3

    def test_get_nonexistent(self):
        store = self.create_store()
        assert store.get("nonexistent") is None

    def test_get_latest(self):
        store = self.create_store()
        v1 = store.create_version(
            workflow_name="wf-a",
            step_entries=_make_entries(("s1",)),
            description="v1",
        )
        v2 = store.create_version(
            workflow_name="wf-a",
            step_entries=_make_entries(("s1", "s2")),
            description="v2",
            parent_version_id=v1.version_id,
        )

        latest = store.get_latest("wf-a")
        assert latest is not None
        assert latest.version_id == v2.version_id
        assert latest.step_count == 2

    def test_get_latest_nonexistent(self):
        store = self.create_store()
        assert store.get_latest("no-such-wf") is None

    def test_history(self):
        store = self.create_store()
        v1 = store.create_version("wf-a", _make_entries(("s1",)), "v1")
        v2 = store.create_version(
            "wf-a", _make_entries(("s1", "s2")), "v2",
            parent_version_id=v1.version_id,
        )

        hist = store.history("wf-a")
        assert len(hist) == 2
        # Most recent first
        assert hist[0].version_id == v2.version_id
        assert hist[1].version_id == v1.version_id

    def test_diff_added_removed(self):
        store = self.create_store()
        v1 = store.create_version(
            "wf-a", _make_entries(("step-a", "step-b")),
        )
        v2 = store.create_version(
            "wf-a", _make_entries(("step-b", "step-c")),
            parent_version_id=v1.version_id,
        )

        diff = store.diff(v1.version_id, v2.version_id)
        assert diff.added == ("step-c",)
        assert diff.removed == ("step-a",)
        assert diff.modified == ()

    def test_diff_modified(self):
        store = self.create_store()
        entries_v1 = (
            StoredStepEntry(step_name="s1", kernel_anchor="a1"),
            StoredStepEntry(step_name="s2", kernel_anchor="a2"),
        )
        entries_v2 = (
            StoredStepEntry(step_name="s1", kernel_anchor="a1-changed"),
            StoredStepEntry(step_name="s2", kernel_anchor="a2"),
        )
        v1 = store.create_version("wf-a", entries_v1)
        v2 = store.create_version(
            "wf-a", entries_v2,
            parent_version_id=v1.version_id,
        )

        diff = store.diff(v1.version_id, v2.version_id)
        assert diff.added == ()
        assert diff.removed == ()
        assert diff.modified == ("s1",)

    def test_query_by_workflow_name(self):
        store = self.create_store()
        store.create_version("wf-a", _make_entries(("s1",)))
        store.create_version("wf-b", _make_entries(("s2",)))
        store.create_version("wf-a", _make_entries(("s1", "s2")))

        options = WorkflowVersionQueryOptions(workflow_name="wf-a")
        results = store.query(options)
        assert len(results) == 2
        assert all(v.workflow_name == "wf-a" for v in results)

    def test_query_all(self):
        store = self.create_store()
        store.create_version("wf-a", _make_entries(("s1",)))
        store.create_version("wf-b", _make_entries(("s2",)))

        results = store.query()
        assert len(results) == 2

    def test_entries_preserved(self):
        store = self.create_store()
        entries = _make_entries(("step-x", "step-y"))
        info = store.create_version("wf-a", entries)

        got_entries = store.get_entries(info.version_id)
        assert len(got_entries) == 2

        names = {e.step_name for e in got_entries}
        assert names == {"step-x", "step-y"}

        step_x = next(e for e in got_entries if e.step_name == "step-x")
        assert step_x.kernel_anchor == "anchor-step-x"
        assert step_x.input_schema_hash == "in-step-x"
        assert step_x.output_schema_hash == "out-step-x"
        assert step_x.description == "Step step-x"

    def test_parent_version_id(self):
        store = self.create_store()
        v1 = store.create_version("wf-a", _make_entries(("s1",)))
        v2 = store.create_version(
            "wf-a", _make_entries(("s1", "s2")),
            parent_version_id=v1.version_id,
        )

        got = store.get(v2.version_id)
        assert got is not None
        assert got.parent_version_id == v1.version_id


# ── InMemory Tests ──────────────────────────────────────────────────────

class TestInMemoryWorkflowVersionStore(_WorkflowVersionStoreTests):
    def create_store(self) -> WorkflowVersionStore:
        return InMemoryWorkflowVersionStore()


# ── SQLite Tests ────────────────────────────────────────────────────────

class TestSQLiteWorkflowVersionStore(_WorkflowVersionStoreTests):
    def create_store(self) -> WorkflowVersionStore:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        return SQLiteWorkflowVersionStore(tmp.name)

    def test_persistence_across_instances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "wfv.db"
            store1 = SQLiteWorkflowVersionStore(db_path)
            store1.create_version("wf-a", _make_entries(("s1",)), "v1")

            store2 = SQLiteWorkflowVersionStore(db_path)
            results = store2.query()
            assert len(results) == 1
            assert results[0].workflow_name == "wf-a"
