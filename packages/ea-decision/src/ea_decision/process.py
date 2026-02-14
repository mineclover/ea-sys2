import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ea_decision.types import Choice, ChoiceOption, DecisionResult, Intent


class DesignThinkingProcess:
    """Orchestrates the decision-making lifecycle through Design Thinking phases."""

    def define_intent(
        self,
        description: str,
        direction: str,
        context_refs: list[str] | None = None,
    ) -> Intent:
        """Starts the process by defining the Intent."""
        return Intent(
            id=str(uuid.uuid4()),
            description=description,
            direction=direction,
            context_refs=context_refs or [],
        )

    def diverge(self, intent: Intent, options_data: list[dict[str, Any]]) -> list[ChoiceOption]:
        """Generates options based on the Intent (Diverge phase)."""
        options: list[ChoiceOption] = []
        for data in options_data:
            options.append(
                ChoiceOption(
                    id=str(uuid.uuid4()),
                    intent_id=intent.id,
                    description=data.get("description", ""),
                    feasibility_score=data.get("feasibility_score", 0.0),
                    alignment_score=data.get("alignment_score", 0.0),
                    metadata=data.get("metadata", {}),
                )
            )
        return options

    def converge(
        self,
        intent: Intent,
        options: list[ChoiceOption],
        selector_func: Callable[[list[ChoiceOption]], ChoiceOption],
    ) -> Choice:
        """Evaluates options and selects one (Converge phase)."""
        selected_option = selector_func(options)

        # Calculate distance (simplified: 1 - alignment)
        distance = 1.0 - selected_option.alignment_score

        return Choice(
            id=str(uuid.uuid4()),
            intent_id=intent.id,
            selected_option_id=selected_option.id,
            rationale=f"Selected based on highest score: {selected_option.alignment_score}",
            distance=distance,
        )

    def utilize(self, choice: Choice, outcome_artifact: Any) -> DecisionResult:
        """Executes the choice to produce a result (Utilize phase)."""
        return DecisionResult(
            id=str(uuid.uuid4()),
            intent_id=choice.intent_id,
            choice_id=choice.id,
            outcome_artifact=outcome_artifact,
            timestamp=datetime.now(UTC).isoformat() + "Z",
        )
