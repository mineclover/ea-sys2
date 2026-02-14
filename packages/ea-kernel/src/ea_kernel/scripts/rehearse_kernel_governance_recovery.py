"""Rehearse kernel governance DB backup/restore recovery flow.

The rehearsal sequence is:
1) bootstrap kernel governance databases (optional),
2) backup with checksum manifest,
3) inject schema failure,
4) verify drift is detected,
5) restore from backup,
6) verify drift and integrity are clean.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import cast

from ea_kernel.migrations.kernel_governance import apply_kernel_governance_migrations

KERNEL_GOVERNANCE_DB_FILES: tuple[str, ...] = (
    "rules.db",
    "decisions.db",
    "versions.db",
    "profiles.db",
)
MANIFEST_FILENAME = "checksums.sha256.json"


@dataclass(frozen=True)
class RecoveryRehearsalReport:
    data_dir: Path
    backup_dir: Path
    manifest_path: Path
    drift_issues_detected: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rehearse kernel governance DB backup/restore recovery.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("governance_data/default"),
        help="Directory containing rules/decisions/versions/profiles DB files.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Backup directory (default: <data_dir>.backup.rehearsal).",
    )
    parser.add_argument(
        "--skip-seed",
        action="store_true",
        help="Skip schema bootstrap; operate on existing DB files only.",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar_paths(db_path: Path) -> tuple[Path, Path, Path]:
    return (
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
        Path(f"{db_path}-journal"),
    )


def _remove_sidecar_files(db_path: Path) -> None:
    for sidecar in _sidecar_paths(db_path):
        if sidecar.exists():
            sidecar.unlink()


def _snapshot_sqlite_db(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    with (
        sqlite3.connect(str(src), timeout=1.0) as src_conn,
        sqlite3.connect(str(dst), timeout=1.0) as dst_conn,
    ):
        src_conn.backup(dst_conn)
        dst_conn.commit()


def _load_drift_module() -> ModuleType:
    script_path = Path(__file__).with_name("check_kernel_governance_drift.py")
    spec = importlib.util.spec_from_file_location("check_kernel_governance_drift", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load drift checker: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_drift_checker() -> Callable[[Path], list[str]]:
    module = _load_drift_module()
    checker = getattr(module, "check_drift", None)
    if not callable(checker):
        raise RuntimeError("Drift checker module has no callable check_drift")
    return cast(Callable[[Path], list[str]], checker)


def drift_issues(data_dir: Path) -> list[str]:
    return _load_drift_checker()(data_dir)


def backup_databases(data_dir: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)

    checksums: dict[str, str] = {}
    for filename in KERNEL_GOVERNANCE_DB_FILES:
        src = data_dir / filename
        if not src.exists():
            raise FileNotFoundError(f"missing-db:{filename}")
        dst = backup_dir / filename
        _remove_sidecar_files(dst)
        _snapshot_sqlite_db(src, dst)
        checksums[filename] = _sha256(dst)

    manifest_path = backup_dir / MANIFEST_FILENAME
    manifest_content = {"files": checksums}
    manifest_path.write_text(
        json.dumps(manifest_content, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def verify_backup_manifest(backup_dir: Path) -> dict[str, str]:
    manifest_path = backup_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing-manifest:{manifest_path}")

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    files_obj = raw.get("files") if isinstance(raw, dict) else None
    if not isinstance(files_obj, dict) or not files_obj:
        raise ValueError("invalid-manifest:files")

    checksums: dict[str, str] = {}
    for filename, expected_hash in files_obj.items():
        if not isinstance(filename, str) or not isinstance(expected_hash, str):
            raise ValueError("invalid-manifest-entry")
        db_path = backup_dir / filename
        if not db_path.exists():
            raise FileNotFoundError(f"missing-backup-db:{filename}")
        actual_hash = _sha256(db_path)
        if actual_hash != expected_hash:
            raise ValueError(
                f"checksum mismatch for {filename}: expected={expected_hash} actual={actual_hash}"
            )
        checksums[filename] = actual_hash

    return checksums


def restore_databases(backup_dir: Path, data_dir: Path) -> None:
    checksums = verify_backup_manifest(backup_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in checksums:
        src = backup_dir / filename
        dst = data_dir / filename
        tmp = dst.with_suffix(f"{dst.suffix}.restore.tmp")
        _remove_sidecar_files(dst)
        _snapshot_sqlite_db(src, tmp)
        tmp.replace(dst)
        _remove_sidecar_files(dst)


def integrity_issues(data_dir: Path, *, timeout: float = 0.1) -> list[str]:
    issues: list[str] = []
    for filename in KERNEL_GOVERNANCE_DB_FILES:
        db_path = data_dir / filename
        if not db_path.exists():
            issues.append(f"missing-db:{filename}")
            continue

        try:
            with sqlite3.connect(str(db_path), timeout=timeout) as conn:
                row = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            issues.append(f"integrity-error:{filename}:{exc}")
            continue

        result = None if row is None else row[0]
        if result != "ok":
            issues.append(f"integrity-fail:{filename}:{result}")
    return issues


def inject_failure_drop_model_versions(data_dir: Path) -> None:
    profiles_db = data_dir / "profiles.db"
    with sqlite3.connect(str(profiles_db)) as conn:
        conn.execute("DROP TABLE model_versions")
        conn.commit()


def rehearse_recovery(
    data_dir: Path,
    backup_dir: Path,
    *,
    seed: bool = True,
) -> RecoveryRehearsalReport:
    if seed:
        apply_kernel_governance_migrations(data_dir)

    manifest_path = backup_databases(data_dir, backup_dir)
    verify_backup_manifest(backup_dir)

    inject_failure_drop_model_versions(data_dir)
    detected = tuple(drift_issues(data_dir))
    if not detected:
        raise RuntimeError("failure injection did not produce drift")

    restore_databases(backup_dir, data_dir)

    drift_after_restore = drift_issues(data_dir)
    if drift_after_restore:
        raise RuntimeError(f"drift remains after restore: {drift_after_restore}")

    integrity_after_restore = integrity_issues(data_dir)
    if integrity_after_restore:
        raise RuntimeError(f"integrity check failed after restore: {integrity_after_restore}")

    return RecoveryRehearsalReport(
        data_dir=data_dir,
        backup_dir=backup_dir,
        manifest_path=manifest_path,
        drift_issues_detected=detected,
    )


def main() -> int:
    args = parse_args()
    data_dir = args.data_dir
    backup_dir = args.backup_dir or Path(f"{data_dir}.backup.rehearsal")

    report = rehearse_recovery(data_dir, backup_dir, seed=not args.skip_seed)
    print(f"[ok] backup+restore rehearsal succeeded for {report.data_dir}")
    print(f"backup_dir={report.backup_dir}")
    print(f"manifest={report.manifest_path}")
    print(f"detected_drift={len(report.drift_issues_detected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
