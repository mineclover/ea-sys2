"""Kernel model registration service.

K2 scope:
- Persistent registration metadata for independently validated models
- Atomic register -> validate transaction
- Explicit activation and re-validation workflow
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ea_kernel.profile_auditor import ProfileAuditor
from ea_kernel.profile_loader import load_profile
from ea_kernel.profile_serializer import compute_content_hash, dict_to_profile, profile_to_dict
from ea_kernel.profile_types import AuditResult, KernelProfile
from ea_kernel.types import KernelSchema


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ModelRegistrationError(Exception):
    """Raised when model registration contract is violated."""


@dataclass(frozen=True)
class ModelRegistryEntry:
    model_id: str
    model_name: str
    owner: str
    status: str
    active_version_id: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ModelVersionEntry:
    version_id: str
    model_id: str
    version: str
    content_hash: str
    parent_version_id: str | None
    created_by: str
    created_at: str


@dataclass(frozen=True)
class ValidationRunEntry:
    run_id: str
    model_id: str
    version_id: str
    validator: str
    passed: bool
    errors: tuple[dict[str, str], ...]
    context: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class RegistrationResult:
    model_id: str
    model_name: str
    version_id: str
    version: str
    validation_run_id: str


class KernelModelRegistrationService:
    """Persistent model registration/validation service."""

    __slots__ = ("_db_path", "_kernel", "_auditor")

    def __init__(self, db_path: str | Path, kernel: KernelSchema) -> None:
        self._db_path = Path(db_path)
        self._kernel = kernel
        self._auditor = ProfileAuditor(kernel)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_info (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_registry (
                    model_id           TEXT PRIMARY KEY,
                    model_name         TEXT NOT NULL UNIQUE,
                    owner              TEXT NOT NULL DEFAULT '',
                    status             TEXT NOT NULL DEFAULT 'registered'
                        CHECK (status IN ('registered', 'active', 'disabled')),
                    active_version_id  TEXT,
                    created_at         TEXT NOT NULL,
                    updated_at         TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS model_versions (
                    version_id         TEXT PRIMARY KEY,
                    model_id           TEXT NOT NULL REFERENCES model_registry(model_id) ON DELETE CASCADE,
                    version            TEXT NOT NULL,
                    content_hash       TEXT NOT NULL,
                    profile_data       TEXT NOT NULL,
                    parent_version_id  TEXT REFERENCES model_versions(version_id),
                    created_by         TEXT NOT NULL DEFAULT '',
                    created_at         TEXT NOT NULL,
                    UNIQUE(model_id, version)
                );

                CREATE TABLE IF NOT EXISTS validation_runs (
                    run_id          TEXT PRIMARY KEY,
                    model_id        TEXT NOT NULL REFERENCES model_registry(model_id) ON DELETE CASCADE,
                    version_id      TEXT NOT NULL REFERENCES model_versions(version_id) ON DELETE CASCADE,
                    validator       TEXT NOT NULL,
                    passed          INTEGER NOT NULL CHECK (passed IN (0, 1)),
                    errors_json     TEXT NOT NULL DEFAULT '[]',
                    context_json    TEXT NOT NULL DEFAULT '{}',
                    created_at      TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_mr_status
                    ON model_registry(status);
                CREATE INDEX IF NOT EXISTS idx_mv_model
                    ON model_versions(model_id);
                CREATE INDEX IF NOT EXISTS idx_mv_hash
                    ON model_versions(content_hash);
                CREATE INDEX IF NOT EXISTS idx_vr_model_version_created
                    ON validation_runs(model_id, version_id, created_at DESC);
                """
            )
            current = conn.execute(
                "SELECT value FROM schema_info WHERE key='schema_version'"
            ).fetchone()
            if current is None:
                conn.execute(
                    "INSERT INTO schema_info (key, value) VALUES ('schema_version', '2')"
                )
            else:
                try:
                    cur_val = int(current["value"])
                except ValueError:
                    cur_val = 0
                if cur_val < 2:
                    conn.execute(
                        "UPDATE schema_info SET value='2' WHERE key='schema_version'"
                    )
            conn.commit()

    def register_from_toml(
        self,
        path: Path,
        *,
        owner: str = "",
        created_by: str = "",
        context: dict[str, Any] | None = None,
    ) -> RegistrationResult:
        profile = load_profile(path, kernel=self._kernel)
        return self.register(profile, owner=owner, created_by=created_by, context=context)

    def register(
        self,
        profile: KernelProfile,
        *,
        owner: str = "",
        created_by: str = "",
        context: dict[str, Any] | None = None,
    ) -> RegistrationResult:
        now = _now_iso()
        model_name = profile.name
        content_hash = compute_content_hash(profile)
        profile_json = json.dumps(profile_to_dict(profile), sort_keys=True, ensure_ascii=False)
        context_json = json.dumps(context or {}, sort_keys=True, ensure_ascii=False)

        with self._connection() as conn:
            try:
                conn.execute("BEGIN")
                model_row = conn.execute(
                    "SELECT model_id FROM model_registry WHERE model_name = ?",
                    (model_name,),
                ).fetchone()

                if model_row is None:
                    model_id = uuid.uuid4().hex
                    conn.execute(
                        """
                        INSERT INTO model_registry (
                            model_id, model_name, owner, status,
                            active_version_id, created_at, updated_at
                        ) VALUES (?, ?, ?, 'registered', NULL, ?, ?)
                        """,
                        (model_id, model_name, owner, now, now),
                    )
                else:
                    model_id = str(model_row["model_id"])
                    conn.execute(
                        "UPDATE model_registry SET owner = ?, updated_at = ? WHERE model_id = ?",
                        (owner, now, model_id),
                    )

                parent_row = conn.execute(
                    """
                    SELECT version_id
                    FROM model_versions
                    WHERE model_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (model_id,),
                ).fetchone()
                parent_version_id = str(parent_row["version_id"]) if parent_row else None

                version_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO model_versions (
                        version_id, model_id, version, content_hash, profile_data,
                        parent_version_id, created_by, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        version_id,
                        model_id,
                        profile.version,
                        content_hash,
                        profile_json,
                        parent_version_id,
                        created_by,
                        now,
                    ),
                )

                audit_result = self._auditor.audit_profile(profile)
                validation_run_id = uuid.uuid4().hex
                conn.execute(
                    """
                    INSERT INTO validation_runs (
                        run_id, model_id, version_id, validator, passed,
                        errors_json, context_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        validation_run_id,
                        model_id,
                        version_id,
                        "profile_auditor",
                        1 if audit_result.passed else 0,
                        json.dumps(_audit_errors(audit_result), ensure_ascii=False, sort_keys=True),
                        context_json,
                        now,
                    ),
                )

                if not audit_result.passed:
                    raise ModelRegistrationError(
                        f"Validation failed for model '{model_name}' version '{profile.version}'"
                    )

                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                msg = str(exc)
                if "model_versions.model_id, model_versions.version" in msg:
                    raise ModelRegistrationError(
                        f"Model '{model_name}' version '{profile.version}' already exists"
                    ) from exc
                raise ModelRegistrationError(f"Registration failed: {msg}") from exc
            except ModelRegistrationError:
                conn.rollback()
                raise

        return RegistrationResult(
            model_id=model_id,
            model_name=model_name,
            version_id=version_id,
            version=profile.version,
            validation_run_id=validation_run_id,
        )

    def activate(
        self,
        model_name: str,
        version: str,
        *,
        actor: str = "",
    ) -> ModelRegistryEntry:
        now = _now_iso()
        with self._connection() as conn:
            conn.execute("BEGIN")
            row = conn.execute(
                """
                SELECT mr.model_id AS model_id, mv.version_id AS version_id
                FROM model_registry mr
                JOIN model_versions mv ON mv.model_id = mr.model_id
                WHERE mr.model_name = ? AND mv.version = ?
                """,
                (model_name, version),
            ).fetchone()
            if row is None:
                conn.rollback()
                raise ModelRegistrationError(
                    f"Model '{model_name}' version '{version}' not found"
                )

            model_id = str(row["model_id"])
            version_id = str(row["version_id"])
            validated = conn.execute(
                """
                SELECT passed
                FROM validation_runs
                WHERE model_id = ? AND version_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (model_id, version_id),
            ).fetchone()
            if validated is None or int(validated["passed"]) != 1:
                conn.rollback()
                raise ModelRegistrationError(
                    f"Cannot activate unvalidated model '{model_name}' version '{version}'"
                )

            owner_update = actor if actor else conn.execute(
                "SELECT owner FROM model_registry WHERE model_id = ?",
                (model_id,),
            ).fetchone()["owner"]
            conn.execute(
                """
                UPDATE model_registry
                SET status = 'active', active_version_id = ?, owner = ?, updated_at = ?
                WHERE model_id = ?
                """,
                (version_id, owner_update, now, model_id),
            )
            conn.commit()

        model = self.get_model(model_name)
        if model is None:
            raise ModelRegistrationError(f"Model '{model_name}' not found after activate")
        return model

    def validate_registered(
        self,
        model_name: str,
        version: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> ValidationRunEntry:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT mr.model_id AS model_id, mv.version_id AS version_id, mv.profile_data AS profile_data
                FROM model_registry mr
                JOIN model_versions mv ON mv.model_id = mr.model_id
                WHERE mr.model_name = ? AND mv.version = ?
                """,
                (model_name, version),
            ).fetchone()
            if row is None:
                raise ModelRegistrationError(
                    f"Model '{model_name}' version '{version}' not found"
                )

            model_id = str(row["model_id"])
            version_id = str(row["version_id"])
            profile_data = json.loads(str(row["profile_data"]))
            profile = dict_to_profile(profile_data)
            audit_result = self._auditor.audit_profile(profile)

            run_id = uuid.uuid4().hex
            now = _now_iso()
            errors = _audit_errors(audit_result)
            context_obj = context or {}

            conn.execute(
                """
                INSERT INTO validation_runs (
                    run_id, model_id, version_id, validator, passed,
                    errors_json, context_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    model_id,
                    version_id,
                    "profile_auditor",
                    1 if audit_result.passed else 0,
                    json.dumps(errors, ensure_ascii=False, sort_keys=True),
                    json.dumps(context_obj, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
            conn.commit()

        return ValidationRunEntry(
            run_id=run_id,
            model_id=model_id,
            version_id=version_id,
            validator="profile_auditor",
            passed=audit_result.passed,
            errors=tuple(errors),
            context=context_obj,
            created_at=now,
        )

    def get_model(self, model_name: str) -> ModelRegistryEntry | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT model_id, model_name, owner, status, active_version_id, created_at, updated_at
                FROM model_registry
                WHERE model_name = ?
                """,
                (model_name,),
            ).fetchone()
        return _row_to_model(row) if row is not None else None

    def list_versions(self, model_name: str) -> tuple[ModelVersionEntry, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT mv.version_id, mv.model_id, mv.version, mv.content_hash,
                       mv.parent_version_id, mv.created_by, mv.created_at
                FROM model_versions mv
                JOIN model_registry mr ON mv.model_id = mr.model_id
                WHERE mr.model_name = ?
                ORDER BY mv.created_at
                """,
                (model_name,),
            ).fetchall()
        return tuple(_row_to_model_version(r) for r in rows)

    def list_validation_runs(
        self,
        *,
        model_name: str | None = None,
        version_id: str | None = None,
        limit: int = 100,
    ) -> tuple[ValidationRunEntry, ...]:
        query = """
            SELECT vr.run_id, vr.model_id, vr.version_id, vr.validator, vr.passed,
                   vr.errors_json, vr.context_json, vr.created_at
            FROM validation_runs vr
            JOIN model_registry mr ON vr.model_id = mr.model_id
        """
        params: list[str | int] = []
        conditions: list[str] = []
        if model_name:
            conditions.append("mr.model_name = ?")
            params.append(model_name)
        if version_id:
            conditions.append("vr.version_id = ?")
            params.append(version_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY vr.created_at DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return tuple(_row_to_validation_run(r) for r in rows)


def _audit_errors(result: AuditResult) -> list[dict[str, str]]:
    return [
        {
            "severity": finding.severity.value,
            "category": finding.category,
            "message": finding.message,
            "rule_id": finding.rule_id,
        }
        for finding in result.findings
    ]


def _row_to_model(row: sqlite3.Row) -> ModelRegistryEntry:
    active = row["active_version_id"]
    return ModelRegistryEntry(
        model_id=str(row["model_id"]),
        model_name=str(row["model_name"]),
        owner=str(row["owner"]),
        status=str(row["status"]),
        active_version_id=str(active) if active else None,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _row_to_model_version(row: sqlite3.Row) -> ModelVersionEntry:
    parent = row["parent_version_id"]
    return ModelVersionEntry(
        version_id=str(row["version_id"]),
        model_id=str(row["model_id"]),
        version=str(row["version"]),
        content_hash=str(row["content_hash"]),
        parent_version_id=str(parent) if parent else None,
        created_by=str(row["created_by"]),
        created_at=str(row["created_at"]),
    )


def _row_to_validation_run(row: sqlite3.Row) -> ValidationRunEntry:
    errors_obj = json.loads(str(row["errors_json"]))
    context_obj = json.loads(str(row["context_json"]))
    return ValidationRunEntry(
        run_id=str(row["run_id"]),
        model_id=str(row["model_id"]),
        version_id=str(row["version_id"]),
        validator=str(row["validator"]),
        passed=bool(row["passed"]),
        errors=tuple(errors_obj),
        context=context_obj,
        created_at=str(row["created_at"]),
    )

