"""MCP server for ea-kernel — stdio transport.

Requires: pip install ea-kernel[mcp]
Usage: python -m ea_kernel mcp
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

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


@mcp.tool()
def kernel_list_entities() -> str:
    """List all kernel entities grouped by layer (L1-L4).

    Returns entity names, parents, abstract status, and descriptions
    organized by the 4-layer progressive abstraction model.
    """
    from ea_kernel.kernel_service import list_entities

    return json.dumps(list_entities(), indent=2)


@mcp.tool()
def kernel_list_relations() -> str:
    """List all kernel relations grouped by layer with roles.

    Returns relation names, parent relations, role definitions (name + player),
    and descriptions for L2 (Relationship) and L3 (Behavioral) layers.
    """
    from ea_kernel.kernel_service import list_relations

    return json.dumps(list_relations(), indent=2)


@mcp.tool()
def kernel_list_rules(group: str | None = None, relation: str | None = None) -> str:
    """List kernel validity rules with optional filtering.

    If neither filter is given, returns a group-level summary with counts.
    Use 'group' to filter by rule group (e.g. 'specialization', 'association', 'flow').
    Use 'relation' to filter by relation name.
    """
    from ea_kernel.kernel_service import list_rules

    return json.dumps(list_rules(group=group, relation=relation), indent=2)


@mcp.tool()
def kernel_describe_profile(name: str) -> str:
    """Describe a kernel profile — elements by layer, relations, rule summary.

    Requires a profile name (e.g. 'ArchiMate', 'TOGAF', 'Zachman', 'SysML2', 'BPMN').
    Returns profile metadata, elements grouped by domain layer, relations,
    and rule summary (allow/deny counts).
    """
    from ea_kernel.kernel_service import describe_profile

    result = describe_profile(name)
    if result is None:
        return json.dumps({"error": f"Profile not found: {name}"})
    return json.dumps(result, indent=2)


@mcp.tool()
def kernel_describe_rule(rule_id: str) -> str:
    """Describe a single kernel validity rule with full metadata.

    Returns rule source/target patterns, relation, validity, priority,
    conditions, notes, and metadata (group, category, confidence, rationale, tags).
    """
    from ea_kernel.kernel_service import describe_rule

    result = describe_rule(rule_id)
    if result is None:
        return json.dumps({"error": f"Rule not found: {rule_id}"})
    return json.dumps(result, indent=2)


@mcp.tool()
def kernel_judge(source: str, target: str, relation: str) -> str:
    """Evidence-based judgment for a relationship triple.

    Evaluates whether a relationship (source -> target via relation) is valid
    according to kernel rules. Returns verdict (allow/deny), confidence level,
    matching evidence with rule details, and any conflicts detected.
    """
    from ea_kernel.kernel_service import judge

    return json.dumps(judge(source, target, relation), indent=2)


@mcp.tool()
def kernel_get_entity_names() -> str:
    """Get all valid kernel entity names (sorted).

    Useful for input validation and auto-completion when constructing
    queries for other kernel tools.
    """
    from ea_kernel.kernel_service import get_entity_names

    return json.dumps(get_entity_names(), indent=2)


def run_stdio() -> None:
    """Start the MCP server with stdio transport."""
    mcp.run(transport="stdio")
