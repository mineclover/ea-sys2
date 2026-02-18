"""Governance service layer — pure functions for governance-specific queries.

Follows kernel_service.py pattern: pure functions, dict[str, Any] return, lazy import.
Depends only on ProfileRegistry (not GovernanceContainer).
"""

from __future__ import annotations

import hashlib
from typing import Any

from ea_profile.types import classify_pattern, make_node_id


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


def _m2_identifier(layer_key: str, kind: str, name: str) -> str:
    return f"m2::{layer_key}::{kind}::{name}"


def _m2_rule_identifier(
    layer_key: str,
    source: str,
    relation: str,
    target: str,
    valid: bool,
    priority: int,
) -> str:
    rule_key = f"{source}|{relation}|{target}|{int(valid)}|{priority}"
    digest = hashlib.sha1(rule_key.encode("utf-8")).hexdigest()[:12]
    return f"m2::{layer_key}::rule::{digest}"


def _m1_rule_identifier(profile_name: str, rule_id: str) -> str:
    return f"m1::{profile_name}::rule::{rule_id}"


def _kernel_entity_layer(kernel_type: str) -> str:
    """Resolve kernel layer (L1..L4) for a profile element kernel_type."""
    from ea_kernel.spec import KERNEL_SPEC

    entity = KERNEL_SPEC.get_entity(kernel_type)
    if entity is None:
        return ""
    return entity.layer.value


def _kernel_relation_layer(kernel_relation: str) -> str:
    """Resolve kernel layer (L2/L3) for a profile relation mapping."""
    from ea_kernel.spec import KERNEL_SPEC

    relation = KERNEL_SPEC.get_relation(kernel_relation)
    if relation is None:
        return ""
    return relation.layer.value


def _m2_identifier_system(layer_key: str, profile_name: str) -> dict[str, Any]:
    """Return the canonical identifier computation contract for layer M2."""
    return {
        "layer_key": layer_key,
        "profile_name": profile_name,
        "namespace": "m2",
        "object_identifiers": {
            "element": f"m2::{layer_key}::element::{{element_name}}",
            "relation": f"m2::{layer_key}::relation::{{relation_name}}",
            "category": f"m2::{layer_key}::category::{{category_name}}",
        },
        "rule_identifier": {
            "pattern": f"m2::{layer_key}::rule::{{digest12}}",
            "digest_algorithm": "sha1",
            "digest_length": 12,
            "input_template": "{source}|{relation}|{target}|{valid_int}|{priority_int}",
            "valid_encoding": {"true": 1, "false": 0},
        },
        "profile_rule_binding": {
            "profile_rule_identifier_pattern": f"m1::{profile_name}::rule::{{rule_id}}",
            "binding_fields": ["profile_name", "profile_layer_key", "profile_rule_id"],
        },
        "kernel_layer_mapping": {
            "entity": "KERNEL_SPEC.get_entity(kernel_type).layer.value",
            "relation": "KERNEL_SPEC.get_relation(kernel_relation).layer.value",
        },
    }


_BLUEPRINT_CATEGORY_KO: dict[str, str] = {
    "Composite": "복합 구조",
    "ActiveStructure": "능동 구조",
    "PassiveStructure": "수동 구조",
    "Interface": "인터페이스",
    "Governance": "거버넌스",
    "Behavior": "행동",
    "Event": "이벤트",
    "Goal": "목표",
    "Executable": "실행 항목",
    "Context": "컨텍스트",
    "Assessment": "평가",
}

_LAYER_RESPONSIBILITY_ENTRIES: list[dict[str, Any]] = [
    {
        "layer": "L1",
        "role": "Structure vocabulary (entity nodes)",
        "role_i18n": {"en": "Structure vocabulary (entity nodes)", "ko": "구조 어휘 계층 (엔티티 노드)"},
    },
    {
        "layer": "L2",
        "role": "Structural relation contracts (edge semantics)",
        "role_i18n": {
            "en": "Structural relation contracts (edge semantics)",
            "ko": "정적 관계 계약 (엣지 의미론)",
        },
    },
    {
        "layer": "L3",
        "role": "Behavioral relation contracts (runtime edge semantics)",
        "role_i18n": {
            "en": "Behavioral relation contracts (runtime edge semantics)",
            "ko": "동작 관계 계약 (런타임 엣지 의미론)",
        },
    },
    {
        "layer": "L4",
        "role": "Concrete runtime entities (entity nodes)",
        "role_i18n": {"en": "Concrete runtime entities (entity nodes)", "ko": "구체 런타임 엔티티 (엔티티 노드)"},
    },
]


def _category_display_i18n(category_name: str) -> dict[str, str]:
    return {
        "en": category_name,
        "ko": _BLUEPRINT_CATEGORY_KO.get(category_name, category_name),
    }


def _category_description_i18n(category_name: str, kernel_layer: str) -> dict[str, str]:
    return {
        "en": f"M2 category for {category_name} elements ({kernel_layer}).",
        "ko": f"{category_name} 요소를 분류하는 M2 카테고리 ({kernel_layer}).",
    }


def _build_m2_blueprint(layer_key: str, profile: Any) -> dict[str, Any]:
    """Build kernel-style M2 blueprint from profile categories/rules.

    - categories: profile categories projected with kernel_type/layer
    - relations: profile relations projected with kernel relation layer
    - rules: concrete+pattern rules aggregated at category-to-category level
    """

    category_info: dict[str, dict[str, Any]] = {}
    element_by_name: dict[str, Any] = {}
    for elem in profile.elements:
        element_by_name[elem.name] = elem
        current = category_info.get(elem.category)
        if current is None:
            category_layer = _kernel_entity_layer(elem.kernel_type)
            category_info[elem.category] = {
                "identifier": _m2_identifier(layer_key, "category", elem.category),
                "name": elem.category,
                "kernel_type": elem.kernel_type,
                "kernel_layer": category_layer,
                "display_name": _category_display_i18n(elem.category),
                "description": _category_description_i18n(elem.category, category_layer),
                "element_count": 1,
                "sample_elements": [elem.name],
            }
            continue
        current["element_count"] += 1
        if len(current["sample_elements"]) < 4:
            current["sample_elements"].append(elem.name)

    relation_info: dict[str, dict[str, Any]] = {}
    for rel in profile.relations:
        relation_info[rel.name] = {
            "identifier": _m2_identifier(layer_key, "relation", rel.name),
            "name": rel.name,
            "kernel_relation": rel.kernel_relation,
            "kernel_layer": _kernel_relation_layer(rel.kernel_relation),
            "description": _serialize_i18n(rel.description),
            "display_name": _serialize_i18n(rel.display_name) if rel.display_name else None,
            "direction": getattr(rel, "direction", "") or "",
        }

    def resolve_category(pattern: str) -> str | None:
        if pattern.startswith("@"):
            cat = pattern[1:]
            return cat if cat in category_info else None
        if pattern.startswith("#") or pattern == "*":
            return None
        elem = element_by_name.get(pattern)
        return elem.category if elem is not None else None

    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    rule_ref_sample_limit = 12
    for rule in profile.validity_rules:
        if not rule.valid:
            continue
        src_cat = resolve_category(rule.source_pattern)
        tgt_cat = resolve_category(rule.target_pattern)
        if not src_cat or not tgt_cat:
            continue
        key = (src_cat, tgt_cat, rule.relationship_name)
        existing = edge_map.get(key)
        if existing is None:
            edge_map[key] = {
                "identifier": _m2_rule_identifier(
                    layer_key,
                    src_cat,
                    rule.relationship_name,
                    tgt_cat,
                    True,
                    rule.priority,
                ),
                "source_category": src_cat,
                "target_category": tgt_cat,
                "relation": rule.relationship_name,
                "kernel_relation": relation_info.get(rule.relationship_name, {}).get("kernel_relation", ""),
                "kernel_layer": relation_info.get(rule.relationship_name, {}).get("kernel_layer", ""),
                "rule_count": 1,
                "priority_max": rule.priority,
                "source_examples": [rule.source_pattern],
                "target_examples": [rule.target_pattern],
                "profile_name": profile.name,
                "profile_layer_key": layer_key,
                "profile_rule_ids": [rule.id],
                "profile_rule_identifiers": [_m1_rule_identifier(profile.name, rule.id)],
            }
            continue

        existing["rule_count"] += 1
        if rule.priority > existing["priority_max"]:
            existing["priority_max"] = rule.priority
        if rule.source_pattern not in existing["source_examples"] and len(existing["source_examples"]) < 4:
            existing["source_examples"].append(rule.source_pattern)
        if rule.target_pattern not in existing["target_examples"] and len(existing["target_examples"]) < 4:
            existing["target_examples"].append(rule.target_pattern)
        profile_rule_ids = existing.get("profile_rule_ids")
        if not isinstance(profile_rule_ids, list):
            profile_rule_ids = []
            existing["profile_rule_ids"] = profile_rule_ids
        if rule.id not in profile_rule_ids and len(profile_rule_ids) < rule_ref_sample_limit:
            profile_rule_ids.append(rule.id)
        profile_rule_identifiers = existing.get("profile_rule_identifiers")
        if not isinstance(profile_rule_identifiers, list):
            profile_rule_identifiers = []
            existing["profile_rule_identifiers"] = profile_rule_identifiers
        profile_rule_identifier = _m1_rule_identifier(profile.name, rule.id)
        if (
            profile_rule_identifier not in profile_rule_identifiers
            and len(profile_rule_identifiers) < rule_ref_sample_limit
        ):
            profile_rule_identifiers.append(profile_rule_identifier)

    categories = sorted(
        category_info.values(),
        key=lambda item: (str(item["kernel_layer"]), str(item["name"]).lower()),
    )
    relations = sorted(
        relation_info.values(),
        key=lambda item: (str(item["kernel_layer"]), str(item["name"]).lower()),
    )
    rules = sorted(
        edge_map.values(),
        key=lambda item: (
            str(item["kernel_layer"]),
            str(item["source_category"]).lower(),
            str(item["target_category"]).lower(),
            str(item["relation"]).lower(),
        ),
    )

    return {
        "categories": categories,
        "relations": relations,
        "rules": rules,
        "summary": {
            "category_count": len(categories),
            "relation_count": len(relations),
            "rule_edge_count": len(rules),
        },
        "layer_responsibilities": _LAYER_RESPONSIBILITY_ENTRIES,
    }


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
    from ea_kernel.kernel_service import projection_policy_snapshot

    projection_policy = projection_policy_snapshot(profile_name=reg_name)

    # Elements grouped by domain layer
    elements_by_layer: list[dict[str, Any]] = []
    for layer in profile.domain_layers():
        elems = profile.elements_in_layer(layer)
        elements_by_layer.append({
            "layer": layer,
            "count": len(elems),
            "elements": [
                {
                    "identifier": _m2_identifier(layer_key, "element", e.name),
                    "name": e.name,
                    "kernel_type": e.kernel_type,
                    "kernel_layer": _kernel_entity_layer(e.kernel_type),
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
            "identifier": _m2_identifier(layer_key, "relation", r.name),
            "name": r.name,
            "kernel_relation": r.kernel_relation,
            "kernel_layer": _kernel_relation_layer(r.kernel_relation),
            "description": _serialize_i18n(r.description),
            "display_name": _serialize_i18n(r.display_name) if r.display_name else None,
            "direction": getattr(r, "direction", None),
        }
        for r in profile.relations
    ]

    # Validity rules (raw profile rules — M2 definitions + profile ownership)
    rules = []
    for r in profile.validity_rules:
        identifier = _m2_rule_identifier(
            layer_key,
            r.source_pattern,
            r.relationship_name,
            r.target_pattern,
            r.valid,
            r.priority,
        )
        rules.append({
            "identifier": identifier,
            "source": r.source_pattern,
            "target": r.target_pattern,
            "relation": r.relationship_name,
            "valid": r.valid,
            "priority": r.priority,
            "notes": r.notes or "",
            "description": _serialize_i18n(r.description),
            "source_pattern_kind": classify_pattern(r.source_pattern).value,
            "target_pattern_kind": classify_pattern(r.target_pattern).value,
            "profile_name": reg_name,
            "profile_layer_key": layer_key,
            "profile_rule_id": r.id,
            "profile_rule_identifier": _m1_rule_identifier(reg_name, r.id),
        })

    return {
        "layer_key": layer_key,
        "profile_name": reg_name,
        "version": profile.version,
        "identifier_system": _m2_identifier_system(layer_key, reg_name),
        "element_count": len(profile.elements),
        "relation_count": len(profile.relations),
        "rule_count": len(profile.validity_rules),
        "elements_by_layer": elements_by_layer,
        "relations": relations,
        "rules": rules,
        "m2_blueprint": _build_m2_blueprint(layer_key, profile),
        "projection_policy": projection_policy,
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
