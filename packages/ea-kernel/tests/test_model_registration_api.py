from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - optional dependency
    TestClient = None

if TestClient is not None:
    from ea_kernel.api.server import create_app
    from ea_kernel.schema_loader import load_kernel_schema_from_package
else:  # pragma: no cover - optional dependency
    create_app = None
    load_kernel_schema_from_package = None


pytestmark = pytest.mark.skipif(TestClient is None, reason="fastapi not installed")


def _profile_toml(name: str = "APITestModel", version: str = "1.0") -> str:
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


@pytest.fixture
def client(tmp_path):
    assert load_kernel_schema_from_package is not None
    assert create_app is not None
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    return TestClient(app)


def test_register_model_and_query_state(client):
    payload = {
        "profile_toml": _profile_toml(name="APITestModel", version="1.0"),
        "owner": "qa-team",
        "created_by": "api-tester",
        "activate": False,
        "decision_id": "dec-api-model-register-001",
    }
    register_response = client.post("/models/register", json=payload)
    assert register_response.status_code == 200
    reg = register_response.json()
    assert reg["model_name"] == "APITestModel"
    assert reg["version"] == "1.0"
    assert reg["created"] is True
    assert reg["activated"] is False

    get_response = client.get("/models/APITestModel")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["model"]["status"] == "registered"
    assert len(data["versions"]) == 1
    assert len(data["validation_runs"]) >= 1


def test_register_existing_model_revalidates(client):
    payload = {
        "profile_toml": _profile_toml(name="APIDedupModel", version="1.0"),
        "owner": "qa-team",
        "created_by": "api-tester",
        "decision_id": "dec-api-model-register-002",
    }
    first = client.post("/models/register", json=payload)
    second = client.post("/models/register", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["created"] is False

    state = client.get("/models/APIDedupModel").json()
    assert len(state["versions"]) == 1
    assert len(state["validation_runs"]) >= 2


def test_validate_and_activate_model(client):
    register_response = client.post(
        "/models/register",
        json={
            "profile_toml": _profile_toml(name="APIActivateModel", version="1.0"),
            "owner": "qa-team",
            "created_by": "api-tester",
            "decision_id": "dec-api-model-register-003",
        },
    )
    assert register_response.status_code == 200

    validate_response = client.post(
        "/models/validate",
        json={
            "model_name": "APIActivateModel",
            "version": "1.0",
            "decision_id": "dec-api-model-validate-003",
        },
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["passed"] is True

    activate_response = client.post(
        "/models/activate",
        json={
            "model_name": "APIActivateModel",
            "version": "1.0",
            "actor": "ops",
            "decision_id": "dec-api-model-activate-003",
        },
    )
    assert activate_response.status_code == 200
    act = activate_response.json()
    assert act["status"] == "active"
    assert act["active_version_id"]


def test_register_invalid_toml_returns_400(client):
    response = client.post(
        "/models/register",
        json={
            "profile_toml": "not valid toml",
            "owner": "qa-team",
            "created_by": "api-tester",
            "decision_id": "dec-api-model-register-004",
        },
    )
    assert response.status_code == 400


def test_register_requires_decision_id(client):
    response = client.post(
        "/models/register",
        json={
            "profile_toml": _profile_toml(name="MissingDecisionModel", version="1.0"),
            "owner": "qa-team",
            "created_by": "api-tester",
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["category"] == "bad_request"
    assert "decision_id is required" in detail["detail"]
