"""Tests for what_if_simulator — S5 Evolution simulation.

Extracted from test_governance_phase3.py for module-level focus.

Tests:
- WhatIfSimulator rule removal simulation
- WhatIfSimulator multi-change simulation
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from ea_kernel.governance_types import EvidenceSummaryItem
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    RuleConfidence,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Temporary database path."""
    return tmp_path / "test_what_if_simulator.db"


# ═══════════════════════════════════════════════════════════════════════════════
# WhatIfSimulator Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatIfSimulator:
    """Tests for WhatIfSimulator."""

    def test_simulate_rule_removal(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.what_if_simulator import (
            WhatIfSimulator,
        )

        # Setup decision store with some records
        store = SQLiteDecisionStore(db_path)

        # Create some decision records
        for i in range(10):
            judgment = JudgmentReport(
                verdict=True,
                evidence=(),
                confidence=RuleConfidence.UNIVERSAL,
                domains=("kernel",),
                conflicts=(),
            )
            record = DecisionRecord(
                id=f"dec-{i:03d}",
                timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
                actor="human:user",
                decision_type="validate",
                subject_triple=("Source", f"Target-{i}", "relates"),
                judgment=judgment,
            )
            # Create evidence summary
            evidence_summary = (
                EvidenceSummaryItem(
                    rule_id="rule-winning",
                    domain="kernel",
                    matched=True,
                    is_winner=True,
                ),
            )
            store.store(record, evidence_summary=evidence_summary)

        # Simulate removing the winning rule
        simulator = WhatIfSimulator(store)
        result = simulator.simulate_rule_removal("rule-winning")

        assert result.total_decisions_analyzed == 10
        assert result.simulation_id.startswith("sim-")

    def test_simulate_with_multiple_changes(self, db_path: Path) -> None:
        from ea_kernel.decision_store import SQLiteDecisionStore
        from ea_kernel.what_if_simulator import (
            ChangeType,
            SimulatedChange,
            WhatIfSimulator,
        )

        store = SQLiteDecisionStore(db_path)

        # Add decisions
        for i in range(5):
            judgment = JudgmentReport(
                verdict=True,
                evidence=(),
                confidence=RuleConfidence.UNIVERSAL,
                domains=("kernel",),
                conflicts=(),
            )
            record = DecisionRecord(
                id=f"dec-{i:03d}",
                timestamp=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
                actor="human:user",
                decision_type="validate",
                subject_triple=("A", f"B-{i}", "C"),
                judgment=judgment,
            )
            evidence_summary = (
                EvidenceSummaryItem(
                    rule_id=f"rule-{i % 2}",
                    domain="kernel",
                    matched=True,
                    is_winner=(i % 2 == 0),
                ),
            )
            store.store(record, evidence_summary=evidence_summary)

        # Simulate multiple changes
        simulator = WhatIfSimulator(store)
        changes = [
            SimulatedChange(ChangeType.REMOVE_RULE, "rule-0"),
            SimulatedChange(ChangeType.CHANGE_PRIORITY, "rule-1", new_priority=200),
        ]

        result = simulator.simulate(changes)

        assert len(result.changes) == 2
        assert result.total_decisions_analyzed == 5
