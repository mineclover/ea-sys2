from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from ea_kernel.profiles.ea_sys import LAYER_ORDER

_LAYER_COUNT = len(LAYER_ORDER)


def _load_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ea_kernel"
        / "scripts"
        / "kernel_governance_reference_snapshot.py"
    )
    spec = importlib.util.spec_from_file_location(
        "kernel_governance_reference_snapshot",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_and_verify_reference_snapshot(tmp_path: Path):
    module = _load_module()
    data_dir = tmp_path / "reference_data"
    snapshot_path = tmp_path / "snapshot.json"

    payload = module.build_reference_snapshot(data_dir, snapshot_path)

    assert snapshot_path.exists()
    assert payload["reference_version"] == "1.0.0"
    assert len(payload["model_registry"]) == _LAYER_COUNT
    assert payload["active_models"] == ["EASystemLayerModel.kernel"]
    assert payload["db_contract"]["profiles.db"]["row_counts"]["model_registry"] == _LAYER_COUNT
    assert payload["db_contract"]["profiles.db"]["row_counts"]["validation_runs"] == _LAYER_COUNT + 1
    seed_profiles = payload["seed_profiles"]
    assert len(seed_profiles) == _LAYER_COUNT

    base_rule_count = len(module.KERNEL_SPEC.validity_rules)
    by_layer = {row["layer"]: row for row in seed_profiles}
    assert by_layer["flow"]["compiled_transformed_rules"] > 0
    assert by_layer["governance"]["compiled_transformed_rules"] > 0

    for row in seed_profiles:
        assert row["compiled_skipped_rules"] == 0
        assert row["runtime_rules"] == base_rule_count + row["compiled_rules"]
        assert row["runtime_entities"] >= row["runtime_added_entities"]
        assert row["runtime_relations"] >= row["runtime_added_relations"]

    issues = module.verify_reference_snapshot(data_dir, snapshot_path)
    assert issues == []


def test_verify_detects_registry_drift(tmp_path: Path):
    module = _load_module()
    data_dir = tmp_path / "reference_data"
    snapshot_path = tmp_path / "snapshot.json"

    module.build_reference_snapshot(data_dir, snapshot_path)
    profiles_db = data_dir / "profiles.db"
    with sqlite3.connect(str(profiles_db)) as conn:
        conn.execute(
            "UPDATE model_registry SET status='disabled' WHERE model_name='EASystemLayerModel.kernel'"
        )
        conn.commit()

    issues = module.verify_reference_snapshot(data_dir, snapshot_path)
    assert any("active_models" in issue or "model_registry" in issue for issue in issues)


def test_build_requires_empty_data_dir_without_force_reset(tmp_path: Path):
    module = _load_module()
    data_dir = tmp_path / "reference_data"
    snapshot_path = tmp_path / "snapshot.json"

    module.build_reference_snapshot(data_dir, snapshot_path)
    with pytest.raises(RuntimeError, match="data_dir is not empty"):
        module.build_reference_snapshot(data_dir, snapshot_path)

    payload = module.build_reference_snapshot(
        data_dir,
        snapshot_path,
        force_reset=True,
    )
    assert payload["active_models"] == ["EASystemLayerModel.kernel"]
