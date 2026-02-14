"""Load kernel validity rules from TOML specification files."""

from __future__ import annotations

try:
    import tomllib
except ImportError:
    import tomli as tomllib
from pathlib import Path

from ea_kernel.types import (
    KernelConditionType,
    KernelRuleCondition,
    KernelValidityRule,
    Layer,
    LayerConstraint,
    RuleCategory,
    RuleConfidence,
    RuleGroup,
    RuleMetadata,
)

SPECS_DIR = Path(__file__).parent / "specs"

_CONDITION_MAP: dict[str, KernelConditionType] = {
    "LAYER_ORDER": KernelConditionType.LAYER_ORDER,
    "SAME_LAYER": KernelConditionType.SAME_LAYER,
    "SAME_BRANCH": KernelConditionType.SAME_ENTITY_BRANCH,
    "ANCESTOR_OF": KernelConditionType.ANCESTOR_OF,
    "SAME_CATEGORY": KernelConditionType.SAME_CATEGORY,
}

_LAYER_MAP: dict[str, Layer] = {
    "L1": Layer.L1, "L2": Layer.L2, "L3": Layer.L3, "L4": Layer.L4,
}


class RuleLoadError(Exception):
    """Raised when a TOML rule file cannot be parsed or validated."""


def _parse_condition(raw: str | dict) -> KernelRuleCondition:
    """Parse a condition entry (string or dict with type+params)."""
    if isinstance(raw, str):
        ct = _CONDITION_MAP.get(raw)
        if ct is None:
            raise RuleLoadError(f"Unknown condition: {raw!r}")
        return KernelRuleCondition(ct)
    # dict form: {type = "...", params = {k: v, ...}}
    ct = _CONDITION_MAP.get(raw["type"])
    if ct is None:
        raise RuleLoadError(f"Unknown condition type: {raw['type']!r}")
    params = tuple(sorted(raw.get("params", {}).items()))
    return KernelRuleCondition(ct, parameters=params)


def _parse_rule(rule_id: str, data: dict) -> KernelValidityRule:
    """Parse a single rule entry from TOML."""
    for field in ("source", "target", "relation"):
        if field not in data:
            raise RuleLoadError(f"Rule {rule_id!r} missing required field: {field!r}")
    conditions = tuple(_parse_condition(c) for c in data.get("conditions", []))
    return KernelValidityRule(
        id=rule_id,
        source_pattern=data["source"],
        target_pattern=data["target"],
        relationship_name=data["relation"],
        valid=data.get("valid", True),
        priority=data.get("priority", 0),
        conditions=conditions,
        notes=data.get("notes", ""),
    )


def _parse_layer_constraint(data: dict, index: int) -> LayerConstraint:
    """Parse a layer constraint entry from TOML."""
    src = data.get("source_layer")
    tgt = data.get("target_layer")
    if src not in _LAYER_MAP:
        raise RuleLoadError(f"Layer constraint #{index}: invalid source_layer {src!r}")
    if tgt not in _LAYER_MAP:
        raise RuleLoadError(f"Layer constraint #{index}: invalid target_layer {tgt!r}")
    forbidden = data.get("forbidden", [])
    allowed = tuple(tuple(pair) for pair in data.get("allowed_pairs", []))
    return LayerConstraint(
        source_layer=_LAYER_MAP[src],
        target_layer=_LAYER_MAP[tgt],
        forbidden_relations=tuple(forbidden),
        allowed_pairs=allowed,
        priority=data.get("priority", 90),
        notes=data.get("notes", ""),
    )


def _generate_fallbacks(
    names: list[str],
) -> tuple[KernelValidityRule, ...]:
    """Generate deny-by-default fallback rules for each relation name."""
    return tuple(
        KernelValidityRule(
            id=f"fallback-{name}",
            source_pattern="*",
            target_pattern="*",
            relationship_name=name,
            valid=False,
            priority=1,
            notes=f"Deny-by-default for {name}",
        )
        for name in names
    )


def load_from_content(
    toml_content: str,
) -> tuple[tuple[KernelValidityRule, ...], tuple[LayerConstraint, ...]]:
    """Load kernel rules from a TOML string.

    This is the common parsing core used by both file-based loading
    and the RuleVersionStore.

    Returns (validity_rules, layer_constraints).
    """
    doc = tomllib.loads(toml_content)

    meta = doc.get("meta", {})

    # Parse explicit rules
    rules_section = doc.get("rules", {})
    explicit_rules = tuple(
        _parse_rule(rid, rdata) for rid, rdata in rules_section.items()
    )

    # Self-verification: count check
    expected_explicit = meta.get("total_explicit_rules")
    if expected_explicit is not None and len(explicit_rules) != expected_explicit:
        raise RuleLoadError(
            f"Expected {expected_explicit} explicit rules, got {len(explicit_rules)}"
        )

    # Parse layer constraints
    constraints_raw = doc.get("layer_constraints", [])
    constraints = tuple(
        _parse_layer_constraint(lc, i) for i, lc in enumerate(constraints_raw)
    )

    expected_constraints = meta.get("total_layer_constraints")
    if expected_constraints is not None and len(constraints) != expected_constraints:
        raise RuleLoadError(
            f"Expected {expected_constraints} layer constraints, got {len(constraints)}"
        )

    # Generate fallback rules
    fallback_names = meta.get("fallback_relations", [])
    fallbacks = _generate_fallbacks(fallback_names)

    all_rules = (*explicit_rules, *fallbacks)
    return all_rules, constraints


def load_kernel_rules(
    path: Path | None = None,
) -> tuple[tuple[KernelValidityRule, ...], tuple[LayerConstraint, ...]]:
    """Load kernel rules from a TOML file.

    Returns (validity_rules, layer_constraints).
    """
    path = path or (SPECS_DIR / "kernel_rules.toml")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RuleLoadError(f"Rule file not found: {path}")
    return load_from_content(raw.decode())


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata-aware loading — Phase 0.5
# ═══════════════════════════════════════════════════════════════════════════════

_CATEGORY_MAP: dict[str, RuleCategory] = {
    "structural": RuleCategory.STRUCTURAL,
    "behavioral": RuleCategory.BEHAVIORAL,
    "domain": RuleCategory.DOMAIN,
    "empirical": RuleCategory.EMPIRICAL,
}

_CONFIDENCE_MAP: dict[str, RuleConfidence] = {
    "universal": RuleConfidence.UNIVERSAL,
    "common": RuleConfidence.COMMON,
    "contextual": RuleConfidence.CONTEXTUAL,
    "empirical": RuleConfidence.EMPIRICAL,
}

def _parse_metadata(rule_id: str, data: dict) -> RuleMetadata | None:
    """Parse metadata sub-table from a rule entry, if present."""
    meta = data.get("metadata")
    if meta is None:
        return None
    category = _CATEGORY_MAP.get(meta.get("category", ""))
    if category is None:
        raise RuleLoadError(f"Rule {rule_id!r}: invalid metadata.category")
    confidence = _CONFIDENCE_MAP.get(meta.get("confidence", ""))
    if confidence is None:
        raise RuleLoadError(f"Rule {rule_id!r}: invalid metadata.confidence")
    # group: TOML에 있으면 사용, 없으면 rule의 relation에서 파생
    group_str = meta.get("group")
    group = RuleGroup.from_relation(group_str or data.get("relation", ""))
    return RuleMetadata(
        domain=meta.get("domain", "kernel"),
        tags=tuple(meta.get("tags", ())),
        category=category,
        confidence=confidence,
        source=meta.get("source", ""),
        established_version=meta.get("established_version", ""),
        rationale=meta.get("rationale", ""),
        group=group,
    )


def load_kernel_rules_with_metadata(
    path: Path | None = None,
) -> tuple[
    tuple[KernelValidityRule, ...],
    tuple[LayerConstraint, ...],
    dict[str, RuleMetadata],
]:
    """Load kernel rules and any embedded metadata from a TOML file.

    Returns (validity_rules, layer_constraints, metadata_map).
    The metadata_map keys are rule IDs; only rules with explicit
    [rules.xxx.metadata] sections are included.
    """
    path = path or (SPECS_DIR / "kernel_rules.toml")
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise RuleLoadError(f"Rule file not found: {path}")

    content = raw.decode()
    rules, constraints = load_from_content(content)

    # Re-parse to extract metadata (load_from_content ignores unknown fields)
    doc = tomllib.loads(content)
    meta_section = doc.get("meta", {})
    rules_section = doc.get("rules", {})
    metadata_map: dict[str, RuleMetadata] = {}
    for rule_id, rdata in rules_section.items():
        meta = _parse_metadata(rule_id, rdata)
        if meta is not None:
            metadata_map[rule_id] = meta

    # Self-verification: metadata count check
    expected_metadata = meta_section.get("total_explicit_metadata")
    if expected_metadata is not None and len(metadata_map) != expected_metadata:
        raise RuleLoadError(
            f"Expected {expected_metadata} explicit metadata entries, "
            f"got {len(metadata_map)}"
        )

    return rules, constraints, metadata_map
