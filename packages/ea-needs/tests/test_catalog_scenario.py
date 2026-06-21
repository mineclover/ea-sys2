"""Tests for NeedCatalog scenario flow management."""

import json

import pytest
from ea_needs.catalog import NeedCatalog
from ea_needs.types import ScenarioFlow, ScenarioStep, ScenarioType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def catalog() -> NeedCatalog:
    return NeedCatalog(name="Scenario Test Catalog", description="For scenario tests")


@pytest.fixture
def catalog_with_use_case(catalog: NeedCatalog):
    uc = catalog.add_use_case(
        title="Login",
        actor="User",
        situation="unauthenticated",
        purpose="access the system",
    )
    return catalog, uc


def _main_steps() -> tuple[ScenarioStep, ...]:
    return (
        ScenarioStep(order=1, actor="User", action="enters credentials", system_response="validates"),
        ScenarioStep(order=2, actor="System", action="authenticates", system_response="redirects to dashboard"),
        ScenarioStep(order=3, actor="System", action="creates session", system_response="session token issued"),
    )


# ---------------------------------------------------------------------------
# add_scenario
# ---------------------------------------------------------------------------

class TestAddScenario:
    def test_add_main_scenario(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = _main_steps()
        scenario = catalog.add_scenario(
            use_case_id=uc.id,
            title="Happy path login",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        assert scenario.id.startswith("sf-")
        assert scenario.use_case_id == uc.id
        assert scenario.title == "Happy path login"
        assert scenario.scenario_type == ScenarioType.MAIN
        assert len(scenario.steps) == 3
        assert scenario.preconditions == ()
        assert scenario.postconditions == ()
        assert scenario.trigger == ""
        assert scenario.branch_from_step is None
        assert scenario.version == 1
        assert scenario.created_at.endswith("Z")
        assert len(catalog.scenarios) == 1

    def test_add_scenario_with_string_type(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = _main_steps()
        scenario = catalog.add_scenario(
            use_case_id=uc.id,
            title="Main flow",
            scenario_type="main",
            steps=steps,
        )
        assert scenario.scenario_type == ScenarioType.MAIN

    def test_add_scenario_with_all_optional_fields(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = _main_steps()
        scenario = catalog.add_scenario(
            use_case_id=uc.id,
            title="Full scenario",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
            preconditions=("User has account",),
            postconditions=("User is authenticated",),
            trigger="User clicks login button",
        )
        assert scenario.preconditions == ("User has account",)
        assert scenario.postconditions == ("User is authenticated",)
        assert scenario.trigger == "User clicks login button"

    def test_add_alternative_scenario(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        # First add main
        catalog.add_scenario(
            use_case_id=uc.id,
            title="Happy path",
            scenario_type=ScenarioType.MAIN,
            steps=_main_steps(),
        )
        # Then add alternative
        alt_steps = (
            ScenarioStep(order=1, actor="User", action="enters wrong password", system_response="shows error"),
        )
        alt = catalog.add_scenario(
            use_case_id=uc.id,
            title="Wrong password",
            scenario_type=ScenarioType.ALTERNATIVE,
            steps=alt_steps,
            branch_from_step=1,
        )
        assert alt.scenario_type == ScenarioType.ALTERNATIVE
        assert alt.branch_from_step == 1

    def test_add_exception_scenario(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        catalog.add_scenario(
            use_case_id=uc.id,
            title="Happy path",
            scenario_type=ScenarioType.MAIN,
            steps=_main_steps(),
        )
        exc_steps = (
            ScenarioStep(order=1, actor="System", action="detects timeout", system_response="shows error"),
        )
        exc = catalog.add_scenario(
            use_case_id=uc.id,
            title="Timeout",
            scenario_type=ScenarioType.EXCEPTION,
            steps=exc_steps,
            branch_from_step=2,
        )
        assert exc.scenario_type == ScenarioType.EXCEPTION
        assert exc.branch_from_step == 2

    def test_updates_catalog_timestamp(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        old_ts = catalog.updated_at
        catalog.add_scenario(
            use_case_id=uc.id,
            title="Main",
            scenario_type=ScenarioType.MAIN,
            steps=_main_steps(),
        )
        assert catalog.updated_at >= old_ts


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class TestScenarioValidation:
    def test_unknown_use_case_raises(self, catalog: NeedCatalog):
        steps = (ScenarioStep(order=1, actor="User", action="a", system_response="b"),)
        with pytest.raises(ValueError, match="not found"):
            catalog.add_scenario(
                use_case_id="uc-nonexistent",
                title="Bad",
                scenario_type=ScenarioType.MAIN,
                steps=steps,
            )

    def test_empty_steps_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        with pytest.raises(ValueError, match="at least one step"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Empty",
                scenario_type=ScenarioType.MAIN,
                steps=(),
            )

    def test_second_main_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = _main_steps()
        catalog.add_scenario(
            use_case_id=uc.id,
            title="First main",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        with pytest.raises(ValueError, match="already has a MAIN"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Second main",
                scenario_type=ScenarioType.MAIN,
                steps=steps,
            )

    def test_non_sequential_orders_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (
            ScenarioStep(order=1, actor="User", action="a", system_response="b"),
            ScenarioStep(order=3, actor="User", action="c", system_response="d"),
        )
        with pytest.raises(ValueError, match="sequential"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Bad order",
                scenario_type=ScenarioType.MAIN,
                steps=steps,
            )

    def test_duplicate_orders_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (
            ScenarioStep(order=1, actor="User", action="a", system_response="b"),
            ScenarioStep(order=1, actor="User", action="c", system_response="d"),
        )
        with pytest.raises(ValueError, match="sequential"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Dup order",
                scenario_type=ScenarioType.MAIN,
                steps=steps,
            )

    def test_zero_order_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (
            ScenarioStep(order=0, actor="User", action="a", system_response="b"),
        )
        with pytest.raises(ValueError, match="sequential"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Zero order",
                scenario_type=ScenarioType.MAIN,
                steps=steps,
            )

    def test_alternative_without_main_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (ScenarioStep(order=1, actor="User", action="a", system_response="b"),)
        with pytest.raises(ValueError, match="without a MAIN"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Alt without main",
                scenario_type=ScenarioType.ALTERNATIVE,
                steps=steps,
            )

    def test_exception_without_main_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (ScenarioStep(order=1, actor="User", action="a", system_response="b"),)
        with pytest.raises(ValueError, match="without a MAIN"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Exc without main",
                scenario_type=ScenarioType.EXCEPTION,
                steps=steps,
            )

    def test_branch_from_invalid_step_raises(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        catalog.add_scenario(
            use_case_id=uc.id,
            title="Main",
            scenario_type=ScenarioType.MAIN,
            steps=_main_steps(),
        )
        steps = (ScenarioStep(order=1, actor="User", action="a", system_response="b"),)
        with pytest.raises(ValueError, match="branch_from_step=99"):
            catalog.add_scenario(
                use_case_id=uc.id,
                title="Bad branch",
                scenario_type=ScenarioType.ALTERNATIVE,
                steps=steps,
                branch_from_step=99,
            )

    def test_main_across_different_use_cases_ok(self, catalog: NeedCatalog):
        uc1 = catalog.add_use_case(title="UC1", actor="User", situation="s1", purpose="p1")
        uc2 = catalog.add_use_case(title="UC2", actor="User", situation="s2", purpose="p2")
        steps = (ScenarioStep(order=1, actor="User", action="a", system_response="b"),)
        s1 = catalog.add_scenario(uc1.id, "Main 1", ScenarioType.MAIN, steps)
        s2 = catalog.add_scenario(uc2.id, "Main 2", ScenarioType.MAIN, steps)
        assert s1.use_case_id != s2.use_case_id


# ---------------------------------------------------------------------------
# Query methods
# ---------------------------------------------------------------------------

class TestScenarioQueries:
    def test_get_scenario(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        scenario = catalog.add_scenario(
            use_case_id=uc.id,
            title="Main",
            scenario_type=ScenarioType.MAIN,
            steps=_main_steps(),
        )
        found = catalog.get_scenario(scenario.id)
        assert found is scenario

    def test_get_scenario_not_found(self, catalog: NeedCatalog):
        assert catalog.get_scenario("sf-nonexistent") is None

    def test_scenarios_for_use_case(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        catalog.add_scenario(uc.id, "Main", ScenarioType.MAIN, _main_steps())
        catalog.add_scenario(
            uc.id, "Alt",
            ScenarioType.ALTERNATIVE,
            (ScenarioStep(order=1, actor="User", action="a", system_response="b"),),
            branch_from_step=1,
        )

        results = catalog.scenarios_for_use_case(uc.id)
        assert len(results) == 2

    def test_scenarios_for_use_case_empty(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        results = catalog.scenarios_for_use_case(uc.id)
        assert results == []

    def test_main_scenario_for(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        main = catalog.add_scenario(uc.id, "Main", ScenarioType.MAIN, _main_steps())
        found = catalog.main_scenario_for(uc.id)
        assert found is main

    def test_main_scenario_for_none(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        assert catalog.main_scenario_for(uc.id) is None


# ---------------------------------------------------------------------------
# add_use_case extension (pre/postconditions)
# ---------------------------------------------------------------------------

class TestAddUseCaseExtension:
    def test_backward_compatible(self, catalog: NeedCatalog):
        uc = catalog.add_use_case(
            title="Test",
            actor="User",
            situation="testing",
            purpose="verify",
        )
        assert uc.preconditions == ()
        assert uc.postconditions == ()

    def test_with_preconditions_postconditions(self, catalog: NeedCatalog):
        uc = catalog.add_use_case(
            title="Login",
            actor="User",
            situation="unauthenticated",
            purpose="access system",
            preconditions=("User has account",),
            postconditions=("User is logged in",),
        )
        assert uc.preconditions == ("User has account",)
        assert uc.postconditions == ("User is logged in",)

    def test_none_defaults_to_empty_tuple(self, catalog: NeedCatalog):
        uc = catalog.add_use_case(
            title="Test",
            actor="User",
            situation="s",
            purpose="p",
            preconditions=None,
            postconditions=None,
        )
        assert uc.preconditions == ()
        assert uc.postconditions == ()



# ---------------------------------------------------------------------------
# JSON Serialization
# ---------------------------------------------------------------------------

class TestScenarioSerialization:
    def test_roundtrip_scenario(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = _main_steps()
        scenario = catalog.add_scenario(
            use_case_id=uc.id,
            title="Main login",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
            preconditions=("User has account",),
            postconditions=("User is authenticated",),
            trigger="User clicks login",
        )
        # Add an alternative too
        alt_steps = (
            ScenarioStep(order=1, actor="User", action="wrong password", system_response="error"),
        )
        catalog.add_scenario(
            use_case_id=uc.id,
            title="Wrong password",
            scenario_type=ScenarioType.ALTERNATIVE,
            steps=alt_steps,
            branch_from_step=1,
        )

        json_str = catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert len(restored.scenarios) == 2

        main = restored.scenarios[0]
        assert main.title == "Main login"
        assert main.scenario_type == ScenarioType.MAIN
        assert len(main.steps) == 3
        assert main.steps[0].order == 1
        assert main.steps[0].actor == "User"
        assert main.steps[0].action == "enters credentials"
        assert main.preconditions == ("User has account",)
        assert main.postconditions == ("User is authenticated",)
        assert main.trigger == "User clicks login"

        alt = restored.scenarios[1]
        assert alt.scenario_type == ScenarioType.ALTERNATIVE
        assert alt.branch_from_step == 1

    def test_roundtrip_use_case_pre_postconditions(self, catalog: NeedCatalog):
        catalog.add_use_case(
            title="Login",
            actor="User",
            situation="unauthenticated",
            purpose="access system",
            preconditions=("Account exists",),
            postconditions=("Session created",),
        )

        json_str = catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        uc = restored.use_cases[0]
        assert uc.preconditions == ("Account exists",)
        assert uc.postconditions == ("Session created",)

    def test_backward_compat_missing_scenarios(self):
        """Old JSON without scenarios key deserializes cleanly."""
        data = {
            "id": "catalog-test",
            "name": "Old Catalog",
            "description": "",
            "created_at": "",
            "updated_at": "",
            "use_cases": [],
            "stakeholders": [],
            "needs": [],
            "relations": [],
            "process_units": [],
        }
        catalog = NeedCatalog.from_json(json.dumps(data))
        assert catalog.scenarios == []

    def test_backward_compat_missing_use_case_conditions(self):
        """Old JSON without UseCase pre/postconditions deserializes cleanly."""
        data = {
            "id": "catalog-test",
            "name": "Old Catalog",
            "description": "",
            "created_at": "",
            "updated_at": "",
            "use_cases": [
                {
                    "id": "uc-old",
                    "title": "Old UC",
                    "actor": "User",
                    "situation": "s",
                    "purpose": "p",
                    "outcome": "",
                    "tags": [],
                    "version": 1,
                    "created_at": "",
                    "updated_at": "",
                }
            ],
            "stakeholders": [],
            "needs": [],
            "relations": [],
            "process_units": [],
        }
        catalog = NeedCatalog.from_json(json.dumps(data))
        assert catalog.use_cases[0].preconditions == ()
        assert catalog.use_cases[0].postconditions == ()

    def test_scenario_with_kernel_ref_roundtrip(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (
            ScenarioStep(
                order=1, actor="User", action="login", system_response="ok",
                kernel_ref="entity:auth-service",
            ),
            ScenarioStep(
                order=2, actor="System", action="notify", system_response="ok",
            ),
        )
        catalog.add_scenario(uc.id, "With refs", ScenarioType.MAIN, steps)

        json_str = catalog.to_json()
        restored = NeedCatalog.from_json(json_str)

        assert restored.scenarios[0].steps[0].kernel_ref == "entity:auth-service"
        assert restored.scenarios[0].steps[1].kernel_ref is None

    def test_json_includes_scenarios(self, catalog_with_use_case):
        catalog, uc = catalog_with_use_case
        steps = (ScenarioStep(order=1, actor="A", action="b", system_response="c"),)
        catalog.add_scenario(uc.id, "Test", ScenarioType.MAIN, steps)

        data = json.loads(catalog.to_json())
        assert "scenarios" in data
        assert len(data["scenarios"]) == 1
        assert "steps" in data["scenarios"][0]

    def test_json_includes_use_case_conditions(self, catalog: NeedCatalog):
        catalog.add_use_case(
            title="Test",
            actor="User",
            situation="s",
            purpose="p",
            preconditions=("pre",),
            postconditions=("post",),
        )
        data = json.loads(catalog.to_json())
        assert data["use_cases"][0]["preconditions"] == ["pre"]
        assert data["use_cases"][0]["postconditions"] == ["post"]
