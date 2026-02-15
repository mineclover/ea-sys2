"""Service layer for kernel onboarding use cases.

Pure functions returning structured dicts — suitable for CLI, MCP, or API consumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ea_kernel.types import (
    KernelSchema,
    Layer,
    RuleGroup,
    RuleMetadata,
)

if TYPE_CHECKING:
    from ea_kernel.rule_corpus import RuleCorpus

# Layer display names
_LAYER_LABELS: dict[Layer, str] = {
    Layer.L1: "L1 Structure",
    Layer.L2: "L2 Relationship",
    Layer.L3: "L3 Behavioral",
    Layer.L4: "L4 Concrete",
}


def _get_spec() -> KernelSchema:
    from ea_kernel.spec import KERNEL_SPEC
    return KERNEL_SPEC


def _get_corpus() -> RuleCorpus:
    from ea_kernel.rule_corpus import RuleCorpus
    from ea_kernel.spec import KERNEL_SPEC
    from ea_kernel.spec_loader import load_kernel_rules_with_metadata
    _, _, metadata_map = load_kernel_rules_with_metadata()
    return RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map)


def _get_metadata_map() -> dict[str, RuleMetadata]:
    from ea_kernel.spec_loader import load_kernel_rules_with_metadata
    _, _, metadata_map = load_kernel_rules_with_metadata()
    return metadata_map


# ── UC1: Entity/Relation exploration ──────────────────────────


def list_entities() -> dict[str, Any]:
    """UC1: List all kernel entities grouped by layer with hierarchy tree."""
    spec = _get_spec()
    layers: list[dict[str, Any]] = []
    for layer in Layer:
        entities_in = spec.entities_in_layer(layer)
        layer_data: dict[str, Any] = {
            "name": _LAYER_LABELS[layer],
            "count": len(entities_in),
            "entities": [
                {
                    "name": e.name,
                    "parent": e.parent,
                    "is_abstract": e.is_abstract,
                    "description": e.description,
                }
                for e in entities_in
            ],
        }
        layers.append(layer_data)
    return {
        "total": len(spec.entities),
        "layers": layers,
    }


def list_relations() -> dict[str, Any]:
    """UC1: List all kernel relations grouped by layer with roles."""
    spec = _get_spec()
    layers: list[dict[str, Any]] = []
    for layer in (Layer.L2, Layer.L3):
        relations_in = spec.relations_in_layer(layer)
        layer_data: dict[str, Any] = {
            "name": _LAYER_LABELS[layer],
            "count": len(relations_in),
            "relations": [
                {
                    "name": r.name,
                    "parent": r.parent,
                    "roles": [
                        {"name": role.name, "player": role.player}
                        for role in spec.effective_roles(r.name)
                    ],
                    "description": r.description,
                }
                for r in relations_in
            ],
        }
        layers.append(layer_data)
    return {
        "total": len(spec.relations),
        "layers": layers,
    }


# ── UC2: Profile detail ──────────────────────────────────────


def describe_profile(name: str) -> dict[str, Any] | None:
    """UC2: Describe a profile — elements by layer, relations, rule summary."""
    from ea_kernel.profile_registry import ProfileRegistry
    registry = ProfileRegistry()
    registry.bootstrap()
    profile = registry.get(name)
    if profile is None:
        return None

    # Elements grouped by domain layer
    elements_by_layer: list[dict[str, Any]] = []
    for layer in profile.domain_layers():
        elems = profile.elements_in_layer(layer)
        elements_by_layer.append({
            "layer": layer,
            "count": len(elems),
            "elements": [
                {"name": e.name, "kernel_type": e.kernel_type}
                for e in elems
            ],
        })

    # Relations
    relations = [
        {"name": r.name, "kernel_relation": r.kernel_relation}
        for r in profile.relations
    ]

    # Rule summary
    allow_count = sum(1 for r in profile.validity_rules if r.valid)
    deny_count = sum(1 for r in profile.validity_rules if not r.valid)

    return {
        "name": profile.name,
        "version": profile.version,
        "standard": profile.metadata.standard if profile.metadata else "",
        "organization": profile.metadata.organization if profile.metadata else "",
        "element_count": len(profile.elements),
        "relation_count": len(profile.relations),
        "rule_count": len(profile.validity_rules),
        "elements_by_layer": elements_by_layer,
        "relations": relations,
        "rule_summary": {"allow": allow_count, "deny": deny_count},
    }


# ── UC3: Rule exploration/filtering ──────────────────────────


def list_rules(group: str | None = None, relation: str | None = None) -> dict[str, Any]:
    """UC3: List rules with optional filtering by group or relation.

    If neither filter is given, returns group-level summary.
    """
    corpus = _get_corpus()

    if group is not None:
        try:
            rg = RuleGroup(group)
        except ValueError:
            return {"error": f"Unknown group: {group}", "valid_groups": [g.value for g in RuleGroup]}
        entries = corpus.by_group(rg)
        rules = [
            {
                "id": e.rule.id,
                "source": e.rule.source_pattern,
                "target": e.rule.target_pattern,
                "relation": e.rule.relationship_name,
                "valid": e.rule.valid,
                "priority": e.rule.priority,
                "notes": e.rule.notes,
            }
            for e in sorted(entries, key=lambda e: e.rule.id)
        ]
        return {"total": len(rules), "group": group, "rules": rules}

    if relation is not None:
        relation_entries = [
            e for e in corpus.entries if e.rule.relationship_name == relation
        ]
        rules = [
            {
                "id": e.rule.id,
                "source": e.rule.source_pattern,
                "target": e.rule.target_pattern,
                "relation": e.rule.relationship_name,
                "valid": e.rule.valid,
                "priority": e.rule.priority,
                "notes": e.rule.notes,
            }
            for e in sorted(relation_entries, key=lambda e: e.rule.id)
        ]
        return {"total": len(rules), "relation": relation, "rules": rules}

    # No filter: group summary
    summary = corpus.group_summary()
    groups = [
        {"name": g.value, "count": c}
        for g, c in sorted(summary.items(), key=lambda kv: kv[0].value)
    ]
    return {"total": len(corpus.entries), "groups": groups}


# ── UC4: Single rule detail ─────────────────────────────────


def describe_rule(rule_id: str) -> dict[str, Any] | None:
    """UC4: Describe a single rule with full metadata."""
    corpus = _get_corpus()
    entry = corpus._by_id.get(rule_id)
    if entry is None:
        return None
    r = entry.rule
    m = entry.metadata
    return {
        "id": r.id,
        "source": r.source_pattern,
        "target": r.target_pattern,
        "relation": r.relationship_name,
        "valid": r.valid,
        "priority": r.priority,
        "conditions": [
            {"type": c.condition_type.value, "parameters": dict(c.parameters)}
            for c in r.conditions
        ],
        "notes": r.notes,
        "metadata": {
            "group": m.group.value,
            "category": m.category.value,
            "confidence": m.confidence.value,
            "source": m.source,
            "rationale": m.rationale,
            "tags": list(m.tags),
            "established_version": m.established_version,
        },
    }


# ── UC5: Evidence-based judgment ─────────────────────────────


def judge(source: str, target: str, relation: str) -> dict[str, Any]:
    """UC5: Evidence-based judgment for a relationship triple."""
    spec = _get_spec()

    # Input validation
    src_entity = spec.get_entity(source)
    tgt_entity = spec.get_entity(target)
    if src_entity is None:
        return {"error": f"Unknown entity: {source}", "valid_entities": get_entity_names()}
    if tgt_entity is None:
        return {"error": f"Unknown entity: {target}", "valid_entities": get_entity_names()}
    if spec.get_relation(relation) is None:
        rel_names = [r.name for r in spec.relations]
        return {"error": f"Unknown relation: {relation}", "valid_relations": rel_names}

    corpus = _get_corpus()
    report = corpus.judge(source, target, relation)

    evidence: list[dict[str, Any]] = []
    for ev in report.evidence:
        if not ev.matched:
            continue
        evidence.append({
            "rule_id": ev.entry.rule.id,
            "matched": ev.matched,
            "winner": ev.is_winner,
            "valid": ev.entry.rule.valid,
            "source": ev.entry.rule.source_pattern,
            "target": ev.entry.rule.target_pattern,
            "priority": ev.entry.rule.priority,
        })

    return {
        "verdict": report.verdict,
        "confidence": report.confidence.value,
        "evidence": evidence,
        "conflicts": list(report.conflicts),
    }


# ── UC6: Profile graph traversal ──────────────────────────────


def _load_profile(name: str) -> Any:
    from ea_kernel.profile_registry import ProfileRegistry
    registry = ProfileRegistry()
    registry.bootstrap()
    return registry.get(name)


def profile_topology(profile_name: str) -> dict[str, Any]:
    """UC6: Full topology graph (nodes + edges) for a profile."""
    from ea_kernel.profile_graph import ProfileTopologyGraph

    profile = _load_profile(profile_name)
    if profile is None:
        return {"error": f"Profile not found: {profile_name}"}

    graph = ProfileTopologyGraph(profile)

    nodes = [
        {
            "name": elem.name,
            "layer": elem.layer,
            "category": elem.category,
            "kernel_type": elem.kernel_type,
            "description": elem.description,
        }
        for elem in profile.elements
    ]

    edges: list[dict[str, Any]] = []
    for src in graph.nodes:
        for edge in graph.outgoing(src):
            edges.append({
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "rule_id": edge.rule_id,
                "priority": edge.priority,
            })

    return {
        "profile": profile_name,
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "relation_distribution": graph.relation_distribution(),
    }


def profile_reachable(
    profile_name: str,
    element: str,
    *,
    max_depth: int = 3,
    relation: str | None = None,
) -> dict[str, Any]:
    """UC6: Reachable elements from a profile element."""
    from ea_kernel.profile_graph import ProfileTopologyGraph

    profile = _load_profile(profile_name)
    if profile is None:
        return {"error": f"Profile not found: {profile_name}"}

    graph = ProfileTopologyGraph(profile)
    if element not in graph.nodes:
        return {
            "error": f"Element not found: {element}",
            "available_elements": list(graph.nodes),
        }

    rel_filter = frozenset([relation]) if relation else None
    reached = graph.reachable(element, max_depth=max_depth, relation_filter=rel_filter)
    return {
        "profile": profile_name,
        "source": element,
        "max_depth": max_depth,
        "relation_filter": relation,
        "reachable": list(reached),
        "count": len(reached),
    }


def profile_paths(
    profile_name: str,
    source: str,
    target: str,
    *,
    max_depth: int = 5,
    relation: str | None = None,
) -> dict[str, Any]:
    """UC6: Find paths between two profile elements."""
    from ea_kernel.profile_graph import ProfileTopologyGraph

    profile = _load_profile(profile_name)
    if profile is None:
        return {"error": f"Profile not found: {profile_name}"}

    graph = ProfileTopologyGraph(profile)
    missing = [n for n in (source, target) if n not in graph.nodes]
    if missing:
        return {
            "error": f"Element(s) not found: {', '.join(missing)}",
            "available_elements": list(graph.nodes),
        }

    rel_filter = frozenset([relation]) if relation else None
    paths = graph.find_paths(source, target, max_depth=max_depth, relation_filter=rel_filter)
    return {
        "profile": profile_name,
        "source": source,
        "target": target,
        "max_depth": max_depth,
        "relation_filter": relation,
        "paths": [
            {
                "length": len(p.edges),
                "edges": [
                    {
                        "source": e.source,
                        "target": e.target,
                        "relation": e.relation,
                        "rule_id": e.rule_id,
                    }
                    for e in p.edges
                ],
            }
            for p in paths
        ],
        "count": len(paths),
    }


def profile_impact(
    profile_name: str,
    element: str,
    *,
    direction: str = "both",
    max_depth: int = 3,
) -> dict[str, Any]:
    """UC6: Impact analysis for a profile element."""
    from ea_kernel.profile_graph import ProfileTopologyGraph

    profile = _load_profile(profile_name)
    if profile is None:
        return {"error": f"Profile not found: {profile_name}"}

    graph = ProfileTopologyGraph(profile)
    if element not in graph.nodes:
        return {
            "error": f"Element not found: {element}",
            "available_elements": list(graph.nodes),
        }

    impact = graph.impact_analysis(element, direction=direction, max_depth=max_depth)
    return {
        "profile": profile_name,
        "element": element,
        "direction": direction,
        "max_depth": max_depth,
        "impact": {
            name: [
                {
                    "length": len(p.edges),
                    "edges": [
                        {"source": e.source, "target": e.target, "relation": e.relation}
                        for e in p.edges
                    ],
                }
                for p in paths
            ]
            for name, paths in impact.items()
        },
        "affected_count": len(impact),
    }


# ── Helper ───────────────────────────────────────────────────


def get_entity_names() -> list[str]:
    """List all valid entity names (for input validation)."""
    spec = _get_spec()
    return sorted(e.name for e in spec.entities)
