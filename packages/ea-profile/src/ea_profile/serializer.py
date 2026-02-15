"""Dict/JSON round-trip serialization for KernelProfile.

Guarantees: dict_to_profile(profile_to_dict(p)) == p for all valid profiles.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ea_profile.types import (
    KernelProfile,
    ProfileElement,
    ProfileMetadata,
    ProfileRelation,
    ProfileRule,
    RuleCondition,
)


def profile_to_dict(profile: KernelProfile) -> dict[str, Any]:
    """KernelProfile → plain dict (JSON-safe)."""
    elements = [
        {
            "name": e.name,
            "kernel_type": e.kernel_type,
            "layer": e.layer,
            "category": e.category,
            "description": e.description,
        }
        for e in profile.elements
    ]

    relations = [
        {
            "name": r.name,
            "kernel_relation": r.kernel_relation,
            "description": r.description,
        }
        for r in profile.relations
    ]

    rules = [_rule_to_dict(r) for r in profile.validity_rules]

    metadata = None
    if profile.metadata is not None:
        metadata = {
            "standard": profile.metadata.standard,
            "organization": profile.metadata.organization,
            "extra": profile.metadata.extra,
        }

    return {
        "name": profile.name,
        "version": profile.version,
        "kernel_version": profile.kernel_version,
        "elements": elements,
        "relations": relations,
        "validity_rules": rules,
        "metadata": metadata,
    }


def dict_to_profile(data: dict[str, Any]) -> KernelProfile:
    """plain dict → KernelProfile (deserialization)."""
    elements = tuple(
        ProfileElement(
            name=e["name"],
            kernel_type=e["kernel_type"],
            layer=e["layer"],
            category=e["category"],
            description=e.get("description", ""),
        )
        for e in data["elements"]
    )

    relations = tuple(
        ProfileRelation(
            name=r["name"],
            kernel_relation=r["kernel_relation"],
            description=r.get("description", ""),
        )
        for r in data["relations"]
    )

    rules = tuple(_dict_to_rule(r) for r in data.get("validity_rules", []))

    metadata = None
    md = data.get("metadata")
    if md is not None:
        metadata = ProfileMetadata(
            standard=md["standard"],
            organization=md["organization"],
            extra=md.get("extra"),
        )

    return KernelProfile(
        name=data["name"],
        version=data["version"],
        kernel_version=data["kernel_version"],
        elements=elements,
        relations=relations,
        validity_rules=rules,
        metadata=metadata,
    )


def profile_to_json(profile: KernelProfile, *, indent: int = 2) -> str:
    """KernelProfile → JSON string."""
    return json.dumps(profile_to_dict(profile), indent=indent, ensure_ascii=False)


def json_to_profile(json_str: str) -> KernelProfile:
    """JSON string → KernelProfile."""
    return dict_to_profile(json.loads(json_str))


def compute_content_hash(profile: KernelProfile) -> str:
    """SHA256 hash of canonical JSON representation."""
    canonical = json.dumps(profile_to_dict(profile), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ── Internal helpers ─────────────────────────────────────────────

def _rule_to_dict(rule: ProfileRule) -> dict[str, Any]:
    conditions = [
        {
            "condition_type": str(c.condition_type),
            "parameters": [list(p) for p in c.parameters],
        }
        for c in rule.conditions
    ]
    return {
        "id": rule.id,
        "source_pattern": rule.source_pattern,
        "target_pattern": rule.target_pattern,
        "relationship_name": rule.relationship_name,
        "valid": rule.valid,
        "priority": rule.priority,
        "conditions": conditions,
        "notes": rule.notes,
    }


def _dict_to_rule(d: dict[str, Any]) -> ProfileRule:
    conditions = tuple(
        RuleCondition(
            condition_type=c["condition_type"],
            parameters=tuple(tuple(p) for p in c.get("parameters", [])),
        )
        for c in d.get("conditions", [])
    )
    return ProfileRule(
        id=d["id"],
        source_pattern=d["source_pattern"],
        target_pattern=d["target_pattern"],
        relationship_name=d["relationship_name"],
        valid=d.get("valid", True),
        priority=d.get("priority", 0),
        conditions=conditions,
        notes=d.get("notes", ""),
    )
