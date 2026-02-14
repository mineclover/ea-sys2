"""CLI entrypoint for ea-kernel-self."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from ea_kernel_self.runner import run_self_check, save_report


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run practical self-checks for ea-kernel using a self profile.",
    )
    parser.add_argument(
        "--profile-path",
        type=Path,
        help="Path to kernel self profile TOML. Defaults to workspace kernel_self_profile.toml.",
    )
    parser.add_argument(
        "--kernel-src",
        type=Path,
        help="Path to ea_kernel source directory. Defaults to workspace packages/ea-kernel/src/ea_kernel.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Base directory where runtime artifacts (DB/report context) are created.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional output path for JSON report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when any issue is detected.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)

    report = run_self_check(
        profile_path=args.profile_path,
        kernel_src=args.kernel_src,
        work_dir=args.work_dir,
    )

    if args.output_json is not None:
        save_report(report, args.output_json)

    alignment = report["alignment"]
    registration = report["registration"]

    print(f"status={report['status']}")
    print(f"run_dir={report['paths']['run_dir']}")
    print(
        f"alignment={alignment['matched_element_count']}/{alignment['model_element_count']} "
        f"({alignment['coverage_percent']}%)"
    )
    print(
        f"registration=model:{registration['model_name']} status:{registration['status']} "
        f"post_validation_passed:{registration['post_validation_passed']}"
    )

    for check in report["runtime"]["checks"]:
        raw_verdict = check["raw"]["verdict"]
        compiled_verdict = check["compiled"]["verdict"]
        expected = check["expected"]
        print(
            f"check={check['name']} expected={expected} "
            f"raw={raw_verdict} compiled={compiled_verdict}"
        )

    if report["issues"]:
        print("issues:")
        for issue in report["issues"]:
            print(f"- [{issue['severity']}] {issue['code']}: {issue['message']}")

    if args.strict and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
