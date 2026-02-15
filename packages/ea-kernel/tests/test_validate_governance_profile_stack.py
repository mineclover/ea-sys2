"""Tests for examples/validate_governance_profile_stack.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_validate_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "validate_governance_profile_stack.py"
    )
    spec = importlib.util.spec_from_file_location(
        "validate_governance_profile_stack",
        script_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("profile_id", "filename", "expected"),
    [
        ("meta", "00-governance-meta-model.toml", (23, 9, 51)),
        ("ea_sys", "10-governance.toml", (61, 9, 156)),
        ("external", "20-external-governance.toml", (22, 9, 54)),
    ],
)
def test_validate_profile_success(profile_id, filename, expected):
    mod = _load_validate_module()

    path, elements, relations, rules = mod.validate_profile(profile_id)

    assert path.endswith(filename)
    assert (elements, relations, rules) == expected


def test_main_simulate_success(monkeypatch, capsys):
    mod = _load_validate_module()
    monkeypatch.setattr(
        mod.sys,
        "argv",
        ["validate_governance_profile_stack.py", "--simulate"],
    )

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "[sim] governance-meta-model: passed" in out
    assert "[sim] ea-sys-governance-profile: passed" in out
    assert "[sim] external-governance-profile: passed" in out
    assert "[sim] decision-trace-contract: passed" in out
    assert "[sim] purpose-alignment: passed" in out
    assert "[sim] passed" in out
