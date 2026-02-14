
import pytest

pytest.importorskip("fastapi")
from unittest.mock import MagicMock

from ea_kernel.api.server import create_app
from ea_kernel.evidence_analyzer import AnalysisReport, RuleEffectiveness
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
from ea_kernel.schema_loader import load_kernel_schema_from_package
from ea_kernel.types import (
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_mock_system(tmp_path):
    schema = load_kernel_schema_from_package()
    data_dir = tmp_path / "gov_data"
    data_dir.mkdir()

    # Initialize app which creates system
    app = create_app(data_dir=data_dir, schema=schema)
    return app

def test_get_promotion_proposals_empty(app_with_mock_system):
    client = TestClient(app_with_mock_system)
    response = client.get("/automation/promotions")
    assert response.status_code == 200
    assert response.json() == []

def test_get_promotion_proposals_with_data(app_with_mock_system):
    app = app_with_mock_system
    # Access the system via app.state
    system = app.state.system
    client = TestClient(app)

    # 1. Mock analyze() to return a report with effectiveness data
    mock_report = AnalysisReport(
        report_id="rep-1",
        corpus_version_id="v1",
        analysis_period_start="",
        analysis_period_end="",
        created_at="2023-01-01T00:00:00Z",
        total_decisions_analyzed=100,
        rule_effectiveness=(
            RuleEffectiveness(
                rule_id="rule:test:promo",
                domain="test",
                total_evaluations=100,
                match_count=50,
                win_count=40,
                override_count=0,
                shadow_count=0,
            ),
        ),
        conflict_hotspots=(),
        usage_profiles=()
    )
    system.analyze = MagicMock(return_value=mock_report)

    # 2. Ensure the rule exists in store and is in REVIEW state
    # We bypass normal submission flow for simplicity
    rule = KernelValidityRule(
        id="rule:test:promo",
        source_pattern="S",
        target_pattern="T",
        relationship_name="R"
    )
    meta = RuleMetadata(
        domain="test",
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.EMPIRICAL,
        group=RuleGroup.FLOW,
        tags=(),
        source="test",
        established_version="1.0",
        rationale="test"
    )
    entry = RuleCorpusEntry(rule=rule, metadata=meta)
    provenance = RuleProvenance(
        author="test",
        source_type="manual",
        source_reference="test-ref",
        created_at="2023-01-01T00:00:00Z"
    )

    # Manually create asset in DRAFT state
    asset = RuleAsset(
        entry=entry,
        provenance=provenance,
        lifecycle=RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    )

    system.rule_store.create(asset)
    system.rule_store.transition(asset.id, RuleLifecycleState.REVIEW, "author", "submit")

    # 3. Call API
    response = client.get("/automation/promotions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["rule_id"] == "rule:test:promo"
    assert data[0]["change_type"] == "promote"


def test_simulation_what_if(app_with_mock_system):
    app = app_with_mock_system
    system = app.state.system
    client = TestClient(app)

    # Mock simulator.simulate
    from ea_kernel.what_if_simulator import ImpactLevel, SimulationResult, VerdictChange

    def mock_simulate(changes, limit=1000):
        return SimulationResult(
            simulation_id="sim-test-123",
            created_at="2023-01-01T00:00:00Z",
            changes=tuple(changes),
            impact_level=ImpactLevel.MEDIUM,
            total_decisions_analyzed=50,
            affected_decisions=1,
            verdict_changes=(
                VerdictChange(
                    triple=("S", "T", "R"),
                    original_verdict=True,
                    simulated_verdict=False,
                    original_winning_rule="rule:old",
                    simulated_winning_rule="rule:new",
                    timestamp="2023-01-01T00:00:00Z"
                ),
            ),
            risk_factors=("Use of deprecated rule",),
            winning_rule_changes=1,
            verdicts_flipped_allow_to_deny=1,
            verdicts_flipped_deny_to_allow=0,
            affected_domains=(),
            safe_to_apply=True
        )

    system.simulator = MagicMock()
    system.simulator.simulate.side_effect = mock_simulate

    payload = {
        "rule_id": "rule:test:sim",
        "new_confidence": "common"
    }

    response = client.post("/simulation/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["simulation_id"] == "sim-test-123"
    assert data["impact_level"] == "medium"
    assert data["total_decisions_analyzed"] == 50
    assert len(data["verdict_changes"]) == 1
    assert data["verdict_changes"][0]["original"] is True
    assert data["verdict_changes"][0]["simulated"] is False
