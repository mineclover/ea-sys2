"""Review alignment between Ralph TUI kernel model and implementation sources."""

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
DEFAULT_PROFILE_PATH = PACKAGE_ROOT / "examples" / "ralph_tui_layers" / "40-kernel.toml"
DEFAULT_REFERENCE_ROOT = PACKAGE_ROOT.parents[1] / "reference"


@dataclass(frozen=True)
class EvidenceRule:
    file: str
    pattern: str
    description: str


EVIDENCE_RULES: dict[str, tuple[EvidenceRule, ...]] = {
    "KernelLayer": (
        EvidenceRule(
            file="src/index.ts",
            pattern=r"export \* from './commands/index\.js';",
            description="Top-level module exposes kernel command/runtime surface.",
        ),
    ),
    "CliEntryPoint": (
        EvidenceRule(
            file="src/cli.tsx",
            pattern=r"function handleSubcommand",
            description="CLI command dispatch exists.",
        ),
    ),
    "ExecutionEngine": (
        EvidenceRule(
            file="src/engine/index.ts",
            pattern=r"export class ExecutionEngine",
            description="Core execution engine class exists.",
        ),
    ),
    "ParallelExecutor": (
        EvidenceRule(
            file="src/parallel/index.ts",
            pattern=r"export class ParallelExecutor",
            description="Parallel executor class exists.",
        ),
    ),
    "AgentRegistry": (
        EvidenceRule(
            file="src/plugins/agents/registry.ts",
            pattern=r"export class AgentRegistry",
            description="Agent plugin registry exists.",
        ),
    ),
    "TrackerRegistry": (
        EvidenceRule(
            file="src/plugins/trackers/registry.ts",
            pattern=r"export class TrackerRegistry",
            description="Tracker plugin registry exists.",
        ),
    ),
    "ConfigManager": (
        EvidenceRule(
            file="src/config/index.ts",
            pattern=r"export async function buildConfig",
            description="Config builder exists.",
        ),
        EvidenceRule(
            file="src/config/index.ts",
            pattern=r"export async function validateConfig",
            description="Config validator exists.",
        ),
    ),
    "SessionManager": (
        EvidenceRule(
            file="src/session/index.ts",
            pattern=r"export async function createSession",
            description="Session creation function exists.",
        ),
        EvidenceRule(
            file="src/session/index.ts",
            pattern=r"export async function checkSession",
            description="Session status check function exists.",
        ),
    ),
    "PromptTemplateEngine": (
        EvidenceRule(
            file="src/templates/engine.ts",
            pattern=r"export function renderPrompt",
            description="Prompt rendering function exists.",
        ),
    ),
    "RateLimitDetector": (
        EvidenceRule(
            file="src/engine/rate-limit-detector.ts",
            pattern=r"export class RateLimitDetector",
            description="Rate limit detector exists.",
        ),
    ),
    "StructuredLogger": (
        EvidenceRule(
            file="src/logs/structured-logger.ts",
            pattern=r"export class StructuredLogger",
            description="Structured logger exists.",
        ),
    ),
    "RemoteServer": (
        EvidenceRule(
            file="src/remote/server.ts",
            pattern=r"export class RemoteServer",
            description="Remote server class exists.",
        ),
    ),
    "TuiRuntime": (
        EvidenceRule(
            file="src/tui/components/RunApp.tsx",
            pattern=r"export interface RunAppProps",
            description="TUI runtime component contract exists.",
        ),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review Ralph TUI kernel-model to implementation alignment.",
    )
    parser.add_argument(
        "--profile-path",
        type=Path,
        default=DEFAULT_PROFILE_PATH,
        help="Kernel layer TOML model path.",
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        default=DEFAULT_REFERENCE_ROOT,
        help="Ralph TUI repository root (contains src/).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output path for alignment report JSON.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if any kernel element has no evidence.",
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


def review_alignment(profile_path: Path, reference_root: Path) -> dict[str, Any]:
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
            target = reference_root / rule.file
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
        "reference_root": str(reference_root),
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
        f"reference={report['reference_root']}",
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
    report = review_alignment(args.profile_path, args.reference_root)

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
