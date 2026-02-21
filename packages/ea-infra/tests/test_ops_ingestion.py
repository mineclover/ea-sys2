"""Tests for ea_infra.ops_ingestion."""

import pytest
from ea_infra.ops_ingestion import (
    InMemoryOpsEventStore,
    SQLiteOpsEventStore,
    build_ops_event_record,
)
from ea_ops.events import FeedbackLayer, ServiceOpsEvent, ServiceOpsSeverity


def _event(payload: dict[str, object]) -> ServiceOpsEvent:
    return ServiceOpsEvent(
        name="incident_opened",
        severity=ServiceOpsSeverity.HIGH,
        feeds_back_to=FeedbackLayer.DECISION,
        payload=payload,
    )


def test_build_ops_event_record_requires_correlation_fields():
    with pytest.raises(ValueError):
        build_ops_event_record(_event({"service_id": "payments-api"}))


def test_in_memory_ops_event_store_append_and_read():
    store = InMemoryOpsEventStore()
    event = _event(
        {
            "trace_id": "trace-1",
            "lineage_id": "lineage-1",
            "service_id": "payments-api",
            "incident_id": "inc-1",
        }
    )

    record_id = store.append(event)
    rows = store.read()
    assert len(rows) == 1
    assert rows[0].id == record_id
    assert rows[0].event_name == "incident_opened"
    assert rows[0].name == "incident_opened"
    assert rows[0].trace_id == "trace-1"
    assert store.count() == 1


def test_sqlite_ops_event_store_append_and_read(tmp_path):
    store = SQLiteOpsEventStore(tmp_path / "ops-events.db")
    event = _event(
        {
            "trace_id": "trace-sql-1",
            "lineage_id": "lineage-sql-1",
            "service_id": "payments-api",
            "incident_id": "inc-001",
        }
    )

    record_id = store.append(event)
    rows = store.read()

    assert store.count() == 1
    assert len(rows) == 1
    assert rows[0].id == record_id
    assert rows[0].event_name == "incident_opened"
    assert rows[0].severity == "high"
    assert rows[0].feeds_back_to == "decision"
    assert rows[0].trace_id == "trace-sql-1"
    assert rows[0].lineage_id == "lineage-sql-1"
    assert rows[0].payload["incident_id"] == "inc-001"
    assert rows[0].ingested_at


def test_sqlite_ops_event_store_persists_across_instances(tmp_path):
    db_path = tmp_path / "ops-events.db"
    event = _event(
        {
            "trace_id": "trace-sql-2",
            "lineage_id": "lineage-sql-2",
            "service_id": "payments-api",
            "incident_id": "inc-002",
        }
    )

    first = SQLiteOpsEventStore(db_path)
    first.append(event)

    second = SQLiteOpsEventStore(db_path)
    rows = second.read()
    assert second.count() == 1
    assert len(rows) == 1
    assert rows[0].trace_id == "trace-sql-2"
    assert rows[0].lineage_id == "lineage-sql-2"
    assert rows[0].payload["service_id"] == "payments-api"


def test_sqlite_ops_event_store_read_after_and_limit(tmp_path):
    store = SQLiteOpsEventStore(tmp_path / "ops-events.db")
    event1 = _event(
        {
            "trace_id": "trace-sql-3-1",
            "lineage_id": "lineage-sql-3",
            "service_id": "payments-api",
        }
    )
    event2 = _event(
        {
            "trace_id": "trace-sql-3-2",
            "lineage_id": "lineage-sql-3",
            "service_id": "payments-api",
        }
    )
    event3 = _event(
        {
            "trace_id": "trace-sql-3-3",
            "lineage_id": "lineage-sql-3",
            "service_id": "payments-api",
        }
    )

    first_id = store.append(event1)
    second_id = store.append(event2)
    store.append(event3)

    one_after_first = store.read(after=first_id, limit=1)
    assert len(one_after_first) == 1
    assert one_after_first[0].id == second_id

    missing_after = store.read(after="missing-id", limit=2)
    assert len(missing_after) == 2
    assert missing_after[0].id == first_id


def test_sqlite_ops_event_store_read_rejects_negative_limit(tmp_path):
    store = SQLiteOpsEventStore(tmp_path / "ops-events.db")
    with pytest.raises(ValueError, match="limit must be >= 0"):
        store.read(limit=-1)
