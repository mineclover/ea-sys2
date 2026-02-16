"""Tests for kernel_service — onboarding use case service layer."""

from __future__ import annotations

from ea_kernel.kernel_service import (
    audit_i18n,
    describe_profile,
    describe_rule,
    get_entity_names,
    judge,
    list_entities,
    list_relations,
    list_rules,
    profile_topology,
)


class TestListEntities:
    """UC1: list_entities()."""

    def test_returns_total_and_layers(self):
        result = list_entities()
        assert "total" in result
        assert "layers" in result
        assert result["total"] > 0

    def test_layers_cover_l1_and_l4(self):
        result = list_entities()
        layer_names = [layer["name"] for layer in result["layers"]]
        assert "L1 Structure" in layer_names
        assert "L4 Concrete" in layer_names

    def test_entities_have_required_fields(self):
        result = list_entities()
        for layer in result["layers"]:
            for e in layer["entities"]:
                assert "name" in e
                assert "parent" in e
                assert "is_abstract" in e

    def test_total_matches_sum_of_layers(self):
        result = list_entities()
        total_from_layers = sum(layer["count"] for layer in result["layers"])
        assert result["total"] == total_from_layers

    def test_lang_ko_returns_i18n_fields(self):
        result = list_entities(lang="ko")
        has_dict = False
        for layer in result["layers"]:
            for e in layer["entities"]:
                if isinstance(e["description"], dict):
                    has_dict = True
                    assert "ko" in e["description"]
        assert has_dict, "Expected at least one entity with dict description"


class TestListRelations:
    """UC1: list_relations()."""

    def test_returns_total_and_layers(self):
        result = list_relations()
        assert "total" in result
        assert "layers" in result
        assert result["total"] > 0

    def test_layers_are_l2_and_l3(self):
        result = list_relations()
        layer_names = [layer["name"] for layer in result["layers"]]
        assert "L2 Relationship" in layer_names
        assert "L3 Behavioral" in layer_names

    def test_relations_have_roles(self):
        result = list_relations()
        for layer in result["layers"]:
            for r in layer["relations"]:
                assert "roles" in r
                for role in r["roles"]:
                    assert "name" in role
                    assert "player" in role

    def test_lang_ko_returns_i18n_fields(self):
        result = list_relations(lang="ko")
        has_dict = False
        for layer in result["layers"]:
            for r in layer["relations"]:
                if isinstance(r["description"], dict):
                    has_dict = True
                    assert "ko" in r["description"]
        assert has_dict, "Expected at least one relation with dict description"


class TestListRules:
    """UC3: list_rules()."""

    def test_no_filter_returns_group_summary(self):
        result = list_rules()
        assert "groups" in result
        assert "total" in result
        assert result["total"] > 0

    def test_filter_by_group(self):
        result = list_rules(group="specialization")
        assert "rules" in result
        assert result["group"] == "specialization"
        assert result["total"] > 0
        for r in result["rules"]:
            assert r["relation"] == "specialization"

    def test_filter_by_relation(self):
        result = list_rules(relation="flow")
        assert "rules" in result
        assert result["relation"] == "flow"
        for r in result["rules"]:
            assert r["relation"] == "flow"

    def test_unknown_group_returns_error(self):
        result = list_rules(group="nonexistent")
        assert "error" in result
        assert "valid_groups" in result


class TestDescribeProfile:
    """UC2: describe_profile()."""

    def test_archimate_profile(self):
        result = describe_profile(name="ArchiMate")
        assert result is not None
        assert result["name"] == "ArchiMate"
        assert result["element_count"] > 0
        assert result["relation_count"] > 0
        assert "elements_by_layer" in result

    def test_unknown_profile_returns_none(self):
        result = describe_profile(name="NonExistent")
        assert result is None

    def test_rule_summary_has_allow_deny(self):
        result = describe_profile(name="ArchiMate")
        assert result is not None
        summary = result["rule_summary"]
        assert "allow" in summary
        assert "deny" in summary


class TestDescribeRule:
    """UC4: describe_rule()."""

    def test_existing_rule(self):
        # Get a known rule id from the list
        rules = list_rules(group="specialization")
        assert rules["total"] > 0
        rule_id = rules["rules"][0]["id"]
        result = describe_rule(rule_id=rule_id)
        assert result is not None
        assert result["id"] == rule_id
        assert "metadata" in result
        assert "group" in result["metadata"]

    def test_unknown_rule_returns_none(self):
        result = describe_rule(rule_id="nonexistent-rule-id")
        assert result is None


class TestJudge:
    """UC5: judge()."""

    def test_allow_verdict(self):
        result = judge(source="classifier", target="feature", relation="specialization")
        assert "verdict" in result
        assert "confidence" in result
        assert "evidence" in result
        assert isinstance(result["evidence"], list)
        assert len(result["evidence"]) > 0

    def test_deny_verdict(self):
        result = judge(source="feature", target="classifier", relation="specialization")
        assert "verdict" in result
        # Should have evidence either way
        assert "evidence" in result

    def test_unknown_source(self):
        result = judge(source="nonexistent", target="feature", relation="specialization")
        assert "error" in result
        assert "valid_entities" in result

    def test_unknown_target(self):
        result = judge(source="classifier", target="nonexistent", relation="specialization")
        assert "error" in result

    def test_unknown_relation(self):
        result = judge(source="classifier", target="feature", relation="nonexistent")
        assert "error" in result
        assert "valid_relations" in result

    def test_conflicts_key_present(self):
        result = judge(source="classifier", target="feature", relation="specialization")
        assert "conflicts" in result


class TestGetEntityNames:
    """Helper: get_entity_names()."""

    def test_returns_sorted_list(self):
        names = get_entity_names()
        assert len(names) > 0
        assert names == sorted(names)

    def test_contains_known_entities(self):
        names = get_entity_names()
        assert "element" in names
        assert "classifier" in names
        assert "feature" in names


class TestProfileTopology:
    """UC6: profile_topology()."""

    def test_topology_returns_nodes_and_edges(self):
        result = profile_topology(profile_name="ArchiMate")
        assert "nodes" in result
        assert "edges" in result
        assert result["node_count"] > 0
        assert result["edge_count"] > 0

    def test_cross_layer_filters_same_layer_edges(self):
        result = profile_topology(profile_name="ArchiMate", cross_layer=True)
        assert result["cross_layer"] is True
        # Build a layer lookup from the returned nodes
        layer_of = {n["name"]: n["layer"] for n in result["nodes"]}
        for edge in result["edges"]:
            src_layer = layer_of.get(edge["source"])
            tgt_layer = layer_of.get(edge["target"])
            if src_layer is not None and tgt_layer is not None:
                assert src_layer != tgt_layer

    def test_cross_layer_prunes_nodes(self):
        full = profile_topology(profile_name="ArchiMate")
        cross = profile_topology(profile_name="ArchiMate", cross_layer=True)
        assert cross["node_count"] <= full["node_count"]

    def test_unknown_profile_returns_error(self):
        result = profile_topology(profile_name="NonExistentProfile")
        assert "error" in result


class TestI18nService:
    """I18n service functions."""

    def test_audit_i18n_returns_report(self):
        result = audit_i18n(lang="ko")
        assert "lang" in result
        assert result["lang"] == "ko"
        assert "coverage" in result
        assert "total_schema_items" in result
        assert "total_translated" in result
        assert "is_clean" in result
        assert isinstance(result["missing"], list)
        assert isinstance(result["orphan"], list)
        assert isinstance(result["stale"], list)

    def test_audit_i18n_ko_has_full_coverage(self):
        result = audit_i18n(lang="ko")
        assert result["total_translated"] == result["total_schema_items"]
        assert result["coverage"] == 1.0

    def test_audit_i18n_unknown_lang(self):
        result = audit_i18n(lang="xx")
        assert result["lang"] == "xx"
        assert result["coverage"] == 0.0
        assert result["total_translated"] == 0
