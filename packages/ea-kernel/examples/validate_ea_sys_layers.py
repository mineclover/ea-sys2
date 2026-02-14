"""Validate EA system layer profiles independently (no merge/composition)."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
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

VALIDATION_LAYERS = ("infra", "governance", "decision", "needs", "kernel", "flow")
MODEL_DEFINITION_ORDER = ("infra", "decision", "needs", "kernel", "flow")
LAYER_DIR = Path(__file__).parent / "ea-sys"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate EA system layer TOML files independently."
    )
    parser.add_argument(
        "--layer",
        choices=("all", *VALIDATION_LAYERS),
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
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run static cross-layer data-flow simulation (no runtime execution).",
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


def _is_exact_pattern(pattern: str) -> bool:
    return pattern != "*" and not pattern.startswith("@") and not pattern.startswith("#")


def _matches_pattern(element: Any, pattern: str) -> bool:
    category = str(getattr(element, "category", ""))
    layer = str(getattr(element, "layer", ""))
    name = str(getattr(element, "name", ""))

    if pattern == "*":
        return True
    if pattern.startswith("@"):
        return category == pattern[1:]
    if pattern.startswith("#"):
        return layer == pattern[1:]
    return name == pattern


def _load_all_layer_profiles() -> dict[str, Any]:
    profiles: dict[str, Any] = {}
    for layer in VALIDATION_LAYERS:
        _, profile = _load_layer_profile(layer)
        profiles[layer] = profile
    return profiles


def _find_undefined_relations(profile: Any) -> list[str]:
    defined = {rel.name for rel in profile.relations}
    used = {rule.relationship_name for rule in profile.validity_rules}
    return sorted(used - defined)


def _build_flow_sequence(flow_profile: Any) -> list[str]:
    # Use explicit next edges only (ignore pattern rules such as @Behavior -> @Executable).
    exact_edges: list[tuple[str, str, int]] = []
    for rule in flow_profile.validity_rules:
        if rule.relationship_name != "next" or not rule.valid:
            continue
        if not _is_exact_pattern(rule.source_pattern) or not _is_exact_pattern(rule.target_pattern):
            continue
        exact_edges.append((rule.source_pattern, rule.target_pattern, rule.priority))

    if not exact_edges:
        return []

    # Prefer higher-priority edges if there are duplicate sources.
    exact_edges.sort(key=lambda x: x[2], reverse=True)
    next_by_source: dict[str, str] = {}
    for src, dst, _priority in exact_edges:
        if src not in next_by_source:
            next_by_source[src] = dst

    sources = set(next_by_source.keys())
    targets = set(next_by_source.values())
    starts = sorted(sources - targets) or sorted(sources)
    start = starts[0]

    visited: set[str] = set()
    sequence: list[str] = []
    current: str | None = start
    while current and current not in visited:
        visited.add(current)
        sequence.append(current)
        current = next_by_source.get(current)
    return sequence


def _collect_exact_relation_edges(
    profile: Any, relationship_name: str
) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = defaultdict(set)
    for rule in profile.validity_rules:
        if rule.relationship_name != relationship_name or not rule.valid:
            continue
        if not _is_exact_pattern(rule.source_pattern) or not _is_exact_pattern(rule.target_pattern):
            continue
        edges[rule.source_pattern].add(rule.target_pattern)
    return edges


def _pattern_has_layer_match(profile: Any, pattern: str, layer: str) -> bool:
    for elem in profile.elements:
        if _matches_pattern(elem, pattern) and str(getattr(elem, "layer", "")) == layer:
            return True
    return False


def simulate_data_flow() -> dict[str, Any]:
    """Simulate cross-layer data flow using static model relations only."""
    profiles = _load_all_layer_profiles()
    infra_profile = profiles["infra"]
    needs_profile = profiles["needs"]
    flow_profile = profiles["flow"]

    versions = {layer: profile.version for layer, profile in profiles.items()}
    relation_integrity_violations: dict[str, list[str]] = {}
    for layer, profile in profiles.items():
        undefined_relations = _find_undefined_relations(profile)
        if undefined_relations:
            relation_integrity_violations[layer] = undefined_relations

    sequence = _build_flow_sequence(flow_profile)
    consumes_by_data = _collect_exact_relation_edges(flow_profile, "consumes")
    produces_by_step = _collect_exact_relation_edges(flow_profile, "produces")

    # In flow rules, consumes is modeled as Data -> Step.
    consumes_by_step: dict[str, set[str]] = defaultdict(set)
    for data_name, step_names in consumes_by_data.items():
        for step_name in step_names:
            consumes_by_step[step_name].add(data_name)

    initial_data = {
        elem.name
        for elem in needs_profile.elements + infra_profile.elements
        if elem.category == "PassiveStructure"
    }
    available_data = set(initial_data)

    step_reports: list[dict[str, Any]] = []
    missing_inputs: list[tuple[str, str]] = []
    flow_local_policy_gaps: list[str] = []

    for step_name in sequence:
        flow_element = flow_profile.get_element(step_name)
        if flow_element is None:
            # Keep simulation robust to partial drafts.
            continue

        required = sorted(consumes_by_step.get(step_name, set()))
        missing = sorted(x for x in required if x not in available_data)
        produced = sorted(produces_by_step.get(step_name, set()))

        flow_local_constrained = any(
            rule.relationship_name == "constrains"
            and rule.valid
            and _matches_pattern(flow_element, rule.target_pattern)
            and _pattern_has_layer_match(flow_profile, rule.source_pattern, "Flow")
            for rule in flow_profile.validity_rules
        )

        if missing:
            missing_inputs.extend((step_name, data_name) for data_name in missing)
        if not flow_local_constrained:
            flow_local_policy_gaps.append(step_name)

        available_data.update(produced)
        step_reports.append(
            {
                "step": step_name,
                "required": required,
                "missing": missing,
                "produced": produced,
                "flow_local_constrained": flow_local_constrained,
            }
        )

    passed = (
        not relation_integrity_violations
        and not missing_inputs
        and not flow_local_policy_gaps
        and bool(sequence)
    )

    return {
        "passed": passed,
        "model_definition_order": list(MODEL_DEFINITION_ORDER),
        "governance_role": "layer-management-system",
        "governance_model_registered_targets": list(MODEL_DEFINITION_ORDER),
        "versions": versions,
        "independent_relation_integrity_ok": not relation_integrity_violations,
        "relation_integrity_violations": relation_integrity_violations,
        "flow_sequence": sequence,
        "initial_data": sorted(initial_data),
        "final_data": sorted(available_data),
        "step_reports": step_reports,
        "missing_inputs": missing_inputs,
        "flow_local_policy_gaps": flow_local_policy_gaps,
    }


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
        "source": "validate_ea_sys_layers",
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
    layers = VALIDATION_LAYERS if args.layer == "all" else (args.layer,)

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

    if args.simulate:
        report = simulate_data_flow()
        seq = " -> ".join(report["flow_sequence"]) if report["flow_sequence"] else "(none)"
        print(f"[sim] model-order: {' > '.join(report['model_definition_order'])}")
        print(f"[sim] governance-role: {report['governance_role']}")
        print(f"[sim] flow-sequence: {seq}")
        if report["relation_integrity_violations"]:
            for layer, rels in sorted(report["relation_integrity_violations"].items()):
                print(f"[sim][fail] relation-integrity layer={layer} undefined={','.join(rels)}")
        if report["missing_inputs"]:
            for step_name, data_name in report["missing_inputs"]:
                print(f"[sim][fail] missing-input step={step_name} data={data_name}")
        if report["flow_local_policy_gaps"]:
            print(
                "[sim][fail] flow-local-policy-gaps: "
                f"{','.join(sorted(set(report['flow_local_policy_gaps'])))}"
            )

        if report["passed"]:
            print("[sim] passed")
        else:
            failures += 1
            print("[sim] failed")

    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
