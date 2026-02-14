"""Check schema/version drift for kernel governance databases."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import TypedDict


class DbSpec(TypedDict):
    schema: tuple[str, int]
    tables: tuple[str, ...]


EXPECTED_DB: dict[str, DbSpec] = {
    "rules.db": {
        "schema": ("schema_version", 1),
        "tables": ("rule_assets", "rule_asset_history"),
    },
    "decisions.db": {
        "schema": ("schema_version", 1),
        "tables": ("decision_records", "judgment_statistics"),
    },
    "versions.db": {
        "schema": ("schema_version", 1),
        "tables": ("corpus_versions", "version_entries"),
    },
    "profiles.db": {
        "schema": ("schema_info", 2),
        "tables": (
            "profile_versions",
            "profile_tags",
            "model_registry",
            "model_versions",
            "validation_runs",
        ),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check kernel governance DB drift.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("governance_data/default"),
        help="Directory containing rules.db/decisions.db/versions.db/profiles.db",
    )
    return parser.parse_args()


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    return {str(row[0]) for row in rows}


def _read_schema_version(db_path: Path, mode: str) -> int | None:
    with sqlite3.connect(str(db_path)) as conn:
        if mode == "schema_version":
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            return int(row[0]) if row and row[0] is not None else None
        if mode == "schema_info":
            row = conn.execute(
                "SELECT value FROM schema_info WHERE key='schema_version'"
            ).fetchone()
            if row is None or row[0] is None:
                return None
            try:
                return int(row[0])
            except ValueError:
                return None
    return None


def check_drift(data_dir: Path) -> list[str]:
    issues: list[str] = []

    for filename, spec in EXPECTED_DB.items():
        db_path = data_dir / filename
        if not db_path.exists():
            issues.append(f"missing-db:{filename}")
            continue

        tables = _table_names(db_path)
        schema_table, expected_version = spec["schema"]
        if schema_table not in tables:
            issues.append(f"missing-schema-table:{filename}:{schema_table}")
        else:
            version = _read_schema_version(db_path, schema_table)
            if version != expected_version:
                issues.append(
                    f"schema-version-mismatch:{filename}:expected={expected_version}:actual={version}"
                )

        for table in spec["tables"]:
            if table not in tables:
                issues.append(f"missing-table:{filename}:{table}")

    return issues


def main() -> int:
    args = parse_args()
    issues = check_drift(args.data_dir)
    if not issues:
        print(f"[ok] no drift detected in {args.data_dir}")
        return 0

    print(f"[fail] drift detected in {args.data_dir}")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
