"""Static validators for ea_profile.v2 aggregate contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ea_profile.v2.types import FlowEdgeSpec, LayerSpec, LoopContractSpec

MANDATORY_FLOW_PATHS: tuple[tuple[str, str], ...] = (
    ("infra", "kernel"),
    ("infra", "flow"),
    ("decision", "needs"),
    ("needs", "kernel"),
    ("kernel", "flow"),
    ("flow", "projection"),
    ("projection", "decision"),
)
_MANDATORY_FLOW_LAYERS = frozenset(
    layer for path in MANDATORY_FLOW_PATHS for layer in path
)


@dataclass(frozen=True)
class TypeSystemValidationIssue:
    """Structured aggregate validation issue."""

    code: str
    field: str
    message: str


class TypeSystemValidationError(ValueError):
    """Raised when one or more v2 aggregate validation rules fail."""

    def __init__(self, issues: tuple[TypeSystemValidationIssue, ...]) -> None:
        if not issues:
            raise ValueError("issues must not be empty")
        self.issues = issues
        rendered = "; ".join(
            f"{issue.code} [{issue.field}] {issue.message}" for issue in issues
        )
        super().__init__(rendered)


def validate_flow_and_loop_contracts(
    *,
    layers: tuple[LayerSpec, ...],
    flow_edges: tuple[FlowEdgeSpec, ...],
    loop_contracts: tuple[LoopContractSpec, ...],
) -> tuple[TypeSystemValidationIssue, ...]:
    """Validate flow-edge integrity and loop-contract path closure."""

    issues: list[TypeSystemValidationIssue] = []
    layer_ids = {layer.id for layer in layers}
    adjacency: dict[str, set[str]] = {}
    required_pairs: set[tuple[str, str]] = set()

    for edge in flow_edges:
        from_layer = edge.from_layer
        to_layer = edge.to_layer
        valid = True

        if from_layer not in layer_ids:
            issues.append(
                TypeSystemValidationIssue(
                    code="FLOW_EDGE_UNKNOWN_LAYER",
                    field=f"flow_edges[{edge.id}].from_layer",
                    message=(
                        f"flow edge references unknown source layer '{from_layer}'"
                    ),
                )
            )
            valid = False
        if to_layer not in layer_ids:
            issues.append(
                TypeSystemValidationIssue(
                    code="FLOW_EDGE_UNKNOWN_LAYER",
                    field=f"flow_edges[{edge.id}].to_layer",
                    message=(
                        f"flow edge references unknown target layer '{to_layer}'"
                    ),
                )
            )
            valid = False
        if not valid:
            continue

        adjacency.setdefault(from_layer, set()).add(to_layer)
        if edge.required:
            required_pairs.add((from_layer, to_layer))

    if _MANDATORY_FLOW_LAYERS.issubset(layer_ids):
        for source, target in MANDATORY_FLOW_PATHS:
            if (source, target) in required_pairs:
                continue
            issues.append(
                TypeSystemValidationIssue(
                    code="FLOW_REQUIRED_PATH_MISSING",
                    field="flow_edges",
                    message=(
                        "missing required flow path "
                        f"'{source}->{target}' with required=true"
                    ),
                )
            )

    for contract in loop_contracts:
        has_invalid_layer = False
        for index, layer_id in enumerate(contract.path):
            if layer_id in layer_ids:
                continue
            issues.append(
                TypeSystemValidationIssue(
                    code="LOOP_PATH_INVALID_LAYER",
                    field=f"loop_contracts[{contract.id}].path[{index}]",
                    message=(
                        f"loop path references unknown layer '{layer_id}'"
                    ),
                )
            )
            has_invalid_layer = True

        if has_invalid_layer:
            continue

        for source, target in zip(contract.path, contract.path[1:], strict=False):
            if target in adjacency.get(source, set()):
                continue
            issues.append(
                TypeSystemValidationIssue(
                    code="LOOP_PATH_DISCONNECTED",
                    field=f"loop_contracts[{contract.id}].path",
                    message=(
                        "loop path is disconnected on flow graph; missing edge "
                        f"'{source}->{target}'"
                    ),
                )
            )

    return tuple(issues)


def ensure_flow_and_loop_contracts(
    *,
    layers: tuple[LayerSpec, ...],
    flow_edges: tuple[FlowEdgeSpec, ...],
    loop_contracts: tuple[LoopContractSpec, ...],
) -> None:
    """Raise an aggregate validation error when flow/loop checks fail."""

    issues = validate_flow_and_loop_contracts(
        layers=layers,
        flow_edges=flow_edges,
        loop_contracts=loop_contracts,
    )
    if issues:
        raise TypeSystemValidationError(issues)
