"""Tests for ea_needs.kernel_bridge — kernel integration bridge."""

from ea_needs.kernel_bridge import validate_kernel_refs, validate_scenario_kernel_refs
from ea_needs.types import ScenarioFlow, ScenarioStep, ScenarioType


class TestValidateScenarioKernelRefs:
    def test_no_kernel_refs(self):
        """Steps without kernel_ref return empty dict."""
        steps = (
            ScenarioStep(order=1, actor="User", action="login", system_response="ok"),
            ScenarioStep(order=2, actor="System", action="auth", system_response="ok"),
        )
        scenario = ScenarioFlow(
            id="sf-test",
            use_case_id="uc-test",
            title="No refs",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        result = validate_scenario_kernel_refs(scenario)
        assert result == {}

    def test_with_kernel_refs(self):
        """Steps with kernel_ref are extracted and validated."""
        steps = (
            ScenarioStep(
                order=1, actor="User", action="login", system_response="ok",
                kernel_ref="element",
            ),
            ScenarioStep(
                order=2, actor="System", action="auth", system_response="ok",
            ),
            ScenarioStep(
                order=3, actor="System", action="notify", system_response="ok",
                kernel_ref="relationship",
            ),
        )
        scenario = ScenarioFlow(
            id="sf-test",
            use_case_id="uc-test",
            title="With refs",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        result = validate_scenario_kernel_refs(scenario)
        # Should have two entries (the non-None kernel_refs)
        assert len(result) == 2
        assert "element" in result
        assert "relationship" in result

    def test_mixed_refs_some_none(self):
        """Only non-None kernel_refs are validated."""
        steps = (
            ScenarioStep(order=1, actor="A", action="a", system_response="b", kernel_ref="element"),
            ScenarioStep(order=2, actor="A", action="c", system_response="d", kernel_ref=None),
        )
        scenario = ScenarioFlow(
            id="sf-test",
            use_case_id="uc-test",
            title="Mixed",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        result = validate_scenario_kernel_refs(scenario)
        assert len(result) == 1
        assert "element" in result

    def test_empty_steps(self):
        """Scenario with no steps returns empty dict."""
        scenario = ScenarioFlow(
            id="sf-test",
            use_case_id="uc-test",
            title="Empty",
            scenario_type=ScenarioType.MAIN,
            steps=(),
        )
        result = validate_scenario_kernel_refs(scenario)
        assert result == {}
