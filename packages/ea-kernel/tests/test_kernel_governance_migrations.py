"""Tests for kernel governance migration runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ea_kernel.migrations.kernel_governance import (
    apply_kernel_governance_migrations,
    format_migration_plan,
    plan_kernel_governance_migrations,
)


def _table_exists(db_path: Path, table_name: str) -> bool:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
    return row is not None


def _read_schema_version(db_path: Path) -> int | None:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        return None
    return int(row[0])


def _read_profile_schema_version(db_path: Path) -> str | None:
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT value FROM schema_info WHERE key = 'schema_version'"
        ).fetchone()
    if row is None:
        return None
    return str(row[0])


def test_plan_reports_all_bootstrap_migrations(tmp_path: Path) -> None:
    data_dir = tmp_path / "governance_data"
    plan = plan_kernel_governance_migrations(data_dir)

    assert len(plan) == 5
    assert [item.target for item in plan].count("rules") == 1
    assert [item.target for item in plan].count("decisions") == 1
    assert [item.target for item in plan].count("versions") == 1
    assert [item.target for item in plan].count("profiles") == 2

    rendered = format_migration_plan(plan)
    assert "rules: v0 -> v1" in rendered
    assert "profiles: v0 -> v1" in rendered
    assert "profiles: v1 -> v2" in rendered


def test_dry_run_does_not_create_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "governance_data"
    planned = apply_kernel_governance_migrations(data_dir, dry_run=True)

    assert len(planned) == 5
    assert not data_dir.exists()


def test_apply_is_idempotent_and_creates_schema_metadata(tmp_path: Path) -> None:
    data_dir = tmp_path / "governance_data"
    first = apply_kernel_governance_migrations(data_dir)
    second = apply_kernel_governance_migrations(data_dir)

    assert len(first) == 5
    assert len(second) == 0

    rules_db = data_dir / "rules.db"
    decisions_db = data_dir / "decisions.db"
    versions_db = data_dir / "versions.db"
    profiles_db = data_dir / "profiles.db"

    assert rules_db.exists()
    assert decisions_db.exists()
    assert versions_db.exists()
    assert profiles_db.exists()

    assert _table_exists(rules_db, "schema_version")
    assert _table_exists(decisions_db, "schema_version")
    assert _table_exists(versions_db, "schema_version")
    assert _table_exists(profiles_db, "schema_info")
    assert _table_exists(profiles_db, "model_registry")
    assert _table_exists(profiles_db, "model_versions")
    assert _table_exists(profiles_db, "validation_runs")

    assert _read_schema_version(rules_db) == 1
    assert _read_schema_version(decisions_db) == 1
    assert _read_schema_version(versions_db) == 1
    assert _read_profile_schema_version(profiles_db) == "2"
