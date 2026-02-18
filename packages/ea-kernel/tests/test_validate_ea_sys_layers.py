"""Tests for examples/validate_ea_sys_layers.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from ea_kernel.kernel_service import profile_topology
from ea_kernel.profile_loader import load_profile
from ea_kernel.profiles.ea_sys import LAYER_FILE_MAP, layer_path
from ea_kernel.spec import KERNEL_SPEC


def _load_validate_module():
    script_path = Path(__file__).resolve().parents[1] / "examples" / "validate_ea_sys_layers.py"
    spec = importlib.util.spec_from_file_location("validate_ea_sys_layers", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected_counts(layer: str) -> tuple[int, int, int]:
    p = load_profile(layer_path(layer), KERNEL_SPEC)
    return (len(p.elements), len(p.relations), len(p.validity_rules))


# Only validate the 6 core layers (web-kernel-viz and development are not in the validate script)
_VALIDATION_LAYERS = [k for k in LAYER_FILE_MAP if k not in ("web-kernel-viz", "development")]


@pytest.mark.parametrize(
    ("layer", "filename"),
    [(layer, LAYER_FILE_MAP[layer]) for layer in _VALIDATION_LAYERS],
)
def test_validate_layer_success(layer, filename):
    mod = _load_validate_module()

    path, elements, relations, rules = mod.validate_layer(layer)

    expected = _expected_counts(layer)
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


@pytest.mark.parametrize("layer", _VALIDATION_LAYERS)
def test_core_layers_have_no_dormant_relations(layer: str):
    profile = load_profile(layer_path(layer), KERNEL_SPEC)
    relation_names = {rel.name for rel in profile.relations}
    used_relations = {
        rule.relationship_name
        for rule in profile.validity_rules
        if rule.valid
    }
    assert relation_names - used_relations == set()


@pytest.mark.parametrize(
    "profile_name",
    [
        "EASystem-Infra",
        "EASystem-Governance",
        "EASystem-Decision",
        "EASystem-Needs",
        "EASystem-Kernel",
        "EASystem-Flow",
    ],
)
def test_actor_focus_default_seed_returns_connected_topology(profile_name: str):
    topology = profile_topology(
        profile_name=profile_name,
        view_mode="focus",
        focus="actor",
        focus_depth=4,
        max_edges=260,
    )
    assert "error" not in topology
    assert topology["edge_count"] > 0
