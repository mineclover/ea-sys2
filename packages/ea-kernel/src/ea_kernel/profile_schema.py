"""Read-only introspection view of a profile's structure."""

from __future__ import annotations

from ea_kernel.profile_types import KernelProfile, ProfileElement
from ea_kernel.types import KernelSchema, KernelValidityRule


class ProfileSchema:
    """Read-only introspection view of a profile's structure."""

    def __init__(self, profile: KernelProfile) -> None:
        self._profile = profile
        # Pre-compute indexes
        self._rules_by_rel: dict[str, list[KernelValidityRule]] = {}
        for r in profile.validity_rules:
            self._rules_by_rel.setdefault(r.relationship_name, []).append(r)

    @property
    def profile(self) -> KernelProfile:
        return self._profile

    # ── Structure ─────────────────────────────────────────────────

    @property
    def layers(self) -> tuple[str, ...]:
        return self._profile.domain_layers()

    @property
    def categories(self) -> tuple[str, ...]:
        seen: list[str] = []
        for e in self._profile.elements:
            if e.category not in seen:
                seen.append(e.category)
        return tuple(seen)

    @property
    def kernel_types_used(self) -> tuple[str, ...]:
        return tuple(sorted({e.kernel_type for e in self._profile.elements}))

    @property
    def kernel_relations_used(self) -> tuple[str, ...]:
        return tuple(sorted({r.kernel_relation for r in self._profile.relations}))

    # ── Pattern resolution ────────────────────────────────────────

    def resolve_pattern(self, pattern: str) -> tuple[ProfileElement, ...]:
        """Resolve a pattern to matching elements."""
        return self._profile.matching_elements(pattern)

    # ── Coverage ──────────────────────────────────────────────────

    def element_coverage(self, kernel: KernelSchema) -> float:
        """Fraction of kernel entity types used by this profile."""
        kernel_types = {e.name for e in kernel.entities}
        if not kernel_types:
            return 0.0
        used = {e.kernel_type for e in self._profile.elements}
        return len(used & kernel_types) / len(kernel_types)

    def relation_coverage(self, kernel: KernelSchema) -> float:
        """Fraction of kernel relation types used by this profile."""
        kernel_rels = {r.name for r in kernel.relations}
        if not kernel_rels:
            return 0.0
        used = {r.kernel_relation for r in self._profile.relations}
        return len(used & kernel_rels) / len(kernel_rels)

    # ── Rule navigation ───────────────────────────────────────────

    def rules_for_relation(self, relation_name: str) -> tuple[KernelValidityRule, ...]:
        return tuple(self._rules_by_rel.get(relation_name, []))

    def rules_between(self, source: str, target: str) -> tuple[KernelValidityRule, ...]:
        """Rules matching a specific source→target pair (pattern-aware)."""
        result: list[KernelValidityRule] = []
        for rule in self._profile.validity_rules:
            if self._matches(source, rule.source_pattern) and \
               self._matches(target, rule.target_pattern):
                result.append(rule)
        return tuple(result)

    def effective_rule(self, source_element: str,
                       target_element: str,
                       relation: str) -> KernelValidityRule | None:
        """Find the highest-priority matching rule for a specific triple."""
        candidates: list[KernelValidityRule] = []
        for rule in self._rules_by_rel.get(relation, []):
            if self._matches(source_element, rule.source_pattern) and \
               self._matches(target_element, rule.target_pattern):
                candidates.append(rule)
        if not candidates:
            return None
        # Highest priority; deny wins at same priority
        candidates.sort(key=lambda r: (r.priority, not r.valid), reverse=True)
        return candidates[0]

    # ── Internal ──────────────────────────────────────────────────

    def _matches(self, element_name: str, pattern: str) -> bool:
        """Check if an element name matches a validity rule pattern."""
        if pattern == "*":
            return True
        if pattern.startswith("@"):
            cat = pattern[1:]
            elem = self._profile.get_element(element_name)
            return elem is not None and elem.category == cat
        if pattern.startswith("#"):
            layer = pattern[1:]
            elem = self._profile.get_element(element_name)
            return elem is not None and elem.layer == layer
        return element_name == pattern
