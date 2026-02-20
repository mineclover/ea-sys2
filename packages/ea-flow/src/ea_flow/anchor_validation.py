"""Kernel Anchor Validation — Bidirectional Kernel↔Flow awareness.

Provides:
- validate_kernel_anchor(): check if a kernel_anchor references a valid kernel element
- AnchorValidationResult: validation outcome with details
- collect_anchors(): extract all kernel_anchors from a WorkflowSpec

References:
- ea_flow/spec.py: StepSpec.kernel_anchor property
- ea_kernel/types.py: KernelSchema (lazy import)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ea_flow.spec import StepSpec, WorkflowSpec


# ═══════════════════════════════════════════════════════════════════════════════
# Anchor Validation Types
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AnchorValidationResult:
    """Validation result for a single kernel_anchor."""
    anchor: str
    valid: bool
    match_type: str = ""  # "entity", "relation", "uri_entity", "uri_relation", "uri_operation"
    resolved_name: str = ""  # The kernel element name that was matched
    message: str = ""


@dataclass(frozen=True)
class WorkflowAnchorReport:
    """Aggregate validation report for all anchors in a workflow."""
    workflow_name: str
    total_steps: int = 0
    anchored_steps: int = 0
    unanchored_steps: int = 0
    valid_anchors: int = 0
    invalid_anchors: int = 0
    results: tuple[AnchorValidationResult, ...] = ()

    @property
    def all_valid(self) -> bool:
        return self.invalid_anchors == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Kernel Schema Access (lazy import)
# ═══════════════════════════════════════════════════════════════════════════════

def _get_kernel_names() -> tuple[frozenset[str], frozenset[str]]:
    """Return (entity_names, relation_names) from kernel schema.

    Lazy-imports ea_kernel to avoid hard dependency at module load time.
    """
    try:
        from ea_kernel.definition import KERNEL_SCHEMA
        entity_names = frozenset(e.name for e in KERNEL_SCHEMA.entities)
        relation_names = frozenset(r.name for r in KERNEL_SCHEMA.relations)
        return entity_names, relation_names
    except ImportError:
        return frozenset(), frozenset()


_URI_PREFIX = "ea:kernel:"


def _parse_uri_anchor(anchor: str) -> tuple[str, str] | None:
    """Parse an ea:kernel:* URI anchor.

    Returns (category, name) or None if not a URI anchor.
    Examples:
        "ea:kernel:entity:User" -> ("entity", "User")
        "ea:kernel:rule:R1" -> ("rule", "R1")
        "ea:kernel:rule_creation" -> ("operation", "rule_creation")
    """
    if not anchor.startswith(_URI_PREFIX):
        return None

    rest = anchor[len(_URI_PREFIX):]
    parts = rest.split(":", 1)

    if len(parts) == 2:
        return parts[0], parts[1]
    # Single segment like "rule_creation" → operation
    return "operation", parts[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Functions
# ═══════════════════════════════════════════════════════════════════════════════

def validate_kernel_anchor(
    anchor: str,
    *,
    entity_names: frozenset[str] | None = None,
    relation_names: frozenset[str] | None = None,
) -> AnchorValidationResult:
    """Validate a kernel_anchor against the kernel schema.

    Supports three anchor formats:
    1. Direct entity/relation name: "element", "feature", "connector"
    2. URI format: "ea:kernel:entity:User", "ea:kernel:rule:R1"
    3. Operation URI: "ea:kernel:rule_creation"

    Args:
        anchor: The kernel_anchor string to validate.
        entity_names: Override entity names (for testing). If None, loaded from kernel.
        relation_names: Override relation names (for testing). If None, loaded from kernel.
    """
    if not anchor:
        return AnchorValidationResult(
            anchor=anchor, valid=False,
            message="Empty kernel_anchor",
        )

    if entity_names is None or relation_names is None:
        _ents, _rels = _get_kernel_names()
        if entity_names is None:
            entity_names = _ents
        if relation_names is None:
            relation_names = _rels

    # 1. Direct name match against entities
    if anchor in entity_names:
        return AnchorValidationResult(
            anchor=anchor, valid=True,
            match_type="entity", resolved_name=anchor,
        )

    # 2. Direct name match against relations
    if anchor in relation_names:
        return AnchorValidationResult(
            anchor=anchor, valid=True,
            match_type="relation", resolved_name=anchor,
        )

    # 3. URI format
    parsed = _parse_uri_anchor(anchor)
    if parsed is not None:
        category, name = parsed

        if category == "entity" and name in entity_names:
            return AnchorValidationResult(
                anchor=anchor, valid=True,
                match_type="uri_entity", resolved_name=name,
            )
        if category == "relation" and name in relation_names:
            return AnchorValidationResult(
                anchor=anchor, valid=True,
                match_type="uri_relation", resolved_name=name,
            )
        # Operations (rule_creation, etc.) and rules are valid URI patterns
        if category in ("operation", "rule"):
            return AnchorValidationResult(
                anchor=anchor, valid=True,
                match_type=f"uri_{category}", resolved_name=name,
            )

        return AnchorValidationResult(
            anchor=anchor, valid=False,
            message=f"URI anchor '{anchor}' does not match any kernel element "
                    f"(category='{category}', name='{name}')",
        )

    # 4. No match
    return AnchorValidationResult(
        anchor=anchor, valid=False,
        message=f"Anchor '{anchor}' is not a known kernel entity, relation, or URI pattern",
    )


def collect_anchors(workflow: WorkflowSpec) -> list[str]:
    """Extract all non-None kernel_anchors from a workflow's steps."""
    anchors: list[str] = []
    for step in workflow.get_steps():
        anchor = step.kernel_anchor
        if anchor is not None:
            anchors.append(anchor)
    return anchors


def validate_workflow_anchors(
    workflow: WorkflowSpec,
    *,
    entity_names: frozenset[str] | None = None,
    relation_names: frozenset[str] | None = None,
) -> WorkflowAnchorReport:
    """Validate all kernel_anchors in a workflow against the kernel schema.

    Returns a report with per-step validation results.
    """
    steps = workflow.get_steps()
    results: list[AnchorValidationResult] = []
    anchored = 0
    unanchored = 0
    valid_count = 0
    invalid_count = 0

    for step in steps:
        anchor = step.kernel_anchor
        if anchor is None:
            unanchored += 1
            continue

        anchored += 1
        result = validate_kernel_anchor(
            anchor,
            entity_names=entity_names,
            relation_names=relation_names,
        )
        results.append(result)
        if result.valid:
            valid_count += 1
        else:
            invalid_count += 1

    return WorkflowAnchorReport(
        workflow_name=workflow.name,
        total_steps=len(steps),
        anchored_steps=anchored,
        unanchored_steps=unanchored,
        valid_anchors=valid_count,
        invalid_anchors=invalid_count,
        results=tuple(results),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Reverse Lookup — Find flow steps by kernel element
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AnchorUsage:
    """A flow step that references a kernel element via kernel_anchor."""
    workflow_name: str
    step_name: str
    kernel_anchor: str
    execution_id: str = ""


def find_anchor_usages(
    records: tuple[Any, ...],
    kernel_element: str,
) -> tuple[AnchorUsage, ...]:
    """Find all execution records whose steps reference a given kernel element.

    Matches both direct name and URI-embedded references.

    Args:
        records: StoredExecutionRecord tuples from ExecutionStore.query()
        kernel_element: Kernel entity or relation name to search for.
    """
    usages: list[AnchorUsage] = []

    for record in records:
        for step in record.step_results:
            if _anchor_matches_element(step.kernel_anchor, kernel_element):
                usages.append(AnchorUsage(
                    workflow_name=record.workflow_name,
                    step_name=step.step_name,
                    kernel_anchor=step.kernel_anchor,
                    execution_id=record.execution_id,
                ))

    return tuple(usages)


def _anchor_matches_element(anchor: str, element: str) -> bool:
    """Check if an anchor references a specific kernel element.

    Matches:
    - Direct: anchor == element
    - URI: "ea:kernel:entity:{element}" or "ea:kernel:rule:{element}"
    """
    if not anchor or not element:
        return False

    if anchor == element:
        return True

    parsed = _parse_uri_anchor(anchor)
    if parsed is not None:
        _, name = parsed
        return name == element

    return False
