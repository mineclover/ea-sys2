"""Validate governance profile stack (meta-meta + system-specific profiles)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
KERNEL_SRC = PACKAGE_ROOT / "src"
if str(KERNEL_SRC) not in sys.path:
    sys.path.insert(0, str(KERNEL_SRC))

from ea_kernel.profiles.ea_sys import PROFILE_DIR as EA_SYS_PROFILE_DIR  # noqa: E402
from ea_kernel.profiles.governance_profile_stack import (  # noqa: E402
    PROFILE_DIR as GOVERNANCE_STACK_PROFILE_DIR,
)

PROFILE_STACK_FILES = {
    "meta": GOVERNANCE_STACK_PROFILE_DIR / "00-governance-meta-model.toml",
    "ea_sys": EA_SYS_PROFILE_DIR / "10-governance.toml",
    "external": GOVERNANCE_STACK_PROFILE_DIR / "20-external-governance.toml",
}

REQUIRED_META_ELEMENTS = {
    "GovernanceMetaBoundary",
    "GovernanceEntryPortContract",
    "ModelEndpointContract",
    "LayerModelPortContract",
    "GovernanceCoordinatorContract",
    "GovernancePolicyContract",
    "GovernanceStepContract",
    "GovernanceActionContract",
    "GovernanceEventContract",
    "RequestRecordContract",
    "ResponseRecordContract",
    "ApiErrorRecordContract",
    "TransactionRecordContract",
    "DecisionTraceRecordContract",
    "DecisionContextRecordContract",
    "DecisionEvidenceRecordContract",
    "DecisionOutcomeRecordContract",
    "EvidenceWarningRecordContract",
    "FeedbackLoopContract",
}

REQUIRED_META_RELATIONS = {
    "registers",
    "coordinates",
    "constrains",
    "consumes",
    "produces",
}

REQUIRED_META_CATEGORIES = {
    "Interface",
    "ActiveStructure",
    "Governance",
    "PassiveStructure",
    "Goal",
}

PURPOSE_GOALS = {
    "transparency": "TransparencyGoal",
    "consistency": "ConsistencyGoal",
    "traceability": "TraceabilityGoal",
    "evolvability": "EvolvabilityGoal",
}

META_PURPOSE_CONSTRAINT_TARGETS = {
    "transparency": {
        "ResponseRecordContract",
        "ApiErrorRecordContract",
        "DecisionTraceRecordContract",
    },
    "consistency": {
        "ModelEndpointContract",
        "LayerModelPortContract",
        "GovernanceCoordinatorContract",
    },
    "traceability": {
        "TransactionRecordContract",
        "DecisionTraceRecordContract",
        "EvidenceWarningRecordContract",
    },
    "evolvability": {
        "GovernancePolicyContract",
        "GovernanceStepContract",
    },
}

META_REQUIRED_EDGES = {
    ("ModelEndpointContract", "RequestRecordContract", "consumes"),
    ("ModelEndpointContract", "DecisionContextRecordContract", "consumes"),
    ("ModelEndpointContract", "DecisionEvidenceRecordContract", "consumes"),
    ("ModelEndpointContract", "ResponseRecordContract", "produces"),
    ("ModelEndpointContract", "DecisionOutcomeRecordContract", "produces"),
    ("GovernanceEventContract", "GovernanceStepContract", "triggers"),
    ("GovernanceStepContract", "GovernanceActionContract", "next"),
    ("GovernanceActionContract", "DecisionOutcomeRecordContract", "produces"),
    ("GovernanceStepContract", "FeedbackLoopContract", "next"),
    ("FeedbackLoopContract", "DecisionTraceRecordContract", "produces"),
}

EA_SYS_PURPOSE_EDGES = {
    "transparency": {
        ("ModelDecisionTraceEndpoint", "ModelDecisionTraceResponseRecord", "produces"),
        ("ModelDecisionTraceEndpoint", "ModelDecisionTraceExploreResponseRecord", "produces"),
        ("ModelDecisionTraceEndpoint", "ModelApiErrorRecord", "produces"),
    },
    "consistency": {
        ("GovernanceEntryPort", "ModelDecisionTraceEndpoint", "coordinates"),
        ("ModelDecisionTraceEndpoint", "LayerModelRegistry", "coordinates"),
        ("ModelDecisionTraceEndpoint", "VersionLifecycleManager", "coordinates"),
    },
    "traceability": {
        ("ModelDecisionTraceEndpoint", "ModelTransactionRecord", "produces"),
        ("ModelDecisionTraceEndpoint", "ModelEvidenceWarningRecord", "produces"),
        ("ModelDecisionTraceEndpoint", "ModelDecisionTraceQueryRecord", "consumes"),
    },
    "evolvability": {
        ("BoundaryPolicy", "ModelDecisionTraceEndpoint", "constrains"),
        ("BoundaryPolicy", "ModelDecisionTraceResponseRecord", "constrains"),
        ("BoundaryPolicy", "ModelDecisionTraceExploreResponseRecord", "constrains"),
    },
}

EXTERNAL_PURPOSE_EDGES = {
    "transparency": {
        ("ExternalDecisionTraceEndpoint", "ExternalDecisionTraceResponseRecord", "produces"),
        ("ExternalDecisionTraceEndpoint", "ExternalDecisionTraceExploreResponseRecord", "produces"),
        ("ExternalDecisionTraceEndpoint", "ExternalApiErrorRecord", "produces"),
    },
    "consistency": {
        ("PartnerGovernanceEntryPort", "ExternalDecisionTraceEndpoint", "coordinates"),
        ("ExternalDecisionTraceEndpoint", "ExternalLayerModelPort", "coordinates"),
        ("ExternalDecisionTraceEndpoint", "ExternalRegistryService", "coordinates"),
    },
    "traceability": {
        ("ExternalDecisionTraceEndpoint", "ExternalTransactionRecord", "produces"),
        ("ExternalDecisionTraceEndpoint", "ExternalEvidenceWarningRecord", "produces"),
        ("ExternalDecisionTraceEndpoint", "ExternalDecisionTraceQueryRecord", "consumes"),
    },
    "evolvability": {
        ("ExternalBoundaryPolicy", "ExternalDecisionTraceEndpoint", "constrains"),
        ("ExternalBoundaryPolicy", "ExternalDecisionTraceResponseRecord", "constrains"),
        ("ExternalBoundaryPolicy", "ExternalDecisionTraceExploreResponseRecord", "constrains"),
    },
}

EA_SYS_EXPECTED = {
    "entry_port": "GovernanceEntryPort",
    "trace_endpoint": "ModelDecisionTraceEndpoint",
    "trace_query_record": "ModelDecisionTraceQueryRecord",
    "trace_response_record": "ModelDecisionTraceResponseRecord",
    "trace_explore_record": "ModelDecisionTraceExploreResponseRecord",
    "trace_warning_record": "ModelEvidenceWarningRecord",
    "api_error_record": "ModelApiErrorRecord",
    "transaction_record": "ModelTransactionRecord",
}

EXTERNAL_EXPECTED = {
    "entry_port": "PartnerGovernanceEntryPort",
    "trace_endpoint": "ExternalDecisionTraceEndpoint",
    "trace_query_record": "ExternalDecisionTraceQueryRecord",
    "trace_response_record": "ExternalDecisionTraceResponseRecord",
    "trace_explore_record": "ExternalDecisionTraceExploreResponseRecord",
    "trace_warning_record": "ExternalEvidenceWarningRecord",
    "api_error_record": "ExternalApiErrorRecord",
    "transaction_record": "ExternalTransactionRecord",
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate governance profile stack contracts."
    )
    parser.add_argument(
        "--profile",
        choices=("all", "meta", "ea_sys", "external"),
        default="all",
        help="Profile to validate (default: all).",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run cross-profile compatibility simulation.",
    )
    return parser.parse_args()


def _load_runtime() -> tuple[Any, Any]:
    package_root = Path(__file__).resolve().parents[1]
    kernel_src = package_root / "src"
    if str(kernel_src) not in sys.path:
        sys.path.insert(0, str(kernel_src))

    from ea_kernel.profile_loader import load_profile
    from ea_kernel.spec import KERNEL_SPEC

    return load_profile, KERNEL_SPEC


def _load_profile(profile_id: str) -> tuple[Path, Any]:
    profile_path = PROFILE_STACK_FILES[profile_id].resolve()
    if not profile_path.exists():
        raise FileNotFoundError(f"Missing profile file: {profile_path}")

    load_profile, kernel_spec = _load_runtime()
    profile = load_profile(profile_path, kernel_spec)
    return profile_path, profile


def validate_profile(profile_id: str) -> tuple[str, int, int, int]:
    path, profile = _load_profile(profile_id)
    return (
        str(path),
        len(profile.elements),
        len(profile.relations),
        len(profile.validity_rules),
    )


def _collect_exact_edges(profile: Any, relation_name: str) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    for rule in profile.validity_rules:
        if rule.relationship_name != relation_name or not rule.valid:
            continue
        source = rule.source_pattern
        target = rule.target_pattern
        if source.startswith("@") or target.startswith("@"):
            continue
        if source.startswith("#") or target.startswith("#"):
            continue
        if source == "*" or target == "*":
            continue
        edges.add((source, target))
    return edges


def _collect_exact_edges_by_relation(profile: Any) -> set[tuple[str, str, str]]:
    edges: set[tuple[str, str, str]] = set()
    for rule in profile.validity_rules:
        if not rule.valid:
            continue
        source = rule.source_pattern
        target = rule.target_pattern
        if source.startswith("@") or target.startswith("@"):
            continue
        if source.startswith("#") or target.startswith("#"):
            continue
        if source == "*" or target == "*":
            continue
        edges.add((source, target, rule.relationship_name))
    return edges


def _collect_relation_names(profile: Any) -> set[str]:
    return {rel.name for rel in profile.relations}


def _collect_categories(profile: Any) -> set[str]:
    return {str(elem.category) for elem in profile.elements}


def _collect_element_names(profile: Any) -> set[str]:
    return {str(elem.name) for elem in profile.elements}


def _validate_meta_model(meta_profile: Any) -> list[str]:
    warnings: list[str] = []

    element_names = _collect_element_names(meta_profile)
    missing_elements = sorted(REQUIRED_META_ELEMENTS - element_names)
    if missing_elements:
        warnings.append(f"meta-missing-elements: {missing_elements}")

    relation_names = _collect_relation_names(meta_profile)
    missing_relations = sorted(REQUIRED_META_RELATIONS - relation_names)
    if missing_relations:
        warnings.append(f"meta-missing-relations: {missing_relations}")

    categories = _collect_categories(meta_profile)
    missing_categories = sorted(REQUIRED_META_CATEGORIES - categories)
    if missing_categories:
        warnings.append(f"meta-missing-categories: {missing_categories}")

    edges = _collect_exact_edges_by_relation(meta_profile)
    missing_edges = sorted(META_REQUIRED_EDGES - edges)
    if missing_edges:
        warnings.append(f"meta-missing-required-edges: {missing_edges}")

    element_names = _collect_element_names(meta_profile)
    constrains = _collect_exact_edges(meta_profile, "constrains")
    for purpose, goal_name in PURPOSE_GOALS.items():
        if goal_name not in element_names:
            warnings.append(f"meta-purpose-goal-missing: {goal_name}")
            continue

        expected_targets = META_PURPOSE_CONSTRAINT_TARGETS[purpose]
        actual_targets = {
            target
            for source, target in constrains
            if source == goal_name
        }
        missing_targets = sorted(expected_targets - actual_targets)
        if missing_targets:
            warnings.append(
                f"meta-purpose-coverage-missing purpose={purpose} "
                f"goal={goal_name} targets={missing_targets}"
            )

    return warnings


def _validate_profile_against_meta(
    profile_name: str,
    meta_profile: Any,
    impl_profile: Any,
    expected: dict[str, str],
) -> list[str]:
    warnings: list[str] = []

    meta_relations = _collect_relation_names(meta_profile)
    impl_relations = _collect_relation_names(impl_profile)
    missing_relations = sorted(meta_relations - impl_relations)
    if missing_relations:
        warnings.append(
            f"{profile_name}-relation-vocabulary-missing: {missing_relations}"
        )

    meta_categories = _collect_categories(meta_profile)
    impl_categories = _collect_categories(impl_profile)
    missing_categories = sorted(meta_categories - impl_categories)
    if missing_categories:
        warnings.append(f"{profile_name}-category-vocabulary-missing: {missing_categories}")

    element_names = _collect_element_names(impl_profile)
    missing_elements = sorted(
        element
        for element in expected.values()
        if element not in element_names
    )
    if missing_elements:
        warnings.append(f"{profile_name}-missing-required-elements: {missing_elements}")

    coordinates = _collect_exact_edges(impl_profile, "coordinates")
    consumes = _collect_exact_edges(impl_profile, "consumes")
    produces = _collect_exact_edges(impl_profile, "produces")
    constrains = _collect_exact_edges(impl_profile, "constrains")

    entry_to_trace = (expected["entry_port"], expected["trace_endpoint"])
    if entry_to_trace not in coordinates:
        warnings.append(
            f"{profile_name}-missing-entrypoint-routing: {entry_to_trace[0]} -> {entry_to_trace[1]}"
        )

    trace_query_edge = (expected["trace_endpoint"], expected["trace_query_record"])
    if trace_query_edge not in consumes:
        warnings.append(
            f"{profile_name}-missing-trace-query-consume: {trace_query_edge[0]} -> {trace_query_edge[1]}"
        )

    required_trace_outputs = {
        (expected["trace_endpoint"], expected["trace_response_record"]),
        (expected["trace_endpoint"], expected["trace_explore_record"]),
        (expected["trace_endpoint"], expected["trace_warning_record"]),
        (expected["trace_endpoint"], expected["api_error_record"]),
        (expected["trace_endpoint"], expected["transaction_record"]),
    }
    missing_trace_outputs = sorted(required_trace_outputs - produces)
    if missing_trace_outputs:
        warnings.append(
            f"{profile_name}-missing-trace-outputs: {missing_trace_outputs}"
        )

    has_boundary_constraint = any(
        target in {
            expected["trace_endpoint"],
            expected["trace_response_record"],
            expected["trace_explore_record"],
        }
        for _, target in constrains
    )
    if not has_boundary_constraint:
        warnings.append(f"{profile_name}-missing-boundary-constraints")

    return warnings


def _validate_profile_purpose_alignment(
    profile_name: str,
    impl_profile: Any,
    expected_edges: dict[str, set[tuple[str, str, str]]],
) -> list[str]:
    warnings: list[str] = []
    edges = _collect_exact_edges_by_relation(impl_profile)
    for purpose, required in expected_edges.items():
        missing = sorted(required - edges)
        if missing:
            warnings.append(
                f"{profile_name}-purpose-missing purpose={purpose} edges={missing}"
            )
    return warnings


def simulate_stack() -> dict[str, Any]:
    _, meta_profile = _load_profile("meta")
    _, ea_sys_profile = _load_profile("ea_sys")
    _, external_profile = _load_profile("external")

    meta_warnings = _validate_meta_model(meta_profile)
    ea_sys_warnings = _validate_profile_against_meta(
        "ea_sys",
        meta_profile,
        ea_sys_profile,
        EA_SYS_EXPECTED,
    )
    external_warnings = _validate_profile_against_meta(
        "external",
        meta_profile,
        external_profile,
        EXTERNAL_EXPECTED,
    )
    ea_sys_purpose_warnings = _validate_profile_purpose_alignment(
        "ea_sys",
        ea_sys_profile,
        EA_SYS_PURPOSE_EDGES,
    )
    external_purpose_warnings = _validate_profile_purpose_alignment(
        "external",
        external_profile,
        EXTERNAL_PURPOSE_EDGES,
    )

    all_warnings = [
        *meta_warnings,
        *ea_sys_warnings,
        *external_warnings,
        *ea_sys_purpose_warnings,
        *external_purpose_warnings,
    ]
    decision_trace_warnings = [
        warning
        for warning in all_warnings
        if "trace" in warning or "decision" in warning
    ]
    purpose_alignment_warnings = [
        warning
        for warning in all_warnings
        if "purpose" in warning or "goal" in warning
    ]

    return {
        "governance_meta_model": {
            "status": "passed" if not meta_warnings else "failed",
            "warnings": meta_warnings,
        },
        "ea_sys_governance_profile": {
            "status": "passed" if not ea_sys_warnings else "failed",
            "warnings": ea_sys_warnings,
        },
        "external_governance_profile": {
            "status": "passed" if not external_warnings else "failed",
            "warnings": external_warnings,
        },
        "decision_trace_contract": {
            "status": "passed" if not decision_trace_warnings else "failed",
            "warnings": decision_trace_warnings,
        },
        "purpose_alignment": {
            "status": "passed" if not purpose_alignment_warnings else "failed",
            "warnings": purpose_alignment_warnings,
        },
        "warnings": all_warnings,
        "passed": len(all_warnings) == 0,
    }


def main() -> int:
    args = parse_args()
    profile_ids = ("meta", "ea_sys", "external") if args.profile == "all" else (args.profile,)

    failed = False
    for profile_id in profile_ids:
        try:
            path, elements, relations, rules = validate_profile(profile_id)
            print(
                f"[ok] {profile_id:<8} {path} "
                f"(elements={elements}, relations={relations}, rules={rules})"
            )
        except Exception as err:  # pragma: no cover - CLI guard
            failed = True
            print(f"[error] {profile_id}: {err}")

    if args.simulate:
        try:
            report = simulate_stack()
        except Exception as err:  # pragma: no cover - CLI guard
            print(f"[sim] failed: {err}")
            return 1

        print(f"[sim] governance-meta-model: {report['governance_meta_model']['status']}")
        print(
            f"[sim] ea-sys-governance-profile: {report['ea_sys_governance_profile']['status']}"
        )
        print(
            f"[sim] external-governance-profile: {report['external_governance_profile']['status']}"
        )
        print(f"[sim] decision-trace-contract: {report['decision_trace_contract']['status']}")
        print(f"[sim] purpose-alignment: {report['purpose_alignment']['status']}")
        for warning in report["warnings"]:
            print(f"[sim][warn] {warning}")
        print(f"[sim] {'passed' if report['passed'] else 'failed'}")
        if not report["passed"]:
            return 1

    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
