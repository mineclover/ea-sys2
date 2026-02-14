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
