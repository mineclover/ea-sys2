from ea_decision.pattern import DecisionPattern


def _as_pattern_key(name: str | dict[str, str]) -> str:
    if isinstance(name, str):
        return name
    return name.get("en") or next(iter(name.values()), "")


class DecisionRegistry:
    """Manages the lifecycle and lookup of DecisionPatterns."""

    def __init__(self) -> None:
        self._patterns: dict[str, DecisionPattern] = {}

    def register(self, pattern: DecisionPattern) -> None:
        self._patterns[_as_pattern_key(pattern.name)] = pattern

    def get_pattern(self, name: str) -> DecisionPattern | None:
        return self._patterns.get(name)

    def list_patterns(self) -> dict[str, DecisionPattern]:
        return self._patterns.copy()

# Singleton instance for easy access
registry = DecisionRegistry()
