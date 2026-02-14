from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, List, Any
from enum import Enum

from ea_decision.types import I18nString

class DecisionComplexity(str, Enum):
    TRIVIAL = "trivial"
    STRUCTURAL = "structural"
    STRATEGIC = "strategic"

@dataclass(frozen=True)
class DecisionPattern:
    """Formal definition of a common architectural decision type."""
    name: I18nString # e.g., "RefinementSelection"
    description: I18nString
    complexity: DecisionComplexity
    governed_rule_group: Optional[str] = None # Links to Kernel RuleGroup name
    required_intent_tags: Tuple[str, ...] = ()

    # Cognitive / Reasoning Template
    inquiry_template: Tuple[I18nString, ...] = ()      # Mandatory questions for Diverge phase
    verification_heuristics: Tuple[I18nString, ...] = () # Guidelines for test cases
    outcome_anchors: Dict[str, I18nString] = None     # "Successful state" vs "Failure state" descriptions

    def matches_intent(self, tags: Tuple[str, ...]) -> bool:
        return all(tag in tags for tag in self.required_intent_tags)


# ---------------------------------------------------------------------------
# Absorbed from pattern_schema.py
# ---------------------------------------------------------------------------

class PatternType(str, Enum):
    TRADE_OFF = "trade_off"       # Comparing A vs B
    COMPLIANCE = "compliance"     # Aligning with Regulation X
    ARCHITECTURE = "architecture" # Structuring a System
    PROCESS = "process"           # Defining a Workflow

@dataclass
class HeuristicRule:
    """A rule of thumb or logic check that applies to this pattern."""
    description: str
    severity: str = "info" # info, warning, critical
    check_function: Optional[str] = None # Name of a function to run (if executable)

@dataclass
class Phase:
    """A required stage in the decision process."""
    name: str # e.g., "Research", "Options", "RFC"
    description: str
    required_artifacts: List[str] = field(default_factory=list) # e.g., ["ResearchNote", "Option"]

@dataclass
class PatternSchema:
    """
    The Meta-Model for a Decision Pattern.
    Defines HOW a decision should be made.
    """
    name: str
    type: PatternType
    description: str
    phases: List[Phase]
    heuristics: List[HeuristicRule] = field(default_factory=list)

    # Template for standard inquiries to ask
    inquiry_template: List[str] = field(default_factory=list)
