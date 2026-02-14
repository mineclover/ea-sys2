
import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from ea_kernel.api.server import create_app
from ea_kernel.schema_loader import load_kernel_schema_from_package
from pathlib import Path

@pytest.fixture
def client(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    return TestClient(app)

def test_get_flow_logic_api(client):
    # Test valid anchor
    anchor = "ea:kernel:rule_creation"
    response = client.get(f"/governance/flow/{anchor}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["anchor"] == anchor
    assert data["format"] == "jsonschema-2020-12"
    assert "input_schema" in data
    assert data["input_schema"]["$schema"] == "https://json-schema.org/draft/2020-12/schema"

def test_get_flow_logic_404(client):
    # Test invalid anchor
    response = client.get("/governance/flow/nonexistent")
    assert response.status_code == 404
