"""Tests for ScenarioStore — S3 Recording for Scenario Flows."""

from __future__ import annotations

import pytest

from ea_needs.scenario_store import (
    InMemoryScenarioStore,
    ScenarioQueryOptions,
    ScenarioStore,
    StoredScenarioSnapshot,
)


def _make_snapshot(
    scenario_id: str = "sc-001",
    use_case_id: str = "uc-001",
    scenario_type: str = "main",
    step_count: int = 3,
    kernel_ref_count: int = 1,
    version: int = 1,
) -> StoredScenarioSnapshot:
    return StoredScenarioSnapshot(
        storage_id="",
        scenario_id=scenario_id,
        use_case_id=use_case_id,
        scenario_type=scenario_type,
        step_count=step_count,
        kernel_ref_count=kernel_ref_count,
        version=version,
        stored_at="",
    )


class TestInMemoryScenarioStore:
    """Test InMemoryScenarioStore implementation."""

    def test_store_and_get_round_trip(self) -> None:
        """AC-23: Store/get round-trip preserves data."""
        store = InMemoryScenarioStore()
        snapshot = _make_snapshot()

        stored = store.store(snapshot)
        assert stored.storage_id != ""
        assert stored.stored_at != ""
        assert stored.scenario_id == "sc-001"
        assert stored.use_case_id == "uc-001"
        assert stored.scenario_type == "main"
        assert stored.step_count == 3
        assert stored.kernel_ref_count == 1
        assert stored.version == 1

        retrieved = store.get(stored.storage_id)
        assert retrieved is not None
        assert retrieved == stored

    def test_get_nonexistent_returns_none(self) -> None:
        store = InMemoryScenarioStore()
        assert store.get("nonexistent") is None

    def test_query_all(self) -> None:
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-001"))
        store.store(_make_snapshot(scenario_id="sc-002"))

        results = store.query()
        assert len(results) == 2

    def test_query_by_use_case_id(self) -> None:
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(use_case_id="uc-001"))
        store.store(_make_snapshot(use_case_id="uc-002"))
        store.store(_make_snapshot(use_case_id="uc-001", scenario_id="sc-003"))

        options = ScenarioQueryOptions(use_case_id="uc-001")
        results = store.query(options)
        assert len(results) == 2
        assert all(r.use_case_id == "uc-001" for r in results)

    def test_query_by_scenario_type(self) -> None:
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_type="main"))
        store.store(_make_snapshot(scenario_type="alternative", scenario_id="sc-002"))
        store.store(_make_snapshot(scenario_type="exception", scenario_id="sc-003"))

        options = ScenarioQueryOptions(scenario_type="main")
        results = store.query(options)
        assert len(results) == 1
        assert results[0].scenario_type == "main"

    def test_query_with_limit_and_offset(self) -> None:
        store = InMemoryScenarioStore()
        for i in range(5):
            store.store(_make_snapshot(scenario_id=f"sc-{i:03d}"))

        options = ScenarioQueryOptions(limit=2, offset=1)
        results = store.query(options)
        assert len(results) == 2

    def test_count(self) -> None:
        store = InMemoryScenarioStore()
        assert store.count() == 0

        store.store(_make_snapshot(scenario_id="sc-001"))
        assert store.count() == 1

        store.store(_make_snapshot(scenario_id="sc-002"))
        assert store.count() == 2

    def test_abc_contract(self) -> None:
        """AC-24: ScenarioStore is a proper ABC."""
        assert issubclass(InMemoryScenarioStore, ScenarioStore)

        # Cannot instantiate ABC directly
        with pytest.raises(TypeError):
            ScenarioStore()  # type: ignore[abstract]

    def test_store_auto_generates_storage_id(self) -> None:
        store = InMemoryScenarioStore()
        snapshot = _make_snapshot()
        stored = store.store(snapshot)
        assert stored.storage_id != ""
        assert len(stored.storage_id) > 0

    def test_store_preserves_explicit_storage_id(self) -> None:
        store = InMemoryScenarioStore()
        snapshot = StoredScenarioSnapshot(
            storage_id="explicit-id",
            scenario_id="sc-001",
            use_case_id="uc-001",
            scenario_type="main",
            step_count=3,
            kernel_ref_count=1,
            version=1,
            stored_at="",
        )
        stored = store.store(snapshot)
        assert stored.storage_id == "explicit-id"
