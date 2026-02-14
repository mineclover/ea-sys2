from dataclasses import dataclass, field
from enum import StrEnum

from ea_decision.types import I18nString


class DecisionComplexity(StrEnum):
    TRIVIAL = "trivial"
    STRUCTURAL = "structural"
    STRATEGIC = "strategic"


@dataclass(frozen=True)
class DecisionPattern:
    """Formal definition of a common architectural decision type."""
    name: I18nString  # e.g., "RefinementSelection"
    description: I18nString
    complexity: DecisionComplexity
    governed_rule_group: str | None = None  # Links to Kernel RuleGroup name
    required_intent_tags: tuple[str, ...] = ()

    # Cognitive / Reasoning Template
    inquiry_template: tuple[I18nString, ...] = ()  # Mandatory questions for Diverge phase
    verification_heuristics: tuple[I18nString, ...] = ()  # Guidelines for test cases
    outcome_anchors: dict[str, I18nString] = field(default_factory=dict)
    # "Successful state" vs "Failure state" descriptions

    def matches_intent(self, tags: tuple[str, ...]) -> bool:
        return all(tag in tags for tag in self.required_intent_tags)


# ---------------------------------------------------------------------------
# Absorbed from pattern_schema.py
# ---------------------------------------------------------------------------

class PatternType(StrEnum):
    TRADE_OFF = "trade_off"  # Comparing A vs B
    COMPLIANCE = "compliance"  # Aligning with Regulation X
    ARCHITECTURE = "architecture"  # Structuring a System
    PROCESS = "process"  # Defining a Workflow


@dataclass
class HeuristicRule:
    """A rule of thumb or logic check that applies to this pattern."""
    description: str
    severity: str = "info"  # info, warning, critical
    check_function: str | None = None  # Name of a function to run (if executable)


@dataclass
class Phase:
    """A required stage in the decision process."""
    name: str  # e.g., "Research", "Options", "RFC"
    description: str
    required_artifacts: list[str] = field(default_factory=list)  # e.g., ["ResearchNote", "Option"]


@dataclass
class PatternSchema:
    """
    The Meta-Model for a Decision Pattern.
    Defines HOW a decision should be made.
    """
    name: str
    type: PatternType
    description: str
    phases: list[Phase]
    heuristics: list[HeuristicRule] = field(default_factory=list)

    # Template for standard inquiries to ask
    inquiry_template: list[str] = field(default_factory=list)
