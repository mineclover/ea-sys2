"""Tests for DecisionSimulator — S5 Evolution What-If."""

from __future__ import annotations

from ea_decision.decision_simulator import (
    AffectedDecision,
    DecisionSimulator,
    ImpactLevel,
    PatternChange,
    PatternChangeType,
    PatternSimulationResult,
)
from ea_decision.topic_store import (
    DecisionSnapshotStatus,
    InMemoryTopicStore,
    StoredDecisionSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    topic_id: str = "topic-001",
    pattern_name: str = "TradeOff",
    complexity: str = "structural",
    status: DecisionSnapshotStatus = DecisionSnapshotStatus.ACCEPTED,
) -> StoredDecisionSnapshot:
    return StoredDecisionSnapshot(
        storage_id="",
        topic_id=topic_id,
        pattern_name=pattern_name,
        complexity=complexity,
        option_count=3,
        evaluation_score=0.75,
        decided_at="2025-01-15T10:00:00Z",
        status=status,
    )


def _populated_store() -> InMemoryTopicStore:
    store = InMemoryTopicStore()
    for i in range(10):
        store.store(_make_snapshot(
            topic_id=f"to-{i}", pattern_name="TradeOff",
        ))
    for i in range(5):
        store.store(_make_snapshot(
            topic_id=f"co-{i}", pattern_name="Compliance",
        ))
    for i in range(3):
        store.store(_make_snapshot(
            topic_id=f"ar-{i}", pattern_name="Architecture",
            complexity="strategic",
        ))
    return store


# ── DecisionSimulator Tests ─────────────────────────────────────────────

class TestDecisionSimulator:
    def test_simulate_no_changes(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        result = sim.simulate([])
        assert result.total_decisions_analyzed == 18
        assert result.affected_decisions == 0
        assert result.impact_level == ImpactLevel.NONE
        assert result.safe_to_apply is True

    def test_simulate_pattern_removal(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        result = sim.simulate_pattern_removal("TradeOff")
        assert result.total_decisions_analyzed == 18
        assert result.orphaned_decisions == 10
        assert result.affected_decisions == 10
        assert result.impact_level in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)

    def test_simulate_complexity_change(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        change = PatternChange(
            change_type=PatternChangeType.MODIFY_COMPLEXITY,
            pattern_name="Architecture",
            new_complexity="trivial",
        )
        result = sim.simulate([change])
        assert result.complexity_mismatches == 3
        assert result.affected_decisions == 3

    def test_simulate_add_pattern_no_impact(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        change = PatternChange(
            change_type=PatternChangeType.ADD_PATTERN,
            pattern_name="NewPattern",
        )
        result = sim.simulate([change])
        assert result.affected_decisions == 0
        assert result.impact_level == ImpactLevel.NONE

    def test_simulate_multiple_removals(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        changes = [
            PatternChange(
                change_type=PatternChangeType.REMOVE_PATTERN,
                pattern_name="TradeOff",
            ),
            PatternChange(
                change_type=PatternChangeType.REMOVE_PATTERN,
                pattern_name="Compliance",
            ),
        ]
        result = sim.simulate(changes)
        assert result.orphaned_decisions == 15
        assert result.impact_level == ImpactLevel.CRITICAL

    def test_change_rate(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        result = sim.simulate_pattern_removal("Compliance")
        assert result.change_rate == 5 / 18

    def test_risk_factors_identified(self):
        store = InMemoryTopicStore()
        for i in range(30):
            store.store(_make_snapshot(
                topic_id=f"t-{i}", pattern_name="Heavy",
            ))

        sim = DecisionSimulator(store)
        result = sim.simulate_pattern_removal("Heavy")
        assert len(result.risk_factors) >= 1

    def test_safe_to_apply_false_for_high_impact(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        result = sim.simulate_pattern_removal("TradeOff")
        assert result.safe_to_apply is False

    def test_simulation_result_has_id_and_timestamp(self):
        store = _populated_store()
        sim = DecisionSimulator(store)

        result = sim.simulate([])
        assert result.simulation_id.startswith("sim-")
        assert result.created_at.endswith("Z")

    def test_empty_store(self):
        store = InMemoryTopicStore()
        sim = DecisionSimulator(store)

        result = sim.simulate_pattern_removal("Any")
        assert result.total_decisions_analyzed == 0
        assert result.impact_level == ImpactLevel.NONE
