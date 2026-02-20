"""Infra storage port contracts — runtime interfaces for 00-infra.toml elements.

Defines Protocol-based contracts for the storage concepts declared in the
infra profile.  Uses structural typing so that existing stores across
packages (ea-kernel, ea-decision, ea-flow, etc.) conform without
explicit inheritance.

Zero external dependencies — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ── Core Storage Ports ─────────────────────────────────────────────────


@runtime_checkable
class StoragePort(Protocol):
    """Row-data storage port — generic CRUD contract.

    Maps to ``storage_port`` entity in 00-infra.toml.
    Any store that exposes store/get/query/count satisfies this protocol.
    """

    def store(self, record: Any) -> Any: ...

    def get(self, storage_id: str) -> Any | None: ...

    def query(self, options: Any = None) -> list: ...

    def count(self, options: Any = None) -> int: ...


@runtime_checkable
class EventStoragePort(Protocol):
    """Append-only event storage port — immutable audit trail.

    Maps to ``event_storage_port`` entity in 00-infra.toml.
    Append-only semantics: events are never updated or deleted.
    """

    def append(self, event: Any) -> str: ...

    def read(self, *, after: str | None = None, limit: int = 100) -> list: ...

    def count(self) -> int: ...


@runtime_checkable
class ProfileStoragePort(Protocol):
    """Profile/model version storage port.

    Maps to ``ProfileStoragePort`` element in 00-infra.toml.
    Extends the generic storage contract with version-aware lookups.
    """

    def store(self, record: Any) -> Any: ...

    def get(self, storage_id: str) -> Any | None: ...

    def query(self, options: Any = None) -> list: ...

    def count(self, options: Any = None) -> int: ...

    def get_latest(self, profile_name: str) -> Any | None: ...

    def list_versions(self, profile_name: str) -> list: ...


# ── Storage Policy Models ──────────────────────────────────────────────


@dataclass(frozen=True)
class RetentionPolicy:
    """Data retention and archival constraints.

    Maps to ``retention_policy`` entity in 00-infra.toml.
    Zero values mean unlimited / disabled.
    """

    max_age_days: int = 0
    max_records: int = 0
    archive_after_days: int = 0
    purge_on_archive: bool = False


@dataclass(frozen=True)
class StorageConstraints:
    """Physical storage constraints for a storage backend.

    Maps to ``storage_policy`` entity in 00-infra.toml.
    """

    max_record_size_bytes: int = 0
    require_wal_mode: bool = True
    allowed_backends: tuple[str, ...] = ("sqlite", "memory")


# ── Schema Migration ───────────────────────────────────────────────────


@dataclass(frozen=True)
class MigrationSpec:
    """Definition for a schema migration step.

    Maps to ``data_migration`` entity in 00-infra.toml.
    """

    migration_id: str
    from_version: str
    to_version: str
    description: str = ""
    reversible: bool = True


@dataclass(frozen=True)
class MigrationResult:
    """Outcome of a schema migration execution."""

    success: bool
    from_version: str
    to_version: str
    records_affected: int = 0
    logs: tuple[str, ...] = ()


# ── Storage Lifecycle ──────────────────────────────────────────────────


@runtime_checkable
class StorageLifecyclePort(Protocol):
    """Schema lifecycle management contract.

    Maps to ``storage_lifecycle_service`` entity in 00-infra.toml.
    Covers schema versioning, migration, and retention enforcement.
    """

    def current_schema_version(self) -> str: ...

    def migrate(self, target_version: str) -> MigrationResult: ...

    def apply_retention(self, policy: RetentionPolicy) -> int: ...


# ── Index Strategy ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class IndexStrategy:
    """Index strategy definition for data access optimization.

    Maps to ``index_strategy`` entity in 00-infra.toml.
    """

    name: str
    target_fields: tuple[str, ...] = ()
    index_type: str = "btree"
    unique: bool = False
    description: str = ""


# ── Data Schema Descriptor ────────────────────────────────────────────


@dataclass(frozen=True)
class DataFieldSpec:
    """A single field within a DataSchemaDescriptor."""

    name: str
    field_type: str = "text"
    required: bool = True
    description: str = ""


@dataclass(frozen=True)
class DataSchemaDescriptor:
    """Describes the data shape for cross-layer integration.

    Maps to ``data_schema`` entity in 00-infra.toml.
    Captures the fields, types, and constraints of a storage schema
    without binding to a specific implementation.
    """

    schema_id: str
    name: str
    version: str = "1.0"
    fields: tuple[DataFieldSpec, ...] = ()
    description: str = ""
