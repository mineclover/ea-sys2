"""Tests for ea_flow.types module."""

from ea_flow.types import FlowStepCategory, I18nString


class TestFlowStepCategory:
    """Test FlowStepCategory enum."""

    def test_action_value(self):
        assert FlowStepCategory.ACTION.value == "action"

    def test_decision_value(self):
        assert FlowStepCategory.DECISION.value == "decision"

    def test_event_value(self):
        assert FlowStepCategory.EVENT.value == "event"

    def test_gateway_value(self):
        assert FlowStepCategory.GATEWAY.value == "gateway"

    def test_transformation_value(self):
        assert FlowStepCategory.TRANSFORMATION.value == "transform"

    def test_enum_count(self):
        assert len(FlowStepCategory) == 5


class TestI18nString:
    """Test I18nString type alias."""

    def test_str_is_valid(self):
        s: I18nString = "plain string"
        assert isinstance(s, str)

    def test_dict_is_valid(self):
        s: I18nString = {"en": "English", "ko": "한국어"}
        assert isinstance(s, dict)
        assert s["en"] == "English"
