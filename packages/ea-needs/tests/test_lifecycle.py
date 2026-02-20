import pytest
from ea_needs.lifecycle import allowed_profile_targets, ensure_profile_transition
from ea_needs.types import NeedStatus


def test_allowed_profile_targets_for_expressed() -> None:
    assert allowed_profile_targets(NeedStatus.EXPRESSED) == ("ACKNOWLEDGED", "WITHDRAWN")


def test_ensure_profile_transition_allows_valid_path() -> None:
    ensure_profile_transition(NeedStatus.DRAFT, NeedStatus.EXPRESSED)


def test_ensure_profile_transition_rejects_invalid_path() -> None:
    with pytest.raises(ValueError, match="Invalid transition"):
        ensure_profile_transition(NeedStatus.ADDRESSED, NeedStatus.DRAFT)
