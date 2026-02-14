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
        },
    )
    assert register.status_code == 200
    assert isinstance(register.json().get("transaction_id"), str)
    validate = client.post(
        "/models/validate",
        json={"model_name": "APIGovernanceModel", "version": "1.0"},
    )
    assert validate.status_code == 200
    assert isinstance(validate.json().get("transaction_id"), str)

    activate = client.post(
        "/models/activate",
        json={"model_name": "APIGovernanceModel", "version": "1.0"},
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
        },
    )
    assert register_resp.status_code == 200
    assert register_resp.json()["model_name"] == "BypassGuardModel"

    validate_resp = client.post(
        "/models/validate",
        json={"model_name": "BypassGuardModel", "version": "1.0"},
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["passed"] is True

    activate_resp = client.post(
        "/models/activate",
        json={
            "model_name": "BypassGuardModel",
            "version": "1.0",
            "actor": "ops",
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
