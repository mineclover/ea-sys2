from typing import Dict, Union
from enum import Enum

# Multi-language string: either a simple string or a mapping of language codes to strings
I18nString = Union[str, Dict[str, str]]

class FlowStepCategory(Enum):
    """
    Classifies the role of a step in the process.
    """
    ACTION = "action"           # Performs a task (e.g., Update DB)
    DECISION = "decision"       # Branches logic (e.g., If X then Y)
    EVENT = "event"             # Wait for internal/external signal
    GATEWAY = "gateway"         # Orchestration (Parallel/Join)
    TRANSFORMATION = "transform" # Data mapping/conversion
