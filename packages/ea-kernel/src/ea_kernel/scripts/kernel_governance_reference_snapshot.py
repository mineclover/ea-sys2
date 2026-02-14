"""Build and verify kernel governance DB v1 reference snapshot.

K5 scope:
- seed canonical reference dataset (Ralph TUI layer profiles),
- produce stable golden snapshot JSON,
- verify runtime DB state against the snapshot contract.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ea_kernel.migrations.kernel_governance import apply_kernel_governance_migrations
from ea_kernel.model_registration import KernelModelRegistrationService
from ea_kernel.profile_loader import load_profile
from ea_kernel.profile_rule_compiler import (
    ProfileRuntimeSchemaResult,
    build_profile_runtime_schema,
)
from ea_kernel.profile_serializer import compute_content_hash
from ea_kernel.profile_types import KernelProfile
from ea_kernel.spec import KERNEL_SPEC

LAYER_FILE_MAP: dict[str, str] = {
    "infra": "00-infra.toml",
    "governance": "10-governance.toml",
    "decision": "20-decision.toml",
    "needs": "30-needs.toml",
    "kernel": "40-kernel.toml",
    "flow": "50-flow.toml",
}
LAYERS_IN_ORDER: tuple[str, ...] = ("infra", "governance", "decision", "needs", "kernel", "flow")

DB_TABLES: dict[str, tuple[str, ...]] = {
    "rules.db": ("schema_version", "rule_assets", "rule_asset_history"),
    "decisions.db": ("schema_version", "decision_records", "judgment_statistics"),
    "versions.db": ("schema_version", "corpus_versions", "version_entries"),
    "profiles.db": (
        "schema_info",
        "profile_versions",
        "profile_tags",
        "model_registry",
        "model_versions",
        "validation_runs",
    ),
}

REFERENCE_VERSION = "1.0.0"
SCRIPT_NAME = "kernel_governance_reference_snapshot.py"
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
LAYER_DIR = PACKAGE_ROOT / "examples" / "ralph_tui_layers"
DEFAULT_SNAPSHOT_PATH = (
    PACKAGE_ROOT
    / "docs"
    / "reference"
    / "kernel_governance_reference_v1.snapshot.json"
)
DATA_DIR_DEFAULT = Path("governance_data/reference_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build/verify kernel governance reference snapshot.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build_p = sub.add_parser("build", help="Build reference dataset and snapshot JSON")
    build_p.add_argument("--data-dir", type=Path, default=DATA_DIR_DEFAULT)
    build_p.add_argument("--snapshot-path", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    build_p.add_argument("--owner", default="kernel-reference")
    build_p.add_argument("--actor", default="reference-builder")
    build_p.add_argument(
        "--force-reset",
        action="store_true",
        help="Remove existing governance DB files before build.",
    )

    verify_p = sub.add_parser("verify", help="Verify dataset matches snapshot JSON")
    verify_p.add_argument("--data-dir", type=Path, default=DATA_DIR_DEFAULT)
    verify_p.add_argument("--snapshot-path", type=Path, default=DEFAULT_SNAPSHOT_PATH)

    return parser.parse_args()


def _profile_with_name(profile: KernelProfile, model_name: str) -> KernelProfile:
    if profile.name == model_name:
        return profile
    return KernelProfile(
        name=model_name,
        version=profile.version,
        kernel_version=profile.kernel_version,
        elements=profile.elements,
        relations=profile.relations,
        validity_rules=profile.validity_rules,
        metadata=profile.metadata,
    )


def _model_name(profile_name: str, layer: str) -> str:
    return f"{profile_name}.{layer}"


@dataclass(frozen=True)
class LayerProjection:
    layer: str
    profile_path: Path
    profile: KernelProfile
    runtime: ProfileRuntimeSchemaResult


def _build_runtime_projection(profile: KernelProfile) -> ProfileRuntimeSchemaResult:
    return build_profile_runtime_schema(
        KERNEL_SPEC,
        profile,
        include_base_schema=True,
        include_base_rules=True,
    )


def _prepare_layer_projections() -> tuple[LayerProjection, ...]:
    projections: list[LayerProjection] = []
    for layer in LAYERS_IN_ORDER:
        profile_path = LAYER_DIR / LAYER_FILE_MAP[layer]
        profile = load_profile(profile_path, KERNEL_SPEC)
        adjusted = _profile_with_name(profile, _model_name(profile.name, layer))
        projections.append(
            LayerProjection(
                layer=layer,
                profile_path=profile_path,
                profile=adjusted,
                runtime=_build_runtime_projection(adjusted),
            )
        )
    return tuple(projections)


def _runtime_projection_payload(runtime: ProfileRuntimeSchemaResult) -> dict[str, int]:
    stats = runtime.compilation.stats
    return {
        "runtime_entities": len(runtime.schema.entities),
        "runtime_relations": len(runtime.schema.relations),
        "runtime_rules": len(runtime.schema.validity_rules),
        "runtime_added_entities": runtime.overlay.added_entity_count,
        "runtime_added_relations": runtime.overlay.added_relation_count,
        "compiled_rules": stats.compiled_rule_count,
        "compiled_transformed_rules": stats.transformed_rule_count,
        "compiled_skipped_rules": stats.skipped_rule_count,
    }


def _seed_profile_manifest(
    projections: tuple[LayerProjection, ...] | None = None,
) -> list[dict[str, Any]]:
    layer_projections = projections or _prepare_layer_projections()
    manifest: list[dict[str, Any]] = []
    for projection in layer_projections:
        profile_path = projection.profile_path
        adjusted = projection.profile
        runtime = projection.runtime
        manifest.append(
            {
                "layer": projection.layer,
                "file": profile_path.name,
                "model_name": adjusted.name,
                "version": adjusted.version,
                "elements": len(adjusted.elements),
                "relations": len(adjusted.relations),
                "rules": len(adjusted.validity_rules),
                "content_hash": compute_content_hash(adjusted),
                **_runtime_projection_payload(runtime),
            }
        )
    return manifest


def _remove_if_exists(path: Path) -> None:
    if path.exists():
        path.unlink()


def _db_sidecars(db_path: Path) -> tuple[Path, Path, Path]:
    return (
        Path(f"{db_path}-wal"),
        Path(f"{db_path}-shm"),
        Path(f"{db_path}-journal"),
    )


def _reset_data_dir(data_dir: Path) -> None:
    for db_name in DB_TABLES:
        db_path = data_dir / db_name
        _remove_if_exists(db_path)
        for sidecar in _db_sidecars(db_path):
            _remove_if_exists(sidecar)


def _ensure_empty_data_dir(data_dir: Path) -> None:
    existing = [db_name for db_name in DB_TABLES if (data_dir / db_name).exists()]
    if existing:
        joined = ", ".join(existing)
        raise RuntimeError(
            f"data_dir is not empty for reference build: {data_dir} (existing: {joined}). "
            "Use --force-reset to rebuild."
        )


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = sorted(str(row[0]) for row in rows if not str(row[0]).startswith("sqlite_"))
    return names


def _row_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    if row is None:
        return 0
    return int(row[0])


def _read_schema_version(conn: sqlite3.Connection, table_names: list[str]) -> int:
    tables = set(table_names)
    if "schema_version" in tables:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        if row is None or row[0] is None:
            return 0
        return int(row[0])
    if "schema_info" in tables:
        row = conn.execute(
            "SELECT value FROM schema_info WHERE key='schema_version'"
        ).fetchone()
        if row is None or row[0] is None:
            return 0
        try:
            return int(row[0])
        except ValueError:
            return 0
    return 0


def _collect_db_contract(data_dir: Path) -> dict[str, dict[str, Any]]:
    contract: dict[str, dict[str, Any]] = {}
    for db_name, required_tables in DB_TABLES.items():
        db_path = data_dir / db_name
        with sqlite3.connect(str(db_path)) as conn:
            table_names = _table_names(conn)
            row_counts = {table: _row_count(conn, table) for table in required_tables}
            contract[db_name] = {
                "schema_version": _read_schema_version(conn, table_names),
                "tables": table_names,
                "required_tables": list(required_tables),
                "row_counts": row_counts,
            }
    return contract


def _collect_model_registry_summary(data_dir: Path) -> list[dict[str, Any]]:
    profiles_db = data_dir / "profiles.db"
    with sqlite3.connect(str(profiles_db)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                mr.model_name AS model_name,
                mr.status AS status,
                mv.version AS version,
                COUNT(vr.run_id) AS validation_runs
            FROM model_registry mr
            JOIN model_versions mv ON mv.model_id = mr.model_id
            LEFT JOIN validation_runs vr
                ON vr.model_id = mr.model_id
               AND vr.version_id = mv.version_id
            GROUP BY mr.model_name, mr.status, mv.version
            ORDER BY mr.model_name ASC
            """
        ).fetchall()

    return [
        {
            "model_name": str(row["model_name"]),
            "status": str(row["status"]),
            "version": str(row["version"]),
            "validation_runs": int(row["validation_runs"]),
        }
        for row in rows
    ]


def _collect_active_models(data_dir: Path) -> list[str]:
    profiles_db = data_dir / "profiles.db"
    with sqlite3.connect(str(profiles_db)) as conn:
        rows = conn.execute(
            """
            SELECT model_name
            FROM model_registry
            WHERE status = 'active'
            ORDER BY model_name ASC
            """
        ).fetchall()
    return [str(row[0]) for row in rows]


def _seed_reference_dataset(
    data_dir: Path,
    *,
    owner: str,
    actor: str,
    projections: tuple[LayerProjection, ...] | None = None,
) -> None:
    apply_kernel_governance_migrations(data_dir)
    service = KernelModelRegistrationService(data_dir / "profiles.db", KERNEL_SPEC)
    layer_projections = projections or _prepare_layer_projections()

    kernel_model_name = ""
    kernel_version = ""

    for projection in layer_projections:
        profile_path = projection.profile_path
        adjusted = projection.profile
        runtime = projection.runtime
        stats = runtime.compilation.stats
        if stats.skipped_rule_count > 0:
            raise RuntimeError(
                f"runtime projection skipped rules for {adjusted.name}: {stats.skipped_rule_count}"
            )
        service.register(
            adjusted,
            owner=owner,
            created_by=actor,
            context={
                "source": "kernel-governance-reference-snapshot",
                "layer": projection.layer,
                "profile_file": profile_path.name,
                "compiled_rules": stats.compiled_rule_count,
                "compiled_transformed_rules": stats.transformed_rule_count,
                "compiled_skipped_rules": stats.skipped_rule_count,
            },
        )
        if projection.layer == "kernel":
            kernel_model_name = adjusted.name
            kernel_version = adjusted.version
            service.activate(adjusted.name, adjusted.version, actor=actor)

    # explicit independent re-validation pass (independent verification contract)
    service.validate_registered(
        kernel_model_name,
        kernel_version,
        context={
            "source": "kernel-governance-reference-snapshot",
            "mode": "independent_revalidation",
        },
    )


def _build_payload(
    data_dir: Path,
    *,
    projections: tuple[LayerProjection, ...] | None = None,
) -> dict[str, Any]:
    return {
        "reference_version": REFERENCE_VERSION,
        "snapshot_kind": "kernel_governance_db_reference",
        "generated_by": SCRIPT_NAME,
        "seed_profiles": _seed_profile_manifest(projections),
        "db_contract": _collect_db_contract(data_dir),
        "model_registry": _collect_model_registry_summary(data_dir),
        "active_models": _collect_active_models(data_dir),
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid snapshot payload: {path}")
    return raw


def _diff(expected: Any, actual: Any, path: str = "root") -> list[str]:
    if type(expected) is not type(actual):
        return [f"{path}: type mismatch expected={type(expected).__name__} actual={type(actual).__name__}"]

    if isinstance(expected, dict):
        dict_issues: list[str] = []
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            dict_issues.append(f"{path}.{key}: missing in actual")
        for key in sorted(actual_keys - expected_keys):
            dict_issues.append(f"{path}.{key}: unexpected key in actual")
        for key in sorted(expected_keys & actual_keys):
            dict_issues.extend(_diff(expected[key], actual[key], f"{path}.{key}"))
        return dict_issues

    if isinstance(expected, list):
        list_issues: list[str] = []
        if len(expected) != len(actual):
            list_issues.append(f"{path}: length mismatch expected={len(expected)} actual={len(actual)}")
            return list_issues
        for idx, (lhs, rhs) in enumerate(zip(expected, actual, strict=True)):
            list_issues.extend(_diff(lhs, rhs, f"{path}[{idx}]"))
        return list_issues

    if expected != actual:
        return [f"{path}: expected={expected!r} actual={actual!r}"]
    return []


def build_reference_snapshot(
    data_dir: Path,
    snapshot_path: Path,
    *,
    owner: str = "kernel-reference",
    actor: str = "reference-builder",
    force_reset: bool = False,
) -> dict[str, Any]:
    data_dir.mkdir(parents=True, exist_ok=True)
    if force_reset:
        _reset_data_dir(data_dir)
    _ensure_empty_data_dir(data_dir)

    projections = _prepare_layer_projections()
    _seed_reference_dataset(
        data_dir,
        owner=owner,
        actor=actor,
        projections=projections,
    )
    payload = _build_payload(data_dir, projections=projections)
    _write_json(snapshot_path, payload)
    return payload


def verify_reference_snapshot(data_dir: Path, snapshot_path: Path) -> list[str]:
    if not snapshot_path.exists():
        return [f"snapshot file not found: {snapshot_path}"]
    expected = _load_json(snapshot_path)
    actual = _build_payload(data_dir)
    return _diff(expected, actual)


def main() -> int:
    args = parse_args()
    if args.command == "build":
        payload = build_reference_snapshot(
            args.data_dir,
            args.snapshot_path,
            owner=args.owner,
            actor=args.actor,
            force_reset=args.force_reset,
        )
        print(f"[ok] built reference snapshot: {args.snapshot_path}")
        print(f"models={len(payload['model_registry'])} active={len(payload['active_models'])}")
        return 0

    if args.command == "verify":
        issues = verify_reference_snapshot(args.data_dir, args.snapshot_path)
        if not issues:
            print(f"[ok] reference snapshot matches: {args.snapshot_path}")
            return 0

        print(f"[fail] reference snapshot mismatch: {args.snapshot_path}")
        for issue in issues[:30]:
            print(f"- {issue}")
        if len(issues) > 30:
            print(f"- ... {len(issues) - 30} more")
        return 1

    raise RuntimeError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
