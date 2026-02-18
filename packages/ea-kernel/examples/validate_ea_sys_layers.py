"""Validate EA system layer profiles independently (no merge/composition)."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

LAYER_FILE_MAP = {
    "infra": "00-infra.toml",
    "governance": "10-governance.toml",
    "decision": "20-decision.toml",
    "needs": "30-needs.toml",
    "kernel": "40-kernel.toml",
    "flow": "50-flow.toml",
    "projection": "70-projection.toml",
}

VALIDATION_LAYERS = ("infra", "governance", "decision", "needs", "kernel", "flow", "projection")
MODEL_DEFINITION_ORDER = ("infra", "decision", "needs", "kernel", "flow", "projection")
ENTRYPOINT_ORDER = ("decision", "needs", "kernel", "flow")
INFRA_ROLE = "row-data-design"
GOVERNANCE_ROLE = "system-entrypoint-design"
LAYER_PORTS = {
    "infra": "InfraModelPort",
    "governance": "GovernanceModelPort",
    "decision": "DecisionModelPort",
    "needs": "NeedsModelPort",
    "kernel": "KernelModelPort",
    "flow": "FlowModelPort",
    "projection": "ProjectionModelPort",
}
FLOW_6X6_MATRIX_ELEMENT = "FlowLayerContractMatrix"
FLOW_6X6_OWNER = "PersistFlowStateStep"
EXPECTED_ENTRYPOINT_START_TARGET = "DecisionModelPort"
EXPECTED_RUNTIME_ENTRYPOINT_COORDINATES = (
    ("DecisionModelPort", "NeedsModelPort"),
    ("NeedsModelPort", "KernelModelPort"),
    ("KernelModelPort", "FlowModelPort"),
)
MODEL_API_ENDPOINTS = (
    "ModelRegisterEndpoint",
    "ModelValidateEndpoint",
    "ModelActivateEndpoint",
    "ModelStateEndpoint",
)
MODEL_API_RECORDS = (
    "ModelRegisterRequestRecord",
    "ModelRegisterResponseRecord",
    "ModelValidateRequestRecord",
    "ModelValidateResponseRecord",
    "ModelActivateRequestRecord",
    "ModelActivateResponseRecord",
    "ModelStateQueryRecord",
    "ModelStateResponseRecord",
    "ModelApiErrorRecord",
    "ModelTransactionRecord",
)
EXPECTED_MODEL_API_ENTRYPOINT_COORDINATES = tuple(
    ("GovernanceEntryPort", endpoint) for endpoint in MODEL_API_ENDPOINTS
)
EXPECTED_MODEL_API_PORT_COORDINATES = tuple(
    (endpoint, "KernelModelPort") for endpoint in MODEL_API_ENDPOINTS
)
EXPECTED_MODEL_API_SERVICE_COORDINATES = (
    ("ModelRegisterEndpoint", "LayerModelRegistry"),
    ("ModelRegisterEndpoint", "ValidationCoordinator"),
    ("ModelRegisterEndpoint", "AgreementCoordinator"),
    ("ModelValidateEndpoint", "ValidationCoordinator"),
    ("ModelActivateEndpoint", "ActivationCoordinator"),
    ("ModelActivateEndpoint", "VersionLifecycleManager"),
    ("ModelStateEndpoint", "LayerModelRegistry"),
    ("ModelStateEndpoint", "VersionLifecycleManager"),
)
EXPECTED_MODEL_API_CONSUMES = (
    ("ModelRegisterEndpoint", "ModelRegisterRequestRecord"),
    ("ModelValidateEndpoint", "ModelValidateRequestRecord"),
    ("ModelActivateEndpoint", "ModelActivateRequestRecord"),
    ("ModelStateEndpoint", "ModelStateQueryRecord"),
)
EXPECTED_MODEL_API_PRODUCES = (
    ("ModelRegisterEndpoint", "ModelRegisterResponseRecord"),
    ("ModelRegisterEndpoint", "ModelRegistrationRequestedEvent"),
    ("ModelRegisterEndpoint", "ModelApiErrorRecord"),
    ("ModelRegisterEndpoint", "ModelTransactionRecord"),
    ("ModelValidateEndpoint", "ModelValidateResponseRecord"),
    ("ModelValidateEndpoint", "ValidationPassedEvent"),
    ("ModelValidateEndpoint", "ValidationFailedEvent"),
    ("ModelValidateEndpoint", "ModelApiErrorRecord"),
    ("ModelValidateEndpoint", "ModelTransactionRecord"),
    ("ModelActivateEndpoint", "ModelActivateResponseRecord"),
    ("ModelActivateEndpoint", "ActivationApprovedEvent"),
    ("ModelActivateEndpoint", "ModelApiErrorRecord"),
    ("ModelActivateEndpoint", "ModelTransactionRecord"),
    ("ModelStateEndpoint", "ModelStateResponseRecord"),
    ("ModelStateEndpoint", "ModelApiErrorRecord"),
    ("ModelStateEndpoint", "ModelTransactionRecord"),
)
LAYER_DIR = Path(__file__).resolve().parents[1] / "src" / "ea_kernel" / "profiles" / "ea_sys"
DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
SYSTEM_SPEC_LAYERS_PATH = DOCS_DIR / "system_spec_layers.md"
LAYER_README_PATH = LAYER_DIR / "README.md"


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


def _validate_governance_entrypoint(governance_profile: Any) -> dict[str, Any]:
    element_names = {elem.name for elem in governance_profile.elements}
    expected_ports = set(LAYER_PORTS.values())
    expected_registry_targets = {"GovernanceEntryPort", *expected_ports}

    missing_ports = sorted(expected_ports - element_names)
    missing_entry_port = "GovernanceEntryPort" not in element_names

    registers = _collect_exact_relation_edges(governance_profile, "registers")
    registry_targets = registers.get("LayerModelRegistry", set())
    missing_registry_targets = sorted(expected_registry_targets - registry_targets)

    coordinates = _collect_exact_relation_edges(governance_profile, "coordinates")
    entrypoint_targets = coordinates.get("GovernanceEntryPort", set())
    missing_entrypoint_routing = (
        []
        if EXPECTED_ENTRYPOINT_START_TARGET in entrypoint_targets
        else [EXPECTED_ENTRYPOINT_START_TARGET]
    )

    coordinate_pairs = {
        (src, dst)
        for src, targets in coordinates.items()
        for dst in targets
    }
    missing_model_definition_coordinates = sorted(
        f"{src}->{dst}"
        for (src, dst) in EXPECTED_RUNTIME_ENTRYPOINT_COORDINATES
        if (src, dst) not in coordinate_pairs
    )

    passed = (
        not missing_ports
        and not missing_entry_port
        and not missing_registry_targets
        and not missing_entrypoint_routing
        and not missing_model_definition_coordinates
    )

    return {
        "passed": passed,
        "missing_ports": missing_ports,
        "missing_entry_port": missing_entry_port,
        "missing_registry_targets": missing_registry_targets,
        "missing_entrypoint_routing": missing_entrypoint_routing,
        "missing_model_definition_coordinates": missing_model_definition_coordinates,
        "registered_targets": sorted(registry_targets),
        "entrypoint_targets": sorted(entrypoint_targets),
    }


def _missing_exact_pairs(
    expected_pairs: tuple[tuple[str, str], ...],
    actual_pairs: set[tuple[str, str]],
) -> list[str]:
    return sorted(
        f"{source}->{target}"
        for (source, target) in expected_pairs
        if (source, target) not in actual_pairs
    )


def _validate_governance_model_api_contract(governance_profile: Any) -> dict[str, Any]:
    element_names = {elem.name for elem in governance_profile.elements}
    missing_endpoints = sorted(set(MODEL_API_ENDPOINTS) - element_names)
    missing_records = sorted(set(MODEL_API_RECORDS) - element_names)

    coordinates = _collect_exact_relation_edges(governance_profile, "coordinates")
    coordinate_pairs = {
        (source, target)
        for source, targets in coordinates.items()
        for target in targets
    }
    missing_entrypoint_coordinates = _missing_exact_pairs(
        EXPECTED_MODEL_API_ENTRYPOINT_COORDINATES,
        coordinate_pairs,
    )
    missing_port_coordinates = _missing_exact_pairs(
        EXPECTED_MODEL_API_PORT_COORDINATES,
        coordinate_pairs,
    )
    missing_service_coordinates = _missing_exact_pairs(
        EXPECTED_MODEL_API_SERVICE_COORDINATES,
        coordinate_pairs,
    )

    consumes = _collect_exact_relation_edges(governance_profile, "consumes")
    consume_pairs = {
        (source, target)
        for source, targets in consumes.items()
        for target in targets
    }
    missing_consumes = _missing_exact_pairs(EXPECTED_MODEL_API_CONSUMES, consume_pairs)

    produces = _collect_exact_relation_edges(governance_profile, "produces")
    produce_pairs = {
        (source, target)
        for source, targets in produces.items()
        for target in targets
    }
    missing_produces = _missing_exact_pairs(EXPECTED_MODEL_API_PRODUCES, produce_pairs)

    passed = (
        not missing_endpoints
        and not missing_records
        and not missing_entrypoint_coordinates
        and not missing_port_coordinates
        and not missing_service_coordinates
        and not missing_consumes
        and not missing_produces
    )

    return {
        "passed": passed,
        "missing_endpoints": missing_endpoints,
        "missing_records": missing_records,
        "missing_entrypoint_coordinates": missing_entrypoint_coordinates,
        "missing_port_coordinates": missing_port_coordinates,
        "missing_service_coordinates": missing_service_coordinates,
        "missing_consumes": missing_consumes,
        "missing_produces": missing_produces,
    }


def _validate_layer_6x6_contract(layer: str, profile: Any) -> dict[str, Any]:
    expected_ports = set(LAYER_PORTS.values())
    element_names = {element.name for element in profile.elements}
    missing_ports = sorted(expected_ports - element_names)
    if layer != "flow":
        return {
            "passed": not missing_ports,
            "mode": "declaration",
            "missing_ports": missing_ports,
        }

    owner = FLOW_6X6_OWNER
    matrix_element = FLOW_6X6_MATRIX_ELEMENT
    missing_owner = owner not in element_names
    missing_matrix_element = matrix_element not in element_names

    coordinates = _collect_exact_relation_edges(profile, "coordinates")
    coordinate_pairs = {
        (source, target)
        for source, targets in coordinates.items()
        for target in targets
    }
    expected_owner_coordinates = tuple((owner, port) for port in sorted(expected_ports))
    missing_owner_coordinates = _missing_exact_pairs(expected_owner_coordinates, coordinate_pairs)

    produces = _collect_exact_relation_edges(profile, "produces")
    produce_pairs = {
        (source, target)
        for source, targets in produces.items()
        for target in targets
    }
    missing_matrix_produce = _missing_exact_pairs(((owner, matrix_element),), produce_pairs)

    passed = (
        not missing_owner
        and not missing_matrix_element
        and not missing_ports
        and not missing_owner_coordinates
        and not missing_matrix_produce
    )

    return {
        "passed": passed,
        "mode": "owner",
        "owner": owner,
        "matrix_element": matrix_element,
        "missing_owner": missing_owner,
        "missing_matrix_element": missing_matrix_element,
        "missing_ports": missing_ports,
        "missing_owner_coordinates": missing_owner_coordinates,
        "missing_matrix_produce": missing_matrix_produce,
    }


def _most_common_value(values: dict[str, Any]) -> Any:
    counts = Counter(values.values())
    top_count = max(counts.values())
    candidates = sorted(value for value, count in counts.items() if count == top_count)
    return candidates[0]


def _relation_signature(profile: Any) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    for rel in profile.relations:
        rows.append((rel.name, rel.kernel_relation, rel.direction or ""))
    return tuple(sorted(rows))


def _format_relation_rows(rows: list[tuple[str, str, str]]) -> str:
    return ",".join(
        f"{name}:{kernel}:{direction if direction else '-'}"
        for name, kernel, direction in rows
    )


def _collect_common_spec_warnings(profiles: dict[str, Any]) -> dict[str, Any]:
    layer_to_profile_version = {layer: profile.version for layer, profile in profiles.items()}
    layer_to_kernel_version = {layer: profile.kernel_version for layer, profile in profiles.items()}
    layer_to_relation_signature = {
        layer: _relation_signature(profile) for layer, profile in profiles.items()
    }

    expected_profile_version = _most_common_value(layer_to_profile_version)
    expected_kernel_version = _most_common_value(layer_to_kernel_version)
    expected_relation_signature = _most_common_value(layer_to_relation_signature)

    warnings: list[str] = []

    for layer in sorted(profiles):
        profile_version = layer_to_profile_version[layer]
        if profile_version != expected_profile_version:
            warnings.append(
                "profile-version-drift "
                f"layer={layer} value={profile_version} expected={expected_profile_version}"
            )

    for layer in sorted(profiles):
        kernel_version = layer_to_kernel_version[layer]
        if kernel_version != expected_kernel_version:
            warnings.append(
                "kernel-version-drift "
                f"layer={layer} value={kernel_version} expected={expected_kernel_version}"
            )

    expected_relations = set(expected_relation_signature)
    for layer in sorted(profiles):
        actual_relations = set(layer_to_relation_signature[layer])
        extras = sorted(actual_relations - expected_relations)
        missing = sorted(expected_relations - actual_relations)
        if extras:
            warnings.append(
                "relation-spec-extra "
                f"layer={layer} values={_format_relation_rows(extras)}"
            )
        if missing:
            warnings.append(
                "relation-spec-missing "
                f"layer={layer} values={_format_relation_rows(missing)}"
            )

    return {
        "status": "ok" if not warnings else "warning",
        "warnings": warnings,
        "expected_profile_version": expected_profile_version,
        "expected_kernel_version": expected_kernel_version,
        "expected_relations": [
            {
                "name": name,
                "kernel_relation": kernel_relation,
                "direction": direction,
            }
            for name, kernel_relation, direction in expected_relation_signature
        ],
    }


def _normalize_role_text(text: str) -> str:
    lowered = text.strip().lower()
    lowered = lowered.replace("`", "")
    lowered = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _load_system_spec_layer_roles(path: Path = SYSTEM_SPEC_LAYERS_PATH) -> tuple[dict[str, str], list[str]]:
    if not path.exists():
        return {}, [f"system-spec-missing path={path}"]

    content = path.read_text(encoding="utf-8")
    roles: dict[str, str] = {}
    warnings: list[str] = []

    table_pattern = re.compile(
        r"^\|\s*\*\*(Infra|Decision|Needs|Kernel|Flow)\*\*\s*\|\s*([^|]+?)\s*\|",
        re.MULTILINE,
    )
    for match in table_pattern.finditer(content):
        layer = match.group(1).lower()
        responsibility = match.group(2).strip()
        roles[layer] = responsibility

    governance_pattern = re.compile(r"^`Governance`는\s*(.+?)\.\s*$", re.MULTILINE)
    governance_match = governance_pattern.search(content)
    if governance_match:
        roles["governance"] = governance_match.group(1).strip()
    else:
        warnings.append("system-spec-missing-governance-role")

    for layer in VALIDATION_LAYERS:
        if layer not in roles:
            warnings.append(f"system-spec-missing-layer-role layer={layer}")
    return roles, warnings


def _load_toml_header_roles() -> tuple[dict[str, str], list[str]]:
    roles: dict[str, str] = {}
    warnings: list[str] = []

    role_pattern = re.compile(r"^#\s*Role:\s*(.+)$")
    for layer, filename in LAYER_FILE_MAP.items():
        path = LAYER_DIR / filename
        if not path.exists():
            warnings.append(f"toml-file-missing layer={layer} path={path}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        role_text = None
        for line in lines[:20]:
            match = role_pattern.match(line.strip())
            if match:
                role_text = match.group(1).strip()
                break
        if role_text is None:
            warnings.append(f"toml-role-comment-missing layer={layer} path={path}")
            continue
        roles[layer] = role_text

    return roles, warnings


def _load_readme_layer_roles(path: Path = LAYER_README_PATH) -> tuple[dict[str, str], list[str]]:
    if not path.exists():
        return {}, [f"layer-readme-missing path={path}"]

    content = path.read_text(encoding="utf-8")
    roles: dict[str, str] = {}
    warnings: list[str] = []

    bullet_pattern = re.compile(
        r"^- `\d{2}-(infra|governance|decision|needs|kernel|flow)\.toml` - (.+)$",
        re.MULTILINE,
    )
    for match in bullet_pattern.finditer(content):
        layer = match.group(1)
        role_text = match.group(2).strip()
        roles[layer] = role_text

    for layer in VALIDATION_LAYERS:
        if layer not in roles:
            warnings.append(f"readme-layer-role-missing layer={layer}")

    return roles, warnings


def _collect_layer_role_sync_warnings() -> dict[str, Any]:
    expected_roles, expected_parse_warnings = _load_system_spec_layer_roles()
    toml_roles, toml_parse_warnings = _load_toml_header_roles()
    readme_roles, readme_parse_warnings = _load_readme_layer_roles()

    warnings = [
        *expected_parse_warnings,
        *toml_parse_warnings,
        *readme_parse_warnings,
    ]

    for layer in VALIDATION_LAYERS:
        expected = expected_roles.get(layer)
        if expected is None:
            continue

        toml_role = toml_roles.get(layer)
        if toml_role is None:
            warnings.append(f"toml-role-missing layer={layer}")
        elif _normalize_role_text(toml_role) != _normalize_role_text(expected):
            warnings.append(
                "toml-role-drift "
                f"layer={layer} expected={expected!r} actual={toml_role!r}"
            )

        readme_role = readme_roles.get(layer)
        if readme_role is None:
            warnings.append(f"readme-role-missing layer={layer}")
        elif _normalize_role_text(readme_role) != _normalize_role_text(expected):
            warnings.append(
                "readme-role-drift "
                f"layer={layer} expected={expected!r} actual={readme_role!r}"
            )

    return {
        "status": "ok" if not warnings else "warning",
        "warnings": warnings,
        "expected_roles": expected_roles,
        "toml_roles": toml_roles,
        "readme_roles": readme_roles,
    }


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
    governance_profile = profiles["governance"]

    versions = {layer: profile.version for layer, profile in profiles.items()}
    governance_entrypoint = _validate_governance_entrypoint(governance_profile)
    governance_model_api_contract = _validate_governance_model_api_contract(governance_profile)
    layer_6x6_contracts = {
        layer: _validate_layer_6x6_contract(layer, profile)
        for layer, profile in profiles.items()
    }
    common_spec_audit = _collect_common_spec_warnings(profiles)
    layer_role_sync = _collect_layer_role_sync_warnings()
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
        and governance_entrypoint["passed"]
        and governance_model_api_contract["passed"]
        and all(result["passed"] for result in layer_6x6_contracts.values())
    )

    return {
        "passed": passed,
        "model_definition_order": list(MODEL_DEFINITION_ORDER),
        "entrypoint_order": list(ENTRYPOINT_ORDER),
        # Backward compatibility key for earlier consumers.
        "governance_entrypoint_order": list(ENTRYPOINT_ORDER),
        "infra_role": INFRA_ROLE,
        "governance_role": GOVERNANCE_ROLE,
        "governance_model_registered_targets": governance_entrypoint["registered_targets"],
        "governance_entrypoint": governance_entrypoint,
        "governance_model_api_contract": governance_model_api_contract,
        "layer_6x6_contracts": layer_6x6_contracts,
        "common_spec_audit": common_spec_audit,
        "layer_role_sync": layer_role_sync,
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
        print(f"[sim] infra-role: {report['infra_role']}")
        print(f"[sim] governance-role: {report['governance_role']}")
        print(f"[sim] entrypoint-order: {' > '.join(report['entrypoint_order'])}")
        entry_status = "passed" if report["governance_entrypoint"]["passed"] else "failed"
        print(f"[sim] governance-entrypoint: {entry_status}")
        model_api_status = "passed" if report["governance_model_api_contract"]["passed"] else "failed"
        print(f"[sim] governance-model-api-contract: {model_api_status}")
        layer_6x6_status = (
            "passed"
            if all(result["passed"] for result in report["layer_6x6_contracts"].values())
            else "failed"
        )
        print(f"[sim] layer-6x6-contract: {layer_6x6_status}")
        print("[sim] layer-6x6-owner: flow")
        print(f"[sim] common-layer-spec: {report['common_spec_audit']['status']}")
        print(f"[sim] layer-role-sync: {report['layer_role_sync']['status']}")
        print(f"[sim] flow-sequence: {seq}")
        for warning in report["common_spec_audit"]["warnings"]:
            print(f"[sim][warn] common-layer-spec: {warning}")
        for warning in report["layer_role_sync"]["warnings"]:
            print(f"[sim][warn] layer-role-sync: {warning}")
        if report["governance_entrypoint"]["missing_ports"]:
            print(
                "[sim][fail] governance-missing-ports: "
                f"{','.join(report['governance_entrypoint']['missing_ports'])}"
            )
        if report["governance_entrypoint"]["missing_entry_port"]:
            print("[sim][fail] governance-missing-entry-port: GovernanceEntryPort")
        if report["governance_entrypoint"]["missing_registry_targets"]:
            print(
                "[sim][fail] governance-missing-registry-targets: "
                f"{','.join(report['governance_entrypoint']['missing_registry_targets'])}"
            )
        if report["governance_entrypoint"]["missing_entrypoint_routing"]:
            print(
                "[sim][fail] governance-missing-entry-routing: "
                f"{','.join(report['governance_entrypoint']['missing_entrypoint_routing'])}"
            )
        if report["governance_entrypoint"]["missing_model_definition_coordinates"]:
            print(
                "[sim][fail] governance-missing-model-flow: "
                f"{','.join(report['governance_entrypoint']['missing_model_definition_coordinates'])}"
            )
        if report["governance_model_api_contract"]["missing_endpoints"]:
            print(
                "[sim][fail] governance-model-api-missing-endpoints: "
                f"{','.join(report['governance_model_api_contract']['missing_endpoints'])}"
            )
        if report["governance_model_api_contract"]["missing_records"]:
            print(
                "[sim][fail] governance-model-api-missing-records: "
                f"{','.join(report['governance_model_api_contract']['missing_records'])}"
            )
        if report["governance_model_api_contract"]["missing_entrypoint_coordinates"]:
            print(
                "[sim][fail] governance-model-api-missing-entry-routing: "
                f"{','.join(report['governance_model_api_contract']['missing_entrypoint_coordinates'])}"
            )
        if report["governance_model_api_contract"]["missing_port_coordinates"]:
            print(
                "[sim][fail] governance-model-api-missing-port-routing: "
                f"{','.join(report['governance_model_api_contract']['missing_port_coordinates'])}"
            )
        if report["governance_model_api_contract"]["missing_service_coordinates"]:
            print(
                "[sim][fail] governance-model-api-missing-service-routing: "
                f"{','.join(report['governance_model_api_contract']['missing_service_coordinates'])}"
            )
        if report["governance_model_api_contract"]["missing_consumes"]:
            print(
                "[sim][fail] governance-model-api-missing-consumes: "
                f"{','.join(report['governance_model_api_contract']['missing_consumes'])}"
            )
        if report["governance_model_api_contract"]["missing_produces"]:
            print(
                "[sim][fail] governance-model-api-missing-produces: "
                f"{','.join(report['governance_model_api_contract']['missing_produces'])}"
            )
        for layer_name, contract in sorted(report["layer_6x6_contracts"].items()):
            if contract["passed"]:
                continue
            if contract["missing_ports"]:
                print(
                    f"[sim][fail] layer-6x6-missing-ports layer={layer_name} "
                    f"ports={','.join(contract['missing_ports'])}"
                )
            if contract.get("mode") != "owner":
                continue
            if contract["missing_owner"]:
                print(
                    f"[sim][fail] layer-6x6-missing-owner layer={layer_name} "
                    f"owner={contract['owner']}"
                )
            if contract["missing_matrix_element"]:
                print(
                    f"[sim][fail] layer-6x6-missing-matrix layer={layer_name} "
                    f"matrix={contract['matrix_element']}"
                )
            if contract["missing_owner_coordinates"]:
                print(
                    f"[sim][fail] layer-6x6-missing-coordinates layer={layer_name} "
                    f"pairs={','.join(contract['missing_owner_coordinates'])}"
                )
            if contract["missing_matrix_produce"]:
                print(
                    f"[sim][fail] layer-6x6-missing-matrix-produce layer={layer_name} "
                    f"pairs={','.join(contract['missing_matrix_produce'])}"
                )
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
