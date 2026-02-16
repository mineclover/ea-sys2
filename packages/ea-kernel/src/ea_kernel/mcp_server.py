"""MCP server for ea-kernel — stdio transport.

Requires: pip install ea-kernel[mcp]
Usage: python -m ea_kernel mcp
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, TypeVar, cast

from mcp.server.fastmcp import FastMCP

mcp_tool_fn = TypeVar("mcp_tool_fn", bound=Callable[..., Any])

mcp = FastMCP(
    "ea-kernel",
    instructions="""\
ea-kernel is a lightweight kernel metamodel inspired by UML 2.5.1 and KerML.
It provides a universal type system that EA frameworks (ArchiMate, TOGAF, Zachman, SysML2, BPMN) map onto.

## 4-Layer Progressive Abstraction

- L1 Structure: Static structural elements (element, type, feature, classifier, package, port, datatype, ...)
- L2 Relationship: Structural connections (specialization, association, connector, feature_typing, membership, ...)
- L3 Behavioral: Behavioral qualification of relationships (flow, succession, triggering, transition, interaction, guarding)
- L4 Concrete: Concrete behavioral models (step, action, state, event, expression)

Core principle: behavior is not separate from structure — it is a qualification of relationships.

## Validity Rules & Judgment

Rules define which entity-to-entity relationships are allowed (valid=true) or denied (valid=false).
Each rule has a priority; when multiple rules match, the highest-priority rule wins.

Priority bands:
- 1: deny-by-default fallback (one per relation)
- 40-50: category-level allow rules
- 60: cross-category allow rules
- 80: explicit deny overrides

Use kernel_judge to evaluate a (source, target, relation) triple — it returns a verdict with full evidence chain.

## Profiles

A profile maps a domain framework's elements to kernel types. 5 built-in profiles: ArchiMate, TOGAF, Zachman, SysML2, BPMN.
Profiles add constraints on top of kernel rules but cannot relax them (2-stage validation).

## Recommended Workflow

1. kernel_get_entity_names → see available entities
2. kernel_list_entities / kernel_list_relations → understand the structure
3. kernel_describe_profile → explore how a framework maps to the kernel
4. kernel_list_rules → browse validity rules by group
5. kernel_judge → evaluate whether a specific relationship is valid\
""",
)


def _typed_tool(*args: Any, **kwargs: Any) -> Callable[[mcp_tool_fn], mcp_tool_fn]:
    """Typed wrapper around FastMCP's untyped decorator API."""
    return cast(Callable[[mcp_tool_fn], mcp_tool_fn], mcp.tool(*args, **kwargs))


@_typed_tool()
def kernel_list_entities() -> str:
    """List all kernel entities grouped by layer (L1-L4).

    Returns entity names, parents, abstract status, and descriptions
    organized by the 4-layer progressive abstraction model.
    """
    from ea_kernel.kernel_service import list_entities

    return json.dumps(list_entities(), indent=2)


@_typed_tool()
def kernel_list_relations() -> str:
    """List all kernel relations grouped by layer with roles.

    Returns relation names, parent relations, role definitions (name + player),
    and descriptions for L2 (Relationship) and L3 (Behavioral) layers.
    """
    from ea_kernel.kernel_service import list_relations

    return json.dumps(list_relations(), indent=2)


@_typed_tool()
def kernel_list_rules(group: str | None = None, relation: str | None = None) -> str:
    """List kernel validity rules with optional filtering.

    If neither filter is given, returns a group-level summary with counts.
    Use 'group' to filter by rule group (e.g. 'specialization', 'association', 'flow').
    Use 'relation' to filter by relation name.
    """
    from ea_kernel.kernel_service import list_rules

    return json.dumps(list_rules(group=group, relation=relation), indent=2)


@_typed_tool()
def kernel_describe_profile(name: str) -> str:
    """Describe a kernel profile — elements by layer, relations, rule summary.

    Requires a profile name (e.g. 'ArchiMate', 'TOGAF', 'Zachman', 'SysML2', 'BPMN').
    Returns profile metadata, elements grouped by domain layer, relations,
    and rule summary (allow/deny counts).
    """
    from ea_kernel.kernel_service import describe_profile

    result = describe_profile(name=name)
    if result is None:
        return json.dumps({"error": f"Profile not found: {name}"})
    return json.dumps(result, indent=2)


@_typed_tool()
def kernel_describe_rule(rule_id: str) -> str:
    """Describe a single kernel validity rule with full metadata.

    Returns rule source/target patterns, relation, validity, priority,
    conditions, notes, and metadata (group, category, confidence, rationale, tags).
    """
    from ea_kernel.kernel_service import describe_rule

    result = describe_rule(rule_id=rule_id)
    if result is None:
        return json.dumps({"error": f"Rule not found: {rule_id}"})
    return json.dumps(result, indent=2)


@_typed_tool()
def kernel_judge(source: str, target: str, relation: str) -> str:
    """Evidence-based judgment for a relationship triple.

    Evaluates whether a relationship (source -> target via relation) is valid
    according to kernel rules. Returns verdict (allow/deny), confidence level,
    matching evidence with rule details, and any conflicts detected.
    """
    from ea_kernel.kernel_service import judge

    return json.dumps(judge(source=source, target=target, relation=relation), indent=2)


@_typed_tool()
def kernel_get_entity_names() -> str:
    """Get all valid kernel entity names (sorted).

    Useful for input validation and auto-completion when constructing
    queries for other kernel tools.
    """
    from ea_kernel.kernel_service import get_entity_names

    return json.dumps(get_entity_names(), indent=2)


@_typed_tool()
def profile_reachable(
    profile_name: str,
    element: str,
    max_depth: int = 3,
    relation: str | None = None,
) -> str:
    """Find all elements reachable from a profile element via valid rules.

    Expands validity rule patterns into concrete edges, then performs
    BFS reachability. Useful for experience discovery traversal.

    Args:
        profile_name: Profile name (e.g. 'ArchiMate', 'TOGAF').
        element: Source element name to start from.
        max_depth: Maximum traversal depth (default 3).
        relation: Optional relation name filter.
    """
    from ea_kernel.kernel_service import profile_reachable as _reachable

    return json.dumps(
        _reachable(profile_name=profile_name, element=element, max_depth=max_depth, relation=relation),
        indent=2,
    )


@_typed_tool()
def profile_paths(
    profile_name: str,
    source: str,
    target: str,
    max_depth: int = 5,
    relation: str | None = None,
) -> str:
    """Find all paths between two profile elements via valid rules.

    Returns each path as a sequence of edges with source, target,
    relation, and rule_id.

    Args:
        profile_name: Profile name.
        source: Source element name.
        target: Target element name.
        max_depth: Maximum path length (default 5).
        relation: Optional relation name filter.
    """
    from ea_kernel.kernel_service import profile_paths as _paths

    return json.dumps(
        _paths(profile_name=profile_name, source=source, target=target, max_depth=max_depth, relation=relation),
        indent=2,
    )


@_typed_tool()
def profile_impact(
    profile_name: str,
    element: str,
    direction: str = "both",
    max_depth: int = 3,
) -> str:
    """Impact analysis for a profile element — find all affected elements.

    Shows which elements are connected and through which paths,
    in both outgoing and incoming directions.

    Args:
        profile_name: Profile name.
        element: Element to analyze.
        direction: 'outgoing', 'incoming', or 'both' (default).
        max_depth: Maximum traversal depth (default 3).
    """
    from ea_kernel.kernel_service import profile_impact as _impact

    return json.dumps(
        _impact(profile_name=profile_name, element=element, direction=direction, max_depth=max_depth),
        indent=2,
    )


@_typed_tool()
def profile_version_history(profile_name: str, limit: int = 50) -> str:
    """List version history for a profile — newest first.

    Returns version metadata (id, version, content_hash, author,
    description, created_at, parent_id) without full profile data.

    Args:
        profile_name: Profile name.
        limit: Maximum number of versions to return (default 50).
    """
    from ea_kernel.kernel_service import profile_version_history as _history

    return json.dumps(_history(profile_name=profile_name, limit=limit), indent=2)


@_typed_tool()
def profile_version_detail(profile_name: str, version: str) -> str:
    """Get detailed info for a specific profile version.

    Returns metadata, element/relation/rule counts, and tags.

    Args:
        profile_name: Profile name.
        version: Version string.
    """
    from ea_kernel.kernel_service import profile_version_detail as _detail

    return json.dumps(_detail(profile_name=profile_name, version=version), indent=2)


@_typed_tool()
def profile_version_diff(profile_name: str, version_a: str, version_b: str) -> str:
    """Compute structural diff between two profile versions.

    Returns element/relation/rule changes (added, removed, modified).

    Args:
        profile_name: Profile name.
        version_a: Source version string.
        version_b: Target version string.
    """
    from ea_kernel.kernel_service import profile_version_diff as _diff

    return json.dumps(
        _diff(profile_name=profile_name, version_a=version_a, version_b=version_b),
        indent=2,
    )


@_typed_tool()
def profile_version_tags(profile_name: str) -> str:
    """List all tags for a profile.

    Returns tag names with their version IDs and creation timestamps.

    Args:
        profile_name: Profile name.
    """
    from ea_kernel.kernel_service import profile_version_tags as _tags

    return json.dumps(_tags(profile_name=profile_name), indent=2)


def run_stdio() -> None:
    """Start the MCP server with stdio transport."""
    mcp.run(transport="stdio")
