"""Tier resolution — resolve tier definitions and node sets.

Extracted from kernel_service.py lines 2319-2370.
"""

from __future__ import annotations

from typing import Any

from ea_projection.tier.classifier import classify_element_tier


TIER_DEFINITIONS_FALLBACK: dict[str, dict[str, Any]] = {
    "ui": {
        "categories": ["Page", "Interface", "Context"],
        "name_patterns": [],
        "name_exclude_patterns": [],
        "transitions": ["function"],
    },
    "function": {
        "categories": ["ActiveStructure", "Behavior", "Executable", "Governance"],
        "name_patterns": [],
        "name_exclude_patterns": [],
        "transitions": ["data", "decision"],
    },
    "data": {
        "categories": ["PassiveStructure", "Composite"],
        "name_patterns": [],
        "name_exclude_patterns": ["Evidence", "Provenance", "Rationale", "Audit", "AnalysisReport", "Compliance"],
        "transitions": ["evidence"],
    },
    "decision": {
        "categories": ["Assessment", "Goal", "Event"],
        "name_patterns": [],
        "name_exclude_patterns": [],
        "transitions": ["evidence"],
    },
    "evidence": {
        "categories": ["PassiveStructure"],
        "name_patterns": ["Evidence", "Provenance", "Rationale", "Audit", "AnalysisReport", "Compliance"],
        "name_exclude_patterns": [],
        "transitions": [],
    },
}

TIER_NAMES: tuple[str, ...] = ("ui", "function", "data", "decision", "evidence")


def resolve_tier_node_set(
    nodes: list[dict[str, Any]],
    tier: str,
    tier_definitions: dict[str, dict[str, Any]],
) -> tuple[set[str], dict[str, str]]:
    """Return (node names matching tier, {name: tier} for all classified nodes)."""
    matched: set[str] = set()
    classification: dict[str, str] = {}
    for node in nodes:
        name = str(node.get("name", ""))
        category = str(node.get("category", ""))
        if not name:
            continue
        classified = classify_element_tier(name, category, tier_definitions)
        if classified:
            classification[name] = classified
        if classified == tier:
            matched.add(name)
    return matched, classification


def resolve_tier_definitions(
    policy_doc_loader: Any = None,
) -> dict[str, dict[str, Any]]:
    """Load tier definitions from a policy document loader or fall back to hardcoded defaults.

    Args:
        policy_doc_loader: A dict with "status" and "document" keys (as returned by
                          load_projection_policy_document), or None for fallback.
    """
    if policy_doc_loader is None:
        return dict(TIER_DEFINITIONS_FALLBACK)

    if not isinstance(policy_doc_loader, dict):
        return dict(TIER_DEFINITIONS_FALLBACK)

    if str(policy_doc_loader.get("status", "")) != "ok":
        return dict(TIER_DEFINITIONS_FALLBACK)

    doc = policy_doc_loader.get("document")
    if not isinstance(doc, dict):
        return dict(TIER_DEFINITIONS_FALLBACK)

    m2 = doc.get("m2")
    if not isinstance(m2, dict):
        return dict(TIER_DEFINITIONS_FALLBACK)

    tiers = m2.get("tiers")
    if not isinstance(tiers, dict):
        return dict(TIER_DEFINITIONS_FALLBACK)

    definitions = tiers.get("definitions")
    if not isinstance(definitions, dict) or not definitions:
        return dict(TIER_DEFINITIONS_FALLBACK)

    result: dict[str, dict[str, Any]] = {}
    for tier_name, tier_def in definitions.items():
        if not isinstance(tier_def, dict):
            continue
        cats = tier_def.get("categories")
        if not isinstance(cats, (list, tuple)) or not cats:
            continue
        result[str(tier_name)] = {
            "categories": [str(c) for c in cats],
            "name_patterns": [str(p) for p in (tier_def.get("name_patterns") or [])],
            "name_exclude_patterns": [str(p) for p in (tier_def.get("name_exclude_patterns") or [])],
            "transitions": [str(t) for t in (tier_def.get("transitions") or [])],
        }
    return result if result else dict(TIER_DEFINITIONS_FALLBACK)
