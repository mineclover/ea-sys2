"""Chainable query builder for profile elements and rules."""

from __future__ import annotations

from ea_kernel.profile_types import KernelProfile, ProfileElement
from ea_kernel.types import KernelValidityRule


class ElementQuery:
    """Chainable element filter."""

    def __init__(self, elements: tuple[ProfileElement, ...]) -> None:
        self._elements = elements

    def in_layer(self, layer: str) -> ElementQuery:
        return ElementQuery(
            tuple(e for e in self._elements if e.layer == layer)
        )

    def in_category(self, category: str) -> ElementQuery:
        return ElementQuery(
            tuple(e for e in self._elements if e.category == category)
        )

    def with_kernel_type(self, kernel_type: str) -> ElementQuery:
        return ElementQuery(
            tuple(e for e in self._elements if e.kernel_type == kernel_type)
        )

    def matching(self, pattern: str) -> ElementQuery:
        """Filter elements matching a validity rule pattern."""
        if pattern == "*":
            return ElementQuery(self._elements)
        if pattern.startswith("@"):
            return self.in_category(pattern[1:])
        if pattern.startswith("#"):
            return self.in_layer(pattern[1:])
        return ElementQuery(
            tuple(e for e in self._elements if e.name == pattern)
        )

    def names(self) -> tuple[str, ...]:
        return tuple(e.name for e in self._elements)

    def count(self) -> int:
        return len(self._elements)

    def first(self) -> ProfileElement | None:
        return self._elements[0] if self._elements else None

    def all(self) -> tuple[ProfileElement, ...]:
        return self._elements


class RuleQuery:
    """Chainable rule filter."""

    def __init__(self, rules: tuple[KernelValidityRule, ...]) -> None:
        self._rules = rules

    def for_relation(self, relation: str) -> RuleQuery:
        return RuleQuery(
            tuple(r for r in self._rules if r.relationship_name == relation)
        )

    def allow_only(self) -> RuleQuery:
        return RuleQuery(tuple(r for r in self._rules if r.valid))

    def deny_only(self) -> RuleQuery:
        return RuleQuery(tuple(r for r in self._rules if not r.valid))

    def with_priority_above(self, p: int) -> RuleQuery:
        return RuleQuery(tuple(r for r in self._rules if r.priority > p))

    def with_priority_below(self, p: int) -> RuleQuery:
        return RuleQuery(tuple(r for r in self._rules if r.priority < p))

    def with_source(self, pattern: str) -> RuleQuery:
        return RuleQuery(
            tuple(r for r in self._rules if r.source_pattern == pattern)
        )

    def with_target(self, pattern: str) -> RuleQuery:
        return RuleQuery(
            tuple(r for r in self._rules if r.target_pattern == pattern)
        )

    def count(self) -> int:
        return len(self._rules)

    def first(self) -> KernelValidityRule | None:
        return self._rules[0] if self._rules else None

    def all(self) -> tuple[KernelValidityRule, ...]:
        return self._rules

    def ids(self) -> tuple[str, ...]:
        return tuple(r.id for r in self._rules)


class ProfileQuery:
    """Chainable query builder for profile elements and rules."""

    def __init__(self, profile: KernelProfile) -> None:
        self._profile = profile

    def elements(self) -> ElementQuery:
        return ElementQuery(self._profile.elements)

    def rules(self) -> RuleQuery:
        return RuleQuery(self._profile.validity_rules)
