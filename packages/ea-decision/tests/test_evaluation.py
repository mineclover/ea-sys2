from ea_decision.evaluation import EvaluationDimension, EvaluationResult, OptionScore


def test_weighted_total_uses_dimension_weights() -> None:
    result = EvaluationResult(
        dimensions=(
            EvaluationDimension(name="cost", description="Cost score", weight=0.4),
            EvaluationDimension(name="risk", description="Risk score", weight=0.6),
        ),
        scores=(
            OptionScore(option_id="opt-a", dimension_name="cost", value=8.0),
            OptionScore(option_id="opt-a", dimension_name="risk", value=5.0),
        ),
    )

    assert result.weighted_total("opt-a") == 8.0 * 0.4 + 5.0 * 0.6


def test_weighted_total_uses_default_weight_for_unknown_dimension() -> None:
    result = EvaluationResult(
        dimensions=(EvaluationDimension(name="cost", description="Cost score", weight=0.5),),
        scores=(OptionScore(option_id="opt-b", dimension_name="unknown", value=3.0),),
    )

    assert result.weighted_total("opt-b") == 3.0


def test_weighted_total_returns_zero_for_missing_option() -> None:
    result = EvaluationResult()
    assert result.weighted_total("missing") == 0.0
