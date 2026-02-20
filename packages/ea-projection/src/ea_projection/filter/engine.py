"""Projection filter engine — topology filtering by relation, category, tier, and edge budget.

Extracted from kernel_service.py lines 1880, 4013-4191.
"""

from __future__ import annotations

from typing import Any

from ea_projection.surface import DEFAULT_SURFACE_PROFILE, SurfaceRelationProfile
from ea_projection.tier.resolver import resolve_tier_node_set


def edge_surface_exposed(
    relation: str,
    surface_profile: SurfaceRelationProfile | None = None,
) -> bool:
    profile = surface_profile or DEFAULT_SURFACE_PROFILE
    return profile.is_surface_exposed(relation)


def _edge_priority_sort_key(edge: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        -int(edge.get("priority", 0)),
        str(edge.get("relation", "")),
        str(edge.get("source", "")),
        str(edge.get("target", "")),
    )


def _cap_edges_relation_balanced(
    edges: list[dict[str, Any]],
    max_edges: int,
) -> list[dict[str, Any]]:
    """Cap edges while preserving relation mix as much as possible."""
    if len(edges) <= max_edges:
        return edges
    if max_edges <= 0:
        return []

    by_relation: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        relation = str(edge.get("relation", ""))
        bucket = by_relation.get(relation)
        if bucket is None:
            by_relation[relation] = [edge]
        else:
            bucket.append(edge)
    for relation in by_relation:
        by_relation[relation] = sorted(by_relation[relation], key=_edge_priority_sort_key)

    total_edges = len(edges)
    relations = sorted(by_relation.keys())
    quotas: dict[str, int] = {}
    fractions: list[tuple[float, int, str]] = []
    allocated = 0

    for relation in relations:
        size = len(by_relation[relation])
        exact = (size * max_edges) / total_edges
        base = min(size, int(exact))
        quotas[relation] = base
        allocated += base
        fractions.append((exact - base, size, relation))

    if len(relations) <= max_edges:
        for relation in relations:
            if quotas[relation] == 0:
                quotas[relation] = 1
                allocated += 1

    if allocated > max_edges:
        over = allocated - max_edges
        reducible = sorted(
            (
                (quotas[relation], relation)
                for relation in relations
                if quotas[relation] > 0
            ),
            key=lambda item: (-item[0], item[1]),
        )
        idx = 0
        while over > 0 and reducible:
            relation = reducible[idx % len(reducible)][1]
            if quotas[relation] > 0:
                quotas[relation] -= 1
                over -= 1
            idx += 1

    elif allocated < max_edges:
        remaining = max_edges - allocated
        expandable = sorted(
            fractions,
            key=lambda item: (-item[0], -item[1], item[2]),
        )
        while remaining > 0:
            progressed = False
            for _fraction, _size, relation in expandable:
                if quotas[relation] >= len(by_relation[relation]):
                    continue
                quotas[relation] += 1
                remaining -= 1
                progressed = True
                if remaining == 0:
                    break
            if not progressed:
                break

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for relation in relations:
        for edge in by_relation[relation][:quotas.get(relation, 0)]:
            selected.append(edge)
            selected_ids.add(id(edge))

    if len(selected) < max_edges:
        remainder_pool = sorted(
            [edge for edge in edges if id(edge) not in selected_ids],
            key=_edge_priority_sort_key,
        )
        need = max_edges - len(selected)
        selected.extend(remainder_pool[:need])

    return sorted(selected[:max_edges], key=_edge_priority_sort_key)


def apply_projection_filters(
    *,
    topology: dict[str, Any],
    allowed_relations: tuple[str, ...] | None,
    allowed_categories: tuple[str, ...] | None,
    max_edges: int | None,
    preserve_nodes: set[str] | None = None,
    tier: str | None = None,
    tier_definitions: dict[str, dict[str, Any]] | None = None,
    max_containment_depth: int | None = None,
) -> dict[str, Any]:
    """Apply projection filters to a topology dict.

    Returns a new topology dict with filtered nodes/edges and projection_filter metadata.
    """
    nodes_in = list(topology.get("nodes", []))
    edges_in = list(topology.get("edges", []))
    preserve = set(preserve_nodes or set())

    relation_allow_set = set(allowed_relations or ())
    category_allow_set = set(allowed_categories or ())
    relation_filter_enabled = len(relation_allow_set) > 0

    tier_node_set: set[str] | None = None
    node_tier_filtered = 0
    if tier and tier_definitions:
        tier_node_set, _ = resolve_tier_node_set(nodes_in, tier, tier_definitions)
    tier_filter_enabled = tier_node_set is not None
    category_filter_enabled = len(category_allow_set) > 0 and not tier_filter_enabled

    category_of: dict[str, str] = {}
    candidate_node_names: set[str] = set()
    all_named_nodes: set[str] = set()
    node_without_name = 0
    node_category_filtered = 0
    node_depth_filtered = 0
    for node in nodes_in:
        name = str(node.get("name", ""))
        category = str(node.get("category", ""))
        if not name:
            node_without_name += 1
            continue
        all_named_nodes.add(name)
        category_of[name] = category
        # Containment depth filter (applied before category/tier)
        if max_containment_depth is not None:
            cd = int(node.get("containment_depth", 0))
            if cd > max_containment_depth:
                node_depth_filtered += 1
                continue
        if tier_filter_enabled:
            if name in tier_node_set:  # type: ignore[operator]
                candidate_node_names.add(name)
            else:
                node_tier_filtered += 1
        elif not category_filter_enabled or category in category_allow_set:
            candidate_node_names.add(name)
        else:
            node_category_filtered += 1
    candidate_node_names.update(preserve)
    preserve_matched = len(preserve & all_named_nodes)
    preserve_unmatched = sorted(preserve - all_named_nodes)

    filtered_edges: list[dict[str, Any]] = []
    edge_invalid_endpoint = 0
    edge_node_scope_filtered = 0
    edge_relation_filtered = 0
    edge_after_node_scope = 0
    for edge in edges_in:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        relation = str(edge.get("relation", ""))
        if not source or not target:
            edge_invalid_endpoint += 1
            continue
        if source not in candidate_node_names or target not in candidate_node_names:
            edge_node_scope_filtered += 1
            continue
        edge_after_node_scope += 1
        if relation_filter_enabled and relation not in relation_allow_set:
            edge_relation_filtered += 1
            continue
        filtered_edges.append(edge)

    connected = {str(edge.get("source", "")) for edge in filtered_edges}
    connected.update({str(edge.get("target", "")) for edge in filtered_edges})
    connected.update(preserve)

    nodes_out = [
        node
        for node in nodes_in
        if str(node.get("name", "")) in connected
    ]
    node_disconnected = 0
    node_candidates = 0
    for node in nodes_in:
        name = str(node.get("name", ""))
        if not name:
            continue
        if name in candidate_node_names:
            node_candidates += 1
            if name not in connected:
                node_disconnected += 1

    edge_total_before_cap = len(filtered_edges)
    projection_capped = False
    if max_edges is not None and max_edges > 0 and edge_total_before_cap > max_edges:
        filtered_edges = _cap_edges_relation_balanced(filtered_edges, max_edges=max_edges)
        projection_capped = True
    edge_capped = max(0, edge_total_before_cap - len(filtered_edges))

    relation_distribution: dict[str, int] = {}
    for edge in filtered_edges:
        relation_name = str(edge.get("relation", ""))
        if not relation_name:
            continue
        relation_distribution[relation_name] = relation_distribution.get(relation_name, 0) + 1

    payload = dict(topology)
    payload["nodes"] = nodes_out
    payload["edges"] = filtered_edges
    payload["node_count"] = len(nodes_out)
    payload["edge_count"] = len(filtered_edges)
    payload["edge_total_before_cap"] = edge_total_before_cap
    payload["edge_truncated"] = bool(topology.get("edge_truncated", False)) or projection_capped
    payload["relation_distribution"] = relation_distribution
    payload["projection_filter"] = {
        "stages": {
            "node_input": len(nodes_in),
            "node_candidates": node_candidates,
            "node_connected_or_preserved": len(nodes_out),
            "edge_input": len(edges_in),
            "edge_after_node_scope": edge_after_node_scope,
            "edge_after_relation": edge_total_before_cap,
            "edge_before_cap": edge_total_before_cap,
            "edge_after_cap": len(filtered_edges),
        },
        "drop_reasons": {
            "node_without_name": node_without_name,
            "node_category_filtered": node_category_filtered,
            "node_tier_filtered": node_tier_filtered,
            "node_depth_filtered": node_depth_filtered,
            "node_disconnected": node_disconnected,
            "edge_invalid_endpoint": edge_invalid_endpoint,
            "edge_node_scope_filtered": edge_node_scope_filtered,
            "edge_relation_filtered": edge_relation_filtered,
            "edge_capped": edge_capped,
        },
        "preserve": {
            "requested": len(preserve),
            "matched": preserve_matched,
            "retained": sum(1 for node in nodes_out if str(node.get("name", "")) in preserve),
            "unmatched": preserve_unmatched[:16],
        },
    }
    return payload
