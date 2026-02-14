from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ea_kernel"
        / "scripts"
        / "kernel_contract_snapshot.py"
    )
    spec = importlib.util.spec_from_file_location(
        "kernel_contract_snapshot",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_and_verify_contract_snapshots(tmp_path: Path):
    module = _load_module()
    output_dir = tmp_path / "contracts"

    payloads = module.build_contract_snapshots(output_dir)

    for filename in module.SNAPSHOT_FILENAMES.values():
        assert (output_dir / filename).exists()

    schema = payloads["schema"]
    rules = payloads["rules"]
    vectors = payloads["vectors"]

    assert schema["kernel_version"] == module.KERNEL_VERSION
    assert schema["stats"]["entities"] == len(module.KERNEL_SCHEMA.entities)
    assert schema["stats"]["relations"] == len(module.KERNEL_SCHEMA.relations)
    assert rules["stats"]["total_rules"] == len(module.KERNEL_SPEC.validity_rules)
    assert rules["stats"]["explicit_rules"] + rules["stats"]["fallback_rules"] == len(
        module.KERNEL_SPEC.validity_rules
    )
    assert vectors["stats"]["vectors"] == len(module.DEFAULT_VECTOR_CASES)

    issues = module.verify_contract_snapshots(output_dir)
    assert issues == []


def test_verify_detects_vector_drift(tmp_path: Path):
    module = _load_module()
    output_dir = tmp_path / "contracts"
    module.build_contract_snapshots(output_dir)

    vector_path = output_dir / module.SNAPSHOT_FILENAMES["vectors"]
    payload = json.loads(vector_path.read_text(encoding="utf-8"))
    assert payload["vectors"]
    payload["vectors"][0]["expected_verdict"] = not payload["vectors"][0]["expected_verdict"]
    vector_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    issues = module.verify_contract_snapshots(output_dir)
    assert any("vectors" in issue for issue in issues)


def test_verify_reports_missing_files(tmp_path: Path):
    module = _load_module()
    output_dir = tmp_path / "contracts"
    output_dir.mkdir(parents=True, exist_ok=True)

    issues = module.verify_contract_snapshots(output_dir)
    assert len(issues) == 3
    assert all("snapshot file not found" in issue for issue in issues)
