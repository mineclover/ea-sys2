"""Tests for ea_governance.governance_service pure functions."""

from ea_governance.governance_service import (
    business_flow_topology,
    cross_layer_summary,
    governance_dashboard,
    layer_schema,
    layer_profile_detail,
    list_managed_layers,
)

# ── GS1: list_managed_layers ────────────────────────────────────


def test_list_managed_layers_structure():
    result = list_managed_layers()
    assert "layers" in result
    assert "governance_stack" in result
    assert "total_profiles" in result
    assert isinstance(result["layers"], list)
    assert isinstance(result["governance_stack"], list)


def test_list_managed_layers_layer_keys():
    result = list_managed_layers()
    keys = [item["layer_key"] for item in result["layers"]]
    assert keys == ["infra", "governance", "decision", "needs", "kernel", "flow"]


def test_list_managed_layers_governance_stack():
    result = list_managed_layers()
    stack_ids = [item["stack_id"] for item in result["governance_stack"]]
    assert "meta" in stack_ids
    assert "external" in stack_ids


def test_list_managed_layers_total_profiles():
    result = list_managed_layers()
    total = result["total_profiles"]
    assert isinstance(total, int)
    assert total >= 0
    # Count loaded items
    loaded_layers = sum(1 for item in result["layers"] if item.get("loaded"))
    loaded_stack = sum(1 for item in result["governance_stack"] if item.get("loaded"))
    loaded_views = sum(1 for item in result.get("system_views", []) if item.get("loaded"))
    assert total == loaded_layers + loaded_stack + loaded_views


def test_list_managed_layers_loaded_profiles_have_counts():
    result = list_managed_layers()
    for item in result["layers"]:
        if item.get("loaded"):
            assert "element_count" in item
            assert "relation_count" in item
            assert "rule_count" in item


# ── GS2: layer_profile_detail ───────────────────────────────────


def test_layer_profile_detail_valid_key():
    result = layer_profile_detail("kernel")
    if "error" not in result:
        assert result["layer_key"] == "kernel"
        assert "profile" in result
        assert "topology" in result
        topo = result["topology"]
        assert "node_count" in topo
        assert "edge_count" in topo


def test_layer_profile_detail_invalid_key():
    result = layer_profile_detail("nonexistent")
    assert "error" in result
    assert "valid_keys" in result


def test_layer_profile_detail_elements_by_layer():
    result = layer_profile_detail("kernel")
    if "error" not in result:
        assert "elements_by_layer" in result
        for group in result["elements_by_layer"]:
            assert "layer" in group
            assert "count" in group
            assert "elements" in group


# ── GS3: cross_layer_summary ────────────────────────────────────


def test_cross_layer_summary_structure():
    result = cross_layer_summary()
    assert "layers" in result
    assert "total_nodes" in result
    assert "total_edges" in result
    assert isinstance(result["total_nodes"], int)
    assert isinstance(result["total_edges"], int)


def test_cross_layer_summary_layer_keys():
    result = cross_layer_summary()
    keys = [item["layer_key"] for item in result["layers"]]
    assert keys == ["infra", "governance", "decision", "needs", "kernel", "flow"]


def test_cross_layer_summary_loaded_entries():
    result = cross_layer_summary()
    for item in result["layers"]:
        if item.get("loaded"):
            assert "node_count" in item
            assert "edge_count" in item
            assert "top_relations" in item


# ── GS4: governance_dashboard ────────────────────────────────────


def test_governance_dashboard_structure():
    result = governance_dashboard()
    assert "managed_layers" in result
    assert "schema" in result
    assert "frameworks" in result


def test_governance_dashboard_schema_info():
    result = governance_dashboard()
    schema = result["schema"]
    assert schema["entity_count"] > 0
    assert schema["relation_count"] > 0
    assert isinstance(schema["entities"], list)
    assert isinstance(schema["relations"], list)


def test_governance_dashboard_frameworks():
    result = governance_dashboard()
    frameworks = result["frameworks"]
    assert isinstance(frameworks, list)
    # At least some frameworks should be loadable
    if frameworks:
        fw = frameworks[0]
        assert "name" in fw
        assert "element_count" in fw


def test_layer_schema_lang_ko_returns_i18n_fields():
    result = layer_schema("kernel", lang="ko")
    assert "error" not in result
    has_ko = False
    for group in result["elements_by_layer"]:
        for elem in group["elements"]:
            if isinstance(elem["display_name"], dict) and "ko" in elem["display_name"]:
                has_ko = True
                break
        if has_ko:
            break
    assert has_ko


def test_business_flow_lang_ko_returns_i18n_fields():
    result = business_flow_topology(lang="ko")
    assert "error" not in result
    has_ko = False
    for layer in result["layers"]:
        if not layer.get("loaded") or not layer.get("elements"):
            continue
        for elem in layer["elements"]:
            if isinstance(elem["display_name"], dict) and "ko" in elem["display_name"]:
                has_ko = True
                break
        if has_ko:
            break
    assert has_ko
