"""Tests for ea_needs.types — frozen vocabulary types."""

from dataclasses import FrozenInstanceError

import pytest
from ea_needs.types import (
    Desire,
    Justification,
    JustificationType,
    NeedKernelChangePhase,
    NeedPriority,
    NeedPurpose,
    NeedRelationType,
    NeedStatement,
    NeedStatus,
    ScenarioFlow,
    ScenarioStep,
    ScenarioType,
    Stakeholder,
    UseCase,
    _generate_id,
    _now,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_generate_id_has_prefix(self):
        result = _generate_id("need")
        assert result.startswith("need-")
        assert len(result) == len("need-") + 8

    def test_generate_id_unique(self):
        ids = {_generate_id("x") for _ in range(100)}
        assert len(ids) == 100

    def test_now_iso_format(self):
        ts = _now()
        assert ts.endswith("Z")
        assert "T" in ts


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_justification_type_values(self):
        assert JustificationType.BECAUSE.value == "because"
        assert JustificationType.IN_ORDER_TO.value == "in_order_to"

    def test_need_priority_values(self):
        assert NeedPriority.CRITICAL.value == "critical"
        assert NeedPriority.HIGH.value == "high"
        assert NeedPriority.MEDIUM.value == "medium"
        assert NeedPriority.LOW.value == "low"

    def test_need_purpose_values(self):
        assert NeedPurpose.SAFETY.value == "safety"
        assert NeedPurpose.EFFICIENCY.value == "efficiency"
        assert NeedPurpose.USABILITY.value == "usability"
        assert NeedPurpose.COMPLIANCE.value == "compliance"
        assert NeedPurpose.GROWTH.value == "growth"
        assert NeedPurpose.TRUST.value == "trust"
        assert NeedPurpose.UNSPECIFIED.value == "unspecified"

    def test_need_status_values(self):
        assert NeedStatus.DRAFT.value == "draft"
        assert NeedStatus.EXPRESSED.value == "expressed"
        assert NeedStatus.ACKNOWLEDGED.value == "acknowledged"
        assert NeedStatus.ADDRESSED.value == "addressed"
        assert NeedStatus.WITHDRAWN.value == "withdrawn"

    def test_need_kernel_change_phase_values(self):
        assert NeedKernelChangePhase.PLANNED.value == "planned"
        assert NeedKernelChangePhase.APPLIED.value == "applied"
        assert NeedKernelChangePhase.SUPERSEDED.value == "superseded"
        assert NeedKernelChangePhase.ROLLED_BACK.value == "rolled_back"

    def test_need_relation_type_values(self):
        assert NeedRelationType.DEPENDS_ON.value == "depends_on"
        assert NeedRelationType.CONFLICTS_WITH.value == "conflicts_with"
        assert NeedRelationType.SUPPORTS.value == "supports"
        assert NeedRelationType.REFINES.value == "refines"
        assert NeedRelationType.SUPERSEDES.value == "supersedes"

    def test_enums_are_str(self):
        """All enums inherit from str for JSON serialization."""
        assert isinstance(NeedStatus.DRAFT, str)
        assert isinstance(NeedKernelChangePhase.PLANNED, str)
        assert isinstance(NeedPriority.HIGH, str)
        assert isinstance(NeedPurpose.SAFETY, str)
        assert isinstance(JustificationType.BECAUSE, str)
        assert isinstance(NeedRelationType.SUPPORTS, str)


# ---------------------------------------------------------------------------
# Frozen value objects
# ---------------------------------------------------------------------------

class TestStakeholder:
    def test_creation(self):
        s = Stakeholder(id="sh-001", name="CTO", role="executive", context="cloud migration")
        assert s.name == "CTO"
        assert s.role == "executive"
        assert s.context == "cloud migration"

    def test_frozen(self):
        s = Stakeholder(id="sh-001", name="CTO", role="executive")
        with pytest.raises(FrozenInstanceError):
            s.name = "CFO"

    def test_default_context(self):
        s = Stakeholder(id="sh-001", name="Dev", role="engineer")
        assert s.context == ""


class TestDesire:
    def test_creation_with_target(self):
        d = Desire(action="migrate", subject="payment system", target="cloud")
        assert d.action == "migrate"
        assert d.subject == "payment system"
        assert d.target == "cloud"

    def test_creation_without_target(self):
        d = Desire(action="reduce", subject="deployment time")
        assert d.target is None

    def test_frozen(self):
        d = Desire(action="migrate", subject="db")
        with pytest.raises(FrozenInstanceError):
            d.action = "delete"


class TestJustification:
    def test_because(self):
        j = Justification(type=JustificationType.BECAUSE, description="system has outages")
        assert j.type == JustificationType.BECAUSE
        assert j.description == "system has outages"

    def test_in_order_to(self):
        j = Justification(type=JustificationType.IN_ORDER_TO, description="achieve high availability")
        assert j.type == JustificationType.IN_ORDER_TO

    def test_frozen(self):
        j = Justification(type=JustificationType.BECAUSE, description="x")
        with pytest.raises(FrozenInstanceError):
            j.description = "y"


class TestNeedStatement:
    def test_creation(self):
        ns = NeedStatement(
            stakeholder_id="sh-001",
            desire=Desire(action="migrate", subject="db", target="cloud"),
            justifications=[
                Justification(type=JustificationType.BECAUSE, description="outages"),
            ],
            kernel_refs=["entity:payment-service"],
            tags=["infrastructure", "cloud"],
        )
        assert ns.stakeholder_id == "sh-001"
        assert ns.desire.action == "migrate"
        assert len(ns.justifications) == 1
        assert len(ns.kernel_refs) == 1
        assert "cloud" in ns.tags
        assert ns.expressed_at.endswith("Z")

    def test_frozen(self):
        ns = NeedStatement(
            stakeholder_id="sh-001",
            desire=Desire(action="reduce", subject="cost"),
        )
        with pytest.raises(FrozenInstanceError):
            ns.stakeholder_id = "sh-002"

    def test_defaults(self):
        ns = NeedStatement(
            stakeholder_id="sh-001",
            desire=Desire(action="reduce", subject="cost"),
        )
        assert ns.justifications == []
        assert ns.kernel_refs == []
        assert ns.tags == []
        assert ns.purpose == NeedPurpose.UNSPECIFIED


# ---------------------------------------------------------------------------
# ScenarioType enum
# ---------------------------------------------------------------------------

class TestScenarioType:
    def test_values(self):
        assert ScenarioType.MAIN.value == "main"
        assert ScenarioType.ALTERNATIVE.value == "alternative"
        assert ScenarioType.EXCEPTION.value == "exception"

    def test_is_str(self):
        assert isinstance(ScenarioType.MAIN, str)


# ---------------------------------------------------------------------------
# ScenarioStep frozen dataclass
# ---------------------------------------------------------------------------

class TestScenarioStep:
    def test_creation(self):
        step = ScenarioStep(
            order=1,
            actor="User",
            action="submits login form",
            system_response="validates credentials",
        )
        assert step.order == 1
        assert step.actor == "User"
        assert step.action == "submits login form"
        assert step.system_response == "validates credentials"
        assert step.kernel_ref is None

    def test_creation_with_kernel_ref(self):
        step = ScenarioStep(
            order=2,
            actor="System",
            action="sends notification",
            system_response="email delivered",
            kernel_ref="entity:notification-service",
        )
        assert step.kernel_ref == "entity:notification-service"

    def test_frozen(self):
        step = ScenarioStep(order=1, actor="User", action="click", system_response="ok")
        with pytest.raises(FrozenInstanceError):
            step.order = 2


# ---------------------------------------------------------------------------
# ScenarioFlow frozen dataclass
# ---------------------------------------------------------------------------

class TestScenarioFlow:
    def test_creation(self):
        steps = (
            ScenarioStep(order=1, actor="User", action="login", system_response="show dashboard"),
            ScenarioStep(order=2, actor="User", action="click report", system_response="show report"),
        )
        flow = ScenarioFlow(
            id="sf-abc12345",
            use_case_id="uc-xyz",
            title="Happy path login",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        assert flow.id == "sf-abc12345"
        assert flow.use_case_id == "uc-xyz"
        assert flow.title == "Happy path login"
        assert flow.scenario_type == ScenarioType.MAIN
        assert len(flow.steps) == 2
        assert flow.preconditions == ()
        assert flow.postconditions == ()
        assert flow.trigger == ""
        assert flow.branch_from_step is None
        assert flow.version == 1
        assert flow.created_at.endswith("Z")

    def test_creation_with_all_fields(self):
        steps = (
            ScenarioStep(order=1, actor="User", action="login", system_response="show dashboard"),
        )
        flow = ScenarioFlow(
            id="sf-abc12345",
            use_case_id="uc-xyz",
            title="Alternative login",
            scenario_type=ScenarioType.ALTERNATIVE,
            steps=steps,
            preconditions=("User has account",),
            postconditions=("User is logged in",),
            trigger="User clicks login",
            branch_from_step=1,
            version=2,
        )
        assert flow.preconditions == ("User has account",)
        assert flow.postconditions == ("User is logged in",)
        assert flow.trigger == "User clicks login"
        assert flow.branch_from_step == 1
        assert flow.version == 2

    def test_frozen(self):
        steps = (ScenarioStep(order=1, actor="User", action="a", system_response="b"),)
        flow = ScenarioFlow(
            id="sf-test",
            use_case_id="uc-test",
            title="Test",
            scenario_type=ScenarioType.MAIN,
            steps=steps,
        )
        with pytest.raises(FrozenInstanceError):
            flow.title = "Changed"


# ---------------------------------------------------------------------------
# UseCase pre/postconditions extension
# ---------------------------------------------------------------------------

class TestUseCaseExtended:
    def test_backward_compatible_creation(self):
        """UseCase without pre/postconditions still works."""
        uc = UseCase(
            id="uc-test",
            title="Test",
            actor="User",
            situation="testing",
            purpose="verify",
        )
        assert uc.preconditions == ()
        assert uc.postconditions == ()

    def test_with_preconditions_postconditions(self):
        uc = UseCase(
            id="uc-test",
            title="Login",
            actor="User",
            situation="unauthenticated",
            purpose="access system",
            preconditions=("User has valid account",),
            postconditions=("User is authenticated", "Session created"),
        )
        assert uc.preconditions == ("User has valid account",)
        assert uc.postconditions == ("User is authenticated", "Session created")

    def test_frozen_preconditions(self):
        uc = UseCase(
            id="uc-test",
            title="Test",
            actor="User",
            situation="testing",
            purpose="verify",
            preconditions=("pre",),
        )
        with pytest.raises(FrozenInstanceError):
            uc.preconditions = ()
