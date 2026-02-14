"""Tests for examples/validate_ralph_tui_layers.py."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest


def _load_validate_module():
    script_path = Path(__file__).resolve().parents[1] / "examples" / "validate_ralph_tui_layers.py"
    spec = importlib.util.spec_from_file_location("validate_ralph_tui_layers", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("layer", "filename", "expected"),
    [
        ("infra", "00-infra.toml", (7, 9, 9)),
        ("governance", "10-governance.toml", (35, 9, 79)),
        ("decision", "20-decision.toml", (10, 9, 15)),
        ("needs", "30-needs.toml", (5, 9, 9)),
        ("kernel", "40-kernel.toml", (13, 9, 30)),
        ("flow", "50-flow.toml", (19, 9, 46)),
    ],
)
def test_validate_layer_success(layer, filename, expected):
    mod = _load_validate_module()

    path, elements, relations, rules = mod.validate_layer(layer)

    assert path.endswith(f"/ralph_tui_layers/{filename}")
    assert (elements, relations, rules) == expected


def test_validate_layer_missing_file_raises(tmp_path, monkeypatch):
    mod = _load_validate_module()
    monkeypatch.setattr(mod, "LAYER_DIR", tmp_path)

    with pytest.raises(FileNotFoundError):
        mod.validate_layer("kernel")


def test_main_all_success(monkeypatch, capsys):
    mod = _load_validate_module()
    monkeypatch.setattr(mod.sys, "argv", ["validate_ralph_tui_layers.py"])

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "[ok] infra" in out
    assert "[ok] governance" in out
    assert "[ok] decision" in out
    assert "[ok] needs" in out
    assert "[ok] kernel" in out
    assert "[ok] flow" in out


def test_main_returns_one_on_failure(monkeypatch, capsys):
    mod = _load_validate_module()

    def _fake_validate(layer):
        if layer == "decision":
            raise RuntimeError("decision failed")
        return (f"/tmp/{layer}.toml", 1, 1, 1)

    monkeypatch.setattr(mod, "validate_layer", _fake_validate)
    monkeypatch.setattr(mod.sys, "argv", ["validate_ralph_tui_layers.py"])

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "[fail] decision" in out
    assert "decision failed" in out


def test_main_registers_single_layer(monkeypatch, capsys, tmp_path):
    mod = _load_validate_module()
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(
        mod.sys,
        "argv",
        [
            "validate_ralph_tui_layers.py",
            "--layer",
            "kernel",
            "--register",
            "--db-path",
            str(db_path),
        ],
    )

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "[ok] kernel" in out
    assert "[reg] kernel" in out

    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT model_name, status FROM model_registry ORDER BY model_name"
        ).fetchone()
        assert row is not None
        assert row[0] == "RalphTUIImplementation.kernel"
        assert row[1] == "registered"


def test_main_registers_all_layers_independently(monkeypatch, capsys, tmp_path):
    mod = _load_validate_module()
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(
        mod.sys,
        "argv",
        [
            "validate_ralph_tui_layers.py",
            "--register",
            "--db-path",
            str(db_path),
            "--register-name-mode",
            "layer",
        ],
    )

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert out.count("[reg]") == 6

    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT model_name FROM model_registry ORDER BY model_name"
        ).fetchall()
        assert len(rows) == 6
        names = [r[0] for r in rows]
        assert "RalphTUIImplementation.infra" in names
        assert "RalphTUIImplementation.flow" in names


def test_simulate_data_flow_success():
    mod = _load_validate_module()

    report = mod.simulate_data_flow()

    assert report["passed"] is True
    assert report["flow_sequence"] == [
        "SyncTrackerStep",
        "SelectTaskStep",
        "BuildPromptStep",
        "ExecuteAgentAction",
        "DetectCompletionStep",
        "UpdateTrackerStep",
        "PersistIterationStep",
    ]
    assert report["missing_inputs"] == []
    assert report["policy_gaps"] == []
    assert report["independent_relation_integrity_ok"] is True
    assert report["model_definition_order"] == [
        "infra",
        "decision",
        "needs",
        "kernel",
        "flow",
    ]
    assert report["governance_role"] == "layer-management-system"


def test_main_simulate_success(monkeypatch, capsys):
    mod = _load_validate_module()
    monkeypatch.setattr(mod.sys, "argv", ["validate_ralph_tui_layers.py", "--simulate"])

    rc = mod.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "[sim] flow-sequence:" in out
    assert "[sim] model-order: infra > decision > needs > kernel > flow" in out
    assert "[sim] governance-role: layer-management-system" in out
    assert "[sim] passed" in out
