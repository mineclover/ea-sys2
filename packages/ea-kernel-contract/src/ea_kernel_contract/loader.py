"""Load and validate ea-kernel contract snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ea_kernel_contract.types import (
    ContractBundle,
    ContractPaths,
    JsonObject,
)

ENV_CONTRACT_DIR = "EA_KERNEL_CONTRACT_DIR"

SCHEMA_FILE = "kernel_schema.snapshot.json"
RULES_FILE = "kernel_rules.snapshot.json"
VECTORS_FILE = "kernel_judgment_vectors.snapshot.json"


def default_contract_dir() -> Path:
    """Resolve default snapshot directory.

    Resolution order:
    1) EA_KERNEL_CONTRACT_DIR (environment override)
    2) monorepo default: packages/ea-kernel/docs/reference/contracts
    """
    from_env = os.getenv(ENV_CONTRACT_DIR)
    if from_env:
        return Path(from_env).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[4]
    return (repo_root / "packages" / "ea-kernel" / "docs" / "reference" / "contracts").resolve()


def resolve_contract_paths(contract_dir: Path | None = None) -> ContractPaths:
    """Resolve snapshot file paths for a contract directory."""
    base = (contract_dir or default_contract_dir()).resolve()
    return ContractPaths(
        contract_dir=base,
        schema_path=base / SCHEMA_FILE,
        rules_path=base / RULES_FILE,
        vectors_path=base / VECTORS_FILE,
    )


def _load_json(path: Path) -> JsonObject:
    if not path.exists():
        raise FileNotFoundError(f"contract snapshot not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid contract snapshot payload: {path}")
    return raw


def load_schema_snapshot(contract_dir: Path | None = None) -> JsonObject:
    paths = resolve_contract_paths(contract_dir)
    return _load_json(paths.schema_path)


def load_rules_snapshot(contract_dir: Path | None = None) -> JsonObject:
    paths = resolve_contract_paths(contract_dir)
    return _load_json(paths.rules_path)


def load_vectors_snapshot(contract_dir: Path | None = None) -> JsonObject:
    paths = resolve_contract_paths(contract_dir)
    return _load_json(paths.vectors_path)


def _require_str(payload: JsonObject, key: str, *, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{context}.{key} must be a string")
    return value


def _require_dict(payload: JsonObject, key: str, *, context: str) -> JsonObject:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{context}.{key} must be an object")
    return value


def _require_list(payload: JsonObject, key: str, *, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{context}.{key} must be a list")
    return value


def validate_bundle_shape(bundle: ContractBundle) -> tuple[str, ...]:
    """Validate minimum shape and version consistency."""
    issues: list[str] = []

    try:
        schema_kind = _require_str(bundle.schema, "snapshot_kind", context="schema")
        schema_version = _require_str(bundle.schema, "kernel_version", context="schema")
        _require_dict(bundle.schema, "stats", context="schema")
        _require_list(bundle.schema, "entities", context="schema")
    except ValueError as err:
        issues.append(str(err))
        schema_kind = ""
        schema_version = ""

    try:
        rules_kind = _require_str(bundle.rules, "snapshot_kind", context="rules")
        rules_version = _require_str(bundle.rules, "kernel_version", context="rules")
        _require_dict(bundle.rules, "stats", context="rules")
        _require_list(bundle.rules, "explicit_rules", context="rules")
        _require_list(bundle.rules, "fallback_rules", context="rules")
    except ValueError as err:
        issues.append(str(err))
        rules_kind = ""
        rules_version = ""

    try:
        vectors_kind = _require_str(bundle.vectors, "snapshot_kind", context="vectors")
        vectors_version = _require_str(bundle.vectors, "kernel_version", context="vectors")
        _require_dict(bundle.vectors, "stats", context="vectors")
        _require_list(bundle.vectors, "vectors", context="vectors")
    except ValueError as err:
        issues.append(str(err))
        vectors_kind = ""
        vectors_version = ""

    if schema_kind and schema_kind != "ea_kernel_schema_contract":
        issues.append(f"schema.snapshot_kind unexpected: {schema_kind}")
    if rules_kind and rules_kind != "ea_kernel_rules_contract":
        issues.append(f"rules.snapshot_kind unexpected: {rules_kind}")
    if vectors_kind and vectors_kind != "ea_kernel_judgment_vectors_contract":
        issues.append(f"vectors.snapshot_kind unexpected: {vectors_kind}")

    versions = {value for value in (schema_version, rules_version, vectors_version) if value}
    if len(versions) > 1:
        issues.append(f"kernel_version mismatch across snapshots: {sorted(versions)}")

    return tuple(issues)


def load_contract_bundle(
    contract_dir: Path | None = None,
    *,
    validate_shape: bool = True,
) -> ContractBundle:
    """Load all contract snapshots and optionally validate minimum shape."""
    paths = resolve_contract_paths(contract_dir)
    bundle = ContractBundle(
        paths=paths,
        schema=_load_json(paths.schema_path),
        rules=_load_json(paths.rules_path),
        vectors=_load_json(paths.vectors_path),
    )
    if validate_shape:
        issues = validate_bundle_shape(bundle)
        if issues:
            joined = "; ".join(issues)
            raise ValueError(f"invalid contract bundle: {joined}")
    return bundle
