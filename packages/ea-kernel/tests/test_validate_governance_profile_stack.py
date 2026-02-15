"""Tests for examples/validate_governance_profile_stack.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from ea_kernel.profile_loader import load_profile
from ea_kernel.profiles.ea_sys import PROFILE_DIR as EA_SYS_PROFILE_DIR
from ea_kernel.profiles.governance_profile_stack import (
    PROFILE_DIR as GOV_STACK_PROFILE_DIR,
    PROFILE_FILE_MAP as GOV_STACK_MAP,
)
from ea_kernel.spec import KERNEL_SPEC

# Profile stack includes governance-meta, ea_sys governance, and external governance
_PROFILE_STACK_FILES: dict[str, Path] = {
    "meta": GOV_STACK_PROFILE_DIR / "00-governance-meta-model.toml",
    "ea_sys": EA_SYS_PROFILE_DIR / "10-governance.toml",
    "external": GOV_STACK_PROFILE_DIR / "20-external-governance.toml",
}


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


def _expected_counts(profile_id: str) -> tuple[int, int, int]:
    p = load_profile(_PROFILE_STACK_FILES[profile_id], KERNEL_SPEC)
    return (len(p.elements), len(p.relations), len(p.validity_rules))


@pytest.mark.parametrize(
    ("profile_id", "filename"),
    [
        ("meta", "00-governance-meta-model.toml"),
        ("ea_sys", "10-governance.toml"),
        ("external", "20-external-governance.toml"),
    ],
)
def test_validate_profile_success(profile_id, filename):
    mod = _load_validate_module()

    path, elements, relations, rules = mod.validate_profile(profile_id)

    expected = _expected_counts(profile_id)
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
