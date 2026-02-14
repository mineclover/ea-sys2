from __future__ import annotations

import json
from pathlib import Path

from ea_kernel_self.runner import run_self_check, save_report


def _workspace_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "packages" / "ea-kernel").exists():
            return candidate
    raise FileNotFoundError("workspace root not found")


def test_run_self_check_smoke(tmp_path: Path) -> None:
    root = _workspace_root(Path(__file__))
    profile_path = root / "packages" / "ea-kernel" / "examples" / "kernel_self_profile.toml"
    kernel_src = root / "packages" / "ea-kernel" / "src" / "ea_kernel"

    report = run_self_check(
        profile_path=profile_path,
        kernel_src=kernel_src,
        work_dir=tmp_path,
    )

    assert report["status"] == "ok"
    assert report["profile"]["name"] == "KernelSelfProfile"
    assert report["registration"]["post_validation_passed"] is True
    assert report["runtime"]["compiled_active_rule_count"] > 0

    checks = {item["name"]: item for item in report["runtime"]["checks"]}
    assert checks["category_contains_should_allow"]["compiled"]["passed"] is True


def test_save_report_writes_json(tmp_path: Path) -> None:
    report = {"status": "ok", "issues": []}
    output = tmp_path / "report.json"

    save_report(report, output)

    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["status"] == "ok"
