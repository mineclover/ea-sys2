"""Review alignment between kernel-self profile and ea-kernel implementation."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ea_kernel.profile_loader import load_profile
from ea_kernel.spec import KERNEL_SPEC

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_PATH = PACKAGE_ROOT / "examples" / "kernel_self_profile.toml"
DEFAULT_KERNEL_SRC = PACKAGE_ROOT / "src" / "ea_kernel"


@dataclass(frozen=True)
class EvidenceRule:
    file: str
    pattern: str
    description: str


EVIDENCE_RULES: dict[str, tuple[EvidenceRule, ...]] = {
    "KernelLayer": (
        EvidenceRule(
            file="spec.py",
            pattern=r"KERNEL_SPEC = build_validated_schema\(\)",
            description="Kernel validated spec object exists.",
        ),
    ),
    "KernelSpecBuilder": (
        EvidenceRule(
            file="spec.py",
            pattern=r"def build_validated_schema\(\)",
            description="Kernel spec builder function exists.",
        ),
    ),
    "KernelSchemaLoader": (
        EvidenceRule(
            file="definition.py",
            pattern=r"load_kernel_schema",
            description="Kernel schema loader wiring exists.",
        ),
    ),
    "KernelRuleSpecLoader": (
        EvidenceRule(
            file="spec_loader.py",
            pattern=r"def load_kernel_rules\(",
            description="Kernel rule loader function exists.",
        ),
    ),
    "KernelRuleCorpus": (
        EvidenceRule(
            file="rule_corpus.py",
            pattern=r"class RuleCorpus",
            description="RuleCorpus class exists.",
        ),
    ),
    "KernelRuleVerifier": (
        EvidenceRule(
            file="rule_verifier.py",
            pattern=r"class RuleVerifier",
            description="RuleVerifier class exists.",
        ),
    ),
    "KernelInstanceValidator": (
        EvidenceRule(
            file="instance_validator.py",
            pattern=r"class InstanceValidator",
            description="InstanceValidator class exists.",
        ),
    ),
    "KernelJudgmentService": (
        EvidenceRule(
            file="judgment_service.py",
            pattern=r"class JudgmentService",
            description="JudgmentService class exists.",
        ),
    ),
    "KernelProfileLoader": (
        EvidenceRule(
            file="profile_loader.py",
            pattern=r"def load_profile\(",
            description="Profile loader function exists.",
        ),
    ),
    "KernelProfileRegistry": (
        EvidenceRule(
            file="profile_registry.py",
            pattern=r"class ProfileRegistry",
            description="ProfileRegistry class exists.",
        ),
    ),
    "KernelModelRegistrationService": (
        EvidenceRule(
            file="model_registration.py",
            pattern=r"class KernelModelRegistrationService",
            description="Model registration service class exists.",
        ),
    ),
    "KernelGovernanceFacade": (
        EvidenceRule(
            file="governance.py",
            pattern=r"class GovernanceSystem",
            description="Governance facade class exists.",
        ),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review kernel-self model alignment with ea-kernel sources.",
    )
    parser.add_argument(
        "--profile-path",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help="Kernel self-profile TOML path.",
    )
    parser.add_argument(
        "--kernel-src",
        type=Path,
        default=DEFAULT_KERNEL_SRC,
        help="ea_kernel source root path.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output path for alignment report JSON.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any kernel-self element has no evidence.",
    )
    return parser.parse_args()


def _kernel_element_names(profile_path: Path) -> list[str]:
    profile = load_profile(profile_path, KERNEL_SPEC)
    names: list[str] = []
    for element in profile.elements:
        if element.layer.lower() == "kernel":
            names.append(element.name)
    names.sort()
    return names


def _find_lines(text: str, pattern: str) -> list[int]:
    regex = re.compile(pattern)
    lines: list[int] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if regex.search(line):
            lines.append(idx)
    return lines


def review_alignment(profile_path: Path, kernel_src: Path) -> dict[str, Any]:
    model_elements = _kernel_element_names(profile_path)
    detail: list[dict[str, Any]] = []
    missing_elements: list[str] = []
    unmapped_elements: list[str] = []

    for element_name in model_elements:
        rules = EVIDENCE_RULES.get(element_name)
        if rules is None:
            unmapped_elements.append(element_name)
            detail.append(
                {
                    "element": element_name,
                    "mapped": False,
                    "matched": False,
                    "rules": [],
                }
            )
            continue

        rule_results: list[dict[str, Any]] = []
        matched_any = False
        for rule in rules:
            target = kernel_src / rule.file
            if not target.exists():
                rule_results.append(
                    {
                        "file": rule.file,
                        "pattern": rule.pattern,
                        "description": rule.description,
                        "exists": False,
                        "lines": [],
                    }
                )
                continue

            content = target.read_text(encoding="utf-8")
            lines = _find_lines(content, rule.pattern)
            if lines:
                matched_any = True
            rule_results.append(
                {
                    "file": rule.file,
                    "pattern": rule.pattern,
                    "description": rule.description,
                    "exists": True,
                    "lines": lines,
                }
            )

        if not matched_any:
            missing_elements.append(element_name)
        detail.append(
            {
                "element": element_name,
                "mapped": True,
                "matched": matched_any,
                "rules": rule_results,
            }
        )

    matched_elements = [
        entry["element"] for entry in detail if entry.get("matched") is True
    ]
    report = {
        "profile_path": str(profile_path),
        "kernel_src": str(kernel_src),
        "model_element_count": len(model_elements),
        "matched_element_count": len(matched_elements),
        "coverage_percent": round(
            (len(matched_elements) / len(model_elements) * 100.0) if model_elements else 100.0,
            2,
        ),
        "missing_elements": missing_elements,
        "unmapped_elements": unmapped_elements,
        "details": detail,
    }
    return report


def render_console_report(report: dict[str, Any]) -> str:
    lines = [
        f"profile={report['profile_path']}",
        f"kernel_src={report['kernel_src']}",
        (
            f"coverage={report['matched_element_count']}/{report['model_element_count']} "
            f"({report['coverage_percent']}%)"
        ),
    ]

    missing = report["missing_elements"]
    unmapped = report["unmapped_elements"]
    if missing:
        lines.append("missing: " + ", ".join(sorted(missing)))
    if unmapped:
        lines.append("unmapped: " + ", ".join(sorted(unmapped)))
    if not missing and not unmapped:
        lines.append("status: aligned")

    for entry in report["details"]:
        mark = "ok" if entry["matched"] else "miss"
        lines.append(f"[{mark}] {entry['element']}")
        for rule in entry["rules"]:
            file_ref = rule["file"]
            found = ", ".join(str(line) for line in rule["lines"]) if rule["lines"] else "-"
            lines.append(f"  - {file_ref} :: {found}")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = review_alignment(args.profile_path, args.kernel_src)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(render_console_report(report))

    has_failure = bool(report["missing_elements"] or report["unmapped_elements"])
    if args.strict and has_failure:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
