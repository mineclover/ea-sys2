from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ea_kernel"
        / "scripts"
        / "review_kernel_self_alignment.py"
    )
    spec = importlib.util.spec_from_file_location(
        "review_kernel_self_alignment",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_review_alignment_reports_mapped_and_unmapped_elements(tmp_path: Path, monkeypatch):
    module = _load_module()

    kernel_src = tmp_path / "ea_kernel"
    kernel_src.mkdir(parents=True, exist_ok=True)
    (kernel_src / "spec.py").write_text(
        "def build_validated_schema():\n    pass\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "_kernel_element_names",
        lambda _profile_path: ["KernelSpecBuilder", "UnknownKernelComponent"],
    )

    report = module.review_alignment(tmp_path / "profile.toml", kernel_src)

    assert report["matched_element_count"] == 1
    assert report["missing_elements"] == []
    assert report["unmapped_elements"] == ["UnknownKernelComponent"]


def test_render_console_report_includes_status_lines(tmp_path: Path, monkeypatch):
    module = _load_module()

    kernel_src = tmp_path / "ea_kernel"
    kernel_src.mkdir(parents=True, exist_ok=True)
    (kernel_src / "spec.py").write_text(
        "def build_validated_schema():\n    pass\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "_kernel_element_names",
        lambda _profile_path: ["KernelSpecBuilder"],
    )

    report = module.review_alignment(tmp_path / "profile.toml", kernel_src)
    text = module.render_console_report(report)

    assert "coverage=1/1" in text
    assert "status: aligned" in text
    assert "[ok] KernelSpecBuilder" in text

