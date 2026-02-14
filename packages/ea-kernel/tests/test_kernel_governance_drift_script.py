from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

from ea_kernel.migrations.kernel_governance import apply_kernel_governance_migrations


def _load_script_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ea_kernel"
        / "scripts"
        / "check_kernel_governance_drift.py"
    )
    spec = importlib.util.spec_from_file_location("check_kernel_governance_drift", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_check_drift_no_issue_after_migration(tmp_path: Path):
    module = _load_script_module()
    data_dir = tmp_path / "governance_data"
    apply_kernel_governance_migrations(data_dir)

    issues = module.check_drift(data_dir)
    assert issues == []


def test_check_drift_detects_missing_table(tmp_path: Path):
    module = _load_script_module()
    data_dir = tmp_path / "governance_data"
    apply_kernel_governance_migrations(data_dir)

    profiles_db = data_dir / "profiles.db"
    with sqlite3.connect(str(profiles_db)) as conn:
        conn.execute("DROP TABLE model_versions")
        conn.commit()

    issues = module.check_drift(data_dir)
    assert any("missing-table:profiles.db:model_versions" in issue for issue in issues)


def test_check_drift_detects_schema_version_mismatch(tmp_path: Path):
    module = _load_script_module()
    data_dir = tmp_path / "governance_data"
    apply_kernel_governance_migrations(data_dir)

    profiles_db = data_dir / "profiles.db"
    with sqlite3.connect(str(profiles_db)) as conn:
        conn.execute(
            "UPDATE schema_info SET value='1' WHERE key='schema_version'"
        )
        conn.commit()

    issues = module.check_drift(data_dir)
    assert any("schema-version-mismatch:profiles.db" in issue for issue in issues)

