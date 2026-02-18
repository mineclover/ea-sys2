
import pytest

pytest.importorskip("fastapi")

from ea_kernel.api.server import create_app
from ea_kernel.schema_loader import load_kernel_schema_from_package
from fastapi.testclient import TestClient


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


def test_i18n_profile_audit_api(client):
    response = client.get("/i18n/audit/profiles/EASystem-Kernel?lang=ko")
    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "m1"
    assert data["profile"] == "EASystem-Kernel"
    assert data["lang"] == "ko"
    assert isinstance(data["missing"], list)


def test_i18n_profile_audit_404(client):
    response = client.get("/i18n/audit/profiles/NonExistentProfile?lang=ko")
    assert response.status_code == 404


def test_profile_topology_summary_view_mode(client):
    response = client.get("/profiles/EASystem-Kernel/topology?view_mode=summary&max_edges=200")
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "EASystem-Kernel"
    assert payload["view_mode"] == "summary"
    assert payload["edge_count"] <= 200
    assert payload["edge_total_raw"] >= payload["edge_count"]
    assert "domain_view" in payload
    if payload["edges"]:
        assert "rule_count" in payload["edges"][0]
        assert payload["edges"][0]["edge_origin"] in {"explicit", "expanded", "mixed"}
        assert payload["edges"][0]["semantic_axis"]
        assert payload["edges"][0]["semantic_intent"]
        assert isinstance(payload["edges"][0]["surface_exposed"], bool)
        assert "rule_refs" not in payload["edges"][0]
        assert "rule_ref" not in payload["edges"][0]
        assert "rule_id" not in payload["edges"][0]
    assert "semantic_view" in payload


def test_profile_topology_domain_scope_query_param(client):
    response = client.get(
        "/profiles/EASystem-Kernel/topology?view_mode=summary&domain_scope=bridge&max_edges=200",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["domain_view"]["requested_scope"] == "bridge"
    assert payload["domain_view"]["scope"] in {"bridge", "all"}


def test_profile_topology_focus_view_mode(client):
    response = client.get("/profiles/EASystem-Kernel/topology?view_mode=focus&focus=core&max_edges=200")
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "EASystem-Kernel"
    assert payload["view_mode"] == "focus"
    assert payload["focus"]["mode"] == "core"
    assert "visible_relations" in payload["focus"]
    assert "hidden_relations" in payload["focus"]
    assert set(payload["focus"]["selected_relations"]).issubset(
        {"contains", "depends_on", "next", "triggers", "constrains"},
    )
    assert payload["edge_count"] <= 200


def test_profile_topology_focus_actor_view_mode(client):
    response = client.get(
        "/profiles/EASystem-Kernel/topology?"
        "view_mode=focus&focus=actor&focus_actor=ModelExplorerContext&focus_depth=4&max_edges=200",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "EASystem-Kernel"
    assert payload["view_mode"] == "focus"
    assert payload["focus"]["mode"] == "actor"
    assert payload["focus"]["actor"] == "ModelExplorerContext"
    assert payload["focus"]["actor_depth"] == 4
    assert "actor_candidates" in payload["focus"]
    selected = set(payload["focus"]["selected_relations"])
    assert selected
    assert all(edge["relation"] in selected for edge in payload["edges"])


def test_profile_topology_focus_topic_view_mode(client):
    response = client.get(
        "/profiles/EASystem-Kernel/topology?"
        "view_mode=focus&focus=topic&focus_topic=ModelExplorer&focus_depth=2&max_edges=220",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["view_mode"] == "focus"
    assert payload["focus"]["mode"] == "topic"
    assert payload["focus"]["topic"] == "ModelExplorer"
    assert payload["focus"]["topic_depth"] == 2
    assert payload["focus"]["topic_seeds"]
    assert payload["focus"]["topic_policy"]["max_scope_nodes_per_depth"] == 48
    selected = set(payload["focus"]["selected_relations"])
    assert selected
    assert all(edge["relation"] in selected for edge in payload["edges"])


def test_profile_topology_focus_topic_infra_layer_override(client):
    response = client.get(
        "/profiles/EASystem-Infra/topology?"
        "view_mode=focus&focus=topic&focus_topic=Infra&max_edges=220",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["focus"]["mode"] == "topic"
    policy = payload["focus"].get("topic_policy", {})
    assert policy.get("max_scope_nodes_per_depth") == 28
    assert policy.get("max_seed_count") == 6
    assert policy.get("max_match_count") == 12
    assert policy.get("min_token_coverage") == 0.6


def test_profile_topology_semantic_layer_overrides(client):
    infra_response = client.get(
        "/profiles/EASystem-Infra/topology?view_mode=summary&max_edges=260",
    )
    assert infra_response.status_code == 200
    infra_payload = infra_response.json()
    infra_semantic = infra_payload.get("semantic_view", {})
    assert infra_semantic.get("profile_scope") == "layer:infra"
    assert infra_semantic.get("layer_key") == "infra"
    infra_registers = [
        edge
        for edge in infra_payload.get("edges", [])
        if edge.get("relation") == "registers"
    ]
    assert infra_registers
    assert all(edge.get("semantic_axis") == "integration" for edge in infra_registers[:5])
    assert all(edge.get("semantic_intent") == "adapter_binding" for edge in infra_registers[:5])

    needs_response = client.get(
        "/profiles/EASystem-Needs/topology?view_mode=summary&max_edges=320",
    )
    assert needs_response.status_code == 200
    needs_payload = needs_response.json()
    needs_semantic = needs_payload.get("semantic_view", {})
    assert needs_semantic.get("profile_scope") == "layer:needs"
    assert needs_semantic.get("layer_key") == "needs"
    needs_constrains = [
        edge
        for edge in needs_payload.get("edges", [])
        if edge.get("relation") == "constrains"
    ]
    assert needs_constrains
    assert all(edge.get("semantic_axis") == "intent" for edge in needs_constrains[:5])
    assert all(edge.get("semantic_intent") == "priority_alignment" for edge in needs_constrains[:5])


def test_profile_projection_endpoint(client):
    response = client.get(
        "/profiles/EASystem-Kernel/projection?"
        "level=l2&actor=ModelExplorerContext&depth=4&domain_scope=owned&max_edges=300",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "EASystem-Kernel"
    assert "projection" in payload
    assert payload["projection"]["level"] == "L2"
    assert payload["projection"]["lens"] == "interaction"
    assert payload["projection"]["policy"]["source"] in {"toml", "fallback"}
    assert payload["projection"]["policy"]["scope"] in {"global", "layer:kernel"}
    assert payload["projection"]["filters"]["domain_scope"] in {"owned", "all"}
    assert payload["edge_count"] <= 300


def test_profile_composed_topology_endpoint(client):
    response = client.get(
        "/profiles/EASystem-Kernel/composed?"
        "domain_scope=owned&max_edges=260&include_profiles=EASystem-Kernel,EASystem-Needs",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"] == "EASystem-Kernel"
    assert payload["view_mode"] == "summary"
    assert payload["composition"]["anchor_layer_key"] == "kernel"
    assert payload["composition"]["source_profile_count"] >= 1
    assert payload["edge_count"] <= 260
    if payload["edges"]:
        assert payload["edges"][0]["edge_origin"] in {"explicit", "expanded", "mixed"}
        assert payload["edges"][0]["semantic_axis"]
        assert payload["edges"][0]["semantic_intent"]
        assert "rule_refs" not in payload["edges"][0]
        assert "rule_ref" not in payload["edges"][0]
        assert "rule_id" not in payload["edges"][0]
    assert "semantic_view" in payload


def test_profile_composed_topology_focus_endpoint(client):
    core_response = client.get(
        "/profiles/EASystem-Kernel/composed?"
        "domain_scope=all&focus=core&max_edges=260",
    )
    assert core_response.status_code == 200
    core_payload = core_response.json()
    assert core_payload["view_mode"] == "focus"
    assert core_payload["focus"]["mode"] == "core"
    assert "actor_candidates" in core_payload["focus"]

    response = client.get(
        "/profiles/EASystem-Kernel/composed?"
        "domain_scope=all&focus=actor&focus_actor=ModelExplorerContext&focus_depth=4&max_edges=260",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["view_mode"] == "focus"
    assert payload["focus"]["mode"] == "actor"
    assert payload["focus"]["actor"] == "ModelExplorerContext"
    assert payload["focus"]["actor_depth"] == 4

    topic_response = client.get(
        "/profiles/EASystem-Kernel/composed?"
        "domain_scope=all&focus=topic&focus_topic=ModelExplorer&focus_depth=2&max_edges=260",
    )
    assert topic_response.status_code == 200
    topic_payload = topic_response.json()
    assert topic_payload["view_mode"] == "focus"
    assert topic_payload["focus"]["mode"] == "topic"
    assert topic_payload["focus"]["topic"] == "ModelExplorer"
    assert topic_payload["focus"]["topic_depth"] == 2
    assert topic_payload["focus"]["topic_seeds"]


def test_profile_topology_rejects_invalid_view_mode(client):
    response = client.get("/profiles/EASystem-Kernel/topology?view_mode=invalid-mode")
    assert response.status_code == 400


def test_profile_topology_rejects_invalid_focus_params(client):
    invalid_focus = client.get("/profiles/EASystem-Kernel/topology?view_mode=focus&focus=invalid")
    assert invalid_focus.status_code == 400

    missing_focus_relation = client.get("/profiles/EASystem-Kernel/topology?view_mode=focus&focus=relation")
    assert missing_focus_relation.status_code == 400

    missing_focus_topic = client.get("/profiles/EASystem-Kernel/topology?view_mode=focus&focus=topic")
    assert missing_focus_topic.status_code == 400

    focus_outside_mode = client.get("/profiles/EASystem-Kernel/topology?view_mode=summary&focus=core")
    assert focus_outside_mode.status_code == 400

    invalid_focus_depth = client.get(
        "/profiles/EASystem-Kernel/topology?view_mode=focus&focus=actor&focus_depth=0",
    )
    assert invalid_focus_depth.status_code == 400

    invalid_projection_level = client.get(
        "/profiles/EASystem-Kernel/projection?level=l9",
    )
    assert invalid_projection_level.status_code == 400

    invalid_domain_scope = client.get(
        "/profiles/EASystem-Kernel/topology?view_mode=summary&domain_scope=invalid",
    )
    assert invalid_domain_scope.status_code == 400

    invalid_composed_domain_scope = client.get(
        "/profiles/EASystem-Kernel/composed?domain_scope=invalid",
    )
    assert invalid_composed_domain_scope.status_code == 400

    invalid_composed_focus = client.get(
        "/profiles/EASystem-Kernel/composed?focus=relation",
    )
    assert invalid_composed_focus.status_code == 400

    missing_composed_focus_topic = client.get(
        "/profiles/EASystem-Kernel/composed?focus=topic",
    )
    assert missing_composed_focus_topic.status_code == 400


def test_profile_graph_endpoints_keyword_only_service_bridge(client):
    reachable = client.get("/profiles/EASystem-Kernel/reachable?element=KernelLayer&max_depth=2")
    assert reachable.status_code == 200
    reachable_payload = reachable.json()
    assert reachable_payload["profile"] == "EASystem-Kernel"
    assert reachable_payload["source"] == "KernelLayer"
    assert isinstance(reachable_payload["reachable"], list)

    scope = client.post(
        "/profiles/EASystem-Kernel/element-scope",
        json={"elements": ["KernelLayer"], "max_depth": 2},
    )
    assert scope.status_code == 200
    scope_payload = scope.json()
    assert scope_payload["profile"] == "EASystem-Kernel"
    assert "KernelLayer" in scope_payload["scope"]

    paths = client.get(
        "/profiles/EASystem-Kernel/paths?"
        "source=KernelLayer&target=KernelModelPort&max_depth=4",
    )
    assert paths.status_code == 200
    paths_payload = paths.json()
    assert paths_payload["profile"] == "EASystem-Kernel"
    assert paths_payload["source"] == "KernelLayer"
    assert paths_payload["target"] == "KernelModelPort"
    assert isinstance(paths_payload["paths"], list)

    impact = client.get("/profiles/EASystem-Kernel/impact?element=KernelLayer&max_depth=2")
    assert impact.status_code == 200
    impact_payload = impact.json()
    assert impact_payload["profile"] == "EASystem-Kernel"
    assert impact_payload["element"] == "KernelLayer"
    assert "impact" in impact_payload


def test_profile_impact_direction_aliases_and_validation(client):
    downstream = client.get(
        "/profiles/EASystem-Kernel/impact?"
        "element=KernelLayer&direction=downstream&max_depth=2",
    )
    assert downstream.status_code == 200
    downstream_payload = downstream.json()
    assert downstream_payload["direction"] == "outgoing"

    outgoing = client.get(
        "/profiles/EASystem-Kernel/impact?"
        "element=KernelLayer&direction=outgoing&max_depth=2",
    )
    assert outgoing.status_code == 200
    outgoing_payload = outgoing.json()
    assert outgoing_payload["direction"] == "outgoing"
    assert downstream_payload["affected_count"] == outgoing_payload["affected_count"]

    upstream = client.get(
        "/profiles/EASystem-Kernel/impact?"
        "element=KernelLayer&direction=upstream&max_depth=2",
    )
    assert upstream.status_code == 200
    upstream_payload = upstream.json()
    assert upstream_payload["direction"] == "incoming"

    invalid = client.get(
        "/profiles/EASystem-Kernel/impact?"
        "element=KernelLayer&direction=sideways&max_depth=2",
    )
    assert invalid.status_code == 400
