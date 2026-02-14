
import pytest
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from ea_kernel.api.server import create_app
from ea_kernel.schema_loader import load_kernel_schema_from_package

@pytest.fixture
def client(tmp_path):
    schema = load_kernel_schema_from_package()
    app = create_app(tmp_path, schema)
    return TestClient(app)

def test_system_self_model_api(client):
    response = client.get("/system/self-model")
    
    if response.status_code != 200:
        print(f"Error Response: {response.json()}")
        
    assert response.status_code == 200
    mermaid_src = response.text
    
    # Check for expected layers/entities
    assert "ea:kernel:schema" in mermaid_src
    assert "ea:flow:metastep" in mermaid_src
    assert "ea:decision:pattern" in mermaid_src
    assert "ea:governance:transaction" in mermaid_src
    
    # Check for expected relations
    assert "targets" in mermaid_src
    assert "grounds" in mermaid_src
    assert "enwraps" in mermaid_src
    
    # Verify it looks like Mermaid
    assert "graph TD" in mermaid_src or "graph LR" in mermaid_src
