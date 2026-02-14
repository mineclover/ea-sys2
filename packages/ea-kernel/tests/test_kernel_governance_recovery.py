from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest
from ea_kernel.migrations.kernel_governance import apply_kernel_governance_migrations


def _load_recovery_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ea_kernel"
        / "scripts"
        / "rehearse_kernel_governance_recovery.py"
    )
    spec = importlib.util.spec_from_file_location(
        "rehearse_kernel_governance_recovery",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rehearsal_recovers_from_schema_failure(tmp_path: Path):
    module = _load_recovery_module()
    data_dir = tmp_path / "governance_data"
    backup_dir = tmp_path / "backup"

    report = module.rehearse_recovery(data_dir, backup_dir)

    assert report.manifest_path.exists()
    assert any("missing-table:profiles.db:model_versions" in issue for issue in report.drift_issues_detected)
    assert module.drift_issues(data_dir) == []
    assert module.integrity_issues(data_dir) == []


def test_verify_manifest_detects_tampered_backup(tmp_path: Path):
    module = _load_recovery_module()
    data_dir = tmp_path / "governance_data"
    backup_dir = tmp_path / "backup"
    apply_kernel_governance_migrations(data_dir)

    module.backup_databases(data_dir, backup_dir)
    rules_backup = backup_dir / "rules.db"
    with rules_backup.open("ab") as file_obj:
        file_obj.write(b"\x00tampered")

    with pytest.raises(ValueError, match="checksum mismatch"):
        module.verify_backup_manifest(backup_dir)


def test_restore_recovers_from_partial_write_corruption(tmp_path: Path):
    module = _load_recovery_module()
    data_dir = tmp_path / "governance_data"
    backup_dir = tmp_path / "backup"
    apply_kernel_governance_migrations(data_dir)

    module.backup_databases(data_dir, backup_dir)
    profiles_db = data_dir / "profiles.db"
    profiles_db.write_bytes(b"not-a-sqlite-db")

    issues_before_restore = module.integrity_issues(data_dir)
    assert any(
        issue.startswith("integrity-error:profiles.db")
        or issue.startswith("integrity-fail:profiles.db")
        for issue in issues_before_restore
    )

    module.restore_databases(backup_dir, data_dir)
    assert module.integrity_issues(data_dir) == []
    assert module.drift_issues(data_dir) == []


def test_integrity_issues_reports_lock_contention(tmp_path: Path):
    module = _load_recovery_module()
    data_dir = tmp_path / "governance_data"
    apply_kernel_governance_migrations(data_dir)

    rules_db = data_dir / "rules.db"
    with sqlite3.connect(str(rules_db), timeout=0.1) as conn:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("INSERT OR IGNORE INTO schema_version(version) VALUES (1)")
        lock_issues = module.integrity_issues(data_dir, timeout=0.0)

    assert any("integrity-error:rules.db:database is locked" in issue for issue in lock_issues)
