from __future__ import annotations

from pathlib import Path

from ea_governance.facade import GovernanceContainer, KernelSchema
from ea_governance.layer_store import SQLiteGovernanceLayerStore
from ea_governance.needs_store import GovernanceNeedsStore
from ea_needs.catalog import NeedCatalog
from ea_needs.types import NeedPriority, NeedPurpose


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
