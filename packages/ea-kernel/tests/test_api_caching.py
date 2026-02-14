from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

import ea_governance.facade as governance_facade
import ea_kernel.profile_rule_compiler as profile_rule_compiler
from ea_kernel.api.server import create_app
from ea_kernel.schema_loader import load_kernel_schema_from_package
from fastapi.testclient import TestClient


@pytest.fixture
def app_and_client(tmp_path: Path) -> tuple[Any, TestClient]:
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    return app, TestClient(app)


def test_governance_container_cached_across_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    app_and_client: tuple[Any, TestClient],
) -> None:
    app, client = app_and_client
    init_count = {"value": 0}

    class FakeContainer:
        def __init__(self, data_dir: Path, schema: Any, flow_runtime: Any = None) -> None:
            _ = data_dir, schema, flow_runtime
            init_count["value"] += 1

        def get_flow_spec(self, anchor_id: str) -> dict[str, Any] | None:
            if anchor_id != "ea:kernel:rule_creation":
                return None
            return {
                "anchor": anchor_id,
                "type": "Step",
                "name": "AddRuleStep",
                "input_schema": {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                },
                "format": "jsonschema-2020-12",
            }

        def get_self_model_diagram(self, lang: str = "en") -> str:
            _ = lang
            return "graph LR\nA --> B"

    monkeypatch.setattr(governance_facade, "GovernanceContainer", FakeContainer)

    flow_resp = client.get("/governance/flow/ea:kernel:rule_creation")
    self_resp = client.get("/system/self-model")
    flow_resp_2 = client.get("/governance/flow/ea:kernel:rule_creation")

    assert flow_resp.status_code == 200
    assert self_resp.status_code == 200
    assert flow_resp_2.status_code == 200
    assert init_count["value"] == 1
    assert isinstance(app.state.governance_container, FakeContainer)


def test_diagram_schema_built_once_per_app_instance(
    monkeypatch: pytest.MonkeyPatch,
    app_and_client: tuple[Any, TestClient],
) -> None:
    _app, client = app_and_client
    build_count = {"value": 0}
    original_build = profile_rule_compiler.build_profile_runtime_schema

    def wrapped_build(*args: Any, **kwargs: Any) -> Any:
        build_count["value"] += 1
        return original_build(*args, **kwargs)

    monkeypatch.setattr(profile_rule_compiler, "build_profile_runtime_schema", wrapped_build)

    resp1 = client.get("/diagram")
    resp2 = client.get("/diagram")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert build_count["value"] == 1
