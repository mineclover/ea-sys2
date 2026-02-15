"""Structural diff between two KernelProfiles."""

from __future__ import annotations

from ea_profile.types import (
    DiffChangeType,
    ElementChange,
    KernelProfile,
    ProfileDiff,
    RelationChange,
    RuleChange,
)


def diff_profiles(a: KernelProfile, b: KernelProfile) -> ProfileDiff:
    """Compute the structural difference between two profiles.

    Elements matched by name, relations by name, rules by ID.
    """
    element_changes = _diff_elements(a, b)
    relation_changes = _diff_relations(a, b)
    rule_changes = _diff_rules(a, b)
    identical = (
        not element_changes and not relation_changes and not rule_changes
    )

    return ProfileDiff(
        from_name=a.name,
        from_version=a.version,
        to_name=b.name,
        to_version=b.version,
        identical=identical,
        element_changes=tuple(element_changes),
        relation_changes=tuple(relation_changes),
        rule_changes=tuple(rule_changes),
    )


def diff_summary(diff: ProfileDiff) -> str:
    """Human-readable diff summary."""
    if diff.identical:
        return f"{diff.from_name} {diff.from_version} == {diff.to_name} {diff.to_version}: identical"

    lines = [
        f"Diff: {diff.from_name} {diff.from_version} → {diff.to_name} {diff.to_version}"
    ]

    added = sum(1 for c in diff.element_changes if c.change_type == DiffChangeType.ADDED)
    removed = sum(1 for c in diff.element_changes if c.change_type == DiffChangeType.REMOVED)
    modified = sum(1 for c in diff.element_changes if c.change_type == DiffChangeType.MODIFIED)
    if added or removed or modified:
        lines.append(f"  Elements: +{added} -{removed} ~{modified}")

    added = sum(1 for c in diff.relation_changes if c.change_type == DiffChangeType.ADDED)
    removed = sum(1 for c in diff.relation_changes if c.change_type == DiffChangeType.REMOVED)
    modified = sum(1 for c in diff.relation_changes if c.change_type == DiffChangeType.MODIFIED)
    if added or removed or modified:
        lines.append(f"  Relations: +{added} -{removed} ~{modified}")

    added = sum(1 for c in diff.rule_changes if c.change_type == DiffChangeType.ADDED)
    removed = sum(1 for c in diff.rule_changes if c.change_type == DiffChangeType.REMOVED)
    modified = sum(1 for c in diff.rule_changes if c.change_type == DiffChangeType.MODIFIED)
    if added or removed or modified:
        lines.append(f"  Rules: +{added} -{removed} ~{modified}")

    return "\n".join(lines)


# ── Internal helpers ─────────────────────────────────────────────

def _diff_elements(a: KernelProfile, b: KernelProfile) -> list[ElementChange]:
    changes: list[ElementChange] = []
    a_map = {e.name: e for e in a.elements}
    b_map = {e.name: e for e in b.elements}

    for name in sorted(set(a_map) | set(b_map)):
        if name not in a_map:
            changes.append(ElementChange(DiffChangeType.ADDED, name))
        elif name not in b_map:
            changes.append(ElementChange(DiffChangeType.REMOVED, name))
        else:
            ea, eb = a_map[name], b_map[name]
            for field in ("kernel_type", "layer", "category", "description"):
                ov = getattr(ea, field)
                nv = getattr(eb, field)
                if ov != nv:
                    changes.append(ElementChange(
                        DiffChangeType.MODIFIED, name,
                        field=field, old_value=str(ov), new_value=str(nv),
                    ))
    return changes


def _diff_relations(a: KernelProfile, b: KernelProfile) -> list[RelationChange]:
    changes: list[RelationChange] = []
    a_map = {r.name: r for r in a.relations}
    b_map = {r.name: r for r in b.relations}

    for name in sorted(set(a_map) | set(b_map)):
        if name not in a_map:
            changes.append(RelationChange(DiffChangeType.ADDED, name))
        elif name not in b_map:
            changes.append(RelationChange(DiffChangeType.REMOVED, name))
        else:
            ra, rb = a_map[name], b_map[name]
            for field in ("kernel_relation", "description"):
                ov = getattr(ra, field)
                nv = getattr(rb, field)
                if ov != nv:
                    changes.append(RelationChange(
                        DiffChangeType.MODIFIED, name,
                        field=field, old_value=str(ov), new_value=str(nv),
                    ))
    return changes


def _diff_rules(a: KernelProfile, b: KernelProfile) -> list[RuleChange]:
    changes: list[RuleChange] = []
    a_map = {r.id: r for r in a.validity_rules}
    b_map = {r.id: r for r in b.validity_rules}

    for rid in sorted(set(a_map) | set(b_map)):
        if rid not in a_map:
            changes.append(RuleChange(DiffChangeType.ADDED, rid))
        elif rid not in b_map:
            changes.append(RuleChange(DiffChangeType.REMOVED, rid))
        else:
            ra, rb = a_map[rid], b_map[rid]
            for field in (
                "source_pattern", "target_pattern", "relationship_name",
                "valid", "priority", "notes",
            ):
                ov = getattr(ra, field)
                nv = getattr(rb, field)
                if ov != nv:
                    changes.append(RuleChange(
                        DiffChangeType.MODIFIED, rid,
                        field=field, old_value=str(ov), new_value=str(nv),
                    ))
            # Conditions: compare as tuples
            if ra.conditions != rb.conditions:
                changes.append(RuleChange(
                    DiffChangeType.MODIFIED, rid,
                    field="conditions",
                    old_value=str(ra.conditions),
                    new_value=str(rb.conditions),
                ))
    return changes
