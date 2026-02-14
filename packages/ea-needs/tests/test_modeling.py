"""Tests for advanced needs modeling: use-cases, versioning, process units, evidence inheritance."""

from __future__ import annotations

import pytest
from ea_needs.catalog import NeedCatalog
from ea_needs.types import (
    NeedCauseType,
    NeedPriority,
    NeedProcessStage,
    NeedResolutionComplexity,
)


@pytest.fixture
def catalog() -> NeedCatalog:
    model = NeedCatalog(name="Needs Modeling")
    model.add_stakeholder("Platform Owner", "owner", "service modernization")
    return model


def _first_stakeholder_id(catalog: NeedCatalog) -> str:
    return catalog.stakeholders[0].id


class TestUseCaseBoundNeedModeling:
    def test_express_need_with_use_case_and_cause_model(self, catalog: NeedCatalog):
        use_case = catalog.add_use_case(
            title="Improve deployment confidence",
            actor="SRE",
            situation="frequent rollback incidents",
            purpose="reduce rollback rate",
            tags=["ops", "risk"],
        )

        need = catalog.express_need(
            stakeholder_id=_first_stakeholder_id(catalog),
            action="stabilize",
            subject="deployments",
            use_case_id=use_case.id,
            cause_types=[NeedCauseType.EMOTIONAL, "logical"],
            purpose="prevent weekend incidents",
            complexity=NeedResolutionComplexity.COMPLEX,
            priority=NeedPriority.CRITICAL,
        )

        assert need.use_case_id == use_case.id
        assert need.statement.use_case_id == use_case.id
        assert need.statement.cause_types == [NeedCauseType.EMOTIONAL, NeedCauseType.LOGICAL]
        assert need.statement.purpose == "prevent weekend incidents"
        assert need.statement.complexity == NeedResolutionComplexity.COMPLEX

    def test_needs_by_use_case(self, catalog: NeedCatalog):
        use_case = catalog.add_use_case(
            title="Faster incident triage",
            actor="On-call engineer",
            situation="slow root-cause lookup",
            purpose="reduce MTTR",
        )

        n1 = catalog.express_need(_first_stakeholder_id(catalog), "improve", "triage", use_case_id=use_case.id)
        catalog.express_need(_first_stakeholder_id(catalog), "add", "dashboards")

        mapped = catalog.needs_by_use_case(use_case.id)
        assert len(mapped) == 1
        assert mapped[0].id == n1.id


class TestNeedVersioningAndIdentification:
    def test_revise_need_assigns_new_id_and_version(self, catalog: NeedCatalog):
        need = catalog.express_need(
            stakeholder_id=_first_stakeholder_id(catalog),
            action="reduce",
            subject="deployment lead time",
            cause_types=["situational"],
        )
        catalog.add_process_unit(need.id, NeedProcessStage.IDENTIFY, "Define lead-time baseline")
        catalog.add_process_unit(need.id, NeedProcessStage.QUERY, "Collect release metrics")

        revised = catalog.revise_need(
            need.id,
            action="stabilize",
            subject="release cadence",
            clone_process_units=True,
        )

        assert revised.id != need.id
        assert revised.lineage_id == need.lineage_id
        assert revised.version == 2
        assert revised.statement.desire.action == "stabilize"
        assert revised.statement.desire.subject == "release cadence"

        cloned_units = catalog.process_units_for_need(revised.id)
        assert len(cloned_units) == 2

    def test_identify_need_by_lineage(self, catalog: NeedCatalog):
        base = catalog.express_need(_first_stakeholder_id(catalog), "reduce", "error rate")
        revised = catalog.revise_need(base.id, subject="production error rate")

        latest = catalog.identify_need(base.lineage_id)
        v1 = catalog.identify_need(base.lineage_id, version=1)
        v2 = catalog.identify_need(base.lineage_id, version=2)

        assert latest is not None
        assert latest.id == revised.id
        assert v1 is not None and v1.id == base.id
        assert v2 is not None and v2.id == revised.id


class TestProcessUnitModeling:
    def test_process_units_grouped_by_stage(self, catalog: NeedCatalog):
        need = catalog.express_need(_first_stakeholder_id(catalog), "improve", "service reliability")
        catalog.add_process_unit(need.id, "identify", "Identify reliability hotspots")
        catalog.add_process_unit(need.id, "query", "Query incident and latency history")
        catalog.add_process_unit(need.id, "model_detail", "Model failure and remediation sub-items")

        detail = catalog.modeled_need_detail(need.id)

        assert detail is not None
        assert len(detail["process_units"][NeedProcessStage.IDENTIFY.value]) == 1
        assert len(detail["process_units"][NeedProcessStage.QUERY.value]) == 1
        assert len(detail["process_units"][NeedProcessStage.MODEL_DETAIL.value]) == 1


class TestDecisionEvidenceInheritance:
    def test_inherit_decision_evidence_deduplicates_refs(self, catalog: NeedCatalog):
        need = catalog.express_need(_first_stakeholder_id(catalog), "improve", "resilience")

        catalog.inherit_decision_evidence(need.id, "topic-001", ["ev://a", "ev://a"])
        catalog.inherit_decision_evidence(need.id, "topic-002", ["ev://b"])

        assert need.decision_evidence_refs == ["ev://a", "ev://b"]
        assert need.inherited_from_decisions == ["topic-001", "topic-002"]
