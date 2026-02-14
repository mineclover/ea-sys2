"""Decision lifecycle state machine (N2).

Follows the Kernel RuleLifecycle pattern: frozen, transition() returns a new instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ea_decision.types import _now


class DecisionLifecycleState(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


VALID_DECISION_TRANSITIONS: dict[DecisionLifecycleState, frozenset[DecisionLifecycleState]] = {
    DecisionLifecycleState.DRAFT: frozenset({DecisionLifecycleState.PROPOSED}),
    DecisionLifecycleState.PROPOSED: frozenset({
        DecisionLifecycleState.ACCEPTED,
        DecisionLifecycleState.REJECTED,
    }),
    DecisionLifecycleState.ACCEPTED: frozenset({
        DecisionLifecycleState.DEPRECATED,
        DecisionLifecycleState.SUPERSEDED,
    }),
    DecisionLifecycleState.REJECTED: frozenset(),
    DecisionLifecycleState.DEPRECATED: frozenset(),
    DecisionLifecycleState.SUPERSEDED: frozenset(),
}


@dataclass(frozen=True)
class DecisionLifecycle:
    """Immutable lifecycle snapshot — transition() returns a new instance."""
    state: DecisionLifecycleState = DecisionLifecycleState.DRAFT
    transitioned_at: str = ""

    def transition(self, target: DecisionLifecycleState) -> DecisionLifecycle:
        allowed = VALID_DECISION_TRANSITIONS.get(self.state, frozenset())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {self.state.value} -> {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        return DecisionLifecycle(state=target, transitioned_at=_now())
