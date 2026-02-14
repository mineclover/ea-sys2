from typing import Dict, Optional
from ea_decision.pattern import DecisionPattern

class DecisionRegistry:
    """Manages the lifecycle and lookup of DecisionPatterns."""
    
    def __init__(self):
        self._patterns: Dict[str, DecisionPattern] = {}

    def register(self, pattern: DecisionPattern):
        self._patterns[pattern.name] = pattern

    def get_pattern(self, name: str) -> Optional[DecisionPattern]:
        return self._patterns.get(name)

    def list_patterns(self) -> Dict[str, DecisionPattern]:
        return self._patterns.copy()

# Singleton instance for easy access
registry = DecisionRegistry()
