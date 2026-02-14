"""Validate Ralph TUI layer profiles independently (no merge/composition)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

LAYER_FILE_MAP = {
    "infra": "00-infra.toml",
    "governance": "10-governance.toml",
    "decision": "20-decision.toml",
    "needs": "30-needs.toml",
    "kernel": "40-kernel.toml",
    "flow": "50-flow.toml",
}

LAYERS_IN_ORDER = ("infra", "governance", "decision", "needs", "kernel", "flow")
LAYER_DIR = Path(__file__).parent / "ralph_tui_layers"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Ralph TUI layer TOML files independently."
    )
    parser.add_argument(
        "--layer",
        choices=("all", *LAYERS_IN_ORDER),
        default="all",
        help="Layer to validate (default: all).",
    )
    parser.add_argument(
        "--register",
        action="store_true",
        help="Register validated models into profiles DB.",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Activate model version after successful registration.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("profiles.db"),
        help="SQLite DB path for model registration (default: ./profiles.db).",
    )
    parser.add_argument(
        "--register-name-mode",
        choices=("layer", "profile"),
        default="layer",
        help="Model name mode for registration (default: layer).",
    )
    parser.add_argument(
        "--owner",
        default="kernel-team",
        help="Owner metadata for registered model.",
    )
    parser.add_argument(
        "--created-by",
        default="layer-validator",
        help="Actor metadata for registration/activation.",
    )
    return parser.parse_args()


def _load_runtime() -> tuple[Any, Any, Any, Any, Any]:
    package_root = Path(__file__).resolve().parents[1]
    kernel_src = package_root / "src"
    sys.path.insert(0, str(kernel_src))

    from ea_kernel.model_registration import (
        KernelModelRegistrationService,
        ModelRegistrationError,
    )
    from ea_kernel.profile_loader import load_profile
    from ea_kernel.profile_types import KernelProfile
    from ea_kernel.spec import KERNEL_SPEC

    return (
        load_profile,
        KERNEL_SPEC,
        KernelModelRegistrationService,
        ModelRegistrationError,
        KernelProfile,
    )


def _load_layer_profile(layer: str) -> tuple[Path, Any]:
    layer_file = LAYER_DIR / LAYER_FILE_MAP[layer]
    if not layer_file.exists():
        raise FileNotFoundError(f"Missing layer file: {layer_file}")

    load_profile, kernel_spec, _, _, _ = _load_runtime()
    profile = load_profile(layer_file, kernel_spec)
    return layer_file, profile


def _profile_with_name(profile: Any, model_name: str, kernel_profile_type: Any) -> Any:
    if profile.name == model_name:
        return profile
    return kernel_profile_type(
        name=model_name,
        version=profile.version,
        kernel_version=profile.kernel_version,
        elements=profile.elements,
        relations=profile.relations,
        validity_rules=profile.validity_rules,
        metadata=profile.metadata,
    )


def _build_model_name(profile_name: str, layer: str, mode: str) -> str:
    if mode == "profile":
        return profile_name
    return f"{profile_name}.{layer}"


def validate_layer(layer: str) -> tuple[str, int, int, int]:
    layer_file, profile = _load_layer_profile(layer)
    return (
        str(layer_file),
        len(profile.elements),
        len(profile.relations),
        len(profile.validity_rules),
    )


def register_layer(
    layer: str,
    *,
    db_path: Path,
    owner: str,
    created_by: str,
    name_mode: str,
    activate: bool,
) -> tuple[str, str, str, str]:
    layer_file, profile = _load_layer_profile(layer)
    (
        _load_profile,
        kernel_spec,
        registration_service_type,
        model_registration_error_type,
        kernel_profile_type,
    ) = _load_runtime()

    model_name = _build_model_name(profile.name, layer, name_mode)
    adjusted = _profile_with_name(profile, model_name, kernel_profile_type)
    service = registration_service_type(db_path, kernel_spec)

    context = {
        "source": "validate_ralph_tui_layers",
        "layer": layer,
        "file": str(layer_file),
        "name_mode": name_mode,
    }

    try:
        result = service.register(
            adjusted,
            owner=owner,
            created_by=created_by,
            context=context,
        )
        run_id = result.validation_run_id
        action = "registered"
    except model_registration_error_type as exc:
        if "already exists" not in str(exc):
            raise
        rerun = service.validate_registered(
            model_name,
            adjusted.version,
            context={**context, "mode": "reregister"},
        )
        run_id = rerun.run_id
        action = "validated-existing"

    if activate:
        service.activate(model_name, adjusted.version, actor=created_by)
        action = f"{action}+activated"

    return model_name, adjusted.version, run_id, action


def main() -> int:
    args = parse_args()
    layers = LAYERS_IN_ORDER if args.layer == "all" else (args.layer,)

    failures = 0
    for layer in layers:
        try:
            path, elements, relations, rules = validate_layer(layer)
            print(
                f"[ok] {layer:<11} {path} "
                f"(elements={elements}, relations={relations}, rules={rules})"
            )
            if args.register:
                model_name, version, run_id, action = register_layer(
                    layer,
                    db_path=args.db_path,
                    owner=args.owner,
                    created_by=args.created_by,
                    name_mode=args.register_name_mode,
                    activate=args.activate,
                )
                print(
                    f"[reg] {layer:<11} model={model_name} "
                    f"version={version} run={run_id} action={action}"
                )
        except Exception as exc:
            failures += 1
            print(f"[fail] {layer:<11} {exc}")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
