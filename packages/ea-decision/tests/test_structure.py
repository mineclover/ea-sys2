from ea_decision.types import Intent, ChoiceOption, Choice, DecisionResult, DecisionPhase

def test_intent_creation():
    intent = Intent(
        id="intent-1",
        description="Test Intent",
        direction="maximize_value",
        context_refs=["ref-1"]
    )
    assert intent.id == "intent-1"
    assert intent.direction == "maximize_value"

def test_choice_option_creation():
    option = ChoiceOption(
        id="opt-1",
        intent_id="intent-1",
        description="Option 1",
        feasibility_score=0.8,
        alignment_score=0.9
    )
    assert option.feasibility_score == 0.8

def test_decision_phase_enum():
    assert DecisionPhase.DIVERGE == "diverge"
    assert DecisionPhase.CONVERGE == "converge"
    assert DecisionPhase.UTILIZE == "utilize"
