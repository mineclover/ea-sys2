"""Tests for examples/validate_ea_sys_layers.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_validate_module():
    script_path = Path(__file__).resolve().parents[1] / "examples" / "validate_ea_sys_layers.py"
    spec = importlib.util.spec_from_file_location("validate_ea_sys_layers", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("layer", "filename", "expected"),
    [
        ("infra", "00-infra.toml", (15, 10, 24)),
        ("governance", "10-governance.toml", (61, 10, 157)),
        ("decision", "20-decision.toml", (28, 10, 62)),
        ("needs", "30-needs.toml", (16, 10, 26)),
        ("kernel", "40-kernel.toml", (31, 10, 63)),
        ("flow", "50-flow.toml", (26, 10, 60)),
    ],
)
def test_validate_layer_success(layer, filename, expected):
    mod = _load_validate_module()

    path, elements, relations, rules = mod.validate_layer(layer)

    assert path.endswith(f"/profiles/ea_sys/{filename}")
    assert (elements, relations, rules) == expected


def test_main_simulate_success(monkeypatch, capsys):
    mod = _load_validate_module()
    monkeypatch.setattr(mod.sys, "argv", ["validate_ea_sys_layers.py", "--simulate"])

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "[sim] flow-sequence:" in out
    assert "[sim] model-order: infra > decision > needs > kernel > flow" in out
    assert "[sim] infra-role: row-data-design" in out
    assert "[sim] governance-role: system-entrypoint-design" in out
    assert "[sim] entrypoint-order: decision > needs > kernel > flow" in out
    assert "[sim] governance-entrypoint: passed" in out
    assert "[sim] governance-model-api-contract: passed" in out
    assert "[sim] layer-6x6-contract: passed" in out
    assert "[sim] layer-6x6-owner: flow" in out
    assert "[sim] common-layer-spec:" in out
    assert "[sim] layer-role-sync:" in out
    assert (
        "[sim] common-layer-spec: ok" in out
        or "[sim][warn] common-layer-spec:" in out
    )
    assert (
        "[sim] layer-role-sync: ok" in out
        or "[sim][warn] layer-role-sync:" in out
    )
    assert "[sim] passed" in out
