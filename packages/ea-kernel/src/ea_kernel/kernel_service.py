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


def describe_profile(*, name: str, lang: str | None = None) -> dict[str, Any] | None:
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


def profile_topology(
    *,
    profile_name: str,
    cross_layer: bool = False,
    lang: str | None = None,
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

    graph = ProfileTopologyGraph(profile)

    # Build layer lookup: element name → domain layer
    layer_of: dict[str, str] = {elem.name: elem.layer for elem in profile.elements}

    all_edges: list[dict[str, Any]] = []
    for src in graph.nodes:
        for edge in graph.outgoing(src):
            all_edges.append({
                "source": edge.source,
                "target": edge.target,
                "relation": edge.relation,
                "rule_id": edge.rule_id,
                "priority": edge.priority,
            })

    def _elem_dict(elem: Any) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": elem.name,
            "layer": elem.layer,
            "category": elem.category,
            "kernel_type": elem.kernel_type,
            "description": _serialize_i18n(elem.description),
        }
        if elem.display_name:
            d["display_name"] = _serialize_i18n(elem.display_name)
        return d

    if cross_layer:
        all_edges = [
            e for e in all_edges
            if layer_of.get(e["source"], "") != layer_of.get(e["target"], "")
        ]
        connected = {e["source"] for e in all_edges} | {e["target"] for e in all_edges}
        nodes = [_elem_dict(elem) for elem in profile.elements if elem.name in connected]
    else:
        nodes = [_elem_dict(elem) for elem in profile.elements]

    # Relation distribution for the (possibly filtered) edge set
    rel_dist: dict[str, int] = {}
    for e in all_edges:
        rel_dist[e["relation"]] = rel_dist.get(e["relation"], 0) + 1

    return {
        "profile": profile_name,
        "cross_layer": cross_layer,
        "nodes": nodes,
        "edges": all_edges,
        "node_count": len(nodes),
        "edge_count": len(all_edges),
        "relation_distribution": rel_dist,
    }


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


# ── I18n Service ─────────────────────────────────────────────


def _get_i18n_store() -> "I18nStore":
    from pathlib import Path

    from ea_kernel.i18n_store import SQLiteI18nStore
    db_path = Path(__file__).parent / "data" / "i18n.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteI18nStore(db_path)


def audit_i18n(*, lang: str = "ko") -> dict[str, Any]:
    """TOML 패치 기반 i18n 감사 리포트."""
    from ea_kernel.schema_loader import audit_i18n_patch
    spec = _get_spec()
    report = audit_i18n_patch(spec, lang)
    return {
        "lang": report.lang,
        "coverage": report.coverage,
        "total_schema_items": report.total_schema_items,
        "total_translated": report.total_translated,
        "total_issues": report.total_issues,
        "is_clean": report.is_clean,
        "missing": [
            {"kind": e.kind, "name": e.name, "field": e.field, "en_current": e.en_current}
            for e in report.missing
        ],
        "orphan": [
            {"kind": e.kind, "name": e.name, "field": e.field}
            for e in report.orphan
        ],
        "stale": [
            {"kind": e.kind, "name": e.name, "field": e.field,
             "en_current": e.en_current, "en_recorded": e.en_recorded}
            for e in report.stale
        ],
    }


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
