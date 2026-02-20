"""Tests for ProjectionSimulator — S5 Evolution What-If."""

from __future__ import annotations

from ea_projection.projection_simulator import (
    AffectedProjection,
    ImpactLevel,
    PolicyChange,
    PolicyChangeType,
    ProjectionSimulationResult,
    ProjectionSimulator,
)
from ea_projection.projection_store import (
    InMemoryProjectionStore,
    StoredProjectionSnapshot,
)


# ── Factory ─────────────────────────────────────────────────────────────

def _make_snapshot(
    profile_name: str = "ea_sys",
    level: str = "l0",
    lens: str = "panorama",
    node_count: int = 10,
    edge_count: int = 20,
    projected_at: str = "2025-01-15T10:00:00Z",
) -> StoredProjectionSnapshot:
    return StoredProjectionSnapshot(
        storage_id="",
        profile_name=profile_name,
        level=level,
        lens=lens,
        node_count=node_count,
        edge_count=edge_count,
        projected_at=projected_at,
    )


def _populated_store() -> InMemoryProjectionStore:
    """Create store with diverse test data."""
    store = InMemoryProjectionStore()

    # L0: 5 projections
    for i in range(5):
        store.store(_make_snapshot(
            level="l0", node_count=10, edge_count=100 + i * 10,
            projected_at=f"2025-01-{10 + i:02d}T10:00:00Z",
        ))

    # L1: 3 projections
    for i in range(3):
        store.store(_make_snapshot(
            level="l1", lens="capability",
            node_count=20, edge_count=200 + i * 10,
            projected_at=f"2025-01-{15 + i:02d}T10:00:00Z",
        ))

    # L2: 2 projections
    for i in range(2):
        store.store(_make_snapshot(
            level="l2", lens="interaction",
            node_count=30, edge_count=300 + i * 10,
            projected_at=f"2025-02-{10 + i:02d}T10:00:00Z",
        ))

    return store


# ── PolicyChange Tests ──────────────────────────────────────────────────

class TestPolicyChange:
    def test_frozen(self):
        change = PolicyChange(
            change_type=PolicyChangeType.REMOVE_LEVEL,
            target_value="l0",
        )
        try:
            change.target_value = "l1"  # type: ignore[misc]
            assert False, "Should raise"
        except AttributeError:
            pass


# ── ProjectionSimulationResult Tests ────────────────────────────────────

class TestProjectionSimulationResult:
    def test_change_rate(self):
        result = ProjectionSimulationResult(
            simulation_id="sim-1",
            created_at="2025-01-15T10:00:00Z",
            changes=(),
            total_projections_analyzed=10,
            affected_projections=3,
        )
        assert result.change_rate == 0.3

    def test_change_rate_zero(self):
        result = ProjectionSimulationResult(
            simulation_id="sim-1",
            created_at="2025-01-15T10:00:00Z",
            changes=(),
        )
        assert result.change_rate == 0.0


# ── ProjectionSimulator Tests ───────────────────────────────────────────

class TestProjectionSimulator:
    def test_simulate_level_removal(self):
        store = _populated_store()
        simulator = ProjectionSimulator(store)

        result = simulator.simulate_level_removal("l0")
        assert result.simulation_id.startswith("sim-")
        assert result.total_projections_analyzed == 10
        assert result.invalidated_projections == 5
        assert result.affected_projections == 5
        assert result.impact_level in (ImpactLevel.HIGH, ImpactLevel.CRITICAL)

    def test_simulate_no_impact(self):
        store = _populated_store()
        simulator = ProjectionSimulator(store)

        result = simulator.simulate([
            PolicyChange(
                change_type=PolicyChangeType.REMOVE_LEVEL,
                target_value="l99",
            ),
        ])
        assert result.affected_projections == 0
        assert result.impact_level == ImpactLevel.NONE
        assert result.safe_to_apply is True

    def test_simulate_edge_budget_violation(self):
        store = _populated_store()
        simulator = ProjectionSimulator(store)

        # L1 has edges around 200-220, set budget to 150
        result = simulator.simulate([
            PolicyChange(
                change_type=PolicyChangeType.CHANGE_MAX_EDGES,
                target_value="l1",
                new_value="150",
            ),
        ])
        assert result.edge_budget_violations > 0
        assert result.affected_projections > 0

    def test_simulate_lens_change(self):
        store = _populated_store()
        simulator = ProjectionSimulator(store)

        result = simulator.simulate([
            PolicyChange(
                change_type=PolicyChangeType.CHANGE_LENS,
                target_value="l0",
                new_value="overview",
            ),
        ])
        # All L0 projections have lens="panorama", changing to "overview"
        assert result.affected_projections == 5

    def test_simulate_multiple_changes(self):
        store = _populated_store()
        simulator = ProjectionSimulator(store)

        result = simulator.simulate([
            PolicyChange(
                change_type=PolicyChangeType.REMOVE_LEVEL,
                target_value="l2",
            ),
            PolicyChange(
                change_type=PolicyChangeType.CHANGE_LENS,
                target_value="l1",
                new_value="overview",
            ),
        ])
        # L2 removed (2) + L1 lens changed (3)
        assert result.affected_projections == 5

    def test_safe_to_apply_false_on_high_impact(self):
        store = InMemoryProjectionStore()
        # Many projections on same level
        for i in range(25):
            store.store(_make_snapshot(
                level="l0",
                projected_at=f"2025-01-{(i % 28) + 1:02d}T10:00:00Z",
            ))

        simulator = ProjectionSimulator(store)
        result = simulator.simulate_level_removal("l0")
        assert result.safe_to_apply is False
        assert result.impact_level == ImpactLevel.CRITICAL

    def test_risk_factors(self):
        store = InMemoryProjectionStore()
        for i in range(15):
            store.store(_make_snapshot(
                level="l0",
                projected_at=f"2025-01-{(i % 28) + 1:02d}T10:00:00Z",
            ))

        simulator = ProjectionSimulator(store)
        result = simulator.simulate_level_removal("l0")
        assert len(result.risk_factors) > 0

    def test_impact_level_low(self):
        store = InMemoryProjectionStore()
        # 20 projections total, only 1 affected → low rate
        for i in range(19):
            store.store(_make_snapshot(
                level="l0", lens="panorama",
                projected_at=f"2025-01-{(i % 28) + 1:02d}T10:00:00Z",
            ))
        store.store(_make_snapshot(
            level="l1", lens="capability",
            projected_at="2025-02-01T10:00:00Z",
        ))

        simulator = ProjectionSimulator(store)
        result = simulator.simulate([
            PolicyChange(
                change_type=PolicyChangeType.CHANGE_LENS,
                target_value="l1",
                new_value="overview",
            ),
        ])
        assert result.impact_level == ImpactLevel.LOW
