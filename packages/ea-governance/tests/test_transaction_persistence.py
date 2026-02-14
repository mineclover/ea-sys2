from __future__ import annotations

from pathlib import Path

import pytest
from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_governance.transaction import TransactionManager, TransactionStatus


def test_transaction_manager_persists_transaction_and_events(tmp_path: Path):
    db_path = tmp_path / "transactions.db"

    manager_1 = TransactionManager(db_path)
    tx = manager_1.begin_transaction(
        "persist-test",
        tx_type="integration",
        payload={"source": "unit"},
    )
    tx_id = tx.id
    assert manager_1.commit(tx_id) is True

    manager_2 = TransactionManager(db_path)
    loaded = manager_2.get_transaction(tx_id)
    assert loaded is not None
    assert loaded.status == TransactionStatus.COMMITTED
    assert any("committed successfully" in log for log in loaded.logs)

    events = manager_2.get_events(tx_id)
    assert len(events) == 2
    assert events[0].event_type == "begin"
    assert events[1].event_type == "commit"


def test_container_reads_persisted_transaction_after_restart(tmp_path: Path):
    schema = KernelSchema(attributes=(), entities=(), relations=())

    container_1 = GovernanceContainer(tmp_path, schema)
    result = container_1.propose_initiative("Persist Tx", "desc")
    tx_id = result["transaction_id"]

    status_1 = container_1.get_transaction_status(tx_id)
    assert status_1 is not None
    assert status_1["status"] == TransactionStatus.COMMITTED

    container_2 = GovernanceContainer(tmp_path, schema)
    status_2 = container_2.get_transaction_status(tx_id)
    assert status_2 is not None
    assert status_2["status"] == TransactionStatus.COMMITTED

    events = container_2.get_transaction_events(tx_id)
    assert len(events) >= 2
    event_types = [event["event_type"] for event in events]
    assert "begin" in event_types
    assert "commit" in event_types


def test_transaction_manager_requires_db_path():
    with pytest.raises(ValueError, match="db_path is required"):
        TransactionManager(None)  # type: ignore[arg-type]


def test_execution_service_default_transaction_db_path(tmp_path: Path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)
    tx_db_path = container.execution_service.tx_manager.db_path

    assert tx_db_path == tmp_path / "transactions.db"
    assert tx_db_path.exists()


def test_transaction_manager_custom_event_and_list_filter(tmp_path: Path):
    manager = TransactionManager(tmp_path / "transactions.db")
    tx = manager.begin_transaction(
        "needs-write",
        tx_type="needs_catalog_write",
        payload={"catalog_id": "catalog-1"},
    )

    assert manager.add_event(
        tx.id,
        "needs_catalog_saved",
        "Needs catalog persisted.",
        payload={"catalog_id": "catalog-1"},
    )
    assert manager.commit(tx.id)

    writes = manager.list_transactions(tx_type="needs_catalog_write")
    assert len(writes) == 1
    assert writes[0].id == tx.id

    events = manager.get_events(tx.id)
    event_types = [event.event_type for event in events]
    assert event_types == ["begin", "needs_catalog_saved", "commit"]
