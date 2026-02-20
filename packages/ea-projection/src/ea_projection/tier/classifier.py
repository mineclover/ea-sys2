"""Tier classification — classify elements into projection tiers.

Extracted from kernel_service.py lines 2286-2316.
"""

from __future__ import annotations

from typing import Any


def classify_element_tier(
    name: str,
    category: str,
    tier_definitions: dict[str, dict[str, Any]],
) -> str | None:
    """Classify an element into a tier based on its category and name patterns.

    Evidence tier is checked first because it shares PassiveStructure with data.
    """
    name_lower = name.lower()
    evidence_def = tier_definitions.get("evidence")
    if evidence_def and category in evidence_def.get("categories", []):
        patterns = evidence_def.get("name_patterns", [])
        if patterns and any(pat.lower() in name_lower for pat in patterns):
            return "evidence"

    for tier_name, tier_def in tier_definitions.items():
        if tier_name == "evidence":
            continue
        categories = tier_def.get("categories", [])
        if category not in categories:
            continue
        exclude_patterns = tier_def.get("name_exclude_patterns", [])
        if exclude_patterns and any(pat.lower() in name_lower for pat in exclude_patterns):
            continue
        include_patterns = tier_def.get("name_patterns", [])
        if include_patterns and not any(pat.lower() in name_lower for pat in include_patterns):
            continue
        return tier_name
    return None
