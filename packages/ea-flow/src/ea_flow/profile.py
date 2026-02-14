from dataclasses import dataclass, field

from ea_flow.spec import FlowMetaStep


def _as_text(value: str | dict[str, str]) -> str:
    if isinstance(value, str):
        return value
    return value.get("en") or next(iter(value.values()), "")


@dataclass(frozen=True)
class FlowProfile:
    """A collection of logic patterns (MetaSteps) for a specific domain."""
    name: str
    version: str
    meta_steps: tuple[FlowMetaStep, ...]
    metadata: dict[str, str] = field(default_factory=dict)

    def get_meta_step(self, name: str) -> FlowMetaStep | None:
        for s in self.meta_steps:
            if _as_text(s.name) == name:
                return s
        return None
