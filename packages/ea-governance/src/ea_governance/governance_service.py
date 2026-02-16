"""Governance service layer — pure functions for governance-specific queries.

Follows kernel_service.py pattern: pure functions, dict[str, Any] return, lazy import.
Depends only on ProfileRegistry (not GovernanceContainer).
"""

from __future__ import annotations

from typing import Any

from ea_profile.types import make_node_id


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

# System view profiles (cross-layer views, not individual layers)
_SYSTEM_VIEW_MAP = {
    "development": "EASystem-Development",
}

# ── Cross-layer node identity (shared by all cross-layer functions) ──
# ModelPort name → owning layer_key  (derived from _EA_SYS_LAYER_KEYS)
_MODEL_PORT_TO_LAYER: dict[str, str] = {
    f"{key.capitalize()}ModelPort": key for key in _EA_SYS_LAYER_KEYS
}


def model_port_home_layer(port_name: str) -> str | None:
    """Return the layer_key that *owns* a ModelPort, or None."""
    return _MODEL_PORT_TO_LAYER.get(port_name)


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
    """6 EA-sys layer profiles + 2 governance stack + system view profiles summary."""
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

    system_views: list[dict[str, Any]] = []
    for view_id, reg_name in _SYSTEM_VIEW_MAP.items():
        profile = registry.get(reg_name)
        if profile is None:
            system_views.append({"view_id": view_id, "profile_name": reg_name, "loaded": False})
        else:
            system_views.append({
                "view_id": view_id,
                "profile_name": reg_name,
                "loaded": True,
                **_profile_summary(profile),
            })

    total = (
        sum(1 for item in layers if item.get("loaded"))
        + sum(1 for item in governance_stack if item.get("loaded"))
        + sum(1 for item in system_views if item.get("loaded"))
    )
    return {
        "layers": layers,
        "governance_stack": governance_stack,
        "system_views": system_views,
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


# ── GS5: Layer M2 schema (raw profile data for graph viz) ────────


def _serialize_i18n(
    value: object,
) -> str | dict[str, str]:
    """Pass through I18nString as-is for JSON serialization."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return value
    return ""


def _load_and_localize(profile_name: str, lang: str | None) -> object | None:
    """Load profile from registry with optional i18n localization."""
    registry = _get_registry()
    profile = registry.get(profile_name)
    if profile is None or not lang or lang == "en":
        return profile

    from pathlib import Path

    import ea_kernel
    from ea_kernel.localizer import ProfileLocalizer

    search_path = Path(ea_kernel.__file__).parent / "profiles" / "ea_sys"
    localizer = ProfileLocalizer(patch_dir=search_path)
    return localizer.localize(profile, lang, search_path=search_path)


def layer_schema(
    layer_key: str,
    *,
    lang: str | None = None,
) -> dict[str, Any]:
    """Return raw M2 profile data for a layer — elements, relations, and rules.

    Unlike layer_profile_detail() which returns topology (expanded M1 edges),
    this returns the profile definition itself — the metamodel (M2).
    """
    if layer_key not in _EA_SYS_PROFILE_MAP:
        return {
            "error": f"Unknown layer key: {layer_key}",
            "valid_keys": list(_EA_SYS_PROFILE_MAP.keys()),
        }
    reg_name = _EA_SYS_PROFILE_MAP[layer_key]
    profile = _load_and_localize(reg_name, lang)
    if profile is None:
        return {"error": f"Profile not loaded: {reg_name}"}

    # Elements grouped by domain layer
    elements_by_layer: list[dict[str, Any]] = []
    for layer in profile.domain_layers():
        elems = profile.elements_in_layer(layer)
        elements_by_layer.append({
            "layer": layer,
            "count": len(elems),
            "elements": [
                {
                    "name": e.name,
                    "kernel_type": e.kernel_type,
                    "category": e.category,
                    "description": _serialize_i18n(e.description),
                    "display_name": _serialize_i18n(e.display_name) if e.display_name else None,
                }
                for e in elems
            ],
        })

    # Relations
    relations = [
        {
            "name": r.name,
            "kernel_relation": r.kernel_relation,
            "description": _serialize_i18n(r.description),
            "display_name": _serialize_i18n(r.display_name) if r.display_name else None,
            "direction": getattr(r, "direction", None),
        }
        for r in profile.relations
    ]

    # Validity rules (raw profile rules — M2 definitions)
    rules = [
        {
            "source": r.source_pattern,
            "target": r.target_pattern,
            "relation": r.relationship_name,
            "valid": r.valid,
            "priority": r.priority,
            "notes": r.notes or "",
        }
        for r in profile.validity_rules
    ]

    return {
        "layer_key": layer_key,
        "profile_name": reg_name,
        "version": profile.version,
        "element_count": len(profile.elements),
        "relation_count": len(profile.relations),
        "rule_count": len(profile.validity_rules),
        "elements_by_layer": elements_by_layer,
        "relations": relations,
        "rules": rules,
    }


# ── GS6: Business flow topology (cross-layer graph) ──────────


_BUSINESS_FLOW_CATEGORIES = {"Composite", "ActiveStructure", "Interface"}

# Runtime chain: Decision → Needs → Kernel → Flow
_RUNTIME_CHAIN = [("decision", "needs"), ("needs", "kernel"), ("kernel", "flow")]


def business_flow_topology(*, lang: str | None = None) -> dict[str, Any]:
    """Build a cross-layer business flow topology from all 6 EA-sys profiles.

    Uses ``make_node_id()`` for globally unique element identity and
    ``model_port_home_layer()`` for 6×6 ModelPort bridge resolution.

    Generates four edge types:
    - ``intra_layer``: validity-rule edges within one layer
    - ``model_port_bridge``: foreign ModelPort → home ModelPort (6×6 cross-layer)
    - ``runtime_chain``: Decision → Needs → Kernel → Flow (synthetic)
    - ``governance_oversight``: Governance → each other layer (synthetic)
    """
    layers: list[dict[str, Any]] = []
    all_edges: list[dict[str, Any]] = []
    total_elements = 0

    # Pass 1: collect elements per layer with namespaced node_id
    for key in _EA_SYS_LAYER_KEYS:
        reg_name = _EA_SYS_PROFILE_MAP[key]
        profile = _load_and_localize(reg_name, lang)
        if profile is None:
            layers.append({"layer_key": key, "loaded": False, "elements": []})
            continue

        filtered: list[dict[str, Any]] = []
        # local name → node_id for rule edge resolution within this layer
        local_id_map: dict[str, str] = {}
        for domain_layer in profile.domain_layers():
            for e in profile.elements_in_layer(domain_layer):
                if e.category not in _BUSINESS_FLOW_CATEGORIES:
                    continue
                is_model_port = e.name.endswith("ModelPort")
                node_id = make_node_id(key, e.name)
                elem_dict: dict[str, Any] = {
                    "node_id": node_id,
                    "name": e.name,
                    "kernel_type": e.kernel_type,
                    "category": e.category,
                    "description": _serialize_i18n(e.description),
                    "display_name": _serialize_i18n(e.display_name) if e.display_name else None,
                    "domain_layer": domain_layer,
                    "is_model_port": is_model_port,
                }
                filtered.append(elem_dict)
                local_id_map[e.name] = node_id

        # Intra-layer edges from validity rules
        for r in profile.validity_rules:
            if not r.valid:
                continue
            src, tgt = r.source_pattern, r.target_pattern
            if src.startswith("@") or src.startswith("#"):
                continue
            if tgt.startswith("@") or tgt.startswith("#"):
                continue
            src_id = local_id_map.get(src)
            tgt_id = local_id_map.get(tgt)
            if not src_id or not tgt_id:
                continue
            all_edges.append({
                "source": src_id,
                "target": tgt_id,
                "relation": r.relationship_name,
                "edge_type": "intra_layer",
                "source_layer": key,
                "target_layer": key,
            })

        layers.append({
            "layer_key": key,
            "loaded": True,
            "profile_name": reg_name,
            "version": profile.version,
            "element_count": len(filtered),
            "elements": filtered,
        })
        total_elements += len(filtered)

    # Pass 2: ModelPort bridge edges (6×6 cross-layer)
    # For each layer's foreign ModelPort, connect to the target layer's home port.
    # E.g. infra::GovernanceModelPort → governance::GovernanceModelPort
    node_id_set = _collect_node_ids(layers)
    for layer in layers:
        if not layer.get("loaded"):
            continue
        src_layer = layer["layer_key"]
        for elem in layer["elements"]:
            if not elem["is_model_port"]:
                continue
            target_layer = model_port_home_layer(elem["name"])
            if not target_layer or target_layer == src_layer:
                continue  # skip home port (self-reference)
            home_node_id = make_node_id(target_layer, elem["name"])
            if home_node_id not in node_id_set:
                continue
            all_edges.append({
                "source": elem["node_id"],
                "target": home_node_id,
                "relation": "model_port_bridge",
                "edge_type": "model_port_bridge",
                "source_layer": src_layer,
                "target_layer": target_layer,
            })

    # Synthetic runtime chain edges (Decision → Needs → Kernel → Flow)
    runtime_chain: list[dict[str, Any]] = []
    for src_layer, tgt_layer in _RUNTIME_CHAIN:
        src_id = _find_layer_composite(layers, src_layer)
        tgt_id = _find_layer_composite(layers, tgt_layer)
        if src_id and tgt_id:
            edge = {
                "source": src_id,
                "target": tgt_id,
                "relation": "runtime_chain",
                "edge_type": "runtime_chain",
                "source_layer": src_layer,
                "target_layer": tgt_layer,
            }
            all_edges.append(edge)
            runtime_chain.append(edge)

    # Synthetic governance oversight edges
    gov_id = _find_layer_composite(layers, "governance")
    if gov_id:
        for key in _EA_SYS_LAYER_KEYS:
            if key == "governance":
                continue
            tgt_id = _find_layer_composite(layers, key)
            if tgt_id:
                all_edges.append({
                    "source": gov_id,
                    "target": tgt_id,
                    "relation": "governance_oversight",
                    "edge_type": "governance_oversight",
                    "source_layer": "governance",
                    "target_layer": key,
                })

    return {
        "layers": layers,
        "edges": all_edges,
        "runtime_chain": runtime_chain,
        "total_elements": total_elements,
        "total_edges": len(all_edges),
    }


def _collect_node_ids(layers: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for layer in layers:
        for elem in layer.get("elements", []):
            ids.add(elem["node_id"])
    return ids


def _find_layer_composite(layers: list[dict[str, Any]], layer_key: str) -> str | None:
    """Find the main *Layer composite node_id for a given layer."""
    for layer in layers:
        if layer["layer_key"] != layer_key or not layer.get("loaded"):
            continue
        for elem in layer["elements"]:
            if elem["category"] == "Composite" and elem["name"].endswith("Layer"):
                return elem["node_id"]
        for elem in layer["elements"]:
            if elem["category"] == "Composite":
                return elem["node_id"]
    return None
