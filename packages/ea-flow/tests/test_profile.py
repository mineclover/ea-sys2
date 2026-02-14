from ea_flow.profile import FlowProfile
from ea_flow.spec import FlowMetaStep


def test_get_meta_step_with_plain_string_name() -> None:
    step = FlowMetaStep(name="ValidateInput", description="validates input")
    profile = FlowProfile(name="default", version="1.0.0", meta_steps=(step,))

    found = profile.get_meta_step("ValidateInput")
    assert found is step


def test_get_meta_step_with_i18n_name_uses_english_label() -> None:
    step = FlowMetaStep(name={"en": "Normalize", "ko": "정규화"}, description="normalize")
    profile = FlowProfile(name="default", version="1.0.0", meta_steps=(step,))

    found = profile.get_meta_step("Normalize")
    assert found is step


def test_get_meta_step_returns_none_for_missing_name() -> None:
    step = FlowMetaStep(name="Known", description="known")
    profile = FlowProfile(name="default", version="1.0.0", meta_steps=(step,))

    assert profile.get_meta_step("Unknown") is None
