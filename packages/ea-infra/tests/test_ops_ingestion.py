"""Tests for ea_infra.ops_ingestion."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from ea_infra.ops_ingestion import (
    InMemoryOpsEventStore,
    OpsEventRetentionPolicy,
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


def _record(trace_id: str, lineage_id: str, *, ingested_at: datetime | None = None):
    record = build_ops_event_record(
        _event(
            {
                "trace_id": trace_id,
                "lineage_id": lineage_id,
                "service_id": "payments-api",
            }
        )
    )
    if ingested_at is None:
        return record
    return replace(record, ingested_at=ingested_at.isoformat() + "Z")


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


def test_ops_event_retention_policy_rejects_negative_values():
    with pytest.raises(ValueError, match="max_age_days must be >= 0"):
        OpsEventRetentionPolicy(max_age_days=-1)
    with pytest.raises(ValueError, match="max_records must be >= 0"):
        OpsEventRetentionPolicy(max_records=-1)


def test_sqlite_ops_event_store_cleanup_preview_and_cleanup_by_age(tmp_path):
    now = datetime(2026, 2, 21, tzinfo=UTC)
    store = SQLiteOpsEventStore(tmp_path / "ops-events.db")
    old = _record("trace-retention-old", "lineage-ret", ingested_at=now - timedelta(days=5))
    boundary = _record("trace-retention-boundary", "lineage-ret", ingested_at=now - timedelta(days=2))
    fresh = _record("trace-retention-fresh", "lineage-ret", ingested_at=now - timedelta(hours=12))

    store.append(old)
    store.append(boundary)
    store.append(fresh)

    policy = OpsEventRetentionPolicy(max_age_days=2)
    preview = store.cleanup_preview(policy, now=now)
    assert preview.before_count == 3
    assert preview.after_count == 2
    assert preview.deleted_count == 1
    assert store.count() == 3

    result = store.cleanup(policy, now=now)
    assert result.before_count == 3
    assert result.after_count == 2
    assert result.deleted_count == 1
    assert store.count() == 2
    assert [row.trace_id for row in store.read(limit=10)] == [
        "trace-retention-boundary",
        "trace-retention-fresh",
    ]


def test_sqlite_ops_event_store_cleanup_respects_max_records(tmp_path):
    now = datetime(2026, 2, 21, tzinfo=UTC)
    store = SQLiteOpsEventStore(tmp_path / "ops-events.db")
    for idx in range(4):
        store.append(
            _record(
                f"trace-retention-{idx}",
                "lineage-ret",
                ingested_at=now - timedelta(minutes=4 - idx),
            )
        )

    policy = OpsEventRetentionPolicy(max_records=2)
    result = store.cleanup(policy, now=now)
    assert result.before_count == 4
    assert result.after_count == 2
    assert result.deleted_count == 2
    assert [row.trace_id for row in store.read(limit=10)] == [
        "trace-retention-2",
        "trace-retention-3",
    ]


def test_in_memory_ops_event_store_cleanup_respects_max_records():
    now = datetime(2026, 2, 21, tzinfo=UTC)
    store = InMemoryOpsEventStore()
    for idx in range(3):
        store.append(
            _record(
                f"trace-memory-{idx}",
                "lineage-memory",
                ingested_at=now - timedelta(minutes=3 - idx),
            )
        )

    result = store.cleanup(OpsEventRetentionPolicy(max_records=1), now=now)
    assert result.before_count == 3
    assert result.after_count == 1
    assert result.deleted_count == 2
    assert [row.trace_id for row in store.read(limit=10)] == ["trace-memory-2"]
