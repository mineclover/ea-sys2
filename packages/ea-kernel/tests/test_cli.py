"""Tests for CLI (__main__.py) — output verification."""

from __future__ import annotations

import subprocess
import sys

_BASE = [sys.executable, "-m", "ea_kernel"]


def _run(*args: str, expect_rc: int = 0) -> str:
    """Run the CLI and return stdout."""
    result = subprocess.run(
        [*_BASE, *args],
        capture_output=True,
        text=True,
    )
    assert result.returncode == expect_rc, (
        f"Expected rc={expect_rc}, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return result.stdout


def _write_profile_toml(path, *, name: str = "CLITestModel", version: str = "1.0") -> None:
    path.write_text(
        f"""\
[profile]
name = "{name}"
version = "{version}"
kernel_version = "2.5.0"

[categories]
Thing = "item"
Action = "step"

[[elements]]
name = "Widget"
layer = "Core"
category = "Thing"

[[elements]]
name = "Task"
layer = "Core"
category = "Action"

[[relations]]
name = "uses"
kernel_relation = "association"

[[rules]]
source = "@Thing"
target = "@Action"
relation = "uses"
priority = 40
""",
        encoding="utf-8",
    )


# ── show entities ─────────────────────────────────────────────


class TestShowEntities:
    def test_header_contains_total(self):
        out = _run("show", "entities")
        assert "Kernel Entities" in out

    def test_contains_l1_structure(self):
        out = _run("show", "entities")
        assert "L1 Structure" in out

    def test_contains_l4_concrete(self):
        out = _run("show", "entities")
        assert "L4 Concrete" in out

    def test_contains_known_entities(self):
        out = _run("show", "entities")
        assert "element" in out
        assert "classifier" in out
        assert "feature" in out

    def test_abstract_marker(self):
        out = _run("show", "entities")
        assert "(abstract)" in out


# ── show relations ────────────────────────────────────────────


class TestShowRelations:
    def test_header_contains_total(self):
        out = _run("show", "relations")
        assert "Kernel Relations" in out

    def test_contains_l2_and_l3(self):
        out = _run("show", "relations")
        assert "L2 Relationship" in out
        assert "L3 Behavioral" in out

    def test_contains_known_relations(self):
        out = _run("show", "relations")
        assert "membership" in out
        assert "specialization" in out
        assert "flow" in out

    def test_roles_shown(self):
        out = _run("show", "relations")
        # At least one role format "name(player)"
        assert "(" in out and ")" in out


# ── show rules ────────────────────────────────────────────────


class TestShowRules:
    def test_summary_mode(self):
        out = _run("show", "rules")
        assert "Rules (" in out
        assert "specialization" in out
        assert "rules" in out

    def test_filter_by_group(self):
        out = _run("show", "rules", "--group", "specialization")
        assert "specialization" in out
        assert "ALLOW" in out or "DENY" in out

    def test_filter_by_relation(self):
        out = _run("show", "rules", "--relation", "flow")
        assert "flow" in out

    def test_unknown_group_returns_error(self):
        out = _run("show", "rules", "--group", "nonexistent", expect_rc=1)
        # Error goes to stderr, stdout may be empty
        assert out == "" or "error" in out.lower()


# ── show profile ──────────────────────────────────────────────


class TestShowProfile:
    def test_archimate(self):
        out = _run("show", "profile", "ArchiMate")
        assert "ArchiMate" in out
        assert "Elements:" in out
        assert "Relations:" in out
        assert "Rules:" in out

    def test_unknown_profile(self):
        _run("show", "profile", "NonExistent", expect_rc=1)

    def test_contains_layers(self):
        out = _run("show", "profile", "ArchiMate")
        assert "Elements by Layer:" in out

    def test_contains_relation_mappings(self):
        out = _run("show", "profile", "ArchiMate")
        assert "->" in out

    def test_rule_summary(self):
        out = _run("show", "profile", "ArchiMate")
        assert "allow" in out
        assert "deny" in out


# ── show rule ─────────────────────────────────────────────────


class TestShowRule:
    def test_existing_rule(self):
        out = _run("show", "rule", "spec-01")
        assert "Rule: spec-01" in out
        assert "Source:" in out
        assert "Target:" in out
        assert "Metadata:" in out

    def test_unknown_rule(self):
        _run("show", "rule", "nonexistent", expect_rc=1)

    def test_metadata_fields(self):
        out = _run("show", "rule", "spec-01")
        assert "Group:" in out
        assert "Category:" in out
        assert "Confidence:" in out


# ── judge ─────────────────────────────────────────────────────


class TestJudge:
    def test_allow_verdict(self):
        out = _run("judge", "classifier", "structure", "specialization")
        assert "ALLOW" in out
        assert "Verdict:" in out

    def test_deny_verdict(self):
        out = _run("judge", "classifier", "feature", "specialization")
        assert "DENY" in out

    def test_evidence_shown(self):
        out = _run("judge", "classifier", "feature", "specialization")
        assert "Evidence:" in out
        assert "[winner]" in out

    def test_unknown_entity_error(self):
        _run("judge", "nonexistent", "feature", "specialization", expect_rc=1)

    def test_unknown_relation_error(self):
        _run("judge", "classifier", "feature", "nonexistent", expect_rc=1)

    def test_no_conflicts(self):
        out = _run("judge", "classifier", "feature", "specialization")
        assert "No conflicts." in out


# ── existing commands still work ──────────────────────────────


class TestExistingCommands:
    def test_info_no_args(self):
        out = _run("info")
        assert "Kernel v" in out

    def test_help(self):
        out = _run()
        assert "ea-kernel" in out.lower() or "usage" in out.lower()


class TestModelCommands:
    def test_model_register_validate_activate_show(self, tmp_path):
        profile_path = tmp_path / "model.toml"
        db_path = tmp_path / "profiles.db"
        _write_profile_toml(profile_path, name="CLITestModel", version="1.0")

        out_register = _run(
            "model",
            "register",
            str(profile_path),
            "--db-path",
            str(db_path),
            "--owner",
            "qa-team",
            "--created-by",
            "tester",
            "--activate",
        )
        assert "[ok] registered model=CLITestModel version=1.0" in out_register
        assert "[ok] activated model=CLITestModel version=1.0" in out_register

        out_validate = _run(
            "model",
            "validate",
            "CLITestModel",
            "1.0",
            "--db-path",
            str(db_path),
        )
        assert "[PASS] model=CLITestModel version=1.0" in out_validate

        out_show = _run(
            "model",
            "show",
            "CLITestModel",
            "--db-path",
            str(db_path),
        )
        assert "Model: CLITestModel" in out_show
        assert "Status: active" in out_show
        assert "Versions: 1" in out_show

    def test_model_register_revalidates_existing_version(self, tmp_path):
        profile_path = tmp_path / "model.toml"
        db_path = tmp_path / "profiles.db"
        _write_profile_toml(profile_path, name="CLIRecheckModel", version="1.0")

        _run("model", "register", str(profile_path), "--db-path", str(db_path))
        out_second = _run("model", "register", str(profile_path), "--db-path", str(db_path))

        assert "[ok] existing model revalidated model=CLIRecheckModel version=1.0" in out_second
