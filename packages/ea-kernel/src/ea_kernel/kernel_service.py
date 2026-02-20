"""Service layer for kernel onboarding use cases.

Pure functions returning structured dicts — suitable for CLI, MCP, or API consumption.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from ea_kernel.types import (
    KernelSchema,
    Layer,
    RuleGroup,
    RuleMetadata,
)
from ea_projection.surface import DEFAULT_SURFACE_PROFILE
from ea_projection.depth import (
    DepthLevelRegistry,
    PROJECTION_DEFAULT_ACTOR_DEPTH,
    PROJECTION_DEFAULT_SEED_DEPTH,
    PROJECTION_LENS_TO_LEVEL,
)
from ea_projection.policy.constants import (
    PROJECTION_POLICY_FILE_NAME,
    TOPIC_QUERY_POLICY_DEFAULT,
)
from ea_projection.policy.normalizer import (
    normalize_topic_query_policy as _normalize_topic_query_policy,
)
from ea_projection.policy.resolver import (
    resolve_projection_policy as _resolve_projection_policy_core,
    projection_policy_snapshot as _projection_policy_snapshot_core,
)
from ea_projection.tier import (
    resolve_tier_definitions as _resolve_tier_definitions_from_loader,
)
from ea_projection.filter import (
    apply_projection_filters as _apply_projection_filters,
    edge_surface_exposed as _edge_surface_exposed,
)
from ea_projection.filter.engine import _cap_edges_relation_balanced
from ea_projection.ext import ProjectionExtension

if TYPE_CHECKING:
    from ea_kernel.rule_corpus import RuleCorpus

# Layer display names
_LAYER_LABELS: dict[Layer, str] = {
    Layer.L1: "L1 Structure",
    Layer.L2: "L2 Relationship",
    Layer.L3: "L3 Behavioral",
    Layer.L4: "L4 Concrete",
}

_RELATION_SEMANTIC_AXIS: dict[str, str] = {
    "contains": "structure",
    "depends_on": "structure",
    "next": "flow",
    "triggers": "causality",
    "constrains": "causality",
    "produces": "dataflow",
    "consumes": "dataflow",
    "coordinates": "orchestration",
    "registers": "registry",
    "available_in": "availability",
    "specialization": "type_meta",
    "redefinition": "type_meta",
    "subsetting": "type_meta",
    "feature_typing": "type_meta",
}
_RELATION_SEMANTIC_INTENT: dict[str, str] = {
    "contains": "composition",
    "depends_on": "dependency",
    "next": "sequence",
    "triggers": "activation",
    "constrains": "guardrail",
    "produces": "output",
    "consumes": "input",
    "coordinates": "coordination",
    "registers": "registration",
    "available_in": "exposure",
    "specialization": "inheritance",
    "redefinition": "override",
    "subsetting": "narrowing",
    "feature_typing": "typing",
}
_RELATION_SEMANTIC_LAYER_OVERRIDES: dict[str, dict[str, dict[str, str]]] = {
    "kernel": {
        "axis": {
            "registers": "contract",
            "available_in": "projection",
            "constrains": "invariant",
        },
        "intent": {
            "registers": "contract_binding",
            "available_in": "projection_surface",
            "constrains": "invariant_enforcement",
        },
    },
    "infra": {
        "axis": {
            "registers": "integration",
            "available_in": "runtime",
            "produces": "persistence",
            "consumes": "persistence",
            "constrains": "policy",
        },
        "intent": {
            "registers": "adapter_binding",
            "available_in": "runtime_exposure",
            "produces": "write",
            "consumes": "read",
            "constrains": "operational_guardrail",
        },
    },
    "needs": {
        "axis": {
            "constrains": "intent",
            "triggers": "motivation",
            "next": "journey",
            "available_in": "touchpoint",
        },
        "intent": {
            "constrains": "priority_alignment",
            "triggers": "need_activation",
            "next": "journey_step",
            "available_in": "context_anchor",
        },
    },
}
_TOPIC_RELATION_PROFILE: dict[str, tuple[str, ...]] = {
    "structural": ("contains", "depends_on", "registers", "available_in"),
    "intent": ("next", "triggers", "constrains", "coordinates", "produces", "consumes"),
}
_TOPIC_VISIBLE_RELATIONS: tuple[str, ...] = (
    *_TOPIC_RELATION_PROFILE["structural"],
    *_TOPIC_RELATION_PROFILE["intent"],
)

_ACTOR_CATEGORY_HINTS: frozenset[str] = frozenset({"Context"})
_ACTOR_NAME_HINTS: tuple[str, ...] = (
    "actor",
    "context",
    "stakeholder",
    "operator",
    "user",
    "author",
    "explorer",
    "designer",
)
_ACTOR_INTERACTION_RELATIONS: tuple[str, ...] = (
    "available_in",
    "contains",
    "depends_on",
    "coordinates",
    "next",
    "triggers",
    "constrains",
)
_ACTOR_INTERACTION_NODE_CATEGORIES: frozenset[str] = frozenset({
    "Context",
    "Composite",
    "Page",
    "Interface",
    "Behavior",
    "Executable",
    "Event",
    "Goal",
    "Governance",
    "Assessment",
})

_PROJECTION_LEVEL_SPECS: dict[str, dict[str, Any]] = DepthLevelRegistry.from_hardcoded().to_level_specs()

_EA_PROFILE_TO_LAYER_KEY: dict[str, str] = {
    "easystem-infra": "infra",
    "easystem-governance": "governance",
    "easystem-decision": "decision",
    "easystem-needs": "needs",
    "easystem-kernel": "kernel",
    "easystem-flow": "flow",
    "easystem-webkernelviz": "web-kernel-viz",
    "easystem-development": "development",
}

_EA_SYS_PROFILE_ORDER: tuple[str, ...] = (
    "EASystem-Infra",
    "EASystem-Governance",
    "EASystem-Decision",
    "EASystem-Needs",
    "EASystem-Kernel",
    "EASystem-Flow",
)

_MODEL_PORT_TO_LAYER: dict[str, str] = {
    f"{layer.capitalize()}ModelPort": layer
    for layer in ("infra", "governance", "decision", "needs", "kernel", "flow")
}


def _projection_policy_path() -> Path:
    return Path(__file__).parent / "profiles" / "ea_sys" / PROJECTION_POLICY_FILE_NAME


@lru_cache(maxsize=64)
def _resolve_projection_policy(profile_name: str) -> dict[str, Any]:
    """Delegate to ea-projection resolver with kernel's policy path."""
    return _resolve_projection_policy_core(
        profile_name,
        policy_path=_projection_policy_path(),
        layer_key=_profile_layer_key(profile_name),
    )


def _resolve_topic_query_policy(profile_name: str) -> dict[str, Any]:
    fallback = _normalize_topic_query_policy(spec=None, fallback=TOPIC_QUERY_POLICY_DEFAULT)
    policy = _resolve_projection_policy(profile_name)
    if "error" in policy:
        return fallback
    topic_policy = policy.get("topic_policy")
    if not isinstance(topic_policy, dict):
        return fallback
    return _normalize_topic_query_policy(spec=topic_policy, fallback=fallback)


def projection_policy_snapshot(*, profile_name: str) -> dict[str, Any]:
    """Expose resolved projection policy (M2 contract + M1 layer policy + UI policy)."""
    return _projection_policy_snapshot_core(
        profile_name=profile_name,
        policy_path=_projection_policy_path(),
        layer_key=_profile_layer_key(profile_name),
    )


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


def _get_localized_spec(lang: str | None = None) -> KernelSchema:
    """Return KERNEL_SPEC with optional i18n patch applied."""
    spec = _get_spec()
    if lang and lang != "en":
        from ea_kernel.schema_loader import load_schema_i18n
        spec = load_schema_i18n(spec, lang)
    return spec


def _serialize_i18n(value: str | dict[str, str]) -> str | dict[str, str]:
    """Pass through I18nString as-is for JSON serialization."""
    return value


# ── UC1: Entity/Relation exploration ──────────────────────────


def list_entities(*, lang: str | None = None) -> dict[str, Any]:
    """UC1: List all kernel entities grouped by layer with hierarchy tree."""
    spec = _get_localized_spec(lang)
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
                    "description": _serialize_i18n(e.description),
                    "display_name": _serialize_i18n(e.display_name) if e.display_name else None,
                }
                for e in entities_in
            ],
        }
        layers.append(layer_data)
    return {
        "total": len(spec.entities),
        "layers": layers,
    }


def list_relations(*, lang: str | None = None) -> dict[str, Any]:
    """UC1: List all kernel relations grouped by layer with roles."""
    spec = _get_localized_spec(lang)
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
                    "owns": list(r.owns),
                    "owns_key": r.owns_key,
                    "description": _serialize_i18n(r.description),
                    "display_name": _serialize_i18n(r.display_name) if r.display_name else None,
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


def describe_profile(
    *,
    name: str,
    lang: str | None = None,
) -> dict[str, Any] | None:
    """UC2: Describe a profile — elements by layer, relations, rule summary."""
    profile = _load_profile(name, lang=lang)
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
                {
                    "name": e.name,
                    "kernel_type": e.kernel_type,
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
            "display_name": _serialize_i18n(r.display_name) if r.display_name else None,
        }
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


def list_rules(*, group: str | None = None, relation: str | None = None) -> dict[str, Any]:
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


def describe_rule(*, rule_id: str) -> dict[str, Any] | None:
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


def judge(*, source: str, target: str, relation: str) -> dict[str, Any]:
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


def _load_profile(name: str, *, lang: str | None = None) -> Any:
    from ea_kernel.profile_registry import ProfileRegistry
    registry = ProfileRegistry()
    registry.bootstrap()
    profile = registry.get(name)
    if profile is None or not lang or lang == "en":
        return profile
    from pathlib import Path
    from ea_kernel.localizer import ProfileLocalizer
    search_path = Path(__file__).parent / "profiles" / "ea_sys"
    localizer = ProfileLocalizer(patch_dir=search_path)
    return localizer.localize(profile, lang, search_path=search_path)


def _profile_layer_key(profile_name: str) -> str | None:
    return _EA_PROFILE_TO_LAYER_KEY.get(profile_name.strip().lower())


def _model_port_home_layer(element_name: str) -> str | None:
    return _MODEL_PORT_TO_LAYER.get(element_name)


def _node_domain_info(
    *,
    element_name: str,
    profile_layer_key: str | None,
) -> tuple[str | None, str]:
    home_layer = _model_port_home_layer(element_name)
    if profile_layer_key is None:
        return home_layer, "unknown"
    if home_layer is None:
        return profile_layer_key, "owned"
    if home_layer == profile_layer_key:
        return home_layer, "home_port"
    return home_layer, "foreign_port"


def _edge_domain_scope(
    edge: dict[str, Any],
    *,
    profile_layer_key: str | None,
) -> str:
    if profile_layer_key is None:
        return "all"
    _, src_ownership = _node_domain_info(
        element_name=str(edge.get("source", "")),
        profile_layer_key=profile_layer_key,
    )
    _, tgt_ownership = _node_domain_info(
        element_name=str(edge.get("target", "")),
        profile_layer_key=profile_layer_key,
    )
    if src_ownership == "foreign_port" or tgt_ownership == "foreign_port":
        return "bridge"
    return "owned"


def _build_rule_ref(
    *,
    profile_name: str,
    profile_layer_key: str | None,
    rule: Any | None,
    fallback_rule_id: str,
    fallback_priority: int,
) -> dict[str, Any]:
    if rule is None:
        return {
            "profile": profile_name,
            "profile_layer_key": profile_layer_key,
            "rule_id": fallback_rule_id,
            "source_pattern": "",
            "target_pattern": "",
            "relation": "",
            "valid": True,
            "priority": fallback_priority,
            "notes": "",
            "description": "",
        }
    return {
        "profile": profile_name,
        "profile_layer_key": profile_layer_key,
        "rule_id": str(rule.id),
        "source_pattern": str(rule.source_pattern),
        "target_pattern": str(rule.target_pattern),
        "relation": str(rule.relationship_name),
        "valid": bool(rule.valid),
        "priority": int(rule.priority),
        "notes": str(rule.notes or ""),
        "description": _serialize_i18n(rule.description),
    }


def _to_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback


def _is_exact_rule_pattern(pattern: str) -> bool:
    normalized = str(pattern).strip()
    return bool(normalized) and normalized != "*" and not normalized.startswith("@") and not normalized.startswith("#")


def _edge_origin_from_rule_patterns(source_pattern: str, target_pattern: str) -> str:
    if _is_exact_rule_pattern(source_pattern) and _is_exact_rule_pattern(target_pattern):
        return "explicit"
    return "expanded"


def _normalize_edge_origin(value: Any) -> str:
    normalized = str(value).strip().lower()
    if normalized in {"explicit", "expanded", "mixed"}:
        return normalized
    return "expanded"


def _edge_origin_from_counts(explicit_count: int, expanded_count: int) -> str:
    if explicit_count > 0 and expanded_count > 0:
        return "mixed"
    if explicit_count > 0:
        return "explicit"
    return "expanded"


def _normalized_semantic_layer_key(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized else "global"


def _semantic_layer_override(
    *,
    semantic_layer_key: str | None,
    relation: str,
    field: str,
) -> str | None:
    relation_name = str(relation).strip().lower()
    if not relation_name:
        return None
    layer_key = _normalized_semantic_layer_key(semantic_layer_key)
    layer_override = _RELATION_SEMANTIC_LAYER_OVERRIDES.get(layer_key)
    if not isinstance(layer_override, dict):
        return None
    typed_override = layer_override.get(field)
    if not isinstance(typed_override, dict):
        return None
    value = typed_override.get(relation_name)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _semantic_profile_scope(semantic_layer_key: str | None) -> str:
    layer_key = _normalized_semantic_layer_key(semantic_layer_key)
    if layer_key in _RELATION_SEMANTIC_LAYER_OVERRIDES:
        return f"layer:{layer_key}"
    return "global"


def _edge_semantic_axis(
    relation: str,
    *,
    semantic_layer_key: str | None,
) -> str:
    override = _semantic_layer_override(
        semantic_layer_key=semantic_layer_key,
        relation=relation,
        field="axis",
    )
    if override is not None:
        return override
    return _RELATION_SEMANTIC_AXIS.get(str(relation).strip().lower(), "other")


def _edge_semantic_intent(
    relation: str,
    *,
    semantic_layer_key: str | None,
) -> str:
    override = _semantic_layer_override(
        semantic_layer_key=semantic_layer_key,
        relation=relation,
        field="intent",
    )
    if override is not None:
        return override
    return _RELATION_SEMANTIC_INTENT.get(str(relation).strip().lower(), "other")



def _edge_origin_counts(edge: dict[str, Any]) -> tuple[int, int]:
    rule_count = max(1, _to_non_negative_int(edge.get("rule_count", 1), 1))
    explicit_count = _to_non_negative_int(edge.get("explicit_count"), 0)
    expanded_count = _to_non_negative_int(edge.get("expanded_count"), 0)
    if explicit_count == 0 and expanded_count == 0:
        origin = _normalize_edge_origin(edge.get("edge_origin", "expanded"))
        if origin == "explicit":
            explicit_count = rule_count
        elif origin == "mixed":
            explicit_count = max(1, rule_count // 2)
            expanded_count = max(1, rule_count - explicit_count)
        else:
            expanded_count = rule_count
    return explicit_count, expanded_count


def _normalize_edge_origin_fields(edge: dict[str, Any]) -> dict[str, Any]:
    explicit_count, expanded_count = _edge_origin_counts(edge)
    edge["explicit_count"] = explicit_count
    edge["expanded_count"] = expanded_count
    edge["edge_origin"] = _edge_origin_from_counts(explicit_count, expanded_count)
    return edge


def _build_semantic_view(
    edges: list[dict[str, Any]],
    *,
    semantic_layer_key: str | None,
) -> dict[str, Any]:
    axis_distribution: dict[str, int] = {}
    intent_distribution: dict[str, int] = {}
    surface_edges = 0
    deep_edges = 0
    for edge in edges:
        relation = str(edge.get("relation", ""))
        axis = str(edge.get("semantic_axis", "")).strip() or _edge_semantic_axis(
            relation,
            semantic_layer_key=semantic_layer_key,
        )
        intent = str(edge.get("semantic_intent", "")).strip() or _edge_semantic_intent(
            relation,
            semantic_layer_key=semantic_layer_key,
        )
        axis_distribution[axis] = axis_distribution.get(axis, 0) + 1
        intent_distribution[intent] = intent_distribution.get(intent, 0) + 1
        if bool(edge.get("surface_exposed")) if "surface_exposed" in edge else _edge_surface_exposed(relation):
            surface_edges += 1
        else:
            deep_edges += 1
    dominant_axis = None
    dominant_axis_edges = 0
    for axis, count in axis_distribution.items():
        if count > dominant_axis_edges:
            dominant_axis = axis
            dominant_axis_edges = count
    total_edges = len(edges)
    return {
        "profile_scope": _semantic_profile_scope(semantic_layer_key),
        "layer_key": _normalized_semantic_layer_key(semantic_layer_key),
        "axis_distribution": axis_distribution,
        "intent_distribution": intent_distribution,
        "surface_edges": surface_edges,
        "deep_edges": deep_edges,
        "dominant_axis": dominant_axis,
        "dominant_axis_share": (dominant_axis_edges / total_edges) if total_edges > 0 else 0.0,
    }


def _finalize_edge_payload(
    edges: list[dict[str, Any]],
    *,
    include_rule_provenance: bool,
    semantic_layer_key: str | None,
) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        item = _normalize_edge_origin_fields(dict(edge))
        relation = str(item.get("relation", ""))
        item["semantic_axis"] = _edge_semantic_axis(
            relation,
            semantic_layer_key=semantic_layer_key,
        )
        item["semantic_intent"] = _edge_semantic_intent(
            relation,
            semantic_layer_key=semantic_layer_key,
        )
        item["surface_exposed"] = _edge_surface_exposed(relation)
        if not include_rule_provenance:
            item.pop("rule_id", None)
            item.pop("rule_ref", None)
            item.pop("rule_refs", None)
        finalized.append(item)
    return finalized


def _edge_priority_sort_key(edge: dict[str, Any]) -> tuple[int, str, str, str]:
    return (
        -int(edge.get("priority", 0)),
        str(edge.get("relation", "")),
        str(edge.get("source", "")),
        str(edge.get("target", "")),
    )


def _is_actor_element(element: Any) -> bool:
    if isinstance(element, dict):
        category = str(element.get("category", ""))
        name = str(element.get("name", "")).lower()
    else:
        category = str(getattr(element, "category", ""))
        name = str(getattr(element, "name", "")).lower()
    if category in _ACTOR_CATEGORY_HINTS:
        return True
    return any(token in name for token in _ACTOR_NAME_HINTS)


def _is_actor_interaction_edge(
    edge: dict[str, Any],
    *,
    category_of: dict[str, str],
) -> bool:
    relation = str(edge.get("relation", ""))
    source = str(edge.get("source", ""))
    target = str(edge.get("target", ""))
    src_category = category_of.get(source, "")
    tgt_category = category_of.get(target, "")

    if (
        src_category not in _ACTOR_INTERACTION_NODE_CATEGORIES
        or tgt_category not in _ACTOR_INTERACTION_NODE_CATEGORIES
    ):
        return False

    if relation == "available_in":
        return src_category == "Context" and tgt_category in {"Composite", "Page", "Interface"}
    if relation == "contains":
        return src_category in {"Composite", "Page", "Interface"} and tgt_category in {
            "Page",
            "Interface",
            "Behavior",
            "Executable",
            "Goal",
            "Event",
        }
    if relation in {"depends_on", "coordinates"}:
        return src_category in {"Page", "Interface", "Behavior", "Executable"} and tgt_category in {
            "Page",
            "Interface",
            "Behavior",
            "Executable",
            "Event",
            "Goal",
            "Governance",
            "Assessment",
        }
    if relation == "next":
        return src_category in {"Page", "Behavior", "Executable"} and tgt_category in {"Page", "Behavior", "Executable"}
    if relation == "triggers":
        return src_category in {"Event"} and tgt_category in {"Behavior", "Executable", "Event"}
    if relation == "constrains":
        return src_category in {"Goal", "Governance", "Assessment"} and tgt_category in {
            "Behavior",
            "Executable",
            "Page",
            "Interface",
            "Goal",
            "Governance",
            "Assessment",
        }
    return False


def _build_actor_focus_graph(
    *,
    edges: list[dict[str, Any]],
    selected_relations: list[str] | tuple[str, ...],
    category_of: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, set[str]], dict[str, int]]:
    selected_set = {str(name) for name in selected_relations if str(name)}
    if not selected_set:
        return [], {}, {}

    interaction_edges: list[dict[str, Any]] = []
    adjacency: dict[str, set[str]] = {}
    interaction_degree: dict[str, int] = {}
    for edge in edges:
        relation_name = str(edge.get("relation", ""))
        if relation_name not in selected_set:
            continue
        if not _is_actor_interaction_edge(edge, category_of=category_of):
            continue
        source_name = str(edge.get("source", ""))
        target_name = str(edge.get("target", ""))
        if not source_name or not target_name:
            continue

        interaction_edges.append(edge)
        adjacency.setdefault(source_name, set()).add(target_name)
        adjacency.setdefault(target_name, set()).add(source_name)
        interaction_degree[source_name] = int(interaction_degree.get(source_name, 0)) + 1
        interaction_degree[target_name] = int(interaction_degree.get(target_name, 0)) + 1
    return interaction_edges, adjacency, interaction_degree


def _rank_actor_candidates(
    *,
    actor_candidates: list[dict[str, Any]],
    interaction_degree: dict[str, int],
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for item in actor_candidates:
        enriched = dict(item)
        actor_name = str(enriched.get("name", ""))
        enriched["interaction_degree"] = int(interaction_degree.get(actor_name, 0))
        ranked.append(enriched)
    return sorted(
        ranked,
        key=lambda item: (
            -int(item.get("interaction_degree", 0)),
            str(item.get("layer", "")),
            str(item.get("name", "")).lower(),
        ),
    )


def _merge_actor_candidates_with_interaction_nodes(
    *,
    actor_candidates: list[dict[str, Any]],
    node_lookup: dict[str, dict[str, Any]],
    interaction_degree: dict[str, int],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in actor_candidates:
        actor_name = str(item.get("name", ""))
        if not actor_name:
            continue
        merged[actor_name] = dict(item)

    for actor_name in sorted(
        interaction_degree.keys(),
        key=lambda name: (
            -int(interaction_degree.get(name, 0)),
            str(name).lower(),
        ),
    ):
        if actor_name in merged:
            continue
        node = node_lookup.get(actor_name)
        if not isinstance(node, dict):
            continue
        category = str(node.get("category", ""))
        if category not in _ACTOR_INTERACTION_NODE_CATEGORIES:
            continue
        merged[actor_name] = {
            "name": actor_name,
            "layer": str(node.get("layer", "")),
            "category": category,
            "description": node.get("description"),
            "display_name": node.get("display_name"),
        }

    return _rank_actor_candidates(
        actor_candidates=list(merged.values()),
        interaction_degree=interaction_degree,
    )


def _resolve_actor_seed(
    *,
    actor_candidates: list[dict[str, Any]],
    requested_actor: str | None,
) -> tuple[str | None, list[str], dict[str, str]]:
    actor_names = [str(item.get("name", "")) for item in actor_candidates if str(item.get("name", ""))]
    actor_lookup = {name.lower(): name for name in actor_names}
    requested = (requested_actor or "").strip()
    if requested:
        return actor_lookup.get(requested.lower()), actor_names, actor_lookup
    for item in actor_candidates:
        if int(item.get("interaction_degree", 0)) > 0:
            return str(item.get("name", "")), actor_names, actor_lookup
    return (actor_names[0] if actor_names else None), actor_names, actor_lookup


def _expand_actor_scope(
    *,
    seed_actor: str,
    depth: int,
    adjacency: dict[str, set[str]],
) -> set[str]:
    scope: set[str] = {seed_actor}
    queue: deque[tuple[str, int]] = deque([(seed_actor, 0)])
    while queue:
        node_name, node_depth = queue.popleft()
        if node_depth >= depth:
            continue
        for next_name in adjacency.get(node_name, set()):
            if next_name in scope:
                continue
            scope.add(next_name)
            queue.append((next_name, node_depth + 1))
    return scope


def _resolve_tier_definitions(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Load tier definitions from resolved policy or fall back to hardcoded defaults."""
    from ea_projection.policy.resolver import load_projection_policy_document
    policy_doc_loaded = load_projection_policy_document(_projection_policy_path())
    return _resolve_tier_definitions_from_loader(policy_doc_loaded)


def _i18n_search_text(value: Any, *, lang: str | None = None) -> str:
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        ordered: list[str] = []
        if lang:
            localized = value.get(lang)
            if isinstance(localized, str) and localized:
                ordered.append(localized)
        english = value.get("en")
        if isinstance(english, str) and english and english not in ordered:
            ordered.append(english)
        for candidate in value.values():
            if isinstance(candidate, str) and candidate and candidate not in ordered:
                ordered.append(candidate)
        return " ".join(ordered).lower()
    return ""


def _topic_query_parts(query: str) -> tuple[str, list[str]]:
    normalized = " ".join(query.strip().lower().split())
    if not normalized:
        return "", []
    tokens = [token for token in re.findall(r"[0-9A-Za-z가-힣_]+", normalized) if token]
    filtered_tokens = [
        token
        for token in tokens
        if len(token) > 1 or not token.isascii()
    ]
    if not filtered_tokens:
        filtered_tokens = [normalized]
    seen: set[str] = set()
    unique_tokens: list[str] = []
    for token in filtered_tokens:
        if token in seen:
            continue
        seen.add(token)
        unique_tokens.append(token)
    return normalized, unique_tokens


def _topic_match_candidates(
    *,
    nodes: list[Any],
    focus_topic: str,
    lang: str | None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query, tokens = _topic_query_parts(focus_topic)
    if not query:
        return {
            "query": "",
            "tokens": [],
            "candidates": [],
        }

    effective_policy = _normalize_topic_query_policy(
        spec=policy,
        fallback=TOPIC_QUERY_POLICY_DEFAULT,
    )
    scoring = effective_policy.get("scoring", {})
    name_token_score = int(scoring.get("name_token", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["name_token"]))
    display_token_score = int(scoring.get("display_token", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["display_token"]))
    description_token_score = int(scoring.get("description_token", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["description_token"]))
    name_exact_score = int(scoring.get("name_exact", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["name_exact"]))
    name_contains_score = int(scoring.get("name_contains", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["name_contains"]))
    display_exact_score = int(scoring.get("display_exact", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["display_exact"]))
    display_contains_score = int(scoring.get("display_contains", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["display_contains"]))
    description_contains_score = int(scoring.get("description_contains", TOPIC_QUERY_POLICY_DEFAULT["scoring"]["description_contains"]))

    candidates: list[dict[str, Any]] = []
    for node in nodes:
        if isinstance(node, dict):
            node_name = str(node.get("name", ""))
            layer_name = str(node.get("layer", ""))
            category_name = str(node.get("category", ""))
            display_value = node.get("display_name")
            description_value = node.get("description")
        else:
            node_name = str(getattr(node, "name", ""))
            layer_name = str(getattr(node, "layer", ""))
            category_name = str(getattr(node, "category", ""))
            display_value = getattr(node, "display_name", None)
            description_value = getattr(node, "description", None)

        if not node_name:
            continue

        name_text = node_name.lower()
        display_text = _i18n_search_text(display_value, lang=lang)
        description_text = _i18n_search_text(description_value, lang=lang)

        score = 0
        matched_in: set[str] = set()
        token_hits = 0
        for token in tokens:
            token_hit = False
            if token in name_text:
                score += name_token_score
                token_hit = True
                matched_in.add("name")
            elif token in display_text:
                score += display_token_score
                token_hit = True
                matched_in.add("display_name")
            elif token in description_text:
                score += description_token_score
                token_hit = True
                matched_in.add("description")
            if token_hit:
                token_hits += 1

        if name_text == query:
            score += name_exact_score
            matched_in.add("name_exact")
        elif query in name_text:
            score += name_contains_score
            matched_in.add("name")

        if display_text == query:
            score += display_exact_score
            matched_in.add("display_name_exact")
        elif query in display_text:
            score += display_contains_score
            matched_in.add("display_name")

        if query in description_text:
            score += description_contains_score
            matched_in.add("description")

        if score <= 0:
            continue
        coverage = (
            (token_hits / len(tokens))
            if tokens
            else 1.0
        )
        candidates.append(
            {
                "name": node_name,
                "layer": layer_name,
                "category": category_name,
                "score": score,
                "coverage": round(coverage, 3),
                "matched_in": sorted(matched_in),
            },
        )

    candidates.sort(
        key=lambda item: (
            -int(item.get("score", 0)),
            -float(item.get("coverage", 0)),
            str(item.get("layer", "")),
            str(item.get("name", "")).lower(),
        ),
    )
    return {
        "query": query,
        "tokens": tokens,
        "candidates": candidates,
    }


def _resolve_topic_relations(
    relation_candidates: list[str],
) -> tuple[list[str], list[str], list[str]]:
    structural = [
        relation
        for relation in _TOPIC_RELATION_PROFILE["structural"]
        if relation in relation_candidates
    ]
    intent = [
        relation
        for relation in _TOPIC_RELATION_PROFILE["intent"]
        if relation in relation_candidates
    ]
    selected: list[str] = []
    for relation in _TOPIC_VISIBLE_RELATIONS:
        if relation not in relation_candidates or relation in selected:
            continue
        selected.append(relation)
    if not selected:
        selected = [
            relation
            for relation in DEFAULT_SURFACE_PROFILE.surface_relations
            if relation in relation_candidates
        ]
    return structural, intent, selected


def _apply_topic_scope(
    *,
    edges: list[dict[str, Any]],
    structural_relations: list[str],
    intent_relations: list[str],
    seed_nodes: list[str],
    focus_depth: int,
    max_scope_nodes: int | None = None,
) -> dict[str, Any]:
    structural_set = set(structural_relations)
    intent_set = set(intent_relations)
    selected_set = structural_set | intent_set

    relation_edges: list[dict[str, Any]] = []
    structural_by_node: dict[str, list[dict[str, Any]]] = {}
    intent_outgoing: dict[str, list[dict[str, Any]]] = {}
    intent_incoming: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        relation = str(edge.get("relation", ""))
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if not source or not target:
            continue
        if relation not in selected_set:
            continue
        relation_edges.append(edge)
        if relation in structural_set:
            structural_by_node.setdefault(source, []).append(edge)
            structural_by_node.setdefault(target, []).append(edge)
        if relation in intent_set:
            intent_outgoing.setdefault(source, []).append(edge)
            intent_incoming.setdefault(target, []).append(edge)

    seed_set = {name for name in seed_nodes if name}
    anchor_scope: set[str] = set(seed_set)
    scope: set[str] = set(seed_set)
    structural_seed_edges: list[dict[str, Any]] = []

    # Keep structural context near topic seeds (directly connected shape only).
    for seed in seed_set:
        for edge in structural_by_node.get(seed, []):
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            if not source or not target:
                continue
            if source not in seed_set and target not in seed_set:
                continue
            structural_seed_edges.append(edge)
            scope.add(source)
            scope.add(target)
            anchor_scope.add(source)
            anchor_scope.add(target)

    # Traverse intent/causal flow from anchored topic scope.
    visited_depth: dict[str, int] = {name: 0 for name in anchor_scope}
    queue: deque[tuple[str, int]] = deque((name, 0) for name in sorted(anchor_scope))
    intent_scope_edges: list[dict[str, Any]] = []
    while queue:
        node_name, depth = queue.popleft()
        if depth >= focus_depth:
            continue
        candidates = list(intent_outgoing.get(node_name, []))
        if depth == 0:
            candidates.extend(intent_incoming.get(node_name, []))

        for edge in candidates:
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            if not source or not target:
                continue
            relation_name = str(edge.get("relation", ""))
            if relation_name not in intent_set:
                continue
            if source == node_name:
                next_node = target
            elif target == node_name:
                next_node = source
            else:
                continue

            intent_scope_edges.append(edge)
            next_depth = depth + 1
            current_best = visited_depth.get(next_node)
            if current_best is not None and current_best <= next_depth:
                continue
            if (
                max_scope_nodes is not None
                and max_scope_nodes > 0
                and next_node not in scope
                and len(scope) >= max_scope_nodes
            ):
                continue
            visited_depth[next_node] = next_depth
            scope.add(next_node)
            queue.append((next_node, next_depth))

    structural_context_edges: list[dict[str, Any]] = []
    for edge in relation_edges:
        relation_name = str(edge.get("relation", ""))
        if relation_name not in structural_set:
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in scope or target not in scope:
            continue
        if source not in anchor_scope and target not in anchor_scope:
            continue
        structural_context_edges.append(edge)

    scoped_edges: list[dict[str, Any]] = []
    seen_edge_ids: set[int] = set()
    for edge in [*structural_seed_edges, *structural_context_edges, *intent_scope_edges]:
        marker = id(edge)
        if marker in seen_edge_ids:
            continue
        seen_edge_ids.add(marker)
        scoped_edges.append(edge)

    if seed_set:
        scope.update(seed_set)
    return {
        "scope": scope,
        "edges": scoped_edges,
        "stats": {
            "input_edges": len(edges),
            "relation_candidate_edges": len(relation_edges),
            "structural_edges": len(structural_context_edges),
            "intent_edges": len(intent_scope_edges),
            "scope_nodes": len(scope),
            "relation_filtered_out": max(0, len(edges) - len(relation_edges)),
            "scope_filtered_out": max(0, len(relation_edges) - len(scoped_edges)),
        },
    }


def profile_topology(
    *,
    profile_name: str,
    cross_layer: bool = False,
    lang: str | None = None,
    max_edges: int | None = None,
    view_mode: str = "raw",
    surface_only: bool = False,
    domain_scope: str | None = "all",
    focus: str | None = None,
    focus_relation: str | None = None,
    focus_layer: str | None = None,
    focus_actor: str | None = None,
    focus_topic: str | None = None,
    focus_seed: str | None = None,
    focus_depth: int | None = None,
    include_rule_provenance: bool = False,
) -> dict[str, Any]:
    """UC6: Full topology graph (nodes + edges) for a profile.

    When *cross_layer* is True only edges that connect elements from
    **different** domain layers are returned and nodes are pruned to those
    participating in at least one such edge.
    """
    from ea_kernel.profile_graph import ProfileTopologyGraph

    profile = _load_profile(profile_name, lang=lang)
    if profile is None:
        return {"error": f"Profile not found: {profile_name}"}

    resolved_profile_layer_key = _profile_layer_key(profile_name)
    requested_domain_scope = (domain_scope or "all").strip().lower()
    if requested_domain_scope not in {"all", "owned", "bridge"}:
        return {
            "error": f"Invalid domain_scope: {domain_scope}. Use one of: all, owned, bridge",
            "valid_domain_scopes": ["all", "owned", "bridge"],
        }

    graph = ProfileTopologyGraph(profile)
    containment_depth_of = graph.containment_depths()

    # Build layer lookup: element name → domain layer
    layer_of: dict[str, str] = {elem.name: elem.layer for elem in profile.elements}
    category_of: dict[str, str] = {elem.name: elem.category for elem in profile.elements}
    rule_lookup: dict[str, Any] = {str(rule.id): rule for rule in profile.validity_rules}

    all_edges: list[dict[str, Any]] = []
    for src in graph.nodes:
        for edge in graph.outgoing(src):
            rule = rule_lookup.get(str(edge.rule_id))
            edge_origin = (
                _edge_origin_from_rule_patterns(
                    source_pattern=str(rule.source_pattern),
                    target_pattern=str(rule.target_pattern),
                )
                if rule is not None
                else "expanded"
            )
            explicit_count = 1 if edge_origin == "explicit" else 0
            all_edges.append({
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "rule_id": edge.rule_id,
                "priority": edge.priority,
                "edge_origin": edge_origin,
                "explicit_count": explicit_count,
                "expanded_count": 1 - explicit_count,
                "rule_ref": _build_rule_ref(
                    profile_name=profile_name,
                    profile_layer_key=resolved_profile_layer_key,
                    rule=rule,
                    fallback_rule_id=str(edge.rule_id),
                    fallback_priority=int(edge.priority),
                ),
            })

    def _elem_dict(elem: Any) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": elem.name,
            "layer": elem.layer,
            "category": elem.category,
            "kernel_type": elem.kernel_type,
            "description": _serialize_i18n(elem.description),
            "containment_depth": containment_depth_of.get(elem.name, 0),
        }
        if elem.display_name:
            d["display_name"] = _serialize_i18n(elem.display_name)
        if resolved_profile_layer_key is not None:
            home_layer, ownership = _node_domain_info(
                element_name=str(elem.name),
                profile_layer_key=resolved_profile_layer_key,
            )
            d["home_layer"] = home_layer
            d["ownership"] = ownership
        return d

    if cross_layer:
        all_edges = [
            e for e in all_edges
            if layer_of.get(e["source"], "") != layer_of.get(e["target"], "")
        ]

    edges_before_domain_scope = list(all_edges)
    if requested_domain_scope != "all" and resolved_profile_layer_key is not None:
        all_edges = [
            edge
            for edge in all_edges
            if _edge_domain_scope(edge, profile_layer_key=resolved_profile_layer_key) == requested_domain_scope
        ]
    effective_domain_scope = (
        requested_domain_scope
        if resolved_profile_layer_key is not None
        else "all"
    )

    owned_edges_total = 0
    bridge_edges_total = 0
    if resolved_profile_layer_key is not None:
        for edge in edges_before_domain_scope:
            if _edge_domain_scope(edge, profile_layer_key=resolved_profile_layer_key) == "bridge":
                bridge_edges_total += 1
            else:
                owned_edges_total += 1

    edge_total_raw = len(all_edges)
    normalized_view = view_mode if view_mode in {"raw", "summary", "focus"} else "raw"
    relation_candidates = sorted({str(edge["relation"]) for edge in all_edges})
    layer_candidates = sorted({str(value) for value in layer_of.values() if value})
    topic_policy = _resolve_topic_query_policy(profile_name)
    focus_payload: dict[str, Any] | None = None
    node_scope: set[str] | None = None
    relation_profile: dict[str, list[str]] = {
        group: [
            name
            for name in relations
            if name in relation_candidates
        ]
        for group, relations in DEFAULT_SURFACE_PROFILE.groups.items()
    }
    relation_profile["interaction"] = [
        name
        for name in _ACTOR_INTERACTION_RELATIONS
        if name in relation_candidates
    ]
    visible_relations = [
        name
        for name in DEFAULT_SURFACE_PROFILE.surface_relations
        if name in relation_candidates
    ]
    hidden_relations = sorted(
        set(relation_candidates) - set(visible_relations),
    )
    surface_filter_applied = False

    def _summarize_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
        for edge in edges:
            key = (
                str(edge["source"]),
                str(edge["target"]),
                str(edge["relation"]),
            )
            existing = grouped.get(key)
            incoming_explicit_count, incoming_expanded_count = _edge_origin_counts(edge)
            if existing is None:
                grouped[key] = {
                    "source": edge["source"],
                    "target": edge["target"],
                    "relation": edge["relation"],
                    "rule_id": edge["rule_id"],
                    "priority": int(edge.get("priority", 0)),
                    "rule_count": 1,
                    "edge_origin": _edge_origin_from_counts(
                        incoming_explicit_count,
                        incoming_expanded_count,
                    ),
                    "explicit_count": incoming_explicit_count,
                    "expanded_count": incoming_expanded_count,
                    "rule_ref": edge.get("rule_ref"),
                    "rule_refs": [edge.get("rule_ref")] if isinstance(edge.get("rule_ref"), dict) else [],
                }
                continue
            existing["rule_count"] = int(existing.get("rule_count", 1)) + 1
            existing["explicit_count"] = _to_non_negative_int(existing.get("explicit_count"), 0) + incoming_explicit_count
            existing["expanded_count"] = _to_non_negative_int(existing.get("expanded_count"), 0) + incoming_expanded_count
            existing["edge_origin"] = _edge_origin_from_counts(
                _to_non_negative_int(existing.get("explicit_count"), 0),
                _to_non_negative_int(existing.get("expanded_count"), 0),
            )
            current_priority = int(edge.get("priority", 0))
            best_priority = int(existing.get("priority", 0))
            if current_priority > best_priority:
                existing["priority"] = current_priority
                existing["rule_id"] = edge["rule_id"]
                existing["rule_ref"] = edge.get("rule_ref")
            elif current_priority == best_priority:
                existing_rule_id = str(existing.get("rule_id", ""))
                candidate_rule_id = str(edge.get("rule_id", ""))
                if candidate_rule_id and (not existing_rule_id or candidate_rule_id < existing_rule_id):
                    existing["rule_id"] = candidate_rule_id
                    existing["rule_ref"] = edge.get("rule_ref")
            candidate_ref = edge.get("rule_ref")
            if isinstance(candidate_ref, dict):
                refs = existing.get("rule_refs")
                if not isinstance(refs, list):
                    refs = []
                    existing["rule_refs"] = refs
                existing_keys = {
                    (str(ref.get("profile", "")), str(ref.get("rule_id", "")))
                    for ref in refs
                    if isinstance(ref, dict)
                }
                ref_key = (
                    str(candidate_ref.get("profile", "")),
                    str(candidate_ref.get("rule_id", "")),
                )
                if ref_key not in existing_keys and len(refs) < 12:
                    refs.append(candidate_ref)
        return sorted(
            grouped.values(),
            key=lambda edge: (
                -int(edge.get("rule_count", 1)),
                -int(edge.get("priority", 0)),
                str(edge.get("relation", "")),
                str(edge.get("source", "")),
                str(edge.get("target", "")),
            ),
        )

    if normalized_view != "focus" and surface_only:
        selected_set = set(visible_relations)
        all_edges = [
            edge
            for edge in all_edges
            if str(edge["relation"]) in selected_set
        ]
        surface_filter_applied = True

    if normalized_view == "summary":
        all_edges = _summarize_edges(all_edges)
    elif normalized_view == "focus":
        normalized_focus = (focus or "core").strip().lower()
        if normalized_focus not in {"core", "relation", "layer", "actor", "topic", "seed"}:
            return {
                "error": f"Invalid focus: {focus}. Use one of: core, relation, layer, actor, topic, seed",
            }

        focus_payload = {
            "mode": normalized_focus,
            "relation_candidates": relation_candidates,
            "layer_candidates": layer_candidates,
            "visibility_profile": relation_profile,
            "visible_relations": visible_relations,
            "hidden_relations": hidden_relations,
        }

        if normalized_focus == "relation":
            requested_relation = (focus_relation or "").strip()
            if not requested_relation:
                return {
                    "error": "focus_relation is required when focus=relation",
                }
            relation_lookup = {name.lower(): name for name in relation_candidates}
            resolved_relation = relation_lookup.get(requested_relation.lower())
            if resolved_relation is None:
                return {
                    "error": f"Unknown focus_relation: {focus_relation}",
                    "available_relations": relation_candidates,
                }
            all_edges = [
                edge
                for edge in all_edges
                if str(edge["relation"]) == resolved_relation
            ]
            focus_payload["relation"] = resolved_relation
        elif normalized_focus == "layer":
            requested_layer = (focus_layer or "").strip()
            if not requested_layer:
                return {
                    "error": "focus_layer is required when focus=layer",
                }
            layer_lookup = {name.lower(): name for name in layer_candidates}
            resolved_layer = layer_lookup.get(requested_layer.lower())
            if resolved_layer is None:
                return {
                    "error": f"Unknown focus_layer: {focus_layer}",
                    "available_layers": layer_candidates,
                }
            all_edges = [
                edge
                for edge in all_edges
                if layer_of.get(str(edge["source"])) == resolved_layer
                or layer_of.get(str(edge["target"])) == resolved_layer
            ]
            focus_payload["layer"] = resolved_layer
        elif normalized_focus == "topic":
            requested_topic = (focus_topic or "").strip()
            if not requested_topic:
                return {
                    "error": "focus_topic is required when focus=topic",
                }
            topic_candidates_payload = _topic_match_candidates(
                nodes=list(profile.elements),
                focus_topic=requested_topic,
                lang=lang,
                policy=topic_policy,
            )
            topic_candidates = topic_candidates_payload.get("candidates", [])
            max_available_topics = int(topic_policy.get("max_available_topics", 60))
            default_depth = int(topic_policy.get("default_depth", 2))
            seed_score_ratio = float(topic_policy.get("seed_score_ratio", 0.72))
            seed_score_floor = int(topic_policy.get("seed_score_floor", 60))
            min_token_coverage = float(topic_policy.get("min_token_coverage", 0.5))
            max_seed_count = int(topic_policy.get("max_seed_count", 8))
            max_match_count = int(topic_policy.get("max_match_count", 16))
            max_scope_nodes_per_depth = int(topic_policy.get("max_scope_nodes_per_depth", 40))
            if not topic_candidates:
                available_topics = sorted(
                    [
                        str(elem.name)
                        for elem in profile.elements
                        if str(elem.name)
                    ],
                    key=str.lower,
                )
                return {
                    "error": f"Unknown focus_topic: {focus_topic}",
                    "available_topics": available_topics[:max_available_topics],
                }

            resolved_depth = focus_depth if focus_depth is not None else default_depth
            if resolved_depth <= 0:
                return {
                    "error": "focus_depth must be greater than zero",
                }

            top_score = int(topic_candidates[0].get("score", 0))
            score_threshold = max(seed_score_floor, int(round(top_score * seed_score_ratio)))
            seed_nodes = [
                str(item.get("name", ""))
                for item in topic_candidates
                if int(item.get("score", 0)) >= score_threshold
                and float(item.get("coverage", 0.0)) >= min_token_coverage
            ][:max_seed_count]
            if not seed_nodes:
                seed_nodes = [str(topic_candidates[0].get("name", ""))]
            seed_nodes = [name for name in seed_nodes if name]
            if not seed_nodes:
                return {
                    "error": f"Unknown focus_topic: {focus_topic}",
                }

            structural_relations, intent_relations, selected_relations = _resolve_topic_relations(
                relation_candidates,
            )
            topic_scope = _apply_topic_scope(
                edges=all_edges,
                structural_relations=structural_relations,
                intent_relations=intent_relations,
                seed_nodes=seed_nodes,
                focus_depth=resolved_depth,
                max_scope_nodes=resolved_depth * max_scope_nodes_per_depth,
            )
            node_scope = set(topic_scope.get("scope", set()))
            all_edges = list(topic_scope.get("edges", []))
            focus_payload["topic"] = requested_topic
            focus_payload["topic_depth"] = resolved_depth
            focus_payload["topic_tokens"] = topic_candidates_payload.get("tokens", [])
            focus_payload["topic_seeds"] = seed_nodes
            focus_payload["topic_matches"] = topic_candidates[:max_match_count]
            focus_payload["selected_relation_profile"] = {
                "structural": structural_relations,
                "intent": intent_relations,
            }
            focus_payload["selected_relations"] = selected_relations
            focus_payload["topic_policy"] = {
                "default_depth": default_depth,
                "seed_score_ratio": seed_score_ratio,
                "seed_score_floor": seed_score_floor,
                "min_token_coverage": min_token_coverage,
                "max_seed_count": max_seed_count,
                "max_match_count": max_match_count,
                "max_scope_nodes_per_depth": max_scope_nodes_per_depth,
            }
            focus_payload["topic_filter_stats"] = topic_scope.get("stats", {})
        elif normalized_focus == "actor":
            actor_node_lookup = {
                elem.name: {
                    "layer": elem.layer,
                    "category": elem.category,
                    "description": _serialize_i18n(elem.description),
                    "display_name": _serialize_i18n(elem.display_name) if elem.display_name else None,
                }
                for elem in profile.elements
                if str(elem.name)
            }
            actor_candidates_raw = sorted(
                [
                    {
                        "name": elem.name,
                        "layer": elem.layer,
                        "category": elem.category,
                        "description": _serialize_i18n(elem.description),
                        "display_name": _serialize_i18n(elem.display_name) if elem.display_name else None,
                    }
                    for elem in profile.elements
                    if _is_actor_element(elem)
                ],
                key=lambda item: (str(item["layer"]), str(item["name"]).lower()),
            )
            selected_relations = relation_profile.get("interaction", [])
            interaction_edges, interaction_adjacency, interaction_degree = _build_actor_focus_graph(
                edges=all_edges,
                selected_relations=selected_relations,
                category_of=category_of,
            )
            actor_candidates = _merge_actor_candidates_with_interaction_nodes(
                actor_candidates=actor_candidates_raw,
                node_lookup=actor_node_lookup,
                interaction_degree=interaction_degree,
            )
            if not actor_candidates:
                return {
                    "error": "No actor candidates available for focus=actor",
                }
            resolved_actor, candidate_names, _ = _resolve_actor_seed(
                actor_candidates=actor_candidates,
                requested_actor=focus_actor,
            )
            if resolved_actor is None:
                return {
                    "error": f"Unknown focus_actor: {focus_actor}",
                    "available_actors": candidate_names,
                }
            if (focus_actor or "").strip() and resolved_actor not in candidate_names:
                return {
                    "error": f"Unknown focus_actor: {focus_actor}",
                    "available_actors": candidate_names,
                }

            resolved_depth = focus_depth if focus_depth is not None else 4
            if resolved_depth <= 0:
                return {
                    "error": "focus_depth must be greater than zero",
                }

            scope = _expand_actor_scope(
                seed_actor=resolved_actor,
                depth=resolved_depth,
                adjacency=interaction_adjacency,
            )
            node_scope = scope
            all_edges = [
                edge
                for edge in interaction_edges
                if str(edge.get("source", "")) in scope
                and str(edge.get("target", "")) in scope
            ]
            focus_payload["actor"] = resolved_actor
            focus_payload["actor_depth"] = resolved_depth
            focus_payload["actor_candidates"] = actor_candidates
            focus_payload["selected_relations"] = selected_relations
            focus_payload["actor_seed_strategy"] = "highest_interaction_degree"
        elif normalized_focus == "seed":
            requested_seed = (focus_seed or "").strip()
            if not requested_seed:
                return {"error": "focus_seed is required when focus=seed"}
            # Case-insensitive element name lookup
            element_name_lookup: dict[str, str] = {
                str(elem.name).lower(): str(elem.name)
                for elem in profile.elements
                if str(elem.name)
            }
            resolved_seed_name = element_name_lookup.get(requested_seed.lower())
            if resolved_seed_name is None:
                return {
                    "error": f"Unknown seed element: {focus_seed}",
                    "available_elements": sorted(element_name_lookup.values())[:60],
                }
            # Build full adjacency from ALL relations (unlike actor which uses interaction only)
            seed_adjacency: dict[str, set[str]] = {}
            for edge in all_edges:
                src = str(edge.get("source", ""))
                tgt = str(edge.get("target", ""))
                if src and tgt:
                    seed_adjacency.setdefault(src, set()).add(tgt)
                    seed_adjacency.setdefault(tgt, set()).add(src)
            resolved_depth = focus_depth if focus_depth is not None else PROJECTION_DEFAULT_SEED_DEPTH
            if resolved_depth <= 0:
                return {"error": "focus_depth must be greater than zero"}
            scope = _expand_actor_scope(
                seed_actor=resolved_seed_name,
                depth=resolved_depth,
                adjacency=seed_adjacency,
            )
            node_scope = scope
            all_edges = [
                edge
                for edge in all_edges
                if str(edge.get("source", "")) in scope
                and str(edge.get("target", "")) in scope
            ]
            focus_payload["seed"] = resolved_seed_name
            focus_payload["seed_depth"] = resolved_depth
            focus_payload["scope_size"] = len(scope)
        else:
            selected_relations = [
                relation
                for relation in DEFAULT_SURFACE_PROFILE.surface_relations
                if relation in relation_candidates
            ]
            selected_set = set(selected_relations)
            all_edges = [
                edge
                for edge in all_edges
                if str(edge["relation"]) in selected_set
            ]
            focus_payload["selected_relations"] = selected_relations

        all_edges = _summarize_edges(all_edges)

    edge_total_before_cap = len(all_edges)
    edge_truncated = False
    if max_edges is not None and edge_total_before_cap > max_edges:
        all_edges = _cap_edges_relation_balanced(all_edges, max_edges=max_edges)
        edge_truncated = True

    if cross_layer:
        connected = {e["source"] for e in all_edges} | {e["target"] for e in all_edges}
        if node_scope is not None:
            connected.update(node_scope)
        nodes = [_elem_dict(elem) for elem in profile.elements if elem.name in connected]
    else:
        if node_scope is None:
            nodes = [_elem_dict(elem) for elem in profile.elements]
        else:
            nodes = [_elem_dict(elem) for elem in profile.elements if elem.name in node_scope]

    # Relation distribution for the (possibly filtered) edge set
    rel_dist: dict[str, int] = {}
    for e in all_edges:
        rel_dist[e["relation"]] = rel_dist.get(e["relation"], 0) + 1
    output_edges = _finalize_edge_payload(
        all_edges,
        include_rule_provenance=include_rule_provenance,
        semantic_layer_key=resolved_profile_layer_key,
    )

    home_model_ports = 0
    foreign_model_ports = 0
    if resolved_profile_layer_key is not None:
        for elem in profile.elements:
            _, ownership = _node_domain_info(
                element_name=str(elem.name),
                profile_layer_key=resolved_profile_layer_key,
            )
            if ownership == "home_port":
                home_model_ports += 1
            elif ownership == "foreign_port":
                foreign_model_ports += 1
    owned_nodes = sum(
        1
        for node in nodes
        if str(node.get("ownership", "")) in {"owned", "home_port"}
    )
    foreign_nodes = sum(
        1
        for node in nodes
        if str(node.get("ownership", "")) == "foreign_port"
    )

    payload = {
        "profile": profile_name,
        "cross_layer": cross_layer,
        "view_mode": normalized_view,
        "surface_filter": {
            "enabled": bool(surface_only),
            "applied": surface_filter_applied,
            "visible_relations": visible_relations,
            "hidden_relations": hidden_relations,
        },
        "edge_total_raw": edge_total_raw,
        "edge_total_before_cap": edge_total_before_cap,
        "edge_truncated": edge_truncated,
        "nodes": nodes,
        "edges": output_edges,
        "node_count": len(nodes),
        "edge_count": len(output_edges),
        "relation_distribution": rel_dist,
        "semantic_view": _build_semantic_view(
            output_edges,
            semantic_layer_key=resolved_profile_layer_key,
        ),
        "domain_view": {
            "profile_layer_key": resolved_profile_layer_key,
            "requested_scope": requested_domain_scope,
            "scope": effective_domain_scope,
            "scope_applied": resolved_profile_layer_key is not None,
            "available_scopes": ["all", "owned", "bridge"] if resolved_profile_layer_key is not None else ["all"],
            "stats": {
                "edges_before_scope": len(edges_before_domain_scope),
                "edges_after_scope": len(all_edges),
                "owned_edges": owned_edges_total,
                "bridge_edges": bridge_edges_total,
                "owned_nodes": owned_nodes,
                "foreign_nodes": foreign_nodes,
                "home_model_ports": home_model_ports,
                "foreign_model_ports": foreign_model_ports,
            },
        },
    }
    if focus_payload is not None:
        payload["focus"] = focus_payload
    return payload


def profile_composed_topology(
    *,
    profile_name: str,
    lang: str | None = None,
    domain_scope: str | None = "all",
    max_edges: int | None = None,
    surface_only: bool = False,
    include_profiles: list[str] | tuple[str, ...] | None = None,
    focus: str | None = None,
    focus_relation: str | None = None,
    focus_layer: str | None = None,
    focus_actor: str | None = None,
    focus_topic: str | None = None,
    focus_seed: str | None = None,
    focus_depth: int | None = None,
    include_rule_provenance: bool = False,
) -> dict[str, Any]:
    """Compose multi-profile M1 topology anchored by a profile.

    This endpoint exposes cross-profile ownership and edge composition.
    Set *include_rule_provenance* to True to include rule_ref/rule_refs
    in the edge payload.
    """
    if max_edges is not None and max_edges <= 0:
        return {"error": "max_edges must be greater than zero"}

    requested_domain_scope = (domain_scope or "all").strip().lower()
    if requested_domain_scope not in {"all", "owned", "bridge"}:
        return {
            "error": f"Invalid domain_scope: {domain_scope}. Use one of: all, owned, bridge",
            "valid_domain_scopes": ["all", "owned", "bridge"],
        }
    if focus is not None:
        normalized_focus = focus.strip().lower()
        if normalized_focus not in {"core", "relation", "layer", "actor", "topic", "seed"}:
            return {"error": f"Invalid focus: {focus}. Use one of: core, relation, layer, actor, topic, seed"}
    elif (
        focus_relation is not None
        or focus_layer is not None
        or focus_actor is not None
        or focus_topic is not None
        or focus_depth is not None
    ):
        return {"error": "focus params are only valid when focus is set"}
    if focus_depth is not None and focus_depth <= 0:
        return {"error": "focus_depth must be greater than zero"}

    resolved_profile_layer_key = _profile_layer_key(profile_name)

    requested_profiles: list[str] = []
    if include_profiles:
        requested_profiles.extend([str(name).strip() for name in include_profiles if str(name).strip()])
    elif resolved_profile_layer_key is not None:
        requested_profiles.extend(_EA_SYS_PROFILE_ORDER)
    else:
        requested_profiles.append(profile_name)

    # Anchor profile must be first for deterministic node metadata precedence.
    ordered_profiles: list[str] = []
    seen_profiles: set[str] = set()
    for name in [profile_name, *requested_profiles]:
        normalized = str(name).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen_profiles:
            continue
        seen_profiles.add(key)
        ordered_profiles.append(normalized)

    node_map: dict[str, dict[str, Any]] = {}
    node_owner_map: dict[str, set[str]] = {}

    edge_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    edge_ref_keys: dict[tuple[str, str, str], set[tuple[str, str]]] = {}

    included_profiles: list[str] = []
    missing_profiles: list[str] = []

    def _collect_rule_refs(edge: dict[str, Any], fallback_profile: str) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        raw_refs = edge.get("rule_refs")
        if isinstance(raw_refs, list):
            for item in raw_refs:
                if isinstance(item, dict):
                    refs.append(dict(item))
        raw_ref = edge.get("rule_ref")
        if isinstance(raw_ref, dict):
            refs.append(dict(raw_ref))
        if refs:
            return refs
        fallback_rule_id = str(edge.get("rule_id", ""))
        fallback_priority = int(edge.get("priority", 0))
        return [
            {
                "profile": fallback_profile,
                "profile_layer_key": _profile_layer_key(fallback_profile),
                "rule_id": fallback_rule_id,
                "source_pattern": "",
                "target_pattern": "",
                "relation": str(edge.get("relation", "")),
                "valid": True,
                "priority": fallback_priority,
                "notes": "",
                "description": "",
            },
        ]

    def _merge_edge_rule_refs(
        key: tuple[str, str, str],
        refs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        seen = edge_ref_keys.setdefault(key, set())
        collected: list[dict[str, Any]] = []
        for item in refs:
            profile_ref = str(item.get("profile", ""))
            rule_id = str(item.get("rule_id", ""))
            ref_key = (profile_ref, rule_id)
            if ref_key in seen:
                continue
            seen.add(ref_key)
            collected.append(item)
        return collected

    for composed_profile in ordered_profiles:
        profile_topology_payload = _profile_topology_summary_for_composed(
            profile_name=composed_profile,
            lang=lang,
        )
        if "error" in profile_topology_payload:
            missing_profiles.append(composed_profile)
            continue

        included_profiles.append(composed_profile)

        for node in profile_topology_payload.get("nodes", []):
            if not isinstance(node, dict):
                continue
            node_name = str(node.get("name", ""))
            if not node_name:
                continue
            existing = node_map.get(node_name)
            if existing is None:
                next_node = dict(node)
                if resolved_profile_layer_key is not None:
                    home_layer, ownership = _node_domain_info(
                        element_name=node_name,
                        profile_layer_key=resolved_profile_layer_key,
                    )
                    next_node["home_layer"] = home_layer
                    next_node["ownership"] = ownership
                node_map[node_name] = next_node
                node_owner_map[node_name] = {composed_profile}
                continue
            owners = node_owner_map.setdefault(node_name, set())
            owners.add(composed_profile)
            if not existing.get("display_name") and node.get("display_name"):
                existing["display_name"] = node.get("display_name")
            if not existing.get("description") and node.get("description"):
                existing["description"] = node.get("description")

        for edge in profile_topology_payload.get("edges", []):
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            relation = str(edge.get("relation", ""))
            if not source or not target or not relation:
                continue

            key = (source, target, relation)
            refs = _collect_rule_refs(edge, composed_profile)
            refs_to_add = _merge_edge_rule_refs(key, refs)
            incoming_rule_count = int(edge.get("rule_count", len(refs) or 1))
            incoming_priority = int(edge.get("priority", 0))
            incoming_rule_id = str(edge.get("rule_id", ""))
            incoming_explicit_count, incoming_expanded_count = _edge_origin_counts(edge)
            incoming_rule_ref = edge.get("rule_ref")
            if not isinstance(incoming_rule_ref, dict):
                incoming_rule_ref = refs[0] if refs else None

            existing = edge_map.get(key)
            if existing is None:
                edge_map[key] = {
                    "source": source,
                    "target": target,
                    "relation": relation,
                    "rule_id": incoming_rule_id,
                    "priority": incoming_priority,
                    "rule_count": max(1, incoming_rule_count),
                    "edge_origin": _edge_origin_from_counts(
                        incoming_explicit_count,
                        incoming_expanded_count,
                    ),
                    "explicit_count": incoming_explicit_count,
                    "expanded_count": incoming_expanded_count,
                    "rule_ref": incoming_rule_ref,
                    "rule_refs": refs_to_add[:40],
                }
                continue

            existing["rule_count"] = int(existing.get("rule_count", 0)) + max(1, incoming_rule_count)
            existing["explicit_count"] = _to_non_negative_int(existing.get("explicit_count"), 0) + incoming_explicit_count
            existing["expanded_count"] = _to_non_negative_int(existing.get("expanded_count"), 0) + incoming_expanded_count
            existing["edge_origin"] = _edge_origin_from_counts(
                _to_non_negative_int(existing.get("explicit_count"), 0),
                _to_non_negative_int(existing.get("expanded_count"), 0),
            )

            current_priority = int(existing.get("priority", 0))
            current_rule_id = str(existing.get("rule_id", ""))
            should_replace_head = incoming_priority > current_priority or (
                incoming_priority == current_priority
                and incoming_rule_id
                and (not current_rule_id or incoming_rule_id < current_rule_id)
            )
            if should_replace_head:
                existing["priority"] = incoming_priority
                existing["rule_id"] = incoming_rule_id
                if incoming_rule_ref is not None:
                    existing["rule_ref"] = incoming_rule_ref

            existing_refs = existing.get("rule_refs")
            if not isinstance(existing_refs, list):
                existing_refs = []
                existing["rule_refs"] = existing_refs
            if refs_to_add:
                available_slots = max(0, 40 - len(existing_refs))
                if available_slots > 0:
                    existing_refs.extend(refs_to_add[:available_slots])

    if not included_profiles:
        return {"error": f"Profile not found: {profile_name}"}

    merged_edges = sorted(edge_map.values(), key=_edge_priority_sort_key)
    edges_before_domain_scope = list(merged_edges)

    if requested_domain_scope != "all" and resolved_profile_layer_key is not None:
        merged_edges = [
            edge
            for edge in merged_edges
            if _edge_domain_scope(edge, profile_layer_key=resolved_profile_layer_key) == requested_domain_scope
        ]

    effective_domain_scope = requested_domain_scope if resolved_profile_layer_key is not None else "all"
    if resolved_profile_layer_key is None:
        requested_domain_scope = "all"
    edge_total_raw = len(merged_edges)

    relation_candidates = sorted({str(edge.get("relation", "")) for edge in merged_edges if str(edge.get("relation", ""))})
    layer_candidates = sorted(
        {
            str(node.get("layer", ""))
            for node in node_map.values()
            if str(node.get("layer", ""))
        },
    )
    topic_policy = _resolve_topic_query_policy(profile_name)
    category_of = {
        str(node.get("name", "")): str(node.get("category", ""))
        for node in node_map.values()
        if str(node.get("name", ""))
    }
    relation_profile: dict[str, list[str]] = {
        group: [
            name
            for name in relations
            if name in relation_candidates
        ]
        for group, relations in DEFAULT_SURFACE_PROFILE.groups.items()
    }
    relation_profile["interaction"] = [
        name
        for name in _ACTOR_INTERACTION_RELATIONS
        if name in relation_candidates
    ]
    visible_relations = [
        name
        for name in DEFAULT_SURFACE_PROFILE.surface_relations
        if name in relation_candidates
    ]
    hidden_relations = sorted(set(relation_candidates) - set(visible_relations))
    actor_candidates_all = sorted(
        [
            {
                "name": str(node.get("name", "")),
                "layer": str(node.get("layer", "")),
                "category": str(node.get("category", "")),
                "description": node.get("description", ""),
                "display_name": node.get("display_name"),
            }
            for node in node_map.values()
            if _is_actor_element(node)
        ],
        key=lambda item: (str(item["layer"]), str(item["name"]).lower()),
    )

    focus_payload: dict[str, Any] | None = None
    node_scope: set[str] | None = None
    surface_filter_applied = False
    normalized_view = "summary"
    if focus is None and surface_only:
        selected_set = set(visible_relations)
        merged_edges = [
            edge
            for edge in merged_edges
            if str(edge.get("relation", "")) in selected_set
        ]
        surface_filter_applied = True

    if focus is not None:
        normalized_view = "focus"
        normalized_focus = focus.strip().lower()
        focus_payload = {
            "mode": normalized_focus,
            "relation_candidates": relation_candidates,
            "layer_candidates": layer_candidates,
            "actor_candidates": actor_candidates_all,
            "visibility_profile": relation_profile,
            "visible_relations": visible_relations,
            "hidden_relations": hidden_relations,
        }

        if normalized_focus == "relation":
            requested_relation = (focus_relation or "").strip()
            if not requested_relation:
                return {"error": "focus_relation is required when focus=relation"}
            relation_lookup = {name.lower(): name for name in relation_candidates}
            resolved_relation = relation_lookup.get(requested_relation.lower())
            if resolved_relation is None:
                return {
                    "error": f"Unknown focus_relation: {focus_relation}",
                    "available_relations": relation_candidates,
                }
            merged_edges = [
                edge
                for edge in merged_edges
                if str(edge.get("relation", "")) == resolved_relation
            ]
            focus_payload["relation"] = resolved_relation
        elif normalized_focus == "layer":
            requested_focus_layer = (focus_layer or "").strip()
            if not requested_focus_layer:
                return {"error": "focus_layer is required when focus=layer"}
            layer_lookup = {name.lower(): name for name in layer_candidates}
            resolved_focus_layer = layer_lookup.get(requested_focus_layer.lower())
            if resolved_focus_layer is None:
                return {
                    "error": f"Unknown focus_layer: {focus_layer}",
                    "available_layers": layer_candidates,
                }
            merged_edges = [
                edge
                for edge in merged_edges
                if (
                    str(node_map.get(str(edge.get("source", "")), {}).get("layer", ""))
                    == resolved_focus_layer
                )
                or (
                    str(node_map.get(str(edge.get("target", "")), {}).get("layer", ""))
                    == resolved_focus_layer
                )
            ]
            focus_payload["layer"] = resolved_focus_layer
        elif normalized_focus == "topic":
            requested_topic = (focus_topic or "").strip()
            if not requested_topic:
                return {"error": "focus_topic is required when focus=topic"}

            topic_candidates_payload = _topic_match_candidates(
                nodes=list(node_map.values()),
                focus_topic=requested_topic,
                lang=lang,
                policy=topic_policy,
            )
            topic_candidates = topic_candidates_payload.get("candidates", [])
            max_available_topics = int(topic_policy.get("max_available_topics", 60))
            default_depth = int(topic_policy.get("default_depth", 2))
            seed_score_ratio = float(topic_policy.get("seed_score_ratio", 0.72))
            seed_score_floor = int(topic_policy.get("seed_score_floor", 60))
            min_token_coverage = float(topic_policy.get("min_token_coverage", 0.5))
            max_seed_count = int(topic_policy.get("max_seed_count", 8))
            max_match_count = int(topic_policy.get("max_match_count", 16))
            max_scope_nodes_per_depth = int(topic_policy.get("max_scope_nodes_per_depth", 40))
            if not topic_candidates:
                available_topics = sorted(
                    [str(name) for name in node_map if str(name)],
                    key=str.lower,
                )
                return {
                    "error": f"Unknown focus_topic: {focus_topic}",
                    "available_topics": available_topics[:max_available_topics],
                }

            resolved_depth = focus_depth if focus_depth is not None else default_depth
            top_score = int(topic_candidates[0].get("score", 0))
            score_threshold = max(seed_score_floor, int(round(top_score * seed_score_ratio)))
            seed_nodes = [
                str(item.get("name", ""))
                for item in topic_candidates
                if int(item.get("score", 0)) >= score_threshold
                and float(item.get("coverage", 0.0)) >= min_token_coverage
            ][:max_seed_count]
            if not seed_nodes:
                seed_nodes = [str(topic_candidates[0].get("name", ""))]
            seed_nodes = [name for name in seed_nodes if name]
            if not seed_nodes:
                return {
                    "error": f"Unknown focus_topic: {focus_topic}",
                }

            structural_relations, intent_relations, selected_relations = _resolve_topic_relations(
                relation_candidates,
            )
            topic_scope = _apply_topic_scope(
                edges=merged_edges,
                structural_relations=structural_relations,
                intent_relations=intent_relations,
                seed_nodes=seed_nodes,
                focus_depth=resolved_depth,
                max_scope_nodes=resolved_depth * max_scope_nodes_per_depth,
            )
            node_scope = set(topic_scope.get("scope", set()))
            merged_edges = list(topic_scope.get("edges", []))
            focus_payload["topic"] = requested_topic
            focus_payload["topic_depth"] = resolved_depth
            focus_payload["topic_tokens"] = topic_candidates_payload.get("tokens", [])
            focus_payload["topic_seeds"] = seed_nodes
            focus_payload["topic_matches"] = topic_candidates[:max_match_count]
            focus_payload["selected_relation_profile"] = {
                "structural": structural_relations,
                "intent": intent_relations,
            }
            focus_payload["selected_relations"] = selected_relations
            focus_payload["topic_policy"] = {
                "default_depth": default_depth,
                "seed_score_ratio": seed_score_ratio,
                "seed_score_floor": seed_score_floor,
                "min_token_coverage": min_token_coverage,
                "max_seed_count": max_seed_count,
                "max_match_count": max_match_count,
                "max_scope_nodes_per_depth": max_scope_nodes_per_depth,
            }
            focus_payload["topic_filter_stats"] = topic_scope.get("stats", {})
        elif normalized_focus == "actor":
            selected_relations = relation_profile.get("interaction", [])
            interaction_edges, interaction_adjacency, interaction_degree = _build_actor_focus_graph(
                edges=merged_edges,
                selected_relations=selected_relations,
                category_of=category_of,
            )
            actor_candidates = _merge_actor_candidates_with_interaction_nodes(
                actor_candidates=actor_candidates_all,
                node_lookup={
                    str(node.get("name", "")): {
                        "layer": str(node.get("layer", "")),
                        "category": str(node.get("category", "")),
                        "description": node.get("description"),
                        "display_name": node.get("display_name"),
                    }
                    for node in node_map.values()
                    if isinstance(node, dict) and str(node.get("name", ""))
                },
                interaction_degree=interaction_degree,
            )
            if not actor_candidates:
                return {"error": "No actor candidates available for focus=actor"}
            resolved_actor, actor_names, _ = _resolve_actor_seed(
                actor_candidates=actor_candidates,
                requested_actor=focus_actor,
            )
            if resolved_actor is None:
                return {
                    "error": f"Unknown focus_actor: {focus_actor}",
                    "available_actors": actor_names,
                }
            if (focus_actor or "").strip() and resolved_actor not in actor_names:
                return {
                    "error": f"Unknown focus_actor: {focus_actor}",
                    "available_actors": actor_names,
                }

            resolved_depth = focus_depth if focus_depth is not None else 4
            scope = _expand_actor_scope(
                seed_actor=resolved_actor,
                depth=resolved_depth,
                adjacency=interaction_adjacency,
            )
            node_scope = scope
            merged_edges = [
                edge
                for edge in interaction_edges
                if str(edge.get("source", "")) in scope
                and str(edge.get("target", "")) in scope
            ]
            focus_payload["actor"] = resolved_actor
            focus_payload["actor_depth"] = resolved_depth
            focus_payload["actor_candidates"] = actor_candidates
            focus_payload["selected_relations"] = selected_relations
            focus_payload["actor_seed_strategy"] = "highest_interaction_degree"
        elif normalized_focus == "seed":
            requested_seed = (focus_seed or "").strip()
            if not requested_seed:
                return {"error": "focus_seed is required when focus=seed"}
            composed_name_lookup: dict[str, str] = {
                str(node.get("name", "")).lower(): str(node.get("name", ""))
                for node in node_map.values()
                if isinstance(node, dict) and str(node.get("name", ""))
            }
            resolved_seed_name = composed_name_lookup.get(requested_seed.lower())
            if resolved_seed_name is None:
                return {
                    "error": f"Unknown seed element: {focus_seed}",
                    "available_elements": sorted(composed_name_lookup.values())[:60],
                }
            seed_adjacency_c: dict[str, set[str]] = {}
            for edge in merged_edges:
                src = str(edge.get("source", ""))
                tgt = str(edge.get("target", ""))
                if src and tgt:
                    seed_adjacency_c.setdefault(src, set()).add(tgt)
                    seed_adjacency_c.setdefault(tgt, set()).add(src)
            resolved_depth = focus_depth if focus_depth is not None else PROJECTION_DEFAULT_SEED_DEPTH
            if resolved_depth <= 0:
                return {"error": "focus_depth must be greater than zero"}
            scope = _expand_actor_scope(
                seed_actor=resolved_seed_name,
                depth=resolved_depth,
                adjacency=seed_adjacency_c,
            )
            node_scope = scope
            merged_edges = [
                edge
                for edge in merged_edges
                if str(edge.get("source", "")) in scope
                and str(edge.get("target", "")) in scope
            ]
            focus_payload["seed"] = resolved_seed_name
            focus_payload["seed_depth"] = resolved_depth
            focus_payload["scope_size"] = len(scope)
        else:
            selected_relations = [
                relation
                for relation in DEFAULT_SURFACE_PROFILE.surface_relations
                if relation in relation_candidates
            ]
            selected_set = set(selected_relations)
            merged_edges = [
                edge
                for edge in merged_edges
                if str(edge.get("relation", "")) in selected_set
            ]
            focus_payload["selected_relations"] = selected_relations

    owned_edges_before_scope = 0
    bridge_edges_before_scope = 0
    if resolved_profile_layer_key is not None:
        for edge in edges_before_domain_scope:
            if _edge_domain_scope(edge, profile_layer_key=resolved_profile_layer_key) == "bridge":
                bridge_edges_before_scope += 1
            else:
                owned_edges_before_scope += 1

    edge_total_before_cap = len(merged_edges)
    edge_truncated = False
    if max_edges is not None and edge_total_before_cap > max_edges:
        merged_edges = _cap_edges_relation_balanced(merged_edges, max_edges=max_edges)
        edge_truncated = True

    connected_names = {str(edge.get("source", "")) for edge in merged_edges}
    connected_names.update({str(edge.get("target", "")) for edge in merged_edges})
    if node_scope is not None:
        connected_names.update(node_scope)

    nodes_out: list[dict[str, Any]] = []
    for name in sorted(node_map.keys()):
        node = node_map[name]
        if connected_names and name not in connected_names:
            continue
        owners = sorted(node_owner_map.get(name, set()))
        if owners:
            node["profile_owners"] = owners
        nodes_out.append(node)

    relation_distribution: dict[str, int] = {}
    for edge in merged_edges:
        relation = str(edge.get("relation", ""))
        if not relation:
            continue
        relation_distribution[relation] = relation_distribution.get(relation, 0) + 1
    output_edges = _finalize_edge_payload(
        merged_edges,
        include_rule_provenance=include_rule_provenance,
        semantic_layer_key=resolved_profile_layer_key,
    )

    owned_edges_after_scope = 0
    bridge_edges_after_scope = 0
    if resolved_profile_layer_key is not None:
        for edge in merged_edges:
            if _edge_domain_scope(edge, profile_layer_key=resolved_profile_layer_key) == "bridge":
                bridge_edges_after_scope += 1
            else:
                owned_edges_after_scope += 1

    owned_nodes = sum(
        1
        for node in nodes_out
        if str(node.get("ownership", "")) in {"owned", "home_port"}
    )
    foreign_nodes = sum(
        1
        for node in nodes_out
        if str(node.get("ownership", "")) == "foreign_port"
    )
    home_model_ports = sum(
        1
        for node in nodes_out
        if str(node.get("ownership", "")) == "home_port"
    )
    foreign_model_ports = sum(
        1
        for node in nodes_out
        if str(node.get("ownership", "")) == "foreign_port"
    )

    payload = {
        "profile": profile_name,
        "cross_layer": False,
        "view_mode": normalized_view,
        "surface_filter": {
            "enabled": bool(surface_only),
            "applied": surface_filter_applied,
            "visible_relations": visible_relations,
            "hidden_relations": hidden_relations,
        },
        "edge_total_raw": edge_total_raw,
        "edge_total_before_cap": edge_total_before_cap,
        "edge_truncated": edge_truncated,
        "nodes": nodes_out,
        "edges": output_edges,
        "node_count": len(nodes_out),
        "edge_count": len(output_edges),
        "relation_distribution": relation_distribution,
        "semantic_view": _build_semantic_view(
            output_edges,
            semantic_layer_key=resolved_profile_layer_key,
        ),
        "domain_view": {
            "profile_layer_key": resolved_profile_layer_key,
            "requested_scope": requested_domain_scope,
            "scope": effective_domain_scope,
            "scope_applied": resolved_profile_layer_key is not None,
            "available_scopes": ["all", "owned", "bridge"] if resolved_profile_layer_key is not None else ["all"],
            "stats": {
                "edges_before_scope": len(edges_before_domain_scope),
                "edges_after_scope": len(merged_edges),
                "owned_edges": owned_edges_after_scope if resolved_profile_layer_key is not None else 0,
                "bridge_edges": bridge_edges_after_scope if resolved_profile_layer_key is not None else 0,
                "owned_edges_before_scope": owned_edges_before_scope if resolved_profile_layer_key is not None else 0,
                "bridge_edges_before_scope": bridge_edges_before_scope if resolved_profile_layer_key is not None else 0,
                "owned_nodes": owned_nodes,
                "foreign_nodes": foreign_nodes,
                "home_model_ports": home_model_ports,
                "foreign_model_ports": foreign_model_ports,
            },
        },
        "composition": {
            "mode": "cross_profile",
            "anchor_profile": profile_name,
            "anchor_layer_key": resolved_profile_layer_key,
            "included_profiles": included_profiles,
            "requested_profiles": ordered_profiles,
            "missing_profiles": missing_profiles,
            "source_profile_count": len(included_profiles),
        },
    }
    if focus_payload is not None:
        payload["focus"] = focus_payload
    return payload


@lru_cache(maxsize=128)
def _profile_topology_summary_for_composed(
    *,
    profile_name: str,
    lang: str | None,
) -> dict[str, Any]:
    """Cached profile summary topology for composed M1 queries."""
    return profile_topology(
        profile_name=profile_name,
        lang=lang,
        cross_layer=False,
        view_mode="summary",
        domain_scope="all",
        max_edges=None,
        include_rule_provenance=True,
    )

# ── Projection Extension Registry ────────────────────────────────
_projection_extensions: dict[str, ProjectionExtension] = {}


def register_projection_extension(ext: ProjectionExtension) -> None:
    """Register a domain projection extension (e.g. FlowProjectionExtension)."""
    _projection_extensions[ext.layer_key] = ext


def _bootstrap_projection_extensions() -> None:
    """Auto-register available projection extensions."""
    if _projection_extensions:
        return
    try:
        from ea_flow.projection_ext import FlowProjectionExtension
        register_projection_extension(FlowProjectionExtension())
    except ImportError:
        pass
    try:
        from ea_decision.projection_ext import DecisionProjectionExtension
        register_projection_extension(DecisionProjectionExtension())
    except ImportError:
        pass


def profile_projection(
    *,
    profile_name: str,
    level: str | None = "l0",
    lens: str | None = None,
    lang: str | None = None,
    cross_layer: bool = False,
    domain_scope: str | None = "all",
    actor: str | None = None,
    depth: int | None = None,
    max_edges: int | None = None,
    tier: str | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    """Projection layer view (L0~L4) for abstraction-first exploration."""
    normalized_lens = (lens or "").strip().lower()
    normalized_level = (level or "").strip().lower()
    policy = _resolve_projection_policy(profile_name)
    if "error" in policy:
        return {
            "error": str(policy["error"]),
            "policy_error": policy.get("policy_error"),
        }
    level_specs = policy.get("level_specs", _PROJECTION_LEVEL_SPECS)
    lens_to_level = policy.get("lens_to_level", PROJECTION_LENS_TO_LEVEL)

    if not normalized_level:
        normalized_level = str(lens_to_level.get(normalized_lens, "l0"))
    spec = level_specs.get(normalized_level)
    if spec is None:
        return {
            "error": f"Unknown projection level: {level}",
            "valid_levels": [str(name).upper() for name in level_specs.keys()],
        }

    if normalized_lens:
        mapped_level = lens_to_level.get(normalized_lens)
        if mapped_level is None:
            return {
                "error": f"Unknown projection lens: {lens}",
                "valid_lenses": sorted(lens_to_level.keys()),
            }
        if mapped_level != normalized_level:
            return {
                "error": f"Lens {lens} is not valid for level {spec['level']}",
                "level": spec["level"],
                "default_lens": spec["lens"],
            }

    if max_edges is not None and max_edges <= 0:
        return {
            "error": "max_edges must be greater than zero",
        }
    if depth is not None and depth <= 0:
        return {
            "error": "depth must be greater than zero",
        }

    # Tier validation
    resolved_tier: str | None = None
    resolved_tier_definitions: dict[str, dict[str, Any]] | None = None
    if tier:
        normalized_tier = tier.strip().lower()
        resolved_tier_definitions = _resolve_tier_definitions(policy)
        if normalized_tier not in resolved_tier_definitions:
            return {
                "error": f"Unknown projection tier: {tier}",
                "valid_tiers": sorted(resolved_tier_definitions.keys()),
            }
        resolved_tier = normalized_tier

    base_view_mode = str(spec.get("base_view_mode", "summary"))
    base_focus = spec.get("base_focus")
    effective_focus = str(base_focus) if base_focus is not None else None
    effective_depth = depth
    effective_view_mode = base_view_mode

    # Seed overrides focus to "seed" and requires focus view mode
    if seed:
        effective_focus = "seed"
        effective_view_mode = "focus"
        if effective_depth is None:
            effective_depth = PROJECTION_DEFAULT_SEED_DEPTH
    elif base_focus == "actor" and effective_depth is None:
        effective_depth = int(policy.get("actor_default_depth", PROJECTION_DEFAULT_ACTOR_DEPTH))

    topology = profile_topology(
        profile_name=profile_name,
        cross_layer=cross_layer,
        lang=lang,
        view_mode=effective_view_mode,
        domain_scope=domain_scope,
        focus=effective_focus,
        focus_actor=actor if effective_focus == "actor" else None,
        focus_seed=seed if effective_focus == "seed" else None,
        focus_depth=effective_depth if effective_focus in ("actor", "seed") else None,
        max_edges=None,
    )
    if "error" in topology:
        return topology

    preserve_nodes: set[str] = set()
    actor_seed_payload: dict[str, Any] | None = None
    if effective_focus == "actor":
        focus_payload = topology.get("focus")
        if isinstance(focus_payload, dict):
            resolved_actor = focus_payload.get("actor")
            if resolved_actor:
                preserve_nodes.add(str(resolved_actor))
            actor_seed_payload = {
                "actor": focus_payload.get("actor"),
                "depth": focus_payload.get("actor_depth"),
                "actor_candidates": focus_payload.get("actor_candidates", []),
            }

    # Seed preserve
    seed_meta_payload: dict[str, Any] | None = None
    if effective_focus == "seed":
        focus_payload = topology.get("focus")
        if isinstance(focus_payload, dict):
            resolved_seed_elem = focus_payload.get("seed")
            if resolved_seed_elem:
                preserve_nodes.add(str(resolved_seed_elem))
            seed_meta_payload = {
                "element": focus_payload.get("seed"),
                "depth": focus_payload.get("seed_depth"),
                "scope_size": focus_payload.get("scope_size"),
            }

    default_max_edges = int(spec.get("default_max_edges", 600))
    effective_max_edges = max_edges if max_edges is not None else default_max_edges

    # When tier is specified, it overrides level's allowed_categories
    filter_categories: tuple[str, ...] | None = None
    if resolved_tier is None:
        filter_categories = tuple(spec.get("allowed_categories", ()))

    max_cd = spec.get("max_containment_depth")
    # Profile-level override: [projection] max_containment_depth_l0 = 0
    _proj_profile = _load_profile(profile_name)
    if _proj_profile and _proj_profile.metadata and _proj_profile.metadata.extra:
        _cd_key = f"projection.max_containment_depth_{normalized_level}"
        _cd_val = _proj_profile.metadata.extra.get(_cd_key)
        if _cd_val is not None:
            max_cd = int(_cd_val)
    projected = _apply_projection_filters(
        topology=topology,
        allowed_relations=tuple(spec.get("allowed_relations", ())),
        allowed_categories=filter_categories,
        max_edges=effective_max_edges,
        preserve_nodes=preserve_nodes,
        tier=resolved_tier,
        tier_definitions=resolved_tier_definitions,
        max_containment_depth=max_cd,
    )
    projection_filter_meta = projected.pop("projection_filter", {})

    # Apply registered projection extensions (enrich nodes/edges, add supplementary edges)
    _bootstrap_projection_extensions()
    extension_meta: dict[str, Any] = {}
    for ext_key, ext in _projection_extensions.items():
        enriched_nodes = ext.enrich_nodes(projected["nodes"], normalized_level, resolved_tier)
        enriched_edges = ext.enrich_edges(projected["edges"], enriched_nodes, normalized_level)
        supplementary = ext.supplementary_edges(enriched_nodes, normalized_level, resolved_tier)
        projected["nodes"] = enriched_nodes
        projected["edges"] = enriched_edges + supplementary
        if supplementary:
            extension_meta[ext_key] = {"supplementary_edges": len(supplementary)}
    projected["node_count"] = len(projected["nodes"])
    projected["edge_count"] = len(projected["edges"])

    source_node_count = int(topology.get("node_count", 0) or 0)
    source_edge_count = int(topology.get("edge_count", 0) or 0)
    source_edge_total_raw = int(topology.get("edge_total_raw", source_edge_count) or 0)
    projected_node_count = int(projected.get("node_count", 0) or 0)
    projected_edge_count = int(projected.get("edge_count", 0) or 0)
    projected_edge_before_cap = int(projected.get("edge_total_before_cap", projected_edge_count) or 0)

    def _ratio(part: int, whole: int) -> float:
        if whole <= 0:
            return 0.0
        return float(part) / float(whole)

    projection_meta: dict[str, Any] = {
        "level": spec["level"],
        "lens": spec["lens"],
        "description": spec["description"],
        "policy": {
            "source": str(policy.get("source", "fallback")),
            "scope": str(policy.get("scope", "global")),
            "layer_key": policy.get("layer_key"),
        },
        "budget": {
            "default_max_edges": default_max_edges,
            "effective_max_edges": effective_max_edges,
        },
        "filters": {
            "relations": list(spec.get("allowed_relations", ())),
            "categories": list(spec.get("allowed_categories", ())),
            "domain_scope": str(topology.get("domain_view", {}).get("scope", "all")),
        },
        "drilldown": {
            "next_levels": list(spec.get("next_levels", ())),
        },
        "source": {
            "view_mode": effective_view_mode,
            "focus": effective_focus,
            "node_count": source_node_count,
            "edge_count": source_edge_count,
            "edge_total_raw": source_edge_total_raw,
        },
        "reduction": {
            "nodes": {
                "source": source_node_count,
                "projected": projected_node_count,
                "ratio": _ratio(projected_node_count, source_node_count),
            },
            "edges": {
                "source": source_edge_count,
                "source_raw": source_edge_total_raw,
                "before_cap": projected_edge_before_cap,
                "projected": projected_edge_count,
                "ratio": _ratio(projected_edge_count, source_edge_count),
                "raw_ratio": _ratio(projected_edge_count, source_edge_total_raw),
                "before_cap_ratio": _ratio(projected_edge_before_cap, source_edge_count),
                "truncated": bool(projected.get("edge_truncated", False)),
            },
        },
    }
    if isinstance(projection_filter_meta, dict):
        stages = projection_filter_meta.get("stages")
        drop_reasons = projection_filter_meta.get("drop_reasons")
        preserve_meta = projection_filter_meta.get("preserve")
        if isinstance(stages, dict):
            projection_meta["reduction"]["stages"] = stages
        if isinstance(drop_reasons, dict):
            projection_meta["reduction"]["drop_reasons"] = drop_reasons
        if isinstance(preserve_meta, dict):
            projection_meta["reduction"]["preserve"] = preserve_meta
    schema_contract = policy.get("schema_contract")
    if isinstance(schema_contract, dict) and schema_contract:
        projection_meta["policy"]["schema"] = schema_contract
    if actor_seed_payload is not None:
        projection_meta["seed"] = actor_seed_payload

    # Tier metadata
    if resolved_tier and resolved_tier_definitions:
        tier_def = resolved_tier_definitions.get(resolved_tier, {})
        projection_meta["tier"] = {
            "name": resolved_tier,
            "categories": tier_def.get("categories", []),
            "next_tiers": tier_def.get("transitions", []),
        }

    # Seed metadata
    if seed_meta_payload is not None:
        projection_meta["seed"] = seed_meta_payload

    # Extension metadata
    if extension_meta:
        projection_meta["extensions"] = extension_meta

    projected["projection"] = projection_meta
    return projected


def profile_reachable(
    *,
    profile_name: str,
    element: str,
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


def profile_element_scope(
    *,
    profile_name: str,
    elements: list[str],
    max_depth: int = 4,
) -> dict[str, Any]:
    """Compute union of reachable sets from multiple seed elements."""
    from ea_kernel.profile_graph import ProfileTopologyGraph

    profile = _load_profile(profile_name)
    if profile is None:
        return {"error": f"Profile not found: {profile_name}"}

    graph = ProfileTopologyGraph(profile)
    missing = [e for e in elements if e not in graph.nodes]
    if missing:
        return {
            "error": f"Element(s) not found: {', '.join(missing)}",
            "available_elements": list(graph.nodes),
        }

    scope: set[str] = set()
    for elem in elements:
        reached = graph.reachable(elem, max_depth=max_depth)
        scope.update(reached)
        scope.add(elem)

    return {
        "profile": profile_name,
        "seeds": elements,
        "scope": sorted(scope),
        "count": len(scope),
    }


def profile_paths(
    *,
    profile_name: str,
    source: str,
    target: str,
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
    *,
    profile_name: str,
    element: str,
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

    normalized_direction = direction.strip().lower()
    if normalized_direction == "downstream":
        normalized_direction = "outgoing"
    elif normalized_direction == "upstream":
        normalized_direction = "incoming"

    if normalized_direction not in {"outgoing", "incoming", "both"}:
        return {
            "error": (
                "Invalid direction: "
                f"{direction}. Use one of: outgoing, incoming, both"
            )
        }

    impact = graph.impact_analysis(
        element,
        direction=normalized_direction,
        max_depth=max_depth,
    )
    return {
        "profile": profile_name,
        "element": element,
        "direction": normalized_direction,
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


# ── I18n Service ─────────────────────────────────────────────


def _get_i18n_store() -> "I18nStore":
    from pathlib import Path

    from ea_kernel.i18n_store import SQLiteI18nStore
    db_path = Path(__file__).parent / "data" / "i18n.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteI18nStore(db_path)


def _make_i18n_identifier(
    *,
    scope: str,
    kind: str,
    name: str,
    field: str | None,
    profile_name: str | None = None,
) -> str:
    normalized_field = field or ""
    if scope == "m1":
        return f"m1:{profile_name}:{kind}:{name}:{normalized_field}"
    return f"m2:{kind}:{name}:{normalized_field}"


def _audit_entry_payload(
    *,
    entry: Any,
    scope: str,
    profile_name: str | None = None,
    include_en_current: bool = False,
    include_en_recorded: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": entry.kind,
        "name": entry.name,
        "field": entry.field,
        "identifier": _make_i18n_identifier(
            scope=scope,
            kind=entry.kind,
            name=entry.name,
            field=entry.field,
            profile_name=profile_name,
        ),
    }
    if profile_name is not None:
        payload["profile"] = profile_name
    if include_en_current:
        payload["en_current"] = entry.en_current
    if include_en_recorded:
        payload["en_recorded"] = entry.en_recorded
    return payload


def _audit_report_payload(
    *,
    report: Any,
    scope: str,
    profile_name: str | None = None,
    patch_path: str | None = None,
) -> dict[str, Any]:
    missing = [
        _audit_entry_payload(
            entry=e,
            scope=scope,
            profile_name=profile_name,
            include_en_current=True,
        )
        for e in report.missing
    ]
    orphan = [
        _audit_entry_payload(
            entry=e,
            scope=scope,
            profile_name=profile_name,
        )
        for e in report.orphan
    ]
    stale = [
        _audit_entry_payload(
            entry=e,
            scope=scope,
            profile_name=profile_name,
            include_en_current=True,
            include_en_recorded=True,
        )
        for e in report.stale
    ]

    payload: dict[str, Any] = {
        "scope": scope,
        "lang": report.lang,
        "coverage": report.coverage,
        "total_schema_items": report.total_schema_items,
        "total_translated": report.total_translated,
        "total_issues": report.total_issues,
        "is_clean": report.is_clean,
        "missing_count": len(missing),
        "orphan_count": len(orphan),
        "stale_count": len(stale),
        "missing": missing,
        "orphan": orphan,
        "stale": stale,
        # Backward-compatible aliases for older admin UI.
        "total": report.total_schema_items,
        "translated": report.total_translated,
        "missing_items": missing,
    }
    if profile_name is not None:
        payload["profile"] = profile_name
    if patch_path is not None:
        payload["patch_path"] = patch_path
    return payload


def _find_profile_patch_path(profile_name: str, lang: str) -> str | None:
    from pathlib import Path

    profiles_root = Path(__file__).parent / "profiles"
    filename = f"{profile_name.lower()}.{lang}.patch.toml"

    direct_candidates = (
        profiles_root / filename,
        profiles_root / "ea_sys" / filename,
        profiles_root / "governance_profile_stack" / filename,
    )
    for candidate in direct_candidates:
        if candidate.exists():
            return str(candidate)

    matches = sorted(profiles_root.rglob(filename))
    if matches:
        return str(matches[0])
    return None


def audit_i18n(*, lang: str = "ko") -> dict[str, Any]:
    """TOML 패치 기반 i18n 감사 리포트."""
    from ea_kernel.schema_loader import audit_i18n_patch

    spec = _get_spec()
    report = audit_i18n_patch(spec, lang)
    return _audit_report_payload(report=report, scope="m2")


def audit_profile_i18n(*, name: str, lang: str = "ko") -> dict[str, Any]:
    """M1 profile i18n patch audit report."""
    from pathlib import Path

    from ea_kernel.localizer import audit_profile_i18n_patch

    profile = _load_profile(name)
    if profile is None:
        return {"error": f"Profile not found: {name}"}

    patch_path_str = _find_profile_patch_path(name, lang)
    patch_path = Path(patch_path_str) if patch_path_str else None
    report = audit_profile_i18n_patch(profile, lang, patch_path=patch_path)
    return _audit_report_payload(
        report=report,
        scope="m1",
        profile_name=name,
        patch_path=patch_path_str,
    )


def list_translations(*, lang: str, kind: str | None = None) -> dict[str, Any]:
    """번역 목록 조회."""
    store = _get_i18n_store()
    entries = store.list_translations(lang, kind)
    return {
        "lang": lang,
        "count": len(entries),
        "translations": [
            {
                "kind": e.target_kind, "name": e.target_name,
                "field": e.field, "value": e.value,
                "version": e.version,
            }
            for e in entries
        ],
    }


def get_translation(*, kind: str, name: str, lang: str, field: str) -> dict[str, Any]:
    """단일 번역 조회."""
    store = _get_i18n_store()
    entry = store.get(kind, name, lang, field)
    if entry is None:
        return {"error": f"Translation not found: {kind}/{name}/{lang}/{field}"}
    return {
        "kind": entry.target_kind, "name": entry.target_name,
        "lang": entry.lang, "field": entry.field,
        "value": entry.value, "en_source": entry.en_source,
        "version": entry.version,
        "created_by": entry.created_by,
        "created_at": entry.created_at, "updated_at": entry.updated_at,
    }


def update_translation(*, kind: str, name: str, lang: str, field: str, value: str) -> dict[str, Any]:
    """번역 수정."""
    from ea_kernel.i18n_store import TranslationEntry
    store = _get_i18n_store()
    existing = store.get(kind, name, lang, field)
    entry = TranslationEntry(
        target_kind=kind, target_name=name, lang=lang, field=field,
        value=value,
        en_source=existing.en_source if existing else "",
        version=0, created_by="manual",
        created_at="", updated_at="",
    )
    result = store.upsert(entry)
    return {
        "kind": result.target_kind, "name": result.target_name,
        "lang": result.lang, "field": result.field,
        "value": result.value, "version": result.version,
        "updated_at": result.updated_at,
    }


def translation_history(*, kind: str, name: str, lang: str, field: str) -> dict[str, Any]:
    """번역 이력 조회."""
    store = _get_i18n_store()
    entries = store.history(kind, name, lang, field)
    return {
        "kind": kind, "name": name, "lang": lang, "field": field,
        "count": len(entries),
        "history": [
            {
                "value": e.value, "version": e.version,
                "created_by": e.created_by, "created_at": e.created_at,
            }
            for e in entries
        ],
    }


# ── Profile Version History Service ──────────────────────────


def _get_profile_store() -> "SQLiteProfileStore":
    from pathlib import Path

    from ea_profile.store import SQLiteProfileStore
    db_path = Path(__file__).parent / "data" / "profiles.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteProfileStore(db_path)
    store.initialize()
    return store


def profile_version_history(
    *, profile_name: str, limit: int = 50,
) -> dict[str, Any]:
    """프로파일 버전 히스토리 조회 — newest first."""
    store = _get_profile_store()
    versions = store.list_versions(profile_name, ascending=False)[:limit]
    return {
        "profile_name": profile_name,
        "count": len(versions),
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "content_hash": v.content_hash,
                "author": v.author,
                "description": v.description,
                "created_at": v.created_at,
                "parent_id": v.parent_id,
            }
            for v in versions
        ],
    }


def profile_version_detail(
    *, profile_name: str, version: str,
) -> dict[str, Any]:
    """단일 버전 상세 — 메타데이터 + 요소/관계/규칙 카운트 + 태그."""
    store = _get_profile_store()
    pv = store.get_by_version(profile_name, version)
    if pv is None:
        return {"error": f"Version not found: {profile_name}@{version}"}

    tags = store.list_tags(version_id=pv.id)
    data = pv.data
    element_count = len(data.get("elements", []))
    relation_count = len(data.get("relations", []))
    rule_count = len(data.get("validity_rules", []))

    return {
        "id": pv.id,
        "profile_name": pv.profile_name,
        "version": pv.version,
        "content_hash": pv.content_hash,
        "author": pv.author,
        "description": pv.description,
        "created_at": pv.created_at,
        "parent_id": pv.parent_id,
        "origin": pv.origin,
        "element_count": element_count,
        "relation_count": relation_count,
        "rule_count": rule_count,
        "tags": [
            {"name": t.name, "created_at": t.created_at}
            for t in tags
        ],
    }


def profile_version_diff(
    *, profile_name: str, version_a: str, version_b: str,
) -> dict[str, Any]:
    """두 버전 간 구조적 diff — elements/relations/rules 변경 목록."""
    from ea_profile.diff import diff_profiles
    from ea_profile.serializer import dict_to_profile

    store = _get_profile_store()
    pv_a = store.get_by_version(profile_name, version_a)
    if pv_a is None:
        return {"error": f"Version not found: {profile_name}@{version_a}"}
    pv_b = store.get_by_version(profile_name, version_b)
    if pv_b is None:
        return {"error": f"Version not found: {profile_name}@{version_b}"}

    profile_a = dict_to_profile(pv_a.data)
    profile_b = dict_to_profile(pv_b.data)
    diff = diff_profiles(profile_a, profile_b)

    return {
        "profile_name": profile_name,
        "from_version": version_a,
        "to_version": version_b,
        "identical": diff.identical,
        "element_changes": [
            {"type": c.change_type.value, "name": c.element_name, "field": c.field,
             "old_value": c.old_value, "new_value": c.new_value}
            for c in diff.element_changes
        ],
        "relation_changes": [
            {"type": c.change_type.value, "name": c.relation_name, "field": c.field,
             "old_value": c.old_value, "new_value": c.new_value}
            for c in diff.relation_changes
        ],
        "rule_changes": [
            {"type": c.change_type.value, "id": c.rule_id, "field": c.field,
             "old_value": c.old_value, "new_value": c.new_value}
            for c in diff.rule_changes
        ],
    }


def profile_version_tags(
    *, profile_name: str,
) -> dict[str, Any]:
    """프로파일의 모든 태그 조회."""
    store = _get_profile_store()
    tags = store.list_tags(profile_name=profile_name)
    return {
        "profile_name": profile_name,
        "count": len(tags),
        "tags": [
            {"name": t.name, "version_id": t.version_id, "created_at": t.created_at}
            for t in tags
        ],
    }
