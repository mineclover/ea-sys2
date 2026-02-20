"""Static validator for M2 profile metadata consistency."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from fnmatch import fnmatchcase

from ea_profile.types import KernelProfile

_STATE_ALIAS_SUFFIX_RE = re.compile(
    r"(?:status|state)([A-Za-z0-9_]+)$",
    flags=re.IGNORECASE,
)
_STATE_ALIAS_SPLIT_RE = re.compile(r"[_\-\s]+")
_CAMEL_CASE_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+")
_STATE_ALIAS_CATEGORIES = frozenset({"Goal", "Context", "State"})


@dataclass(frozen=True)
class ProfileValidationResult:
    """Aggregate result for M2 profile metadata validation."""

    passed: bool
    state_transition_errors: tuple[str, ...] = ()
    artifact_type_errors: tuple[str, ...] = ()
    layer_stack_errors: tuple[str, ...] = ()
    process_unit_errors: tuple[str, ...] = ()

    @property
    def errors(self) -> tuple[str, ...]:
        return (
            self.state_transition_errors
            + self.artifact_type_errors
            + self.layer_stack_errors
            + self.process_unit_errors
        )


def validate_state_transitions(profile: KernelProfile) -> tuple[str, ...]:
    """Validate that state transition references resolve to profile elements."""

    known_state_tokens = _collect_known_state_tokens(profile)
    errors: list[str] = []

    for transition in profile.state_transitions:
        from_state = _normalize_state_token(transition.from_state)
        to_state = _normalize_state_token(transition.to_state)

        if transition.from_state != "*" and from_state not in known_state_tokens:
            errors.append(
                "State transition references unknown from_state "
                f"'{transition.from_state}'"
            )
        if transition.to_state != "*" and to_state not in known_state_tokens:
            errors.append(
                "State transition references unknown to_state "
                f"'{transition.to_state}'"
            )

    return tuple(errors)


def validate_artifact_types(profile: KernelProfile) -> tuple[str, ...]:
    """Validate that artifact type kernel patterns match profile elements."""

    errors: list[str] = []

    for artifact_type in profile.artifact_types:
        if not _matches_kernel_element_pattern(profile, artifact_type.kernel_element_pattern):
            errors.append(
                f"Artifact type '{artifact_type.name}' kernel_element_pattern "
                f"'{artifact_type.kernel_element_pattern}' matches no profile elements"
            )

    return tuple(errors)


def validate_layer_stack(profile: KernelProfile) -> tuple[str, ...]:
    """Validate layer order uniqueness and dependency acyclicity."""

    if profile.layer_stack is None:
        return ()

    layers = profile.layer_stack.layers
    if not layers:
        return ()

    errors: list[str] = []

    order_counts = Counter(layer.order for layer in layers)
    duplicate_orders = sorted(order for order, count in order_counts.items() if count > 1)
    if duplicate_orders:
        errors.append(
            f"Duplicate layer order values in layer_stack: {duplicate_orders}"
        )

    layer_names = {layer.name for layer in layers}
    graph: dict[str, tuple[str, ...]] = {}
    for layer in layers:
        unknown = sorted({dep for dep in layer.depends_on if dep not in layer_names})
        if unknown:
            errors.append(
                f"Layer '{layer.name}' depends on unknown layers: {unknown}"
            )
        graph[layer.name] = tuple(dep for dep in layer.depends_on if dep in layer_names)

    cycle_errors = _detect_layer_cycles(graph)
    errors.extend(cycle_errors)

    return tuple(errors)


def validate_process_units(profile: KernelProfile) -> tuple[str, ...]:
    """Validate process-unit artifact references against artifact types."""

    known_artifacts = {artifact.name for artifact in profile.artifact_types}
    errors: list[str] = []

    for unit in profile.process_units:
        for artifact_name in unit.input_artifacts:
            if artifact_name not in known_artifacts:
                errors.append(
                    f"Process unit '{unit.name}' references unknown input_artifact "
                    f"'{artifact_name}'"
                )
        for artifact_name in unit.output_artifacts:
            if artifact_name not in known_artifacts:
                errors.append(
                    f"Process unit '{unit.name}' references unknown output_artifact "
                    f"'{artifact_name}'"
                )

    return tuple(errors)


def validate_profile(profile: KernelProfile) -> ProfileValidationResult:
    """Run all M2 profile metadata validators."""

    state_errors = validate_state_transitions(profile)
    artifact_errors = validate_artifact_types(profile)
    layer_errors = validate_layer_stack(profile)
    process_errors = validate_process_units(profile)

    return ProfileValidationResult(
        passed=not (state_errors or artifact_errors or layer_errors or process_errors),
        state_transition_errors=state_errors,
        artifact_type_errors=artifact_errors,
        layer_stack_errors=layer_errors,
        process_unit_errors=process_errors,
    )


def _matches_kernel_element_pattern(profile: KernelProfile, pattern: str) -> bool:
    """Return True when a kernel_element_pattern resolves to profile elements."""

    if pattern == "":
        return True

    if pattern == "*" or pattern.startswith("@") or pattern.startswith("#"):
        return bool(profile.matching_elements(pattern))

    if any(char in pattern for char in "*?["):
        for element in profile.elements:
            if fnmatchcase(element.name, pattern):
                return True
            if fnmatchcase(element.kernel_type, pattern):
                return True
        return False

    if profile.get_element(pattern) is not None:
        return True
    return any(element.kernel_type == pattern for element in profile.elements)


def _normalize_state_token(token: str) -> str:
    """Normalize state token comparisons across enum/value representations."""

    normalized = str(token).strip()
    if "." in normalized:
        normalized = normalized.rsplit(".", 1)[-1]
    return normalized.upper()


def _state_alias_from_element_name(name: str) -> str:
    """Extract canonical state alias from element names like NeedStatusDraft."""

    match = _STATE_ALIAS_SUFFIX_RE.search(name)
    if match is None:
        return ""

    suffix = match.group(1).strip()
    if not suffix:
        return ""

    split_tokens = [token for token in _STATE_ALIAS_SPLIT_RE.split(suffix) if token]
    if split_tokens:
        return _normalize_state_token(split_tokens[-1])

    camel_tokens = _CAMEL_CASE_TOKEN_RE.findall(suffix)
    if camel_tokens:
        return _normalize_state_token(camel_tokens[-1])

    return _normalize_state_token(suffix)


def _collect_known_state_tokens(profile: KernelProfile) -> set[str]:
    """Collect transition-reference tokens from state-like profile elements."""

    tokens: set[str] = set()
    for element in profile.elements:
        tokens.add(_normalize_state_token(element.name))
        if element.category not in _STATE_ALIAS_CATEGORIES:
            continue
        alias = _state_alias_from_element_name(element.name)
        if alias:
            tokens.add(alias)
    return tokens


def _detect_layer_cycles(graph: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Detect cycles in a layer dependency graph."""

    visit_state: dict[str, int] = {}
    path: list[str] = []
    cycles: set[tuple[str, ...]] = set()

    def _visit(node: str) -> None:
        visit_state[node] = 1
        path.append(node)
        for dep in graph.get(node, ()):
            state = visit_state.get(dep, 0)
            if state == 0:
                _visit(dep)
            elif state == 1:
                start_index = path.index(dep)
                cycles.add(tuple(path[start_index:] + [dep]))
        path.pop()
        visit_state[node] = 2

    for node in graph:
        if visit_state.get(node, 0) == 0:
            _visit(node)

    return tuple(
        "Layer dependency cycle detected: " + " -> ".join(cycle)
        for cycle in sorted(cycles)
    )
