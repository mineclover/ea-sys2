"""Runtime self-checks built on top of ea-kernel."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from ea_kernel.governance import GovernanceSystem
from ea_kernel.governance_types import RuleAsset, RuleProvenance
from ea_kernel.model_registration import (
    KernelModelRegistrationService,
    ModelRegistrationError,
)
from ea_kernel.profile_loader import load_profile
from ea_kernel.profile_rule_compiler import (
    build_profile_structure_schema,
    compile_profile_rules_for_runtime,
)
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.schema_loader import load_kernel_schema_from_package
from ea_kernel.scripts.review_kernel_self_alignment import review_alignment
from ea_kernel.types import (
    KernelValidityRule,
    RuleCorpusEntry,
    RuleMetadata,
)


@dataclass(frozen=True)
class TripleExpectation:
    name: str
    source: str
    target: str
    relation: str
    expected: bool


CHECKS: tuple[TripleExpectation, ...] = (
    TripleExpectation(
        name="category_contains_should_allow",
        source="KernelLayer",
        target="KernelSpecBuilder",
        relation="contains",
        expected=True,
    ),
    TripleExpectation(
        name="exact_depends_on_should_allow",
        source="KernelSpecBuilder",
        target="KernelSchemaLoader",
        relation="depends_on",
        expected=True,
    ),
    TripleExpectation(
        name="unspecified_consumes_should_deny",
        source="KernelSchemaLoader",
        target="KernelSpecBuilder",
        relation="consumes",
        expected=False,
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _workspace_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() and (candidate / "packages" / "ea-kernel").exists():
            return candidate
    return None


def resolve_default_paths(cwd: Path | None = None) -> tuple[Path, Path]:
    search_root = cwd or Path.cwd()
    workspace = _workspace_root(search_root)
    if workspace is None:
        workspace = _workspace_root(Path(__file__).resolve())
    if workspace is None:
        raise FileNotFoundError("Could not locate workspace root for default paths")

    profile_path = workspace / "packages" / "ea-kernel" / "examples" / "kernel_self_profile.toml"
    kernel_src = workspace / "packages" / "ea-kernel" / "src" / "ea_kernel"

    if not profile_path.exists():
        raise FileNotFoundError(f"Default profile not found: {profile_path}")
    if not kernel_src.exists():
        raise FileNotFoundError(f"Default kernel src not found: {kernel_src}")

    return profile_path, kernel_src


def _entries_from_rules(
    rules: tuple[KernelValidityRule, ...],
    *,
    domain: str,
    established_version: str,
    source: str,
) -> tuple[RuleCorpusEntry, ...]:
    entries: list[RuleCorpusEntry] = []
    for rule in rules:
        inferred = RuleCorpus.infer_metadata(rule)
        metadata = RuleMetadata(
            domain=domain,
            tags=inferred.tags,
            category=inferred.category,
            confidence=inferred.confidence,
            source=source,
            established_version=established_version,
            rationale=rule.notes,
            group=inferred.group,
        )
        entries.append(RuleCorpusEntry(rule=rule, metadata=metadata))
    return tuple(entries)


def _to_asset(entry: RuleCorpusEntry, profile_path: Path, actor: str) -> RuleAsset:
    return RuleAsset(
        entry=entry,
        provenance=RuleProvenance(
            author=actor,
            source_type="profile",
            source_reference=str(profile_path),
        ),
    )


def _load_entries(system: GovernanceSystem, entries: tuple[RuleCorpusEntry, ...], actor: str, profile_path: Path) -> None:
    for entry in entries:
        system.submit_rule(_to_asset(entry, profile_path, actor))
    for entry in entries:
        system.approve_rule(entry.rule.id, actor)


def _evaluate_checks(system: GovernanceSystem) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for check in CHECKS:
        judged = system.evaluate(check.source, check.target, check.relation)
        winner_rule = None
        for evidence in judged.judgment.evidence:
            if evidence.is_winner:
                winner_rule = evidence.entry.rule.id
                break

        rows.append(
            {
                "name": check.name,
                "triple": [check.source, check.target, check.relation],
                "expected": check.expected,
                "verdict": judged.judgment.verdict,
                "passed": judged.judgment.verdict == check.expected,
                "winner_rule": winner_rule,
                "confidence": judged.judgment.confidence.value,
                "domains": list(judged.judgment.domains),
            }
        )
    return rows


def _build_issues(
    *,
    alignment: dict[str, Any],
    registration_validation_passed: bool,
    compiled_stats: dict[str, int],
    raw_results: list[dict[str, Any]],
    compiled_results: list[dict[str, Any]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    missing_elements = alignment.get("missing_elements", [])
    if missing_elements:
        issues.append(
            {
                "severity": "error",
                "code": "alignment_missing_elements",
                "message": f"Alignment missing elements: {', '.join(sorted(missing_elements))}",
            }
        )

    unmapped_elements = alignment.get("unmapped_elements", [])
    if unmapped_elements:
        issues.append(
            {
                "severity": "error",
                "code": "alignment_unmapped_elements",
                "message": f"Alignment unmapped elements: {', '.join(sorted(unmapped_elements))}",
            }
        )

    if not registration_validation_passed:
        issues.append(
            {
                "severity": "error",
                "code": "registration_validation_failed",
                "message": "Model registration validation failed.",
            }
        )

    if compiled_stats["transformed_rule_count"] > 0:
        issues.append(
            {
                "severity": "info",
                "code": "profile_pattern_compiled",
                "message": (
                    "Category/layer patterns were compiled to executable rules for runtime checks. "
                    "Raw runtime may differ from intended profile semantics."
                ),
            }
        )

    if compiled_stats["skipped_rule_count"] > 0:
        issues.append(
            {
                "severity": "warning",
                "code": "compiled_rules_skipped",
                "message": f"Skipped {compiled_stats['skipped_rule_count']} rules while compiling profile patterns.",
            }
        )

    raw_by_name = {row["name"]: row for row in raw_results}
    compiled_by_name = {row["name"]: row for row in compiled_results}

    for check in CHECKS:
        raw_row = raw_by_name[check.name]
        compiled_row = compiled_by_name[check.name]

        if not compiled_row["passed"]:
            issues.append(
                {
                    "severity": "error",
                    "code": "compiled_runtime_mismatch",
                    "message": f"Compiled runtime failed check '{check.name}'.",
                }
            )

        if check.expected and not raw_row["passed"] and compiled_row["passed"]:
            severity = "warning"
            message = (
                f"Raw runtime failed '{check.name}' but compiled runtime passed. "
                "This indicates profile pattern semantics are not directly executable as-is."
            )
            if compiled_stats["transformed_rule_count"] > 0:
                severity = "info"
                message = (
                    f"Raw runtime failed '{check.name}' but compiled runtime passed. "
                    "Pattern-based profile rules are expected to require compilation for executable runtime semantics."
                )
            issues.append(
                {
                    "severity": severity,
                    "code": "raw_runtime_pattern_mismatch",
                    "message": message,
                }
            )

    return issues


def run_self_check(
    *,
    profile_path: Path | None = None,
    kernel_src: Path | None = None,
    work_dir: Path | None = None,
    actor: str = "ea-kernel-self",
) -> dict[str, Any]:
    default_profile, default_kernel_src = resolve_default_paths()
    profile_path = (profile_path or default_profile).resolve()
    kernel_src = (kernel_src or default_kernel_src).resolve()

    if work_dir is None:
        base_work_dir = Path(mkdtemp(prefix="ea-kernel-self-"))
    else:
        base_work_dir = work_dir.resolve()
    base_work_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = base_work_dir / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=False)

    base_schema = load_kernel_schema_from_package()
    profile = load_profile(profile_path, kernel=base_schema)
    extended_schema, _ = build_profile_structure_schema(base_schema, profile)

    alignment = review_alignment(profile_path, kernel_src)

    registration = KernelModelRegistrationService(run_dir / "registration" / "models.db", base_schema)

    registration_created = True
    try:
        registered = registration.register(
            profile,
            owner=actor,
            created_by=actor,
            context={"source": "ea-kernel-self"},
        )
        version_id = registered.version_id
        registration_run_id = registered.validation_run_id
    except ModelRegistrationError as err:
        if "already exists" not in str(err):
            raise
        registration_created = False
        versions = registration.list_versions(profile.name)
        if not versions:
            raise
        version_id = versions[-1].version_id
        registration_run_id = ""

    validation = registration.validate_registered(
        profile.name,
        profile.version,
        context={"source": "ea-kernel-self:validate"},
    )

    activated = registration.activate(profile.name, profile.version, actor=actor)

    raw_entries = _entries_from_rules(
        profile.validity_rules,
        domain=profile.name,
        established_version=profile.version,
        source=f"profile-raw:{profile.name}",
    )
    compilation = compile_profile_rules_for_runtime(profile)
    compiled_entries = _entries_from_rules(
        compilation.rules,
        domain=profile.name,
        established_version=profile.version,
        source=f"profile-compiled:{profile.name}",
    )
    compiled_stats = {
        "source_rule_count": compilation.stats.source_rule_count,
        "compiled_rule_count": compilation.stats.compiled_rule_count,
        "transformed_rule_count": compilation.stats.transformed_rule_count,
        "skipped_rule_count": compilation.stats.skipped_rule_count,
    }

    raw_system = GovernanceSystem(run_dir / "runtime_raw", extended_schema)
    _load_entries(raw_system, raw_entries, actor, profile_path)
    raw_results = _evaluate_checks(raw_system)

    compiled_system = GovernanceSystem(run_dir / "runtime_compiled", extended_schema)
    _load_entries(compiled_system, compiled_entries, actor, profile_path)
    compiled_results = _evaluate_checks(compiled_system)

    issues = _build_issues(
        alignment=alignment,
        registration_validation_passed=validation.passed,
        compiled_stats=compiled_stats,
        raw_results=raw_results,
        compiled_results=compiled_results,
    )

    has_error = any(item["severity"] == "error" for item in issues)
    has_warning = any(item["severity"] == "warning" for item in issues)
    status = "error" if has_error else "warning" if has_warning else "ok"

    raw_by_name = {row["name"]: row for row in raw_results}
    compiled_by_name = {row["name"]: row for row in compiled_results}

    checks: list[dict[str, Any]] = []
    for check in CHECKS:
        checks.append(
            {
                "name": check.name,
                "triple": [check.source, check.target, check.relation],
                "expected": check.expected,
                "raw": raw_by_name[check.name],
                "compiled": compiled_by_name[check.name],
            }
        )

    return {
        "timestamp": _utc_now_iso(),
        "status": status,
        "profile": {
            "path": str(profile_path),
            "name": profile.name,
            "version": profile.version,
            "element_count": len(profile.elements),
            "relation_count": len(profile.relations),
            "rule_count": len(profile.validity_rules),
        },
        "paths": {
            "kernel_src": str(kernel_src),
            "run_dir": str(run_dir),
        },
        "alignment": {
            "coverage_percent": alignment["coverage_percent"],
            "matched_element_count": alignment["matched_element_count"],
            "model_element_count": alignment["model_element_count"],
            "missing_elements": list(alignment["missing_elements"]),
            "unmapped_elements": list(alignment["unmapped_elements"]),
        },
        "registration": {
            "created": registration_created,
            "model_name": activated.model_name,
            "status": activated.status,
            "active_version_id": activated.active_version_id,
            "version_id": version_id,
            "register_validation_run_id": registration_run_id,
            "post_validation_run_id": validation.run_id,
            "post_validation_passed": validation.passed,
            "post_validation_error_count": len(validation.errors),
        },
        "runtime": {
            "raw_active_rule_count": len(raw_system.rule_store.active_rules()),
            "compiled_active_rule_count": len(compiled_system.rule_store.active_rules()),
            "checks": checks,
        },
        "compilation": compiled_stats,
        "issues": issues,
    }


def save_report(report: dict[str, Any], output_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
