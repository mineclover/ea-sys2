from __future__ import annotations

from pathlib import Path

from ea_governance.catalog_policy_store import CatalogAutoExpressPolicy
from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_governance.layer_store import SQLiteGovernanceLayerStore
from ea_governance.needs_store import GovernanceNeedsStore
from ea_needs.catalog import NeedCatalog
from ea_needs.types import NeedPriority, NeedPurpose
from ea_ops.events import FeedbackLayer, ServiceOpsEventSpec, ServiceOpsSeverity


def _build_catalog() -> NeedCatalog:
    catalog = NeedCatalog(name="Needs DB")
    stakeholder = catalog.add_stakeholder("Ops Lead", "operator")
    use_case = catalog.add_use_case(
        title="Improve incident recovery",
        actor="On-call",
        situation="recurring service outages",
        purpose="reduce MTTR",
    )
    catalog.express_need(
        stakeholder_id=stakeholder.id,
        action="stabilize",
        subject="incident recovery",
        use_case_id=use_case.id,
        cause_types=["situational", "logical"],
    )
    return catalog


def test_governance_needs_store_save_get_list(tmp_path: Path):
    layer_store = SQLiteGovernanceLayerStore(tmp_path / "layers" / "needs.db", layer="needs")
    store = GovernanceNeedsStore(layer_store)

    catalog = _build_catalog()
    catalog_id = store.save_catalog(catalog)

    loaded = store.get_catalog(catalog_id)
    assert loaded is not None
    assert loaded.id == catalog.id
    assert len(loaded.use_cases) == 1
    assert len(loaded.needs) == 1

    listed = store.list_catalogs()
    assert len(listed) == 1
    assert listed[0].id == catalog.id


def test_governance_container_manages_needs_db(tmp_path: Path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)

    catalog = _build_catalog()
    result = container.save_needs_catalog(catalog, actor="tester", return_transaction=True)
    assert isinstance(result, dict)
    catalog_id = result["catalog_id"]
    tx_id = result["transaction_id"]

    loaded = container.get_needs_catalog(catalog_id)
    assert loaded is not None
    assert loaded.name == "Needs DB"

    all_catalogs = container.list_needs_catalogs()
    assert len(all_catalogs) == 1
    assert all_catalogs[0].id == catalog.id

    tx_status = container.get_transaction_status(tx_id)
    assert tx_status is not None
    assert str(tx_status["status"]) == "committed"

    tx_events = container.get_transaction_events(tx_id)
    event_types = [event["event_type"] for event in tx_events]
    assert "begin" in event_types
    assert "needs_catalog_saved" in event_types
    assert "commit" in event_types

    history = container.get_needs_catalog_history(catalog_id)
    history_types = [event["event_type"] for event in history]
    assert "needs_catalog_saved" in history_types


def test_governance_container_needs_modeling_workflow(tmp_path: Path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)

    created = container.create_needs_catalog(
        "Ops Needs",
        "Incident recovery and reliability needs",
        actor="architect",
    )
    catalog_id = created["catalog_id"]

    stakeholder_result = container.add_needs_stakeholder(
        catalog_id,
        name="Ops Lead",
        role="operator",
        context="incident response",
        actor="architect",
    )
    stakeholder_id = stakeholder_result["stakeholder_id"]

    use_case_result = container.add_needs_use_case(
        catalog_id,
        title="Recover incidents faster",
        actor_name="On-call",
        situation="repeat outage patterns",
        purpose="reduce MTTR",
        actor="architect",
    )
    use_case_id = use_case_result["use_case_id"]

    need_result = container.express_need_in_catalog(
        catalog_id,
        stakeholder_id=stakeholder_id,
        action="stabilize",
        subject="incident recovery workflow",
        use_case_id=use_case_id,
        cause_types=["situational", "logical"],
        purpose=NeedPurpose.EFFICIENCY,
        priority=NeedPriority.HIGH,
        kernel_change_phase="planned",
        actor="architect",
    )
    need_id = need_result["need_id"]
    lineage_id = need_result["lineage_id"]

    process_result = container.add_need_process_unit(
        catalog_id,
        need_id,
        stage="identify",
        label="Identify recurring outage pattern",
        actor="architect",
    )
    assert process_result["process_unit_id"].startswith("pu-")

    revised = container.revise_need_in_catalog(
        catalog_id,
        need_id,
        changes={"subject": "incident response and recovery workflow"},
        actor="architect",
    )
    revised_need_id = revised["need_id"]
    assert revised["version"] == 2

    inherit_result = container.inherit_need_decision_evidence(
        catalog_id,
        revised_need_id,
        decision_id="topic-123",
        evidence_refs=["ev://runbook", "ev://postmortem"],
        kernel_change_phase="applied",
        actor="architect",
    )
    assert inherit_result["need_id"] == revised_need_id

    loaded = container.get_needs_catalog(catalog_id)
    assert loaded is not None
    latest = loaded.latest_need_version(lineage_id)
    assert latest is not None
    assert latest.id == revised_need_id
    assert latest.version == 2
    assert latest.decision_evidence_refs == ["ev://runbook", "ev://postmortem"]
    assert latest.kernel_change_phase.value == "applied"

    history = container.get_needs_catalog_history(catalog_id)
    history_types = [event["event_type"] for event in history]
    expected = {
        "needs_catalog_created",
        "needs_stakeholder_added",
        "needs_use_case_added",
        "needs_expressed",
        "needs_process_unit_added",
        "needs_revised",
        "needs_decision_evidence_inherited",
        "needs_catalog_saved",
    }
    assert expected.issubset(set(history_types))


def test_governance_container_layer_scoped_store(tmp_path: Path):
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)

    save_result = container.save_layer_snapshot(
        "decision",
        "decision-schema-v1",
        {"nodes": ["context", "option", "outcome"], "version": "1.0.0"},
        actor="architect",
        return_transaction=True,
    )
    assert isinstance(save_result, dict)

    loaded = container.get_layer_snapshot("decision", "decision-schema-v1")
    assert loaded is not None
    assert loaded["version"] == "1.0.0"

    snapshots = container.list_layer_snapshots("decision")
    assert len(snapshots) == 1
    assert snapshots[0]["model_id"] == "decision-schema-v1"


# ═══════════════════════════════════════════════════════════════════════════════
# Needs→Governance Feedback Tests
# ═══════════════════════════════════════════════════════════════════════════════


def _container_with_catalog(tmp_path: Path) -> tuple:
    """Create GovernanceContainer with a needs catalog + stakeholder + need."""
    from ea_needs.types import NeedPriority

    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)

    created = container.create_needs_catalog("Test Catalog", actor="tester")
    catalog_id = created["catalog_id"]

    sh = container.add_needs_stakeholder(
        catalog_id, name="Alice", role="operator", actor="tester",
    )
    stakeholder_id = sh["stakeholder_id"]

    container.express_need_in_catalog(
        catalog_id,
        stakeholder_id=stakeholder_id,
        action="stabilize",
        subject="service recovery",
        priority=NeedPriority.HIGH,
        actor="tester",
    )

    return container, catalog_id


def test_publish_analysis_report(tmp_path: Path):
    """NeedsAnalysisReport is persisted to governance audit + layer store."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class FakeReport:
        report_id: str = "rpt-001"
        created_at: str = "2025-01-15T10:00:00Z"
        total_needs_analyzed: int = 5
        health_score: float = 72.0
        unserved_stakeholders: tuple[str, ...] = ()
        underserved_stakeholders: tuple[str, ...] = ("sh-2",)
        stale_needs_count: int = 1

    container, catalog_id = _container_with_catalog(tmp_path)
    report = FakeReport()

    result = container.publish_needs_analysis_report(
        catalog_id, report, actor="analyzer",
    )

    assert result["report_id"] == "rpt-001"
    assert "transaction_id" in result

    # Verify the report was saved to the layer store
    snapshot = container.get_layer_snapshot(
        "needs", f"needs_report_{catalog_id}_rpt-001",
    )
    assert snapshot is not None
    assert snapshot["health_score"] == 72.0
    assert snapshot["unserved_count"] == 0
    assert snapshot["underserved_count"] == 1

    # Verify transaction events
    tx_events = container.get_transaction_events(result["transaction_id"])
    event_types = [e["event_type"] for e in tx_events]
    assert "needs_analysis_published" in event_types


def test_record_needs_version(tmp_path: Path):
    """Catalog version metadata is recorded to governance."""
    container, catalog_id = _container_with_catalog(tmp_path)

    result = container.record_needs_version(
        catalog_id,
        version_label="v1.0",
        summary="Initial needs baseline",
        actor="architect",
    )

    assert result["version_label"] == "v1.0"
    assert "transaction_id" in result

    # Verify layer snapshot
    snapshot = container.get_layer_snapshot(
        "needs", f"needs_version_{catalog_id}_v1.0",
    )
    assert snapshot is not None
    assert snapshot["version_label"] == "v1.0"
    assert snapshot["needs_count"] >= 1
    assert snapshot["summary"] == "Initial needs baseline"

    # Verify transaction
    tx_events = container.get_transaction_events(result["transaction_id"])
    event_types = [e["event_type"] for e in tx_events]
    assert "needs_version_recorded" in event_types


def test_evaluate_change_policy_pass(tmp_path: Path):
    """Change policy passes for valid catalog state."""
    container, catalog_id = _container_with_catalog(tmp_path)

    result = container.evaluate_needs_change_policy(
        catalog_id,
        proposed_change="publish",
        actor="architect",
    )

    assert result["passed"] is True
    assert result["violations"] == []
    assert "transaction_id" in result

    # Verify policy evaluation was recorded
    tx_events = container.get_transaction_events(result["transaction_id"])
    event_types = [e["event_type"] for e in tx_events]
    assert "needs_policy_evaluated" in event_types


def test_evaluate_change_policy_no_stakeholders(tmp_path: Path):
    """Change policy fails when catalog has no stakeholders."""
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)

    created = container.create_needs_catalog("Empty Catalog", actor="tester")
    catalog_id = created["catalog_id"]

    result = container.evaluate_needs_change_policy(
        catalog_id,
        proposed_change="publish",
        actor="architect",
    )

    assert result["passed"] is False
    assert any("no stakeholders" in v.lower() for v in result["violations"])


def test_evaluate_change_policy_no_needs(tmp_path: Path):
    """Change policy fails for publish when catalog has no needs."""
    schema = KernelSchema(attributes=(), entities=(), relations=())
    container = GovernanceContainer(tmp_path, schema)

    created = container.create_needs_catalog("No Needs", actor="tester")
    catalog_id = created["catalog_id"]

    # Add stakeholder but no needs
    container.add_needs_stakeholder(
        catalog_id, name="Bob", role="dev", actor="tester",
    )

    result = container.evaluate_needs_change_policy(
        catalog_id,
        proposed_change="promote",
        actor="architect",
    )

    assert result["passed"] is False
    assert any("no needs" in v.lower() for v in result["violations"])


def test_ingest_service_ops_event_records_infra_and_needs_feedback(tmp_path: Path):
    container, catalog_id = _container_with_catalog(tmp_path)
    catalog = container.get_needs_catalog(catalog_id)
    assert catalog is not None
    stakeholder_id = catalog.stakeholders[0].id

    spec = ServiceOpsEventSpec(
        name="slo_breached",
        severity=ServiceOpsSeverity.HIGH,
        must_include=("trace_id", "lineage_id", "service_id", "slo_name"),
        feeds_back_to=FeedbackLayer.NEEDS,
    )
    result = container.ingest_service_ops_event(
        spec=spec,
        payload={
            "trace_id": "trace-needs-1",
            "lineage_id": "lineage-needs-1",
            "service_id": "payments-api",
            "slo_name": "latency_p95",
        },
        catalog_id=catalog_id,
        stakeholder_id=stakeholder_id,
        actor="ops-bot",
    )

    assert result["event_name"] == "slo_breached"
    assert result["infra_snapshot_id"] is not None
    assert result["feedback_snapshot_id"] is not None
    assert result["expressed_need"] is None
    assert result["needs_feedback_draft"]["priority"] == "high"

    infra_snapshot = container.get_layer_snapshot("infra", result["infra_snapshot_id"])
    assert infra_snapshot is not None
    assert infra_snapshot["kind"] == "service_ops_event"

    needs_snapshot = container.get_layer_snapshot("needs", result["feedback_snapshot_id"])
    assert needs_snapshot is not None
    assert needs_snapshot["kind"] == "service_ops_feedback"


def test_ingest_service_ops_event_auto_expresses_need(tmp_path: Path):
    container, catalog_id = _container_with_catalog(tmp_path)
    catalog = container.get_needs_catalog(catalog_id)
    assert catalog is not None
    stakeholder_id = catalog.stakeholders[0].id
    before_count = len(catalog.needs)

    policy = CatalogAutoExpressPolicy(
        catalog_id=catalog_id,
        allowed_severities=(ServiceOpsSeverity.CRITICAL,),
        allowed_event_names=("incident_opened",),
        allowed_feeds_back_to=(FeedbackLayer.NEEDS,),
        stakeholder_event_map={stakeholder_id: ("incident_opened",)},
    )
    container.save_catalog_auto_express_policy(policy, actor="architect")

    spec = ServiceOpsEventSpec(
        name="incident_opened",
        severity=ServiceOpsSeverity.CRITICAL,
        must_include=(
            "trace_id",
            "lineage_id",
            "service_id",
            "incident_id",
            "runbook_url",
        ),
        feeds_back_to=FeedbackLayer.NEEDS,
    )
    result = container.ingest_service_ops_event(
        spec=spec,
        payload={
            "trace_id": "trace-needs-2",
            "lineage_id": "lineage-needs-2",
            "service_id": "orders-api",
            "incident_id": "inc-100",
            "runbook_url": "https://runbooks/orders-api",
        },
        catalog_id=catalog_id,
        stakeholder_id=stakeholder_id,
        auto_express=True,
        actor="ops-bot",
    )

    assert result["expressed_need"] is not None
    assert result["expressed_need"]["catalog_id"] == catalog_id
    assert result["auto_express_decision"]["requested"] is True
    assert result["auto_express_decision"]["allowed"] is True
    assert result["auto_express_decision"]["reason_codes"] == []

    updated = container.get_needs_catalog(catalog_id)
    assert updated is not None
    assert len(updated.needs) == before_count + 1


def test_catalog_auto_express_policy_save_get_list(tmp_path: Path):
    container, catalog_id = _container_with_catalog(tmp_path)
    catalog = container.get_needs_catalog(catalog_id)
    assert catalog is not None
    stakeholder_id = catalog.stakeholders[0].id

    policy = CatalogAutoExpressPolicy(
        catalog_id=catalog_id,
        enabled=True,
        allowed_severities=(ServiceOpsSeverity.HIGH, ServiceOpsSeverity.CRITICAL),
        allowed_event_names=("slo_breached", "incident_opened"),
        allowed_feeds_back_to=(FeedbackLayer.NEEDS,),
        stakeholder_event_map={
            stakeholder_id: ("slo_breached", "incident_opened"),
        },
    )
    saved = container.save_catalog_auto_express_policy(policy, actor="architect")

    assert saved["catalog_id"] == catalog_id
    assert "transaction_id" in saved

    loaded = container.get_catalog_auto_express_policy(catalog_id)
    assert loaded is not None
    assert loaded.catalog_id == catalog_id
    assert loaded.enabled is True
    assert loaded.allowed_severities == (
        ServiceOpsSeverity.HIGH,
        ServiceOpsSeverity.CRITICAL,
    )
    assert loaded.allowed_event_names == ("slo_breached", "incident_opened")
    assert loaded.allowed_feeds_back_to == (FeedbackLayer.NEEDS,)
    assert loaded.stakeholder_event_map[stakeholder_id] == (
        "slo_breached",
        "incident_opened",
    )

    listed = container.list_catalog_auto_express_policies()
    assert len(listed) == 1
    assert listed[0].catalog_id == catalog_id


def test_ingest_service_ops_event_policy_denial_records_reason_codes(tmp_path: Path):
    container, catalog_id = _container_with_catalog(tmp_path)
    catalog = container.get_needs_catalog(catalog_id)
    assert catalog is not None
    stakeholder_id = catalog.stakeholders[0].id
    before_count = len(catalog.needs)

    restrictive_policy = CatalogAutoExpressPolicy(
        catalog_id=catalog_id,
        allowed_severities=(ServiceOpsSeverity.LOW,),
        allowed_event_names=("slo_recovered",),
        allowed_feeds_back_to=(FeedbackLayer.NEEDS,),
        stakeholder_event_map={stakeholder_id: ("slo_recovered",)},
    )
    container.save_catalog_auto_express_policy(restrictive_policy, actor="architect")

    spec = ServiceOpsEventSpec(
        name="incident_opened",
        severity=ServiceOpsSeverity.CRITICAL,
        must_include=(
            "trace_id",
            "lineage_id",
            "service_id",
            "incident_id",
            "runbook_url",
        ),
        feeds_back_to=FeedbackLayer.NEEDS,
    )
    result = container.ingest_service_ops_event(
        spec=spec,
        payload={
            "trace_id": "trace-needs-3",
            "lineage_id": "lineage-needs-3",
            "service_id": "orders-api",
            "incident_id": "inc-101",
            "runbook_url": "https://runbooks/orders-api",
        },
        catalog_id=catalog_id,
        stakeholder_id=stakeholder_id,
        auto_express=True,
        actor="ops-bot",
    )

    assert result["expressed_need"] is None
    decision = result["auto_express_decision"]
    assert decision["requested"] is True
    assert decision["allowed"] is False
    assert "severity_not_allowed" in decision["reason_codes"]
    assert "event_name_not_allowed" in decision["reason_codes"]
    assert "stakeholder_event_not_allowed" in decision["reason_codes"]

    updated = container.get_needs_catalog(catalog_id)
    assert updated is not None
    assert len(updated.needs) == before_count

    events = container.get_transaction_events(result["transaction_id"])
    ingested_events = [
        event
        for event in events
        if event["event_type"] == "service_ops_event_ingested"
    ]
    assert len(ingested_events) == 1
    payload = ingested_events[0]["payload"]["auto_express_decision"]
    assert payload["allowed"] is False
    assert "severity_not_allowed" in payload["reason_codes"]


def test_ingest_service_ops_event_policy_checks_feedback_destination(tmp_path: Path):
    container, catalog_id = _container_with_catalog(tmp_path)
    catalog = container.get_needs_catalog(catalog_id)
    assert catalog is not None
    stakeholder_id = catalog.stakeholders[0].id
    before_count = len(catalog.needs)

    policy = CatalogAutoExpressPolicy(
        catalog_id=catalog_id,
        allowed_severities=(ServiceOpsSeverity.HIGH,),
        allowed_event_names=("slo_breached",),
        allowed_feeds_back_to=(FeedbackLayer.NEEDS,),
        stakeholder_event_map={stakeholder_id: ("slo_breached",)},
    )
    container.save_catalog_auto_express_policy(policy, actor="architect")

    spec = ServiceOpsEventSpec(
        name="slo_breached",
        severity=ServiceOpsSeverity.HIGH,
        must_include=("trace_id", "lineage_id", "service_id", "slo_name"),
        feeds_back_to=FeedbackLayer.DECISION,
    )
    result = container.ingest_service_ops_event(
        spec=spec,
        payload={
            "trace_id": "trace-needs-4",
            "lineage_id": "lineage-needs-4",
            "service_id": "payments-api",
            "slo_name": "latency_p95",
        },
        catalog_id=catalog_id,
        stakeholder_id=stakeholder_id,
        auto_express=True,
        actor="ops-bot",
    )

    assert result["expressed_need"] is None
    decision = result["auto_express_decision"]
    assert decision["allowed"] is False
    assert "feeds_back_to_not_needs" in decision["reason_codes"]
    assert "feeds_back_to_not_allowed" in decision["reason_codes"]

    updated = container.get_needs_catalog(catalog_id)
    assert updated is not None
    assert len(updated.needs) == before_count


def test_ingest_service_ops_event_without_policy_records_reason_code(tmp_path: Path):
    container, catalog_id = _container_with_catalog(tmp_path)
    catalog = container.get_needs_catalog(catalog_id)
    assert catalog is not None
    stakeholder_id = catalog.stakeholders[0].id
    before_count = len(catalog.needs)

    spec = ServiceOpsEventSpec(
        name="incident_opened",
        severity=ServiceOpsSeverity.CRITICAL,
        must_include=(
            "trace_id",
            "lineage_id",
            "service_id",
            "incident_id",
            "runbook_url",
        ),
        feeds_back_to=FeedbackLayer.NEEDS,
    )
    result = container.ingest_service_ops_event(
        spec=spec,
        payload={
            "trace_id": "trace-needs-5",
            "lineage_id": "lineage-needs-5",
            "service_id": "orders-api",
            "incident_id": "inc-200",
            "runbook_url": "https://runbooks/orders-api",
        },
        catalog_id=catalog_id,
        stakeholder_id=stakeholder_id,
        auto_express=True,
        actor="ops-bot",
    )

    assert result["expressed_need"] is None
    assert result["auto_express_decision"]["allowed"] is False
    assert "policy_not_found" in result["auto_express_decision"]["reason_codes"]

    updated = container.get_needs_catalog(catalog_id)
    assert updated is not None
    assert len(updated.needs) == before_count
