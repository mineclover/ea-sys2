"""Scenario Simulator — S5 Evolution What-If for Scenario Flows.

Simulates the impact of scenario/use-case changes on existing scenarios.

Provides:
- ScenarioChangeType: Change type enum
- ScenarioChange: Change description
- ScenarioSimulationResult: Simulation result
- ScenarioSimulator: Simulation engine

References:
- ea_needs/needs_simulator.py: S5 simulation pattern
- ea_needs/scenario_store.py: S3 storage pattern
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_needs.scenario_store import ScenarioStore


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Change Types
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioChangeType(StrEnum):
    """Types of scenario changes to simulate."""
    REMOVE_USE_CASE = "remove_use_case"
    REMOVE_SCENARIO = "remove_scenario"
    CHANGE_STEP_ORDER = "change_step_order"


@dataclass(frozen=True)
class ScenarioChange:
    """A change to simulate on the scenario store."""
    change_type: ScenarioChangeType
    target_id: str
    parameters: dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Simulation Results
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ScenarioSimulationResult:
    """Result of simulating a scenario change."""
    change: ScenarioChange
    orphaned_scenarios: tuple[str, ...]
    affected_branches: tuple[str, ...]
    invalid_branch_refs: tuple[str, ...]
    risk_level: str


# ═══════════════════════════════════════════════════════════════════════════════
# ScenarioSimulator
# ═══════════════════════════════════════════════════════════════════════════════

class ScenarioSimulator:
    """Scenario change impact simulator.

    Simulates the effect of removing use cases, removing scenarios,
    or changing step orders on the existing scenario store.
    """

    __slots__ = ("_scenario_store",)

    def __init__(self, scenario_store: ScenarioStore) -> None:
        self._scenario_store = scenario_store

    def simulate(
        self,
        changes: list[ScenarioChange],
    ) -> tuple[ScenarioSimulationResult, ...]:
        """Simulate the impact of scenario changes.

        Args:
            changes: List of changes to simulate.

        Returns:
            Tuple of simulation results, one per change.
        """
        results: list[ScenarioSimulationResult] = []

        for change in changes:
            if change.change_type == ScenarioChangeType.REMOVE_USE_CASE:
                results.append(self._simulate_remove_use_case(change))
            elif change.change_type == ScenarioChangeType.REMOVE_SCENARIO:
                results.append(self._simulate_remove_scenario(change))
            elif change.change_type == ScenarioChangeType.CHANGE_STEP_ORDER:
                results.append(self._simulate_change_step_order(change))

        return tuple(results)

    def _simulate_remove_use_case(
        self,
        change: ScenarioChange,
    ) -> ScenarioSimulationResult:
        """Simulate removing a use case — all its scenarios become orphaned."""
        from ea_needs.scenario_store import ScenarioQueryOptions

        use_case_id = change.target_id
        options = ScenarioQueryOptions(use_case_id=use_case_id)
        records = self._scenario_store.query(options)

        orphaned = tuple(r.scenario_id for r in records)

        risk_level = "LOW"
        if len(orphaned) > 5:
            risk_level = "HIGH"
        elif len(orphaned) > 2:
            risk_level = "MEDIUM"

        return ScenarioSimulationResult(
            change=change,
            orphaned_scenarios=orphaned,
            affected_branches=(),
            invalid_branch_refs=(),
            risk_level=risk_level,
        )

    def _simulate_remove_scenario(
        self,
        change: ScenarioChange,
    ) -> ScenarioSimulationResult:
        """Simulate removing a scenario — detect affected branches."""
        scenario_id = change.target_id

        # Find the scenario to remove
        all_records = self._scenario_store.query()
        target = None
        for r in all_records:
            if r.scenario_id == scenario_id:
                target = r
                break

        if target is None:
            return ScenarioSimulationResult(
                change=change,
                orphaned_scenarios=(),
                affected_branches=(),
                invalid_branch_refs=(),
                risk_level="LOW",
            )

        # If the removed scenario is MAIN, all other scenarios in the
        # same use case that depend on it are affected
        affected: list[str] = []
        if target.scenario_type == "main":
            for r in all_records:
                if (
                    r.use_case_id == target.use_case_id
                    and r.scenario_id != scenario_id
                ):
                    affected.append(r.scenario_id)

        risk_level = "LOW"
        if target.scenario_type == "main":
            risk_level = "HIGH"
        elif len(affected) > 0:
            risk_level = "MEDIUM"

        return ScenarioSimulationResult(
            change=change,
            orphaned_scenarios=(),
            affected_branches=tuple(affected),
            invalid_branch_refs=(),
            risk_level=risk_level,
        )

    def _simulate_change_step_order(
        self,
        change: ScenarioChange,
    ) -> ScenarioSimulationResult:
        """Simulate changing step order — detect invalid branch refs."""
        from ea_needs.scenario_store import ScenarioQueryOptions

        # The target_id is the use_case_id whose steps are being reordered
        use_case_id = change.target_id
        new_max_order_str = change.parameters.get("new_max_order", "")

        options = ScenarioQueryOptions(use_case_id=use_case_id)
        records = self._scenario_store.query(options)

        # If new_max_order is provided, any branch scenarios that reference
        # steps beyond that order become invalid
        invalid_refs: list[str] = []
        if new_max_order_str:
            new_max_order = int(new_max_order_str)
            # In the store we don't have branch_from_step directly,
            # but we can detect scenarios that might be affected:
            # any non-main scenario in this use case is potentially affected
            for r in records:
                if r.scenario_type != "main":
                    # If the scenario has steps that could reference
                    # orders beyond new_max_order, it's invalid
                    if r.step_count > new_max_order:
                        invalid_refs.append(r.scenario_id)

        risk_level = "LOW"
        if len(invalid_refs) > 2:
            risk_level = "HIGH"
        elif len(invalid_refs) > 0:
            risk_level = "MEDIUM"

        return ScenarioSimulationResult(
            change=change,
            orphaned_scenarios=(),
            affected_branches=(),
            invalid_branch_refs=tuple(invalid_refs),
            risk_level=risk_level,
        )
