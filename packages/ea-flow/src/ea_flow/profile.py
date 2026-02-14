from dataclasses import dataclass
from typing import Tuple, Dict, Optional
from ea_flow.spec import FlowMetaStep

@dataclass(frozen=True)
class FlowProfile:
    """A collection of logic patterns (MetaSteps) for a specific domain."""
    name: str
    version: str
    meta_steps: Tuple[FlowMetaStep, ...]
    metadata: Dict[str, str] = None

    def get_meta_step(self, name: str) -> Optional[FlowMetaStep]:
        for s in self.meta_steps:
            if s.name == name:
                return s
        return None
