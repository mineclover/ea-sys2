"""Tests for ScenarioSimulator — S5 Evolution What-If for Scenario Flows."""

from __future__ import annotations

from ea_needs.scenario_simulator import (
    ScenarioChange,
    ScenarioChangeType,
    ScenarioSimulator,
)
from ea_needs.scenario_store import (
    InMemoryScenarioStore,
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


class TestScenarioSimulator:
    """Tests for ScenarioSimulator."""

    def test_remove_use_case_detects_orphaned_scenarios(self) -> None:
        """AC-26: REMOVE_USE_CASE detects orphaned scenarios."""
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-main", use_case_id="uc-001", scenario_type="main"))
        store.store(_make_snapshot(scenario_id="sc-alt", use_case_id="uc-001", scenario_type="alternative"))
        store.store(_make_snapshot(scenario_id="sc-exc", use_case_id="uc-001", scenario_type="exception"))
        store.store(_make_snapshot(scenario_id="sc-other", use_case_id="uc-002", scenario_type="main"))

        simulator = ScenarioSimulator(store)
        results = simulator.simulate([
            ScenarioChange(
                change_type=ScenarioChangeType.REMOVE_USE_CASE,
                target_id="uc-001",
            ),
        ])

        assert len(results) == 1
        result = results[0]
        assert len(result.orphaned_scenarios) == 3
        assert "sc-main" in result.orphaned_scenarios
        assert "sc-alt" in result.orphaned_scenarios
        assert "sc-exc" in result.orphaned_scenarios
        assert result.risk_level == "MEDIUM"

    def test_remove_use_case_high_risk(self) -> None:
        store = InMemoryScenarioStore()
        for i in range(6):
            store.store(_make_snapshot(scenario_id=f"sc-{i:03d}", use_case_id="uc-001"))

        simulator = ScenarioSimulator(store)
        results = simulator.simulate([
            ScenarioChange(
                change_type=ScenarioChangeType.REMOVE_USE_CASE,
                target_id="uc-001",
            ),
        ])

        assert results[0].risk_level == "HIGH"

    def test_remove_scenario_detects_affected_branches(self) -> None:
        """REMOVE_SCENARIO: removing MAIN detects affected branches."""
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-main", use_case_id="uc-001", scenario_type="main"))
        store.store(_make_snapshot(scenario_id="sc-alt", use_case_id="uc-001", scenario_type="alternative"))
        store.store(_make_snapshot(scenario_id="sc-exc", use_case_id="uc-001", scenario_type="exception"))

        simulator = ScenarioSimulator(store)
        results = simulator.simulate([
            ScenarioChange(
                change_type=ScenarioChangeType.REMOVE_SCENARIO,
                target_id="sc-main",
            ),
        ])

        assert len(results) == 1
        result = results[0]
        assert "sc-alt" in result.affected_branches
        assert "sc-exc" in result.affected_branches
        assert result.risk_level == "HIGH"

    def test_remove_scenario_nonexistent(self) -> None:
        store = InMemoryScenarioStore()
        simulator = ScenarioSimulator(store)
        results = simulator.simulate([
            ScenarioChange(
                change_type=ScenarioChangeType.REMOVE_SCENARIO,
                target_id="nonexistent",
            ),
        ])

        assert len(results) == 1
        assert results[0].risk_level == "LOW"

    def test_change_step_order_detects_invalid_branch_refs(self) -> None:
        """CHANGE_STEP_ORDER: detects invalid branch refs."""
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-main", use_case_id="uc-001", scenario_type="main", step_count=5))
        store.store(_make_snapshot(scenario_id="sc-alt", use_case_id="uc-001", scenario_type="alternative", step_count=4))
        store.store(_make_snapshot(scenario_id="sc-exc", use_case_id="uc-001", scenario_type="exception", step_count=2))

        simulator = ScenarioSimulator(store)
        results = simulator.simulate([
            ScenarioChange(
                change_type=ScenarioChangeType.CHANGE_STEP_ORDER,
                target_id="uc-001",
                parameters={"new_max_order": "3"},
            ),
        ])

        assert len(results) == 1
        result = results[0]
        # sc-alt has step_count=4 > new_max_order=3, so it's invalid
        assert "sc-alt" in result.invalid_branch_refs
        # sc-exc has step_count=2 <= 3, so it's fine
        assert "sc-exc" not in result.invalid_branch_refs
        assert result.risk_level == "MEDIUM"

    def test_multiple_changes(self) -> None:
        store = InMemoryScenarioStore()
        store.store(_make_snapshot(scenario_id="sc-001", use_case_id="uc-001"))
        store.store(_make_snapshot(scenario_id="sc-002", use_case_id="uc-002"))

        simulator = ScenarioSimulator(store)
        results = simulator.simulate([
            ScenarioChange(
                change_type=ScenarioChangeType.REMOVE_USE_CASE,
                target_id="uc-001",
            ),
            ScenarioChange(
                change_type=ScenarioChangeType.REMOVE_SCENARIO,
                target_id="sc-002",
            ),
        ])

        assert len(results) == 2
