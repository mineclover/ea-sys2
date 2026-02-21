from __future__ import annotations

from ea_governance.facade import GovernanceContainer
from ea_kernel.definition import KERNEL_SCHEMA


def _profile_toml(name: str = "GovernanceModel", version: str = "1.0") -> str:
    return f"""\
[profile]
name = "{name}"
version = "{version}"
kernel_version = "2.5.0"

[categories]
Thing = "item"
Action = "step"

[[elements]]
name = "Widget"
layer = "Core"
category = "Thing"

[[elements]]
name = "Task"
layer = "Core"
category = "Action"

[[relations]]
name = "uses"
kernel_relation = "association"

[[rules]]
source = "@Thing"
target = "@Action"
relation = "uses"
priority = 40
"""


def test_register_kernel_model_records_governance_transaction_and_snapshot(tmp_path):
    container = GovernanceContainer(tmp_path, KERNEL_SCHEMA)

    result = container.register_kernel_model(
        _profile_toml(name="GovernanceEntryModel"),
        owner="kernel-team",
        created_by="tester",
        actor="tester",
    )

    assert result["model_name"] == "GovernanceEntryModel"
    assert result["created"] is True

    snapshot = container.get_layer_snapshot("kernel", "model:GovernanceEntryModel")
    assert snapshot is not None
    assert snapshot["kind"] == "kernel_model_state"

    txs = container.execution_service.tx_manager.list_transactions(
        tx_type="kernel_model_registry_write",
        limit=5,
    )
    assert txs
    events = container.get_transaction_events(txs[0].id)
    assert any(event["event_type"] == "kernel_model_registered" for event in events)
    assert any(event["event_type"] == "kernel_model_snapshot_saved" for event in events)


def test_validate_kernel_model_records_validation_transaction(tmp_path):
    container = GovernanceContainer(tmp_path, KERNEL_SCHEMA)
    container.register_kernel_model(
        _profile_toml(name="GovernanceValidateModel"),
        owner="kernel-team",
        created_by="tester",
        actor="tester",
    )

    run = container.validate_kernel_model(
        "GovernanceValidateModel",
        "1.0",
        context={"source": "unit-test"},
        actor="qa",
    )

    assert run.passed is True
    txs = container.execution_service.tx_manager.list_transactions(
        tx_type="kernel_model_registry_validate",
        limit=5,
    )
    assert txs
    events = container.get_transaction_events(txs[0].id)
    assert any(event["event_type"] == "kernel_model_validated" for event in events)


def test_model_registration_records_decision_trace_and_exploration(tmp_path):
    container = GovernanceContainer(tmp_path, KERNEL_SCHEMA)
    decision_id = "dec-model-001"

    register = container.register_kernel_model(
        _profile_toml(name="DecisionTraceModel"),
        owner="kernel-team",
        created_by="tester",
        actor="tester",
        decision_id=decision_id,
        evidence_refs=["ev://specs/model-adr"],
        return_transaction=True,
    )
    assert register["transaction_id"]
    assert register["decision_trace"]["decision_id"] == decision_id
    assert register["decision_trace"]["warnings"] == []
    assert register["decision_trace"]["cause_type"] == "decision"
    assert register["decision_trace"]["cause_id"] == decision_id
    assert register["decision_trace"]["change_phase"] == "planned"

    validate = container.validate_kernel_model(
        "DecisionTraceModel",
        "1.0",
        actor="qa",
        decision_id=decision_id,
        evidence_refs=[],
        return_transaction=True,
    )
    assert isinstance(validate, dict)
    assert validate["transaction_id"]
    assert validate["decision_trace"]["decision_id"] == decision_id
    assert "missing_evidence_refs" in validate["decision_trace"]["warnings"]
    assert validate["decision_trace"]["change_phase"] == "planned"

    activate = container.activate_kernel_model(
        "DecisionTraceModel",
        "1.0",
        actor="release",
        decision_id=decision_id,
        evidence_refs=["ev://release/checklist"],
        return_transaction=True,
    )
    assert isinstance(activate, dict)
    assert activate["transaction_id"]
    assert activate["decision_trace"]["decision_id"] == decision_id
    assert activate["decision_trace"]["change_phase"] == "applied"

    trace = container.get_model_decision_trace(decision_id)
    assert trace is not None
    assert trace["kind"] == "decision_trace_contract"
    assert trace["contract_version"] == "1.0"
    assert trace["decision_id"] == decision_id
    assert trace["cause_type"] == "decision"
    assert trace["cause_id"] == decision_id
    assert trace["latest_change_phase"] == "applied"
    assert len(trace["operations"]) == 3
    assert "missing_evidence_refs" in trace["warnings"]

    exploration = container.explore_model_decision_trace(decision_id)
    assert exploration is not None
    assert exploration["decision_id"] == decision_id
    assert "missing_evidence_refs" in exploration["evidence"]["warnings"]
    assert "validate" in exploration["evidence"]["missing_evidence_operations"]
    assert exploration["impact"]["total_operations"] == 3
    assert "DecisionTraceModel" in exploration["impact"]["models"]
    assert exploration["causal_context"]["latest_change_phase"] == "applied"
    assert exploration["lineage"]["missing_required_relations"] == []
    assert exploration["lineage"]["path_error"] is None
    assert len(exploration["lineage"]["path_to_latest_operation"]) >= 1
    assert any(
        row["cause_type"] == "decision" and row["cause_id"] == decision_id
        for row in exploration["causal_context"]["causes"]
    )
    assert any(
        row["event_type"] == "kernel_model_registered"
        for row in exploration["history"]
    )


def test_list_kernel_models_exposes_registry_index(tmp_path):
    container = GovernanceContainer(tmp_path, KERNEL_SCHEMA)
    container.register_kernel_model(
        _profile_toml(name="RegistryIndexModel"),
        owner="kernel-team",
        created_by="tester",
        actor="tester",
    )

    models = container.list_kernel_models()
    names = {item["model_name"] for item in models}

    assert "RegistryIndexModel" in names
