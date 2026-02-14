"""Build-time quality gate for kernel profiles.

Integrates analysis from evaluation.py, profile_analyzer.py, and rule_analysis.py
into a single quality check run at profile build time.

Usage:
    from ea_kernel.v2.profile_quality_gate import check_profile_quality
    from ea_kernel.spec import KERNEL_SPEC

    report = check_profile_quality(MY_PROFILE, KERNEL_SPEC)
    if not report.passed:
        print(f"Dead rules: {report.dead_rules}")
        print(f"Conflicts: {report.conflicting_rules}")
"""

from __future__ import annotations

from ea_kernel.profile_types import KernelProfile, QualityReport
from ea_kernel.types import KernelSchema, KernelValidityRule


def check_profile_quality(
    profile: KernelProfile,
    kernel: KernelSchema,
) -> QualityReport:
    """Run quality checks on a built profile.

    Checks:
    - Dead rules: rules that never win for any matching element pair
    - Conflicting rules: same priority, same pattern, opposite validity
    - Missing fallbacks: relations without deny-by-default rules
    - Invalid patterns: @Category/#Layer/ElementName that don't resolve
    - Invalid kernel refs: kernel_type/kernel_relation not in kernel
    - Coverage: fraction of kernel types/relations used
    """
    dead = _find_dead_rules(profile)
    conflicts = _find_conflicting_rules(profile)
    missing_fb = _find_missing_fallbacks(profile)
    invalid_pats = _find_invalid_patterns(profile)
    invalid_refs = _find_invalid_kernel_refs(profile, kernel)
    coverage = _compute_coverage(profile, kernel)

    passed = (
        not dead
        and not conflicts
        and not missing_fb
        and not invalid_pats
        and not invalid_refs
    )

    return QualityReport(
        passed=passed,
        dead_rules=tuple(dead),
        conflicting_rules=tuple(conflicts),
        missing_fallbacks=tuple(missing_fb),
        invalid_patterns=tuple(invalid_pats),
        invalid_kernel_refs=tuple(invalid_refs),
        coverage=coverage,
    )


def _find_dead_rules(profile: KernelProfile) -> list[str]:
    """Find rules that are always shadowed by higher-priority rules."""
    explicit = [r for r in profile.validity_rules if r.priority > 1]
    dead: list[str] = []

    for rule in explicit:
        shadowed = False
        for other in explicit:
            if other.id == rule.id:
                continue
            if (other.relationship_name == rule.relationship_name
                    and other.priority > rule.priority
                    and _pattern_covers(other.source_pattern, rule.source_pattern)
                    and _pattern_covers(other.target_pattern, rule.target_pattern)
                    and not rule.conditions
                    and not other.conditions):
                shadowed = True
                break
        if shadowed:
            dead.append(rule.id)

    return dead


def _pattern_covers(broader: str, narrower: str) -> bool:
    """Check if `broader` pattern covers all matches of `narrower`."""
    if broader == "*":
        return True
    return broader == narrower


def _find_conflicting_rules(
    profile: KernelProfile,
) -> list[tuple[str, str]]:
    """Find rule pairs at the same priority with opposite validity."""
    explicit = [r for r in profile.validity_rules if r.priority > 1]
    conflicts: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for i, a in enumerate(explicit):
        for b in explicit[i + 1:]:
            if (a.relationship_name == b.relationship_name
                    and a.priority == b.priority
                    and a.valid != b.valid
                    and _patterns_overlap(a, b)):
                key = (min(a.id, b.id), max(a.id, b.id))
                if key not in seen:
                    seen.add(key)
                    conflicts.append(key)

    return conflicts


def _patterns_overlap(a: KernelValidityRule, b: KernelValidityRule) -> bool:
    """Check if two rules' patterns can match the same elements."""
    return (
        _single_pattern_overlap(a.source_pattern, b.source_pattern)
        and _single_pattern_overlap(a.target_pattern, b.target_pattern)
    )


def _single_pattern_overlap(p1: str, p2: str) -> bool:
    """Check if two single patterns can match the same element."""
    if p1 == "*" or p2 == "*":
        return True
    return p1 == p2


def _find_missing_fallbacks(profile: KernelProfile) -> list[str]:
    """Find relations without a deny-by-default fallback rule."""
    fallback_rels: set[str] = set()
    for rule in profile.validity_rules:
        if (not rule.valid and rule.priority == 1
                and rule.source_pattern == "*"
                and rule.target_pattern == "*"):
            fallback_rels.add(rule.relationship_name)

    rel_names = {r.name for r in profile.relations}
    return sorted(rel_names - fallback_rels)


def _find_invalid_patterns(profile: KernelProfile) -> list[str]:
    """Find rule patterns that don't resolve to any elements."""
    categories = {e.category for e in profile.elements}
    layers = {e.layer for e in profile.elements}
    names = {e.name for e in profile.elements}
    invalid: list[str] = []

    for rule in profile.validity_rules:
        for pattern in (rule.source_pattern, rule.target_pattern):
            if pattern == "*":
                continue
            if pattern.startswith("@"):
                if pattern[1:] not in categories:
                    invalid.append(f"{rule.id}:{pattern}")
            elif pattern.startswith("#"):
                if pattern[1:] not in layers:
                    invalid.append(f"{rule.id}:{pattern}")
            elif pattern not in names:
                invalid.append(f"{rule.id}:{pattern}")

    return invalid


def _find_invalid_kernel_refs(
    profile: KernelProfile,
    kernel: KernelSchema,
) -> list[str]:
    """Find kernel type/relation references that don't exist."""
    kernel_entities = {e.name for e in kernel.entities}
    kernel_relations = {r.name for r in kernel.relations}
    invalid: list[str] = []

    for elem in profile.elements:
        if elem.kernel_type not in kernel_entities:
            invalid.append(f"element:{elem.name}→{elem.kernel_type}")

    for rel in profile.relations:
        if rel.kernel_relation not in kernel_relations:
            invalid.append(f"relation:{rel.name}→{rel.kernel_relation}")

    return invalid


def _compute_coverage(
    profile: KernelProfile,
    kernel: KernelSchema,
) -> float:
    """Compute kernel type/relation usage coverage (0.0–1.0)."""
    concrete_types = {e.name for e in kernel.entities if not e.is_abstract}
    kernel_relations = {r.name for r in kernel.relations}

    used_types = {e.kernel_type for e in profile.elements}
    used_rels = {r.kernel_relation for r in profile.relations}

    total = len(concrete_types) + len(kernel_relations)
    if total == 0:
        return 0.0

    used = len(used_types & concrete_types) + len(used_rels & kernel_relations)
    return used / total
