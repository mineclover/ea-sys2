"""Tests for ea_infra.storage_ports — Infra storage port contracts."""

from __future__ import annotations

from typing import Any

import pytest

from ea_infra.storage_ports import (
    DataFieldSpec,
    DataSchemaDescriptor,
    EventStoragePort,
    IndexStrategy,
    MigrationResult,
    MigrationSpec,
    ProfileStoragePort,
    RetentionPolicy,
    StorageConstraints,
    StorageLifecyclePort,
    StoragePort,
)


# ── Concrete implementations for Protocol conformance tests ───────────


class InMemoryStore:
    """Minimal StoragePort-conformant implementation."""

    def __init__(self) -> None:
        self._records: dict[str, Any] = {}
        self._counter = 0

    def store(self, record: Any) -> dict[str, Any]:
        self._counter += 1
        sid = f"id-{self._counter}"
        self._records[sid] = record
        return {"storage_id": sid, **record} if isinstance(record, dict) else record

    def get(self, storage_id: str) -> Any | None:
        return self._records.get(storage_id)

    def query(self, options: Any = None) -> list:
        return list(self._records.values())

    def count(self, options: Any = None) -> int:
        return len(self._records)


class InMemoryEventStore:
    """Minimal EventStoragePort-conformant implementation."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def append(self, event: Any) -> str:
        eid = f"evt-{len(self._events)}"
        self._events.append({"id": eid, "data": event})
        return eid

    def read(self, *, after: str | None = None, limit: int = 100) -> list:
        events = self._events
        if after is not None:
            idx = next(
                (i for i, e in enumerate(events) if e["id"] == after), -1,
            )
            events = events[idx + 1 :]
        return events[:limit]

    def count(self) -> int:
        return len(self._events)


class InMemoryProfileStore:
    """Minimal ProfileStoragePort-conformant implementation."""

    def __init__(self) -> None:
        self._records: dict[str, list[Any]] = {}
        self._by_id: dict[str, Any] = {}
        self._counter = 0

    def store(self, record: Any) -> dict[str, Any]:
        self._counter += 1
        sid = f"id-{self._counter}"
        pname = record.get("profile_name", "default") if isinstance(record, dict) else "default"
        self._records.setdefault(pname, []).append(record)
        self._by_id[sid] = record
        return {"storage_id": sid}

    def get(self, storage_id: str) -> Any | None:
        return self._by_id.get(storage_id)

    def query(self, options: Any = None) -> list:
        return [r for versions in self._records.values() for r in versions]

    def count(self, options: Any = None) -> int:
        return sum(len(v) for v in self._records.values())

    def get_latest(self, profile_name: str) -> Any | None:
        versions = self._records.get(profile_name, [])
        return versions[-1] if versions else None

    def list_versions(self, profile_name: str) -> list:
        return self._records.get(profile_name, [])


class InMemoryLifecycle:
    """Minimal StorageLifecyclePort-conformant implementation."""

    def __init__(self, version: str = "1.0") -> None:
        self._version = version
        self._records: list[Any] = []

    def current_schema_version(self) -> str:
        return self._version

    def migrate(self, target_version: str) -> MigrationResult:
        old = self._version
        self._version = target_version
        return MigrationResult(
            success=True, from_version=old, to_version=target_version,
        )

    def apply_retention(self, policy: RetentionPolicy) -> int:
        if policy.max_records > 0 and len(self._records) > policy.max_records:
            excess = len(self._records) - policy.max_records
            self._records = self._records[excess:]
            return excess
        return 0


# ── Protocol Conformance Tests ─────────────────────────────────────────


class TestStoragePortProtocol:
    def test_in_memory_store_satisfies_protocol(self):
        store = InMemoryStore()
        assert isinstance(store, StoragePort)

    def test_store_and_get(self):
        store = InMemoryStore()
        result = store.store({"name": "test"})
        assert store.count() == 1
        assert store.get("id-1") == {"name": "test"}

    def test_query_returns_all(self):
        store = InMemoryStore()
        store.store({"a": 1})
        store.store({"b": 2})
        assert len(store.query()) == 2


class TestEventStoragePortProtocol:
    def test_in_memory_event_store_satisfies_protocol(self):
        store = InMemoryEventStore()
        assert isinstance(store, EventStoragePort)

    def test_append_and_read(self):
        store = InMemoryEventStore()
        eid = store.append({"type": "created"})
        assert eid.startswith("evt-")
        assert store.count() == 1
        events = store.read()
        assert len(events) == 1

    def test_read_after(self):
        store = InMemoryEventStore()
        e1 = store.append({"type": "a"})
        store.append({"type": "b"})
        events = store.read(after=e1)
        assert len(events) == 1
        assert events[0]["data"] == {"type": "b"}


class TestProfileStoragePortProtocol:
    def test_in_memory_profile_store_satisfies_protocol(self):
        store = InMemoryProfileStore()
        assert isinstance(store, ProfileStoragePort)

    def test_get_latest(self):
        store = InMemoryProfileStore()
        store.store({"profile_name": "ea_sys", "version": "1"})
        store.store({"profile_name": "ea_sys", "version": "2"})
        latest = store.get_latest("ea_sys")
        assert latest is not None
        assert latest["version"] == "2"

    def test_list_versions(self):
        store = InMemoryProfileStore()
        store.store({"profile_name": "ea_sys", "version": "1"})
        store.store({"profile_name": "ea_sys", "version": "2"})
        versions = store.list_versions("ea_sys")
        assert len(versions) == 2

    def test_nonexistent_profile(self):
        store = InMemoryProfileStore()
        assert store.get_latest("nonexistent") is None
        assert store.list_versions("nonexistent") == []


class TestStorageLifecyclePortProtocol:
    def test_in_memory_lifecycle_satisfies_protocol(self):
        lc = InMemoryLifecycle()
        assert isinstance(lc, StorageLifecyclePort)

    def test_schema_version(self):
        lc = InMemoryLifecycle("2.0")
        assert lc.current_schema_version() == "2.0"

    def test_migrate(self):
        lc = InMemoryLifecycle("1.0")
        result = lc.migrate("2.0")
        assert result.success is True
        assert result.from_version == "1.0"
        assert result.to_version == "2.0"
        assert lc.current_schema_version() == "2.0"

    def test_apply_retention(self):
        lc = InMemoryLifecycle()
        lc._records = list(range(10))
        purged = lc.apply_retention(RetentionPolicy(max_records=5))
        assert purged == 5
        assert len(lc._records) == 5

    def test_apply_retention_no_excess(self):
        lc = InMemoryLifecycle()
        lc._records = list(range(3))
        purged = lc.apply_retention(RetentionPolicy(max_records=10))
        assert purged == 0


# ── Policy / Constraint Model Tests ────────────────────────────────────


class TestRetentionPolicy:
    def test_defaults(self):
        policy = RetentionPolicy()
        assert policy.max_age_days == 0
        assert policy.max_records == 0
        assert policy.archive_after_days == 0
        assert policy.purge_on_archive is False

    def test_frozen(self):
        policy = RetentionPolicy(max_age_days=30)
        with pytest.raises(AttributeError):
            policy.max_age_days = 60  # type: ignore[misc]

    def test_custom_values(self):
        policy = RetentionPolicy(
            max_age_days=90, max_records=1000,
            archive_after_days=30, purge_on_archive=True,
        )
        assert policy.max_age_days == 90
        assert policy.max_records == 1000
        assert policy.archive_after_days == 30
        assert policy.purge_on_archive is True


class TestStorageConstraints:
    def test_defaults(self):
        sc = StorageConstraints()
        assert sc.max_record_size_bytes == 0
        assert sc.require_wal_mode is True
        assert sc.allowed_backends == ("sqlite", "memory")

    def test_frozen(self):
        sc = StorageConstraints()
        with pytest.raises(AttributeError):
            sc.require_wal_mode = False  # type: ignore[misc]


# ── Migration Model Tests ──────────────────────────────────────────────


class TestMigrationSpec:
    def test_creation(self):
        spec = MigrationSpec(
            migration_id="m-001",
            from_version="1.0",
            to_version="2.0",
            description="Add index",
        )
        assert spec.migration_id == "m-001"
        assert spec.reversible is True

    def test_frozen(self):
        spec = MigrationSpec(
            migration_id="m-001", from_version="1.0", to_version="2.0",
        )
        with pytest.raises(AttributeError):
            spec.to_version = "3.0"  # type: ignore[misc]


class TestMigrationResult:
    def test_success(self):
        result = MigrationResult(
            success=True, from_version="1.0", to_version="2.0",
            records_affected=42,
        )
        assert result.success is True
        assert result.records_affected == 42
        assert result.logs == ()

    def test_failure(self):
        result = MigrationResult(
            success=False, from_version="1.0", to_version="2.0",
            logs=("Error: table not found",),
        )
        assert result.success is False
        assert len(result.logs) == 1


# ── Index Strategy Tests ───────────────────────────────────────────────


class TestIndexStrategy:
    def test_defaults(self):
        idx = IndexStrategy(name="pk_index")
        assert idx.name == "pk_index"
        assert idx.target_fields == ()
        assert idx.index_type == "btree"
        assert idx.unique is False

    def test_custom_values(self):
        idx = IndexStrategy(
            name="user_email_idx",
            target_fields=("email",),
            index_type="hash",
            unique=True,
            description="Email uniqueness constraint",
        )
        assert idx.target_fields == ("email",)
        assert idx.unique is True

    def test_frozen(self):
        idx = IndexStrategy(name="x")
        with pytest.raises(AttributeError):
            idx.name = "y"  # type: ignore[misc]


# ── Data Schema Descriptor Tests ───────────────────────────────────────


class TestDataSchemaDescriptor:
    def test_creation(self):
        schema = DataSchemaDescriptor(
            schema_id="ds-001",
            name="GovernanceStorageSchema",
            fields=(
                DataFieldSpec(name="model_id", field_type="text"),
                DataFieldSpec(name="version", field_type="integer", required=False),
            ),
        )
        assert schema.schema_id == "ds-001"
        assert len(schema.fields) == 2
        assert schema.fields[0].name == "model_id"
        assert schema.fields[1].required is False

    def test_defaults(self):
        schema = DataSchemaDescriptor(schema_id="ds-002", name="test")
        assert schema.version == "1.0"
        assert schema.fields == ()
        assert schema.description == ""

    def test_field_defaults(self):
        f = DataFieldSpec(name="col1")
        assert f.field_type == "text"
        assert f.required is True
        assert f.description == ""

    def test_frozen(self):
        schema = DataSchemaDescriptor(schema_id="ds-001", name="test")
        with pytest.raises(AttributeError):
            schema.name = "changed"  # type: ignore[misc]
