from __future__ import annotations

import json
from pathlib import Path

import pytest
from ea_kernel_contract.loader import (
    ENV_CONTRACT_DIR,
    SCHEMA_FILE,
    VECTORS_FILE,
    default_contract_dir,
    load_contract_bundle,
    load_schema_snapshot,
    resolve_contract_paths,
    validate_bundle_shape,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_default_contract_dir_points_to_kernel_contracts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    contract_dir = default_contract_dir()
    expected = _repo_root() / "packages" / "ea-kernel" / "docs" / "reference" / "contracts"
    assert contract_dir == expected.resolve()


def test_load_contract_bundle_from_real_snapshots(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    bundle = load_contract_bundle()

    assert bundle.kernel_version == "2.5.0"
    assert bundle.schema["snapshot_kind"] == "ea_kernel_schema_contract"
    assert bundle.rules["snapshot_kind"] == "ea_kernel_rules_contract"
    assert bundle.vectors["snapshot_kind"] == "ea_kernel_judgment_vectors_contract"
    assert isinstance(bundle.vectors["vectors"], list)
    assert len(bundle.vectors["vectors"]) >= 1

    issues = validate_bundle_shape(bundle)
    assert issues == ()


def test_env_override_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    source_dir = _repo_root() / "packages" / "ea-kernel" / "docs" / "reference" / "contracts"
    target_dir = tmp_path / "contracts-copy"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in ("kernel_schema.snapshot.json", "kernel_rules.snapshot.json", VECTORS_FILE):
        (target_dir / filename).write_text((source_dir / filename).read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setenv(ENV_CONTRACT_DIR, str(target_dir))
    bundle = load_contract_bundle()
    assert bundle.paths.contract_dir == target_dir.resolve()


def test_missing_snapshot_file_raises(tmp_path: Path):
    paths = resolve_contract_paths(tmp_path)
    paths.contract_dir.mkdir(parents=True, exist_ok=True)
    paths.schema_path.write_text("{}", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        load_contract_bundle(paths.contract_dir)


def test_invalid_shape_detected(tmp_path: Path):
    contract_dir = tmp_path / "invalid-contract"
    contract_dir.mkdir(parents=True, exist_ok=True)

    schema = {"snapshot_kind": "ea_kernel_schema_contract", "kernel_version": "2.5.0", "stats": {}, "entities": []}
    rules = {"snapshot_kind": "ea_kernel_rules_contract", "kernel_version": "2.5.0", "stats": {}, "explicit_rules": [], "fallback_rules": []}
    vectors = {"snapshot_kind": "ea_kernel_judgment_vectors_contract", "kernel_version": "2.5.1", "stats": {}, "vectors": []}

    (contract_dir / SCHEMA_FILE).write_text(json.dumps(schema), encoding="utf-8")
    (contract_dir / "kernel_rules.snapshot.json").write_text(json.dumps(rules), encoding="utf-8")
    (contract_dir / VECTORS_FILE).write_text(json.dumps(vectors), encoding="utf-8")

    bundle = load_contract_bundle(contract_dir, validate_shape=False)
    issues = validate_bundle_shape(bundle)
    assert any("kernel_version mismatch across snapshots" in issue for issue in issues)


def test_load_schema_snapshot_from_real_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    payload = load_schema_snapshot()
    assert payload["kernel_version"] == "2.5.0"
