from __future__ import annotations

import json
from pathlib import Path

import pytest
from ea_kernel_contract import (
    DEFAULT_MANAGED_GOVERNANCE_LAYERS,
    ENV_CONTRACT_DIR,
    ENV_GOVERNANCE_REFERENCE_PATH,
    RULES_FILE,
    SCHEMA_FILE,
    VECTORS_FILE,
    build_contract_model,
    build_governance_layer_catalog,
    contract_fingerprint,
    default_contract_dir,
    default_governance_reference_path,
    evaluate_relationship,
    get_entity_required_keys,
    list_feedback_targets,
    load_contract_bundle,
    load_governance_reference_snapshot,
    load_schema_snapshot,
    parse_feedback_target,
    resolve_contract_paths,
    resolve_feedback_target,
    validate_bundle_shape,
    validate_governance_layer_catalog,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_default_contract_dir_points_to_kernel_contracts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    contract_dir = default_contract_dir()
    expected = _repo_root() / "packages" / "ea-kernel" / "docs" / "reference" / "contracts"
    assert contract_dir == expected.resolve()


def test_default_governance_reference_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_GOVERNANCE_REFERENCE_PATH, raising=False)
    path = default_governance_reference_path()
    assert path.name == "kernel_governance_reference_v1.snapshot.json"
    assert path.exists()


def test_load_contract_bundle_from_real_snapshots(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    bundle = load_contract_bundle()

    assert bundle.kernel_version == "2.5.0"
    assert bundle.schema["snapshot_kind"] == "ea_kernel_schema_contract"
    assert bundle.rules["snapshot_kind"] == "ea_kernel_rules_contract"
    assert bundle.vectors["snapshot_kind"] == "ea_kernel_judgment_vectors_contract"

    issues = validate_bundle_shape(bundle)
    assert issues == ()


def test_build_contract_model_and_fingerprint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    model = build_contract_model()

    assert len(model.fingerprint) == 64
    assert model.fingerprint == contract_fingerprint(model.bundle)
    assert "structure" in model.index.entity_by_name
    assert "association" in model.index.relation_by_name
    assert "mem-01" in model.index.rule_by_id
    assert "lc-00-l4-l4-association" in model.index.layer_constraint_by_id


def test_env_override_is_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    source_dir = _repo_root() / "packages" / "ea-kernel" / "docs" / "reference" / "contracts"
    target_dir = tmp_path / "contracts-copy"
    target_dir.mkdir(parents=True, exist_ok=True)

    for filename in (SCHEMA_FILE, RULES_FILE, VECTORS_FILE):
        (target_dir / filename).write_text(
            (source_dir / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

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

    schema = {
        "snapshot_kind": "ea_kernel_schema_contract",
        "kernel_version": "2.5.0",
        "stats": {"attributes": 0, "entities": 0, "relations": 0},
        "attributes": [],
        "entities": [],
        "relations": [],
    }
    rules = {
        "snapshot_kind": "ea_kernel_rules_contract",
        "kernel_version": "2.5.0",
        "stats": {
            "total_rules": 0,
            "explicit_rules": 0,
            "fallback_rules": 0,
            "layer_constraints": 0,
            "metadata_entries": 0,
        },
        "explicit_rules": [],
        "fallback_rules": [],
        "layer_constraints": [],
    }
    vectors = {
        "snapshot_kind": "ea_kernel_judgment_vectors_contract",
        "kernel_version": "2.5.1",
        "stats": {"vectors": 0, "allow_vectors": 0, "deny_vectors": 0},
        "vectors": [],
    }

    (contract_dir / SCHEMA_FILE).write_text(json.dumps(schema), encoding="utf-8")
    (contract_dir / RULES_FILE).write_text(json.dumps(rules), encoding="utf-8")
    (contract_dir / VECTORS_FILE).write_text(json.dumps(vectors), encoding="utf-8")

    bundle = load_contract_bundle(contract_dir, validate_shape=False)
    issues = validate_bundle_shape(bundle)
    assert any("kernel_version mismatch across snapshots" in issue for issue in issues)


def test_load_schema_snapshot_from_real_path(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(ENV_CONTRACT_DIR, raising=False)
    payload = load_schema_snapshot()
    assert payload["kernel_version"] == "2.5.0"


def test_feedback_target_resolution():
    model = build_contract_model()

    parsed = parse_feedback_target("rule:mem-01")
    assert parsed.canonical_id == "rule:mem-01"

    resolved = resolve_feedback_target("layer_constraint:lc-00-l4-l4-association", model)
    assert resolved.target_type == "layer_constraint"

    with pytest.raises(ValueError, match="unknown rule target"):
        resolve_feedback_target("rule:unknown-rule", model)


def test_list_feedback_targets_and_required_keys():
    model = build_contract_model()

    targets = list_feedback_targets(model)
    assert any(t.canonical_id == "rule:mem-01" for t in targets)
    assert any(t.canonical_id == "entity_type:structure" for t in targets)

    keys = get_entity_required_keys(model, "structure")
    assert "uid" in keys
    assert "name" in keys
    assert "qualified_name" in keys
    assert "layer" in keys


def test_evaluate_relationship_follows_vectors():
    model = build_contract_model()
    vectors = model.bundle.vectors["vectors"]

    for row in vectors:
        assert isinstance(row, dict)
        triple = row["triple"]
        evaluation = evaluate_relationship(
            model,
            source_entity=triple[0],
            target_entity=triple[1],
            relation=triple[2],
        )

        assert evaluation.allowed is row["expected_verdict"]
        assert evaluation.winner_rule_id == row["expected_winner_rule_id"]


def test_evaluate_relationship_constraint_block():
    model = build_contract_model()
    evaluation = evaluate_relationship(model, "event", "event", "association")

    assert evaluation.allowed is False
    assert evaluation.reason == "constraint_denied"
    assert evaluation.blocking_constraint_id == "lc-00-l4-l4-association"


def test_load_governance_reference_snapshot():
    payload = load_governance_reference_snapshot()
    assert payload["snapshot_kind"] == "kernel_governance_db_reference"


def test_build_governance_layer_catalog_for_managed_5_layers():
    catalog = build_governance_layer_catalog()
    assert catalog.governance_layer_present is True
    assert catalog.expected_managed_layers == DEFAULT_MANAGED_GOVERNANCE_LAYERS
    assert catalog.managed_layers == DEFAULT_MANAGED_GOVERNANCE_LAYERS
    assert catalog.is_valid is True

    issues = validate_governance_layer_catalog(catalog)
    assert issues == ()


def test_governance_layer_catalog_detects_missing_managed_layer(tmp_path: Path):
    source = default_governance_reference_path()
    payload = json.loads(source.read_text(encoding="utf-8"))

    seed_profiles = payload["seed_profiles"]
    payload["seed_profiles"] = [
        row for row in seed_profiles if row.get("layer") != "flow"
    ]

    test_path = tmp_path / source.name
    test_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    catalog = build_governance_layer_catalog(test_path)
    assert "flow" in catalog.missing_managed_layers
    assert catalog.is_valid is False

    issues = validate_governance_layer_catalog(catalog)
    assert any("missing managed governance layers" in issue for issue in issues)


def test_typescript_sdk_contracts_are_synced_with_source():
    repo_root = _repo_root()
    source_dir = repo_root / "packages" / "ea-kernel" / "docs" / "reference" / "contracts"
    sdk_dir = repo_root / "packages" / "ea-kernel-contract-ts" / "contracts"
    files = (SCHEMA_FILE, RULES_FILE, VECTORS_FILE)

    for filename in files:
        source = source_dir / filename
        target = sdk_dir / filename
        assert source.exists()
        assert target.exists()
        assert source.read_text(encoding="utf-8") == target.read_text(encoding="utf-8")
