import pytest
from ea_decision.lifecycle import DecisionLifecycle, DecisionLifecycleState


def test_valid_transition_returns_new_state() -> None:
    lifecycle = DecisionLifecycle()
    proposed = lifecycle.transition(DecisionLifecycleState.PROPOSED)

    assert lifecycle.state == DecisionLifecycleState.DRAFT
    assert proposed.state == DecisionLifecycleState.PROPOSED
    assert proposed.transitioned_at


def test_invalid_transition_raises_value_error() -> None:
    lifecycle = DecisionLifecycle(state=DecisionLifecycleState.DRAFT)

    with pytest.raises(ValueError, match="Invalid transition"):
        lifecycle.transition(DecisionLifecycleState.ACCEPTED)
