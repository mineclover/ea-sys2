
import pytest
from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_governance.transaction import TransactionStatus


# Fix KernelSchema mock as before
@pytest.fixture
def mock_container(tmp_path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    return GovernanceContainer(tmp_path, schema)

def test_facade_initiative_proposal(mock_container):
    # 1. Propose Initiative
    result = mock_container.propose_initiative("Modernize Stack", "Move to Python 3.12")

    # 2. Check Response
    assert "topic" in result
    assert "transaction_id" in result

    tx_id = result["transaction_id"]
    topic = result["topic"]

    assert topic.title == "Modernize Stack"

    # 3. Check Transaction Status via Facade
    status = mock_container.get_transaction_status(tx_id)
    assert status["status"] == TransactionStatus.COMMITTED

    # 4. Check Logs
    logs = mock_container.get_transaction_logs(tx_id)
    assert len(logs) > 0

def test_topic_has_trace_id(mock_container):
    """GAP-5: Topic auto-generates a trace_id."""
    topic = mock_container.create_topic("Trace Test", "Test")
    assert topic.trace_id.startswith("trace-")
    assert len(topic.trace_id) == 18  # "trace-" + 12 hex chars


def test_trace_id_propagates_to_transaction(mock_container):
    """GAP-5: trace_id propagates from Topic through execution to Transaction."""
    topic = mock_container.create_topic("Traced Decision", "Test")
    topic.add_option("Opt1", "Desc")
    report = topic.finalize_plan("Plan", "S", topic.options[0].id, "R")
    report.add_action("create_rule", "rule:x", "desc", payload={"id": "x"})

    result = mock_container.interpret_decision(report.id, topic)
    assert result["success"] is True

    tx_id = result["transaction_id"]
    tx = mock_container.execution_service.tx_manager.get_transaction(tx_id)
    assert tx is not None
    assert tx.trace_id == topic.trace_id

    # query by trace_id
    txs = mock_container.execution_service.tx_manager.list_transactions(
        trace_id=topic.trace_id,
    )
    assert len(txs) >= 1
    assert any(t.id == tx_id for t in txs)


def test_query_by_trace_id(mock_container):
    """GAP-5: query_by_trace_id aggregates cross-layer results."""
    topic = mock_container.create_topic("Cross-Layer", "Test")
    trace_id = topic.trace_id
    topic.add_option("Opt1", "Desc")
    report = topic.finalize_plan("Plan", "S", topic.options[0].id, "R")
    report.add_action("create_rule", "rule:x", "desc", payload={"id": "x"})

    mock_container.interpret_decision(report.id, topic)
    mock_container.record_projection_result(
        profile_name="test", level="l0", node_count=5, edge_count=3,
        trace_id=trace_id,
    )

    result = mock_container.query_by_trace_id(trace_id)
    assert result["trace_id"] == trace_id
    assert len(result["transactions"]) >= 1
    assert len(result["projection_snapshots"]) == 1


def test_facade_record_projection_result(mock_container):
    """GAP-2: Projection execution result is recorded via governance."""
    result = mock_container.record_projection_result(
        profile_name="ea_sys",
        level="l0",
        node_count=5,
        edge_count=8,
        projection_filter={
            "stages": {"node_input": 20, "node_connected_or_preserved": 5},
            "drop_reasons": {"node_category_filtered": 10, "node_disconnected": 5},
        },
        return_transaction=True,
    )

    assert isinstance(result, dict)
    assert "model_id" in result
    assert "transaction_id" in result
    assert result["model_id"].startswith("proj:ea_sys:l0:")

    # Verify persisted
    snapshots = mock_container.list_layer_snapshots("projection")
    assert len(snapshots) == 1
    payload = snapshots[0]["payload"]
    assert payload["profile_name"] == "ea_sys"
    assert payload["level"] == "l0"
    assert payload["node_count"] == 5
    assert payload["edge_count"] == 8
    assert "projection_filter" in payload

    # Verify transaction committed
    status = mock_container.get_transaction_status(result["transaction_id"])
    assert status["status"] == TransactionStatus.COMMITTED


def test_facade_record_projection_with_tier_and_seed(mock_container):
    """GAP-2: Projection recording preserves tier and seed metadata."""
    model_id = mock_container.record_projection_result(
        profile_name="ea_sys",
        level="l1",
        node_count=3,
        edge_count=4,
        tier="t1",
        seed="my-element",
    )
    assert isinstance(model_id, str)

    snapshots = mock_container.list_layer_snapshots("projection")
    assert len(snapshots) == 1
    payload = snapshots[0]["payload"]
    assert payload["tier"] == "t1"
    assert payload["seed"] == "my-element"


def test_detect_projection_drift_no_data(mock_container):
    """GAP-3: No drift if fewer than 2 snapshots."""
    assert mock_container.detect_projection_drift("ea_sys") is None


def test_detect_projection_drift_no_change(mock_container):
    """GAP-3: No drift if values are within threshold."""
    mock_container.record_projection_result(
        profile_name="ea_sys", level="l0", node_count=10, edge_count=20,
    )
    mock_container.record_projection_result(
        profile_name="ea_sys", level="l0", node_count=11, edge_count=21,
    )
    drift = mock_container.detect_projection_drift("ea_sys")
    assert drift is None


def test_detect_projection_drift_significant(mock_container):
    """GAP-3: Drift detected when node/edge counts change significantly."""
    mock_container.record_projection_result(
        profile_name="ea_sys", level="l0", node_count=10, edge_count=20,
    )
    mock_container.record_projection_result(
        profile_name="ea_sys", level="l0", node_count=15, edge_count=35,
    )
    drift = mock_container.detect_projection_drift("ea_sys")
    assert drift is not None
    assert drift["node_drift"] == 0.5  # 5/10
    assert drift["edge_drift"] == 0.75  # 15/20
    assert drift["recommendation"] == "revise_decision"


def test_apply_projection_feedback(mock_container):
    """GAP-3: Projection feedback triggers decision revision."""
    topic = mock_container.create_topic("Feedback Test", "Test")
    topic.add_option("Opt", "Desc")
    report = topic.finalize_plan("Plan", "S", topic.options[0].id, "R")
    report.add_action("create_rule", "rule:x", "desc", payload={"id": "x"})
    mock_container.interpret_decision(report.id, topic)

    assert topic.status == "completed"
    assert topic.report is not None

    drift = {"recommendation": "revise_decision"}
    revised = mock_container.apply_projection_feedback(topic, drift)

    assert revised is True
    assert topic.status == "active"
    assert topic.report is None  # archived to history


def test_apply_projection_feedback_already_active(mock_container):
    """GAP-3: No revision if topic is already active."""
    topic = mock_container.create_topic("Active Topic", "Test")
    assert topic.status == "active"

    revised = mock_container.apply_projection_feedback(topic, {})
    assert revised is False


def test_apply_critical_impact_deprecates_rules(mock_container):
    """GAP-4/S6: Critical impact triggers auto-deprecation of affected rules."""
    from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
    from ea_kernel.types import (
        KernelValidityRule, RuleCategory, RuleConfidence, RuleCorpusEntry, RuleMetadata,
    )

    # Submit and approve a rule first
    rule = KernelValidityRule(
        id="test-rule-001", source_pattern="S", target_pattern="T",
        relationship_name="r", valid=True, priority=50,
    )
    metadata = RuleMetadata(
        domain="test", tags=(), category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.COMMON, source="test",
        established_version="v1", rationale="test",
    )
    entry = RuleCorpusEntry(rule=rule, metadata=metadata)
    provenance = RuleProvenance(author="test", source_type="manual")
    asset = RuleAsset(entry=entry, provenance=provenance, lifecycle=RuleLifecycle())
    mock_container.submit_kernel_rule(asset)
    mock_container.approve_kernel_rule("test-rule-001")

    # Build an ImpactReport-like dict with CRITICAL severity
    impact = {
        "severity": "critical",
        "affected_decisions": [
            {
                "decision_id": "d-1",
                "potential_verdict_change": True,
                "affected_by_rules": ["test-rule-001"],
            },
        ],
    }
    result = mock_container.apply_critical_impact(impact)
    assert result["action"] == "auto_deprecate"
    assert "test-rule-001" in result["deprecated_rules"]


def test_apply_critical_impact_skips_low_severity(mock_container):
    """GAP-4/S6: Low severity does not trigger auto-deprecation."""
    impact = {
        "severity": "low",
        "affected_decisions": [],
    }
    result = mock_container.apply_critical_impact(impact)
    assert result["action"] == "none"


def test_facade_decision_execution(mock_container):
    # 1. Setup Topic & Report
    topic = mock_container.create_topic("Test Decision", "Desc")
    topic.add_option("Opt1", "Desc")
    report = topic.finalize_plan("Plan", "Summary", topic.options[0].id, "Ratio")
    report.add_action("create_rule", "rule:x", "desc", payload={"id":"x"})

    # 2. Interpret via Facade
    result = mock_container.interpret_decision(report.id, topic)

    # 3. Check Response
    assert result["success"] is True
    assert "transaction_id" in result

    tx_id = result["transaction_id"]

    # 4. Verify Status
    status = mock_container.get_transaction_status(tx_id)
    assert status["status"] == TransactionStatus.COMMITTED
