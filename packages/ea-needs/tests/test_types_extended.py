"""Extended tests for new needs vocabulary types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from ea_needs.types import (
    NeedCauseType,
    NeedProcessStage,
    NeedProcessUnit,
    NeedResolutionComplexity,
    UseCase,
)


class TestNeedCauseType:
    def test_values(self):
        assert NeedCauseType.EMOTIONAL.value == "emotional"
        assert NeedCauseType.SITUATIONAL.value == "situational"
        assert NeedCauseType.PHYSICAL.value == "physical"
        assert NeedCauseType.LOGICAL.value == "logical"
        assert NeedCauseType.MENTAL.value == "mental"
        assert NeedCauseType.PHILOSOPHICAL.value == "philosophical"


class TestNeedResolutionComplexity:
    def test_values(self):
        assert NeedResolutionComplexity.SIMPLE.value == "simple"
        assert NeedResolutionComplexity.PROCEDURAL.value == "procedural"
        assert NeedResolutionComplexity.COMPLEX.value == "complex"


class TestNeedProcessStage:
    def test_values(self):
        assert NeedProcessStage.IDENTIFY.value == "identify"
        assert NeedProcessStage.QUERY.value == "query"
        assert NeedProcessStage.MODEL_DETAIL.value == "model_detail"


class TestUseCase:
    def test_creation(self):
        use_case = UseCase(
            id="uc-001",
            title="Improve onboarding",
            actor="Team lead",
            situation="new engineers ramp slowly",
            purpose="reduce onboarding time",
            tags=["people"],
        )

        assert use_case.id == "uc-001"
        assert use_case.version == 1
        assert use_case.tags == ["people"]

    def test_frozen(self):
        use_case = UseCase(
            id="uc-001",
            title="x",
            actor="y",
            situation="z",
            purpose="p",
        )
        with pytest.raises(FrozenInstanceError):
            use_case.title = "changed"


class TestNeedProcessUnit:
    def test_creation(self):
        unit = NeedProcessUnit(
            id="pu-001",
            need_id="need-001",
            stage=NeedProcessStage.QUERY,
            label="Collect domain constraints",
            sequence=2,
            metadata={"source": "incident-log"},
        )

        assert unit.stage == NeedProcessStage.QUERY
        assert unit.sequence == 2
        assert unit.metadata["source"] == "incident-log"

    def test_frozen(self):
        unit = NeedProcessUnit(
            id="pu-001",
            need_id="need-001",
            stage=NeedProcessStage.IDENTIFY,
            label="Identify actors",
        )
        with pytest.raises(FrozenInstanceError):
            unit.label = "changed"
