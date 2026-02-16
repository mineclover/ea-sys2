"""Tests for NeedsSimulator — S5 Evolution What-If."""

from __future__ import annotations

import pytest

from ea_needs.needs_simulator import (
    AffectedNeed,
    ImpactLevel,
    NeedChange,
    NeedChangeType,
    NeedSimulationResult,
    NeedsSimulator,
)
from ea_needs.needs_store import (
    InMemoryNeedStore,
    NeedSnapshotStatus,
    StoredNeedSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    need_id: str = "need-1",
    stakeholder_id: str = "sh-cto",
    status: NeedSnapshotStatus = NeedSnapshotStatus.ADDRESSED,
    priority: str = "high",
    complexity: str = "procedural",
    use_case_id: str = "",
) -> StoredNeedSnapshot:
    return StoredNeedSnapshot(
        storage_id="",
        need_id=need_id,
        lineage_id=need_id,
        stakeholder_id=stakeholder_id,
        status=status,
        priority=priority,
        complexity=complexity,
        use_case_id=use_case_id,
        expressed_at="2025-01-15T10:00:00Z",
    )


def _populated_store() -> InMemoryNeedStore:
    store = InMemoryNeedStore()
    # CTO: 5 needs
    for i in range(5):
        store.store(_make_snapshot(
            need_id=f"cto-{i}", stakeholder_id="sh-cto",
            priority="high", complexity="procedural",
            use_case_id="uc-payment",
        ))
    # Dev: 3 needs
    for i in range(3):
        store.store(_make_snapshot(
            need_id=f"dev-{i}", stakeholder_id="sh-dev",
            priority="medium", complexity="complex",
            use_case_id="uc-deploy",
        ))
    # QA: 2 needs
    for i in range(2):
        store.store(_make_snapshot(
            need_id=f"qa-{i}", stakeholder_id="sh-qa",
            priority="low", complexity="simple",
        ))
    return store


# ── NeedsSimulator Tests ───────────────────────────────────────────────

class TestNeedsSimulator:
    def test_simulate_no_changes(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        result = simulator.simulate([])
        assert result.total_needs_analyzed == 10
        assert result.affected_needs == 0
        assert result.impact_level == ImpactLevel.NONE
        assert result.safe_to_apply is True

    def test_simulate_stakeholder_removal(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        result = simulator.simulate_stakeholder_removal("sh-cto")
        assert result.affected_needs == 5
        assert result.orphaned_needs == 5
        # 5/10 = 0.5 change_rate > 0.3 → HIGH
        assert result.impact_level == ImpactLevel.HIGH

    def test_simulate_priority_withdrawal(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        change = NeedChange(
            change_type=NeedChangeType.WITHDRAW_BY_PRIORITY,
            target_value="low",
        )
        result = simulator.simulate([change])
        assert result.affected_needs == 2  # 2 QA needs

    def test_simulate_use_case_removal(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        change = NeedChange(
            change_type=NeedChangeType.REMOVE_USE_CASE,
            target_value="uc-payment",
        )
        result = simulator.simulate([change])
        assert result.affected_needs == 5  # 5 CTO needs

    def test_simulate_complexity_change(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        change = NeedChange(
            change_type=NeedChangeType.CHANGE_COMPLEXITY,
            target_value="procedural",
            new_complexity="complex",
        )
        result = simulator.simulate([change])
        assert result.complexity_mismatches == 5  # 5 CTO needs

    def test_simulate_multiple_changes(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        changes = [
            NeedChange(
                change_type=NeedChangeType.REMOVE_STAKEHOLDER,
                target_value="sh-qa",
            ),
            NeedChange(
                change_type=NeedChangeType.WITHDRAW_BY_PRIORITY,
                target_value="medium",
            ),
        ]
        result = simulator.simulate(changes)
        # 2 QA orphaned + 3 dev by priority
        assert result.affected_needs == 5

    def test_impact_level_critical(self):
        store = InMemoryNeedStore()
        # Create 10 needs for one stakeholder
        for i in range(10):
            store.store(_make_snapshot(
                need_id=f"n{i}", stakeholder_id="sh-only",
            ))

        simulator = NeedsSimulator(store)
        result = simulator.simulate_stakeholder_removal("sh-only")
        # 10/10 = 1.0 change_rate > 0.5 → CRITICAL
        assert result.impact_level == ImpactLevel.CRITICAL

    def test_change_rate(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        result = simulator.simulate_stakeholder_removal("sh-cto")
        assert result.change_rate == pytest.approx(0.5)

    def test_risk_factors(self):
        store = InMemoryNeedStore()
        for i in range(20):
            store.store(_make_snapshot(
                need_id=f"n{i}", stakeholder_id="sh-only",
            ))

        simulator = NeedsSimulator(store)
        result = simulator.simulate_stakeholder_removal("sh-only")
        assert len(result.risk_factors) > 0
        assert result.safe_to_apply is False

    def test_safe_to_apply_small_change(self):
        store = _populated_store()
        simulator = NeedsSimulator(store)

        change = NeedChange(
            change_type=NeedChangeType.WITHDRAW_BY_PRIORITY,
            target_value="low",
        )
        result = simulator.simulate([change])
        assert result.safe_to_apply is True

    def test_empty_store(self):
        store = InMemoryNeedStore()
        simulator = NeedsSimulator(store)

        result = simulator.simulate_stakeholder_removal("sh-none")
        assert result.total_needs_analyzed == 0
        assert result.affected_needs == 0
        assert result.impact_level == ImpactLevel.NONE
