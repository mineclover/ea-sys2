"""Dict/JSON round-trip serialization for KernelProfile.

Guarantees: dict_to_profile(profile_to_dict(p)) == p for all valid profiles.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ea_profile.types import (
    KernelProfile,
    LayerDefinition,
    LayerStack,
    ProfileArtifactType,
    ProfileElement,
    ProfileMetadata,
    ProfileRelation,
    ProfileRule,
    ProfileStateTransition,
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
    state_transitions = [
        {
            "from_state": t.from_state,
            "to_state": t.to_state,
            "guard_condition": t.guard_condition,
            "description": t.description,
        }
        for t in profile.state_transitions
    ]
    artifact_types = [
        {
            "name": a.name,
            "tier": a.tier,
            "description": a.description,
            "kernel_element_pattern": a.kernel_element_pattern,
        }
        for a in profile.artifact_types
    ]

    metadata = None
    if profile.metadata is not None:
        metadata = {
            "standard": profile.metadata.standard,
            "organization": profile.metadata.organization,
            "extra": profile.metadata.extra,
        }

    layer_stack = None
    if profile.layer_stack is not None:
        layer_stack = {
            "layers": [
                {
                    "name": layer.name,
                    "order": layer.order,
                    "depends_on": list(layer.depends_on),
                    "responsibility": layer.responsibility,
                    "model_perspective": layer.model_perspective,
                }
                for layer in profile.layer_stack.layers
            ],
            "definition_flow": profile.layer_stack.definition_flow,
            "runtime_flow": profile.layer_stack.runtime_flow,
            "feedback_flow": profile.layer_stack.feedback_flow,
        }

    return {
        "name": profile.name,
        "version": profile.version,
        "kernel_version": profile.kernel_version,
        "elements": elements,
        "relations": relations,
        "validity_rules": rules,
        "state_transitions": state_transitions,
        "artifact_types": artifact_types,
        "metadata": metadata,
        "layer_stack": layer_stack,
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
    state_transitions = tuple(
        ProfileStateTransition(
            from_state=t["from_state"],
            to_state=t["to_state"],
            guard_condition=t.get("guard_condition", ""),
            description=t.get("description", ""),
        )
        for t in data.get("state_transitions", [])
    )
    artifact_types = tuple(
        ProfileArtifactType(
            name=a["name"],
            tier=a["tier"],
            description=a.get("description", ""),
            kernel_element_pattern=a.get("kernel_element_pattern", ""),
        )
        for a in data.get("artifact_types", [])
    )

    metadata = None
    md = data.get("metadata")
    if md is not None:
        metadata = ProfileMetadata(
            standard=md["standard"],
            organization=md["organization"],
            extra=md.get("extra"),
        )

    layer_stack = None
    ls = data.get("layer_stack")
    if ls is not None:
        layer_stack = LayerStack(
            layers=tuple(
                LayerDefinition(
                    name=layer["name"],
                    order=layer["order"],
                    depends_on=tuple(layer.get("depends_on", [])),
                    responsibility=layer.get("responsibility", ""),
                    model_perspective=layer.get("model_perspective", ""),
                )
                for layer in ls.get("layers", [])
            ),
            definition_flow=ls.get("definition_flow", ""),
            runtime_flow=ls.get("runtime_flow", ""),
            feedback_flow=ls.get("feedback_flow", ""),
        )

    return KernelProfile(
        name=data["name"],
        version=data["version"],
        kernel_version=data["kernel_version"],
        elements=elements,
        relations=relations,
        validity_rules=rules,
        metadata=metadata,
        state_transitions=state_transitions,
        artifact_types=artifact_types,
        layer_stack=layer_stack,
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
    d: dict[str, Any] = {
        "id": rule.id,
        "source_pattern": rule.source_pattern,
        "target_pattern": rule.target_pattern,
        "relationship_name": rule.relationship_name,
        "valid": rule.valid,
        "priority": rule.priority,
        "conditions": conditions,
        "notes": rule.notes,
    }
    if rule.scope:
        d["scope"] = rule.scope
    return d


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
        scope=d.get("scope", ""),
    )
