from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from ea_kernel.api.server import create_app
from ea_kernel.governance_types import RuleAsset, RuleLifecycle, RuleLifecycleState, RuleProvenance
from ea_kernel.schema_loader import load_kernel_schema_from_package
from ea_kernel.types import (
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleGroup,
    RuleMetadata,
)
from fastapi.testclient import TestClient


def _draft_rule_asset(rule_id: str) -> RuleAsset:
    rule = KernelValidityRule(
        id=rule_id,
        source_pattern="feature",
        target_pattern="feature",
        relationship_name="association",
        valid=True,
        priority=100,
    )
    metadata = RuleMetadata(
        domain="kernel",
        tags=("api", "entrypoint"),
        category=RuleCategory.STRUCTURAL,
        confidence=RuleConfidence.UNIVERSAL,
        source="test",
        established_version="1.0.0",
        rationale="api-governance-entrypoint test",
        group=RuleGroup.ASSOCIATION,
    )
    entry = RuleCorpusEntry(rule=rule, metadata=metadata)
    provenance = RuleProvenance(
        author="human:tester",
        source_type="manual",
        source_reference="tests/test_api_governance_entrypoint.py",
        created_at=datetime.now(UTC).replace(tzinfo=None).isoformat() + "Z",
    )
    lifecycle = RuleLifecycle(current_state=RuleLifecycleState.DRAFT)
    return RuleAsset(entry=entry, provenance=provenance, lifecycle=lifecycle)


def _model_profile_toml(name: str, version: str = "1.0") -> str:
    return f"""\
[profile]
name = "{name}"
version = "{version}"
kernel_version = "2.5.0"

[categories]
Thing = "item"
Action = "step"

[[elements]]
name = "Widget"
layer = "Core"
category = "Thing"

[[elements]]
name = "Task"
layer = "Core"
category = "Action"

[[relations]]
name = "uses"
kernel_relation = "association"

[[rules]]
source = "@Thing"
target = "@Action"
relation = "uses"
priority = 40
"""


def test_judgment_endpoint_records_governance_kernel_snapshot(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    response = client.post(
        "/judgment/execute",
        json={
            "source": "feature",
            "target": "feature",
            "relation": "association",
            "actor": "api-tester",
        },
    )
    assert response.status_code == 200

    container = app.state.governance_container
    snapshots = container.list_kernel_judgment_snapshots()
    assert snapshots
    assert snapshots[-1]["payload"]["kind"] == "kernel_judgment"
    assert snapshots[-1]["payload"]["actor"] == "api-tester"


def test_rule_approve_endpoint_uses_governance_entrypoint(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    system = app.state.system
    draft = _draft_rule_asset("rule:api:entrypoint")
    system.submit_rule(draft)

    response = client.post("/rules/rule:api:entrypoint/approve", params={"actor": "admin"})
    assert response.status_code == 200
    assert response.json() == {"status": "approved", "rule_id": "rule:api:entrypoint"}

    container = app.state.governance_container
    snapshot = container.get_kernel_rule_snapshot("rule:api:entrypoint")
    assert snapshot is not None
    assert snapshot["kind"] == "kernel_rule_asset"
    assert snapshot["lifecycle"]["state"] == "approved"


def test_model_registration_endpoints_use_governance_entrypoint(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    register = client.post(
        "/models/register",
        json={
            "profile_toml": _model_profile_toml(name="APIGovernanceModel"),
            "owner": "qa-team",
            "created_by": "api-tester",
            "decision_id": "dec-api-governance-register-01",
        },
    )
    assert register.status_code == 200
    assert isinstance(register.json().get("transaction_id"), str)
    validate = client.post(
        "/models/validate",
        json={
            "model_name": "APIGovernanceModel",
            "version": "1.0",
            "decision_id": "dec-api-governance-validate-01",
        },
    )
    assert validate.status_code == 200
    assert isinstance(validate.json().get("transaction_id"), str)

    activate = client.post(
        "/models/activate",
        json={
            "model_name": "APIGovernanceModel",
            "version": "1.0",
            "decision_id": "dec-api-governance-activate-01",
        },
    )
    assert activate.status_code == 200
    assert isinstance(activate.json().get("transaction_id"), str)

    container = app.state.governance_container
    snapshots = container.list_layer_snapshots("kernel")
    assert any(
        snapshot["model_id"] == "model:APIGovernanceModel"
        and snapshot["payload"]["kind"] == "kernel_model_state"
        for snapshot in snapshots
    )

    txs = container.execution_service.tx_manager.list_transactions(limit=20)
    tx_ids = {
        tx.id
        for tx in txs
        if tx.tx_type in {"kernel_model_registry_write", "kernel_model_registry_validate"}
    }
    assert tx_ids
    events = []
    for tx_id in tx_ids:
        events.extend(container.get_transaction_events(tx_id))

    assert any(event["event_type"] == "kernel_model_registered" for event in events)
    assert any(event["event_type"] == "kernel_model_validated" for event in events)


def test_model_decision_trace_endpoints_expose_evidence_impact_history(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)
    decision_id = "dec-api-01"

    register = client.post(
        "/models/register",
        json={
            "profile_toml": _model_profile_toml(name="APIDecisionTraceModel"),
            "owner": "qa-team",
            "created_by": "api-tester",
            "decision_id": decision_id,
            "evidence_refs": ["ev://adr/0001"],
            "cause_type": "decision",
            "change_phase": "planned",
        },
    )
    assert register.status_code == 200
    assert register.json()["decision_trace"]["decision_id"] == decision_id
    assert register.json()["decision_trace"]["cause_type"] == "decision"
    assert register.json()["decision_trace"]["cause_id"] == decision_id
    assert register.json()["decision_trace"]["change_phase"] == "planned"

    validate = client.post(
        "/models/validate",
        json={
            "model_name": "APIDecisionTraceModel",
            "version": "1.0",
            "decision_id": decision_id,
            "evidence_refs": [],
            "cause_type": "decision",
            "cause_id": decision_id,
            "change_phase": "planned",
        },
    )
    assert validate.status_code == 200
    assert "missing_evidence_refs" in validate.json()["decision_trace"]["warnings"]
    assert validate.json()["decision_trace"]["cause_type"] == "decision"
    assert validate.json()["decision_trace"]["cause_id"] == decision_id

    activate = client.post(
        "/models/activate",
        json={
            "model_name": "APIDecisionTraceModel",
            "version": "1.0",
            "decision_id": decision_id,
            "evidence_refs": ["ev://release/checklist"],
            "change_phase": "applied",
        },
    )
    assert activate.status_code == 200
    assert activate.json()["decision_trace"]["decision_id"] == decision_id
    assert activate.json()["decision_trace"]["change_phase"] == "applied"

    trace_response = client.get(f"/models/decisions/{decision_id}")
    assert trace_response.status_code == 200
    trace = trace_response.json()
    assert trace["kind"] == "decision_trace_contract"
    assert trace["decision_id"] == decision_id
    assert trace["latest_change_phase"] == "applied"
    assert len(trace["operations"]) == 3
    assert "missing_evidence_refs" in trace["warnings"]

    explore_response = client.get(f"/models/decisions/{decision_id}/explore")
    assert explore_response.status_code == 200
    explore = explore_response.json()
    assert "validate" in explore["evidence"]["missing_evidence_operations"]
    assert explore["impact"]["total_operations"] == 3
    assert explore["causal_context"]["latest_change_phase"] == "applied"
    assert explore["causal_context"]["phase_counts"]["planned"] >= 1
    assert any(
        row["event_type"] == "kernel_model_activated"
        for row in explore["history"]
    )


def test_models_endpoints_do_not_bypass_governance_container(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)

    class PoisonRegistration:
        def __getattr__(self, name: str):
            raise AssertionError(f"model registration bypass is forbidden: {name}")

    class FakeContainer:
        def __init__(self) -> None:
            self.calls: dict[str, list[dict[str, object]]] = {
                "register": [],
                "validate": [],
                "activate": [],
                "get_state": [],
            }

        def register_kernel_model(self, profile_toml: str, **kwargs):
            self.calls["register"].append({"profile_toml": profile_toml, **kwargs})
            return {
                "model_name": "BypassGuardModel",
                "version": "1.0",
                "created": True,
                "validation_run_id": "run-guard-1",
                "activated": False,
                "status": "registered",
                "active_version_id": None,
            }

        def validate_kernel_model(self, model_name: str, version: str, **kwargs):
            self.calls["validate"].append(
                {"model_name": model_name, "version": version, **kwargs}
            )
            return SimpleNamespace(passed=True, run_id="run-guard-2", errors=())

        def activate_kernel_model(self, model_name: str, version: str, **kwargs):
            self.calls["activate"].append(
                {"model_name": model_name, "version": version, **kwargs}
            )
            return SimpleNamespace(
                model_name=model_name,
                status="active",
                active_version_id="version-id-guard",
                owner=str(kwargs.get("actor", "api-user")),
            )

        def get_kernel_model_state(self, model_name: str, *, limit_runs: int = 5):
            self.calls["get_state"].append(
                {"model_name": model_name, "limit_runs": limit_runs}
            )
            return {
                "model": {
                    "model_id": "model-id-guard",
                    "model_name": model_name,
                    "owner": "qa-team",
                    "status": "active",
                    "active_version_id": "version-id-guard",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
                "versions": [],
                "validation_runs": [],
            }

    fake_container = FakeContainer()
    app.state.governance_container = fake_container
    app.state.registration = PoisonRegistration()
    client = TestClient(app)

    register_resp = client.post(
        "/models/register",
        json={
            "profile_toml": "ignored-by-fake",
            "owner": "qa-team",
            "created_by": "api-tester",
            "decision_id": "dec-api-bypass-register-01",
        },
    )
    assert register_resp.status_code == 200
    assert register_resp.json()["model_name"] == "BypassGuardModel"

    validate_resp = client.post(
        "/models/validate",
        json={
            "model_name": "BypassGuardModel",
            "version": "1.0",
            "decision_id": "dec-api-bypass-validate-01",
        },
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["passed"] is True

    activate_resp = client.post(
        "/models/activate",
        json={
            "model_name": "BypassGuardModel",
            "version": "1.0",
            "actor": "ops",
            "decision_id": "dec-api-bypass-activate-01",
        },
    )
    assert activate_resp.status_code == 200
    assert activate_resp.json()["status"] == "active"

    get_resp = client.get("/models/BypassGuardModel?limit_runs=3")
    assert get_resp.status_code == 200
    assert get_resp.json()["model"]["model_name"] == "BypassGuardModel"

    assert len(fake_container.calls["register"]) == 1
    assert fake_container.calls["register"][0]["on_exists"] == "validate"
    assert fake_container.calls["register"][0]["return_transaction"] is True
    assert fake_container.calls["register"][0]["context"]["source"] == "api:models/register"
    assert len(fake_container.calls["validate"]) == 1
    assert fake_container.calls["validate"][0]["actor"] == "api-user"
    assert fake_container.calls["validate"][0]["return_transaction"] is True
    assert len(fake_container.calls["activate"]) == 1
    assert fake_container.calls["activate"][0]["actor"] == "ops"
    assert fake_container.calls["activate"][0]["return_transaction"] is True
    assert len(fake_container.calls["get_state"]) == 1
    assert fake_container.calls["get_state"][0]["limit_runs"] == 3


def test_models_endpoint_error_envelope_matches_model_api_error_record(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    not_found = client.get("/models/unknown-model")
    assert not_found.status_code == 404
    assert not_found.json()["detail"]["status_code"] == 404
    assert not_found.json()["detail"]["category"] == "not_found"
    assert "unknown-model" in not_found.json()["detail"]["detail"]

    bad_request = client.get("/models/unknown-model?limit_runs=0")
    assert bad_request.status_code == 400
    assert bad_request.json()["detail"]["status_code"] == 400
    assert bad_request.json()["detail"]["category"] == "bad_request"

    missing_trace = client.get("/models/decisions/unknown-decision")
    assert missing_trace.status_code == 404
    assert missing_trace.json()["detail"]["status_code"] == 404
    assert missing_trace.json()["detail"]["category"] == "not_found"


def test_models_index_and_layer_stack_endpoints(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    register = client.post(
        "/models/register",
        json={
            "profile_toml": _model_profile_toml(name="LayerStackModel.kernel"),
            "owner": "qa-team",
            "created_by": "api-tester",
            "decision_id": "dec-api-layerstack-register-01",
        },
    )
    assert register.status_code == 200

    models_index = client.get("/models")
    assert models_index.status_code == 200
    payload = models_index.json()
    assert payload["total"] >= 1
    assert any(item["model_name"] == "LayerStackModel.kernel" for item in payload["models"])

    stack = client.get("/layers/kernel/stack?lang=ko&m0_limit=10")
    assert stack.status_code == 200
    stack_payload = stack.json()
    assert stack_payload["layer_key"] == "kernel"
    assert "m2" in stack_payload
    assert "m1" in stack_payload
    assert "m0" in stack_payload
    assert stack_payload["m2"]["layer_key"] == "kernel"
    assert stack_payload["m1"]["profile"] == stack_payload["profile_name"]
    assert stack_payload["m1"]["view_mode"] == "summary"
    assert stack_payload["m1"]["surface_filter"]["applied"] is True
    assert "snapshots" in stack_payload["m0"]
    assert "model_candidates" in stack_payload["m0"]

    infra_m2 = client.get("/layers/infra/m2?lang=ko")
    assert infra_m2.status_code == 200
    infra_payload = infra_m2.json()
    assert infra_payload["layer_key"] == "infra"
    assert "elements_by_layer" in infra_payload
    assert "identifier" in infra_payload["elements_by_layer"][0]["elements"][0]
    assert infra_payload["identifier_system"]["object_identifiers"]["relation"] == "m2::infra::relation::{relation_name}"
    assert infra_payload["m2_blueprint"]["categories"][0]["display_name"]["ko"]
    assert infra_payload["m2_blueprint"]["layer_responsibilities"][0]["role_i18n"]["ko"]
    assert infra_payload["projection_policy"]["ui"]["presets"]["overview"]["max_edges"] == 320
    assert infra_payload["projection_policy"]["ui"]["presets"]["actor-route"]["focus_depth"] == 2

    needs_m2 = client.get("/layers/needs/m2?lang=ko")
    assert needs_m2.status_code == 200
    needs_payload = needs_m2.json()
    assert needs_payload["layer_key"] == "needs"
    assert needs_payload["identifier_system"]["object_identifiers"]["element"] == "m2::needs::element::{element_name}"
    assert needs_payload["m2_blueprint"]["summary"]["category_count"] > 0
    assert "description" in needs_payload["m2_blueprint"]["relations"][0]
    assert needs_payload["projection_policy"]["ui"]["presets"]["trace"]["max_edges"] == 700

    invalid_limit = client.get("/layers/kernel/stack?m0_limit=0")
    assert invalid_limit.status_code == 400


def test_layer_stack_endpoints_available_for_all_core_layers(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    for layer in ("infra", "governance", "decision", "needs", "kernel", "flow"):
        response = client.get(f"/layers/{layer}/stack?lang=en&m0_limit=20")
        assert response.status_code == 200
        payload = response.json()
        assert payload["layer_key"] == layer
        assert payload["m1"]["view_mode"] == "summary"
        assert payload["m1"]["surface_filter"]["applied"] is True
        assert payload["m1"]["edge_count"] > 0


def test_kernel_m2_endpoints_remain_canonical_and_active(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    entities = client.get("/kernel/entities?lang=ko")
    assert entities.status_code == 200
    entities_payload = entities.json()
    entity_layers = {layer["name"]: layer for layer in entities_payload["layers"]}
    assert "L1 Structure" in entity_layers
    assert "L4 Concrete" in entity_layers
    assert entity_layers["L1 Structure"]["count"] > 0
    assert entity_layers["L4 Concrete"]["count"] > 0

    relations = client.get("/kernel/relations?lang=ko")
    assert relations.status_code == 200
    relations_payload = relations.json()
    relation_layers = {layer["name"]: layer for layer in relations_payload["layers"]}
    assert "L2 Relationship" in relation_layers
    assert "L3 Behavioral" in relation_layers
    assert relation_layers["L2 Relationship"]["count"] > 0
    assert relation_layers["L3 Behavioral"]["count"] > 0

    rules = client.get("/kernel/rules")
    assert rules.status_code == 200
    rules_payload = rules.json()
    assert rules_payload["total"] > 0
    assert len(rules_payload["groups"]) > 0

    kernel_m2 = client.get("/layers/kernel/m2?lang=ko")
    assert kernel_m2.status_code == 200
    kernel_m2_payload = kernel_m2.json()
    assert kernel_m2_payload["layer_key"] == "kernel"
    assert kernel_m2_payload["identifier_system"]["namespace"] == "m2"
    assert kernel_m2_payload["identifier_system"]["object_identifiers"]["element"] == "m2::kernel::element::{element_name}"
    assert kernel_m2_payload["identifier_system"]["rule_identifier"]["digest_algorithm"] == "sha1"


def test_needs_api_extended_write_and_filter_surface(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    client = TestClient(app)

    create_catalog = client.post(
        "/needs/catalogs",
        json={"name": "Needs API Surface", "description": "regression"},
    )
    assert create_catalog.status_code == 200
    catalog_id = create_catalog.json()["catalog_id"]

    stakeholder_resp = client.post(
        f"/needs/catalogs/{catalog_id}/stakeholders",
        json={"name": "Platform Team", "role": "team", "context": "availability"},
    )
    assert stakeholder_resp.status_code == 200
    stakeholder_id = stakeholder_resp.json()["stakeholder_id"]

    use_case_resp = client.post(
        f"/needs/catalogs/{catalog_id}/use-cases",
        json={
            "title": "Incident handling",
            "actor": "SRE",
            "situation": "Sev1 outage",
            "purpose": "safety",
            "outcome": "restore service quickly",
            "tags": ["ops", "incident"],
        },
    )
    assert use_case_resp.status_code == 200
    use_case_id = use_case_resp.json()["use_case_id"]

    expressed = client.post(
        f"/needs/catalogs/{catalog_id}/needs",
        json={
            "stakeholder_id": stakeholder_id,
            "action": "stabilize",
            "subject": "runtime",
            "priority": "high",
            "purpose": "safety",
            "cause_types": ["situational"],
            "complexity": "complex",
            "kernel_change_phase": "planned",
            "use_case_id": use_case_id,
        },
    )
    assert expressed.status_code == 200
    need_id = expressed.json()["need_id"]

    detail = client.get(f"/needs/catalogs/{catalog_id}/needs/{need_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["priority"] == "high"
    assert detail_payload["purpose"] == "safety"
    assert detail_payload["kernel_change_phase"] == "planned"
    assert detail_payload["decision_linked"] is False
    assert detail_payload["decision_evidence_refs"] == []
    assert detail_payload["inherited_from_decisions"] == []

    listing = client.get(
        f"/needs/catalogs/{catalog_id}/needs",
        params={
            "priority": "high",
            "purpose": "safety",
            "complexity": "complex",
            "use_case_id": use_case_id,
            "cause_type": "situational",
            "kernel_change_phase": "planned",
        },
    )
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) == 1
    assert rows[0]["purpose"] == "safety"
    assert rows[0]["cause_types"] == ["situational"]
    assert rows[0]["complexity"] == "complex"
    assert rows[0]["use_case_id"] == use_case_id
    assert rows[0]["kernel_change_phase"] == "planned"
    assert rows[0]["decision_linked"] is False
    assert rows[0]["decision_evidence_refs"] == []
    assert rows[0]["inherited_from_decisions"] == []

    revised = client.post(
        f"/needs/catalogs/{catalog_id}/needs/{need_id}/revise",
        json={"subject": "service runtime", "priority": "critical"},
    )
    assert revised.status_code == 200
    revised_need_id = revised.json()["need_id"]
    assert revised_need_id != need_id

    revised_detail = client.get(f"/needs/catalogs/{catalog_id}/needs/{revised_need_id}")
    assert revised_detail.status_code == 200
    revised_payload = revised_detail.json()
    assert revised_payload["priority"] == "critical"
    assert revised_payload["subject"] == "service runtime"
    assert revised_payload["kernel_change_phase"] == "planned"

    process_unit = client.post(
        f"/needs/catalogs/{catalog_id}/needs/{revised_need_id}/process-units",
        json={
            "stage": "identify",
            "label": "Detect incident signal",
            "description": "monitoring alert",
            "metadata": {"source": "pager"},
        },
    )
    assert process_unit.status_code == 200
    assert process_unit.json()["process_unit_id"].startswith("pu-")

    inherited = client.post(
        f"/needs/catalogs/{catalog_id}/needs/{revised_need_id}/inherit-decision-evidence",
        json={
            "decision_id": "dec-ops-001",
            "evidence_refs": ["ev://runbook/incident"],
            "kernel_change_phase": "applied",
        },
    )
    assert inherited.status_code == 200
    assert inherited.json()["need_id"] == revised_need_id

    linked_listing = client.get(
        f"/needs/catalogs/{catalog_id}/needs",
        params={
            "decision_linked": True,
            "decision_id": "dec-ops-001",
        },
    )
    assert linked_listing.status_code == 200
    linked_rows = linked_listing.json()
    assert len(linked_rows) == 1
    assert linked_rows[0]["id"] == revised_need_id
    assert linked_rows[0]["decision_linked"] is True
    assert linked_rows[0]["inherited_from_decisions"] == ["dec-ops-001"]
    assert "ev://runbook/incident" in linked_rows[0]["decision_evidence_refs"]

    catalog_detail = client.get(f"/needs/catalogs/{catalog_id}")
    assert catalog_detail.status_code == 200
    needs = catalog_detail.json()["needs"]
    revised_row = next(n for n in needs if n["id"] == revised_need_id)
    assert "ev://runbook/incident" in revised_row["decision_evidence_refs"]
    assert revised_row["kernel_change_phase"] == "applied"
