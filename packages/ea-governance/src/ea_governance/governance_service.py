"""Governance service layer — pure functions for governance-specific queries.

Follows kernel_service.py pattern: pure functions, dict[str, Any] return, lazy import.
Depends only on ProfileRegistry (not GovernanceContainer).
"""

from __future__ import annotations

from typing import Any


def _get_registry() -> Any:
    from ea_kernel.profile_registry import ProfileRegistry
    registry = ProfileRegistry()
    registry.bootstrap()
    return registry


# Layer keys that map to EA-sys profiles
_EA_SYS_LAYER_KEYS = ("infra", "governance", "decision", "needs", "kernel", "flow")
_EA_SYS_PROFILE_MAP = {
    "infra": "EASystem-Infra",
    "governance": "EASystem-Governance",
    "decision": "EASystem-Decision",
    "needs": "EASystem-Needs",
    "kernel": "EASystem-Kernel",
    "flow": "EASystem-Flow",
}
_GOV_STACK_PROFILE_MAP = {
    "meta": "GovernanceStack-Meta",
    "external": "GovernanceStack-External",
}


def _profile_summary(profile: Any) -> dict[str, Any]:
    """Build a compact summary dict from a profile object."""
    return {
        "name": profile.name,
        "version": profile.version,
        "element_count": len(profile.elements),
        "relation_count": len(profile.relations),
        "rule_count": len(profile.validity_rules),
    }


# ── GS1: Managed layers overview ────────────────────────────────


def list_managed_layers() -> dict[str, Any]:
    """6 EA-sys layer profiles + 2 governance stack profiles summary."""
    registry = _get_registry()

    layers: list[dict[str, Any]] = []
    for key in _EA_SYS_LAYER_KEYS:
        reg_name = _EA_SYS_PROFILE_MAP[key]
        profile = registry.get(reg_name)
        if profile is None:
            layers.append({"layer_key": key, "profile_name": reg_name, "loaded": False})
        else:
            layers.append({
                "layer_key": key,
                "profile_name": reg_name,
                "loaded": True,
                **_profile_summary(profile),
            })

    governance_stack: list[dict[str, Any]] = []
    for stack_id, reg_name in _GOV_STACK_PROFILE_MAP.items():
        profile = registry.get(reg_name)
        if profile is None:
            governance_stack.append({"stack_id": stack_id, "profile_name": reg_name, "loaded": False})
        else:
            governance_stack.append({
                "stack_id": stack_id,
                "profile_name": reg_name,
                "loaded": True,
                **_profile_summary(profile),
            })

    total = sum(1 for item in layers if item.get("loaded")) + sum(
        1 for item in governance_stack if item.get("loaded")
    )
    return {
        "layers": layers,
        "governance_stack": governance_stack,
        "total_profiles": total,
    }


# ── GS2: Single layer profile detail ────────────────────────────


def layer_profile_detail(layer_key: str) -> dict[str, Any]:
    """Specific layer profile detail + topology metrics."""
    if layer_key not in _EA_SYS_PROFILE_MAP:
        return {
            "error": f"Unknown layer key: {layer_key}",
            "valid_keys": list(_EA_SYS_PROFILE_MAP.keys()),
        }

    reg_name = _EA_SYS_PROFILE_MAP[layer_key]
    registry = _get_registry()
    profile = registry.get(reg_name)
    if profile is None:
        return {"error": f"Profile not loaded: {reg_name}"}

    from ea_kernel.profile_graph import ProfileTopologyGraph
    graph = ProfileTopologyGraph(profile)

    # Elements by layer
    elements_by_layer: list[dict[str, Any]] = []
    for layer in profile.domain_layers():
        elems = profile.elements_in_layer(layer)
        elements_by_layer.append({
            "layer": layer,
            "count": len(elems),
            "elements": [{"name": e.name, "kernel_type": e.kernel_type} for e in elems],
        })

    edges: list[dict[str, Any]] = []
    for src in graph.nodes:
        for edge in graph.outgoing(src):
            edges.append({
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
            })

    return {
        "layer_key": layer_key,
        "profile": _profile_summary(profile),
        "elements_by_layer": elements_by_layer,
        "topology": {
            "node_count": len(graph.nodes),
            "edge_count": len(edges),
            "relation_distribution": graph.relation_distribution(),
        },
    }


# ── GS3: Cross-layer comparison ─────────────────────────────────


def cross_layer_summary() -> dict[str, Any]:
    """6-layer comparison: node_count, edge_count, top relations."""
    registry = _get_registry()

    from ea_kernel.profile_graph import ProfileTopologyGraph

    layer_entries: list[dict[str, Any]] = []
    total_nodes = 0
    total_edges = 0

    for key in _EA_SYS_LAYER_KEYS:
        reg_name = _EA_SYS_PROFILE_MAP[key]
        profile = registry.get(reg_name)
        if profile is None:
            layer_entries.append({"layer_key": key, "loaded": False})
            continue

        graph = ProfileTopologyGraph(profile)
        edge_count = sum(len(graph.outgoing(n)) for n in graph.nodes)
        dist = graph.relation_distribution()
        top_relations = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[:3]

        layer_entries.append({
            "layer_key": key,
            "loaded": True,
            "node_count": len(graph.nodes),
            "edge_count": edge_count,
            "top_relations": [{"relation": r, "count": c} for r, c in top_relations],
        })
        total_nodes += len(graph.nodes)
        total_edges += edge_count

    return {
        "layers": layer_entries,
        "total_nodes": total_nodes,
        "total_edges": total_edges,
    }


# ── GS4: Governance dashboard ───────────────────────────────────


def governance_dashboard() -> dict[str, Any]:
    """Overall governance status: layers + schema + framework profiles."""
    managed = list_managed_layers()

    from ea_governance.governance_schema import GOVERNANCE_SCHEMA
    schema_info = {
        "entity_count": len(GOVERNANCE_SCHEMA.entities),
        "relation_count": len(GOVERNANCE_SCHEMA.relations),
        "entities": [e.name for e in GOVERNANCE_SCHEMA.entities],
        "relations": [r.name for r in GOVERNANCE_SCHEMA.relations],
    }

    registry = _get_registry()
    framework_names = ("ArchiMate", "TOGAF", "Zachman", "BPMN", "SysML2")
    frameworks: list[dict[str, Any]] = []
    for name in framework_names:
        profile = registry.get(name)
        if profile is not None:
            frameworks.append(_profile_summary(profile))

    return {
        "managed_layers": managed,
        "schema": schema_info,
        "frameworks": frameworks,
    }
