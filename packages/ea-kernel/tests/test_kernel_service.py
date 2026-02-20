"""Tests for kernel_service — onboarding use case service layer."""

from __future__ import annotations

import ea_kernel.kernel_service as kernel_service_module

from ea_kernel.kernel_service import (
    audit_i18n,
    audit_profile_i18n,
    describe_profile,
    describe_rule,
    get_entity_names,
    judge,
    list_entities,
    list_relations,
    list_rules,
    profile_composed_topology,
    profile_projection,
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

    def test_easystem_kernel_profile_ko_relation_display_names_are_localized(self):
        result = describe_profile(name="EASystem-Kernel", lang="ko")
        assert result is not None
        relation_map = {
            rel["name"]: rel.get("display_name")
            for rel in result["relations"]
        }
        contains_name = relation_map.get("contains")
        assert isinstance(contains_name, dict)
        assert contains_name.get("ko") == "포함"


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

    def test_topology_edges_include_rule_provenance(self):
        result = profile_topology(profile_name="EASystem-Kernel", view_mode="raw", include_rule_provenance=True)
        assert result["edges"], "expected non-empty topology edges"
        first = result["edges"][0]
        assert "rule_ref" in first
        assert first["rule_ref"]["profile"] == "EASystem-Kernel"
        assert first["rule_ref"]["rule_id"]
        assert first["rule_ref"]["source_pattern"] is not None
        assert first["rule_ref"]["target_pattern"] is not None

    def test_topology_summary_edges_include_rule_ref_samples(self):
        result = profile_topology(profile_name="EASystem-Kernel", view_mode="summary", include_rule_provenance=True)
        assert result["edges"], "expected non-empty summary topology edges"
        first = result["edges"][0]
        assert "rule_refs" in first
        assert isinstance(first["rule_refs"], list)
        if first["rule_refs"]:
            assert first["rule_refs"][0]["profile"] == "EASystem-Kernel"

    def test_topology_domain_scope_filters_bridge_edges(self):
        all_scope = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="summary",
            domain_scope="all",
        )
        bridge_scope = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="summary",
            domain_scope="bridge",
        )
        owned_scope = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="summary",
            domain_scope="owned",
        )
        assert all_scope["domain_view"]["scope"] == "all"
        assert bridge_scope["domain_view"]["scope"] == "bridge"
        assert owned_scope["domain_view"]["scope"] == "owned"
        assert bridge_scope["edge_count"] <= all_scope["edge_count"]
        assert owned_scope["edge_count"] <= all_scope["edge_count"]
        assert (
            bridge_scope["domain_view"]["stats"]["bridge_edges"]
            + bridge_scope["domain_view"]["stats"]["owned_edges"]
            == bridge_scope["domain_view"]["stats"]["edges_before_scope"]
        )

    def test_summary_view_mode_aggregates_rule_edges(self):
        raw = profile_topology(profile_name="ArchiMate", view_mode="raw")
        summary = profile_topology(profile_name="ArchiMate", view_mode="summary")
        assert summary["view_mode"] == "summary"
        assert summary["edge_total_raw"] == raw["edge_count"]
        assert summary["edge_count"] <= raw["edge_count"]
        assert all(int(edge.get("rule_count", 1)) >= 1 for edge in summary["edges"])

    def test_summary_view_mode_respects_max_edges(self):
        summary = profile_topology(profile_name="ArchiMate", view_mode="summary", max_edges=10)
        assert summary["edge_count"] <= 10
        assert summary["edge_truncated"] is True
        assert summary["edge_total_before_cap"] >= summary["edge_count"]

    def test_surface_only_filters_non_focus_relations(self):
        filtered = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="summary",
            surface_only=True,
        )
        assert "error" not in filtered
        assert filtered["surface_filter"]["enabled"] is True
        assert filtered["surface_filter"]["applied"] is True
        visible = set(filtered["surface_filter"]["visible_relations"])
        assert visible
        assert all(edge["relation"] in visible for edge in filtered["edges"])

    def test_surface_only_ignored_in_focus_mode(self):
        focused = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="focus",
            focus="actor",
            focus_actor="ModelExplorerContext",
            surface_only=True,
        )
        assert "error" not in focused
        assert focused["surface_filter"]["enabled"] is True
        assert focused["surface_filter"]["applied"] is False

    def test_focus_view_mode_core_returns_focus_payload(self):
        raw = profile_topology(profile_name="ArchiMate", view_mode="raw")
        focus = profile_topology(profile_name="ArchiMate", view_mode="focus", focus="core")
        assert focus["view_mode"] == "focus"
        assert focus["focus"]["mode"] == "core"
        assert focus["edge_count"] <= raw["edge_count"]
        assert set(focus["focus"]["selected_relations"]).issubset(
            {"contains", "depends_on", "next", "triggers", "constrains"},
        )
        assert "visibility_profile" in focus["focus"]
        assert "visible_relations" in focus["focus"]
        assert "hidden_relations" in focus["focus"]

    def test_focus_view_mode_relation_filters_edges(self):
        raw = profile_topology(profile_name="ArchiMate", view_mode="raw")
        assert raw["edges"], "expected non-empty topology edges"
        relation = raw["edges"][0]["relation"]
        focus = profile_topology(
            profile_name="ArchiMate",
            view_mode="focus",
            focus="relation",
            focus_relation=relation,
        )
        assert focus["view_mode"] == "focus"
        assert focus["focus"]["mode"] == "relation"
        assert focus["focus"]["relation"] == relation
        assert all(edge["relation"] == relation for edge in focus["edges"])

    def test_focus_view_mode_layer_filters_edges(self):
        raw = profile_topology(profile_name="ArchiMate", view_mode="raw")
        assert raw["edges"], "expected non-empty topology edges"
        layer_of = {node["name"]: node["layer"] for node in raw["nodes"]}
        sample_edge = raw["edges"][0]
        layer = layer_of[sample_edge["source"]]
        focus = profile_topology(
            profile_name="ArchiMate",
            view_mode="focus",
            focus="layer",
            focus_layer=layer,
        )
        assert focus["view_mode"] == "focus"
        assert focus["focus"]["mode"] == "layer"
        assert focus["focus"]["layer"] == layer
        assert focus["edge_count"] > 0
        focus_layer_of = {node["name"]: node["layer"] for node in focus["nodes"]}
        assert all(
            focus_layer_of.get(edge["source"]) == layer
            or focus_layer_of.get(edge["target"]) == layer
            for edge in focus["edges"]
        )

    def test_focus_view_mode_actor_filters_to_actor_interaction_scope(self):
        focus = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="focus",
            focus="actor",
            focus_actor="ModelExplorerContext",
            focus_depth=4,
        )
        assert focus["view_mode"] == "focus"
        assert focus["focus"]["mode"] == "actor"
        assert focus["focus"]["actor"] == "ModelExplorerContext"
        assert focus["focus"]["actor_depth"] == 4
        assert "actor_candidates" in focus["focus"]
        assert any(node["name"] == "ModelExplorerContext" for node in focus["nodes"])
        selected = set(focus["focus"]["selected_relations"])
        assert selected
        assert all(edge["relation"] in selected for edge in focus["edges"])

    def test_focus_view_mode_actor_rejects_unknown_actor(self):
        focus = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="focus",
            focus="actor",
            focus_actor="NonExistentActor",
        )
        assert "error" in focus
        assert "available_actors" in focus

    def test_focus_view_mode_actor_without_seed_prefers_connected_candidate(self):
        for profile_name in ("EASystem-Infra", "EASystem-Governance", "EASystem-Needs"):
            focus = profile_topology(
                profile_name=profile_name,
                view_mode="focus",
                focus="actor",
                focus_depth=4,
                max_edges=260,
            )
            assert "error" not in focus
            assert focus["edge_count"] > 0
            actor_name = str(focus["focus"]["actor"])
            candidate_map = {
                str(item.get("name", "")): item
                for item in focus["focus"]["actor_candidates"]
            }
            assert actor_name in candidate_map
            assert int(candidate_map[actor_name].get("interaction_degree", 0)) > 0

    def test_focus_view_mode_topic_filters_to_topic_scope(self):
        focus = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="focus",
            focus="topic",
            focus_topic="ModelExplorer",
            focus_depth=2,
        )
        assert "error" not in focus
        assert focus["view_mode"] == "focus"
        assert focus["focus"]["mode"] == "topic"
        assert focus["focus"]["topic"] == "ModelExplorer"
        assert focus["focus"]["topic_depth"] == 2
        assert focus["focus"]["topic_seeds"]
        selected = set(focus["focus"]["selected_relations"])
        assert selected
        assert all(edge["relation"] in selected for edge in focus["edges"])

    def test_focus_view_mode_topic_uses_toml_policy_defaults(self):
        focus = profile_topology(
            profile_name="EASystem-Kernel",
            view_mode="focus",
            focus="topic",
            focus_topic="ModelExplorer",
        )
        assert "error" not in focus
        assert focus["focus"]["topic_depth"] == 2
        policy = focus["focus"].get("topic_policy", {})
        assert policy.get("default_depth") == 2
        assert policy.get("max_scope_nodes_per_depth") == 48
        assert policy.get("max_match_count") == 20

    def test_focus_view_mode_topic_uses_infra_layer_override(self):
        focus = profile_topology(
            profile_name="EASystem-Infra",
            view_mode="focus",
            focus="topic",
            focus_topic="Infra",
        )
        assert "error" not in focus
        policy = focus["focus"].get("topic_policy", {})
        assert policy.get("max_scope_nodes_per_depth") == 28
        assert policy.get("max_seed_count") == 6
        assert policy.get("max_match_count") == 12
        assert policy.get("min_token_coverage") == 0.6

    def test_focus_view_mode_topic_uses_fallback_policy_on_non_kernel_layer(self):
        focus = profile_topology(
            profile_name="EASystem-Needs",
            view_mode="focus",
            focus="topic",
            focus_topic="Need",
        )
        assert "error" not in focus
        policy = focus["focus"].get("topic_policy", {})
        assert policy.get("max_scope_nodes_per_depth") == 40

    def test_focus_view_mode_rejects_invalid_focus_mode(self):
        focus = profile_topology(profile_name="ArchiMate", view_mode="focus", focus="invalid")
        assert "error" in focus


class TestProfileProjection:
    """Projection-layer API helpers."""

    def test_projection_default_level_l0(self):
        result = profile_projection(profile_name="EASystem-Kernel")
        assert "projection" in result
        assert result["projection"]["level"] == "L0"
        assert result["projection"]["lens"] == "panorama"
        assert result["projection"]["filters"]["domain_scope"] in {"all", "owned", "bridge"}
        assert result["node_count"] > 0
        assert result["edge_count"] > 0
        assert result["edge_count"] <= result["projection"]["budget"]["effective_max_edges"]

    def test_projection_l2_actor_seed(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l2",
            actor="ModelExplorerContext",
            depth=4,
        )
        assert "projection" in result
        assert result["projection"]["level"] == "L2"
        seed = result["projection"].get("seed")
        assert isinstance(seed, dict)
        assert seed["actor"] == "ModelExplorerContext"

    def test_projection_uses_toml_layer_policy_override(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l2",
            actor="ModelExplorerContext",
            depth=4,
        )
        assert "projection" in result
        projection = result["projection"]
        assert projection["policy"]["source"] == "toml"
        assert projection["policy"]["scope"] == "layer:kernel"
        assert projection["budget"]["default_max_edges"] == 620
        assert projection["budget"]["effective_max_edges"] == 620

    def test_projection_includes_reduction_explainability_metadata(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l2",
            actor="ModelExplorerContext",
            depth=4,
        )
        assert "projection" in result
        reduction = result["projection"].get("reduction")
        assert isinstance(reduction, dict)

        nodes = reduction.get("nodes")
        assert isinstance(nodes, dict)
        assert nodes["source"] >= nodes["projected"] >= 0
        assert 0.0 <= nodes["ratio"] <= 1.0

        edges = reduction.get("edges")
        assert isinstance(edges, dict)
        assert edges["source"] >= edges["projected"] >= 0
        assert edges["source_raw"] >= edges["source"] >= 0
        assert edges["before_cap"] >= edges["projected"] >= 0
        assert 0.0 <= edges["ratio"] <= 1.0
        assert 0.0 <= edges["raw_ratio"] <= 1.0

        stages = reduction.get("stages")
        assert isinstance(stages, dict)
        assert stages["edge_input"] >= stages["edge_after_node_scope"] >= stages["edge_after_relation"] >= stages["edge_after_cap"]

        drop_reasons = reduction.get("drop_reasons")
        assert isinstance(drop_reasons, dict)
        assert drop_reasons["edge_relation_filtered"] >= 0
        assert drop_reasons["edge_node_scope_filtered"] >= 0

        preserve = reduction.get("preserve")
        assert isinstance(preserve, dict)
        assert preserve["requested"] >= preserve["matched"] >= 0
        assert preserve["retained"] >= 0

    def test_projection_reduction_cap_drop_matches_edge_totals(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            max_edges=20,
        )
        assert "projection" in result
        reduction = result["projection"].get("reduction")
        assert isinstance(reduction, dict)
        drop_reasons = reduction.get("drop_reasons")
        assert isinstance(drop_reasons, dict)
        # Supplementary edges from extensions are added after the cap stage,
        # so subtract them to get the true capped count.
        extensions = result["projection"].get("extensions", {})
        supplementary_total = sum(
            ext.get("supplementary_edges", 0) for ext in extensions.values()
        )
        assert drop_reasons["edge_capped"] == result["edge_total_before_cap"] - (result["edge_count"] - supplementary_total)

    def test_projection_policy_fail_fast_on_invalid_contract(self, monkeypatch):
        import ea_projection.policy.resolver as resolver_module

        def fake_policy_loader(policy_path):
            return {
                "status": "ok",
                "path": "/tmp/projection_policy.toml",
                "document": {
                    "m2": {
                        "schema": {
                            "levels": ["l0"],
                            "lenses": ["panorama"],
                            "base_view_modes": ["summary"],
                            "focus_modes": ["actor"],
                            "required_level_fields": ["level", "lens", "default_max_edges"],
                            "lens_to_level": {
                                "panorama": "l9",
                            },
                        },
                        "defaults": {"actor_default_depth": 0},
                    },
                    "m1": {
                        "global": {
                            "levels": {
                                "l0": {
                                    "level": "L0",
                                    "lens": "panorama",
                                    "default_max_edges": -1,
                                },
                            },
                        },
                    },
                },
            }

        kernel_service_module._resolve_projection_policy.cache_clear()
        resolver_module.resolve_projection_policy.cache_clear()
        monkeypatch.setattr(resolver_module, "load_projection_policy_document", fake_policy_loader)

        result = kernel_service_module.profile_projection(profile_name="EASystem-Kernel", level="l0")

        assert "error" in result
        assert result["error"] == "Projection policy contract validation failed"
        policy_error = result.get("policy_error")
        assert isinstance(policy_error, dict)
        assert policy_error.get("status") == "invalid_contract"
        issues = policy_error.get("issues")
        assert isinstance(issues, list)
        assert len(issues) > 0

        kernel_service_module._resolve_projection_policy.cache_clear()
        resolver_module.resolve_projection_policy.cache_clear()

    def test_projection_rejects_invalid_level(self):
        result = profile_projection(profile_name="EASystem-Kernel", level="l9")
        assert "error" in result
        assert "valid_levels" in result

    # --- Tier tests ---

    def test_projection_tier_ui_filters_categories(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            tier="ui",
        )
        assert "error" not in result
        assert "projection" in result
        tier_meta = result["projection"].get("tier")
        assert isinstance(tier_meta, dict)
        assert tier_meta["name"] == "ui"
        assert set(tier_meta["categories"]) == {"Page", "Interface", "Context"}
        # All returned nodes must be in ui tier categories
        for node in result.get("nodes", []):
            assert node["category"] in {"Page", "Interface", "Context"}, (
                f"Node {node['name']} has category {node['category']} not in ui tier"
            )

    def test_projection_tier_function(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            tier="function",
        )
        assert "error" not in result
        tier_meta = result["projection"].get("tier")
        assert isinstance(tier_meta, dict)
        assert tier_meta["name"] == "function"
        allowed = {"ActiveStructure", "Behavior", "Executable", "Governance"}
        for node in result.get("nodes", []):
            assert node["category"] in allowed, (
                f"Node {node['name']} has category {node['category']} not in function tier"
            )

    def test_projection_tier_evidence_name_pattern(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            tier="evidence",
        )
        assert "error" not in result
        tier_meta = result["projection"].get("tier")
        assert isinstance(tier_meta, dict)
        assert tier_meta["name"] == "evidence"
        evidence_patterns = {"evidence", "provenance", "rationale", "audit", "analysisreport", "compliance"}
        for node in result.get("nodes", []):
            assert node["category"] == "PassiveStructure", (
                f"Evidence node {node['name']} has wrong category {node['category']}"
            )
            name_lower = node["name"].lower()
            assert any(pat in name_lower for pat in evidence_patterns), (
                f"Evidence node {node['name']} doesn't match evidence name patterns"
            )

    def test_projection_tier_data_excludes_evidence(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            tier="data",
        )
        assert "error" not in result
        tier_meta = result["projection"].get("tier")
        assert isinstance(tier_meta, dict)
        assert tier_meta["name"] == "data"
        evidence_patterns = {"evidence", "provenance", "rationale", "audit", "analysisreport", "compliance"}
        for node in result.get("nodes", []):
            name_lower = node["name"].lower()
            if node["category"] == "PassiveStructure":
                assert not any(pat in name_lower for pat in evidence_patterns), (
                    f"Data tier should exclude evidence-patterned node: {node['name']}"
                )

    def test_projection_tier_overrides_level_categories(self):
        # L0 normally only shows 6 categories; tier=function should show its own set
        result_l0_no_tier = profile_projection(
            profile_name="EASystem-Kernel",
            level="l0",
        )
        result_l0_with_tier = profile_projection(
            profile_name="EASystem-Kernel",
            level="l0",
            tier="function",
        )
        assert "error" not in result_l0_no_tier
        assert "error" not in result_l0_with_tier
        # With tier, the category filter should come from the tier definition
        tier_meta = result_l0_with_tier["projection"].get("tier")
        assert isinstance(tier_meta, dict)
        assert tier_meta["name"] == "function"

    def test_projection_tier_next_tiers(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            tier="ui",
        )
        assert "error" not in result
        tier_meta = result["projection"].get("tier")
        assert isinstance(tier_meta, dict)
        next_tiers = tier_meta.get("next_tiers", [])
        assert isinstance(next_tiers, list)
        assert "function" in next_tiers
        valid_tiers = {"ui", "function", "data", "decision", "evidence"}
        for t in next_tiers:
            assert t in valid_tiers, f"Invalid next_tier: {t}"

    def test_projection_invalid_tier(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l0",
            tier="nonexistent_tier",
        )
        assert "error" in result
        assert "valid_tiers" in result

    # --- Seed tests ---

    def test_projection_seed_element_bfs(self):
        # First get a known element name from l4
        base = profile_projection(profile_name="EASystem-Kernel", level="l4")
        assert "error" not in base
        assert base["nodes"], "expected nodes from l4"
        sample_name = base["nodes"][0]["name"]

        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            seed=sample_name,
            depth=1,
        )
        assert "error" not in result
        assert result["node_count"] <= base["node_count"]
        seed_meta = result["projection"].get("seed")
        assert isinstance(seed_meta, dict)
        assert seed_meta["element"] == sample_name
        assert seed_meta["depth"] == 1
        assert seed_meta["scope_size"] >= 1

    def test_projection_seed_plus_tier(self):
        base = profile_projection(profile_name="EASystem-Kernel", level="l4")
        assert "error" not in base
        assert base["nodes"]
        sample_name = base["nodes"][0]["name"]

        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l4",
            seed=sample_name,
            depth=2,
            tier="function",
        )
        assert "error" not in result
        # Should have both tier and seed metadata
        assert result["projection"].get("tier") is not None
        assert result["projection"].get("seed") is not None

    def test_projection_invalid_seed(self):
        result = profile_projection(
            profile_name="EASystem-Kernel",
            level="l0",
            seed="__nonexistent_element__",
        )
        assert "error" in result
        assert "available_elements" in result or "seed" in str(result["error"]).lower()

    def test_tier_definitions_in_policy(self):
        from ea_kernel.kernel_service import (
            _resolve_tier_definitions,
            _resolve_projection_policy,
        )
        policy = _resolve_projection_policy("EASystem-Kernel")
        tier_defs = _resolve_tier_definitions(policy)
        assert len(tier_defs) == 5
        assert set(tier_defs.keys()) == {"ui", "function", "data", "decision", "evidence"}
        for tier_name, tier_def in tier_defs.items():
            assert tier_def["categories"], f"Tier {tier_name} has empty categories"
            assert isinstance(tier_def["transitions"], list)


class TestProfileComposedTopology:
    """Cross-profile composed M1 topology helpers."""

    def test_composed_topology_contains_composition_metadata(self):
        result = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="owned",
            max_edges=320,
        )
        assert "error" not in result
        composition = result["composition"]
        assert composition["anchor_profile"] == "EASystem-Kernel"
        assert composition["anchor_layer_key"] == "kernel"
        assert composition["source_profile_count"] >= 1
        assert "EASystem-Kernel" in composition["included_profiles"]
        assert result["edge_count"] <= 320

    def test_composed_topology_edges_keep_rule_profile_provenance(self):
        result = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            max_edges=240,
            include_rule_provenance=True,
        )
        assert "error" not in result
        assert result["edges"], "expected composed edges"
        first = result["edges"][0]
        refs = first.get("rule_refs", [])
        assert isinstance(refs, list)
        assert refs, "expected rule_refs on composed edge"
        assert all(ref.get("profile") for ref in refs)

    def test_composed_topology_rejects_invalid_domain_scope(self):
        result = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="invalid",
        )
        assert "error" in result
        assert "valid_domain_scopes" in result

    def test_composed_topology_unknown_anchor_returns_error(self):
        result = profile_composed_topology(profile_name="NonExistentProfile")
        assert "error" in result

    def test_composed_topology_focus_relation_filters_edges(self):
        base = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            max_edges=320,
        )
        assert "error" not in base
        assert base["edges"], "expected composed edges"
        relation = base["edges"][0]["relation"]

        focused = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            focus="relation",
            focus_relation=relation,
            max_edges=320,
        )
        assert "error" not in focused
        assert focused["view_mode"] == "focus"
        assert focused["focus"]["mode"] == "relation"
        assert focused["focus"]["relation"] == relation
        assert all(edge["relation"] == relation for edge in focused["edges"])

    def test_composed_topology_focus_actor_filters_interaction_scope(self):
        focused = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            focus="actor",
            focus_actor="ModelExplorerContext",
            focus_depth=4,
            max_edges=360,
        )
        assert "error" not in focused
        assert focused["view_mode"] == "focus"
        assert focused["focus"]["mode"] == "actor"
        assert focused["focus"]["actor"] == "ModelExplorerContext"
        assert focused["focus"]["actor_depth"] == 4
        selected = set(focused["focus"]["selected_relations"])
        assert selected
        assert all(edge["relation"] in selected for edge in focused["edges"])

    def test_composed_topology_focus_core_includes_actor_candidates(self):
        focused = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            focus="core",
            max_edges=320,
        )
        assert "error" not in focused
        assert focused["view_mode"] == "focus"
        assert focused["focus"]["mode"] == "core"
        assert "actor_candidates" in focused["focus"]
        assert isinstance(focused["focus"]["actor_candidates"], list)

    def test_composed_topology_surface_only_filters_non_focus_relations(self):
        result = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            surface_only=True,
            max_edges=320,
        )
        assert "error" not in result
        assert result["surface_filter"]["enabled"] is True
        assert result["surface_filter"]["applied"] is True
        visible = set(result["surface_filter"]["visible_relations"])
        assert visible
        assert all(edge["relation"] in visible for edge in result["edges"])

    def test_composed_topology_focus_topic_filters_to_topic_scope(self):
        focused = profile_composed_topology(
            profile_name="EASystem-Kernel",
            domain_scope="all",
            focus="topic",
            focus_topic="ModelExplorer",
            focus_depth=2,
            max_edges=320,
        )
        assert "error" not in focused
        assert focused["view_mode"] == "focus"
        assert focused["focus"]["mode"] == "topic"
        assert focused["focus"]["topic"] == "ModelExplorer"
        assert focused["focus"]["topic_depth"] == 2
        assert focused["focus"]["topic_seeds"]
        selected = set(focused["focus"]["selected_relations"])
        assert selected
        assert all(edge["relation"] in selected for edge in focused["edges"])

    def test_composed_topology_focus_rejects_invalid_args(self):
        invalid_focus = profile_composed_topology(
            profile_name="EASystem-Kernel",
            focus="invalid",
        )
        assert "error" in invalid_focus

        missing_focus_relation = profile_composed_topology(
            profile_name="EASystem-Kernel",
            focus="relation",
        )
        assert "error" in missing_focus_relation

        missing_focus_topic = profile_composed_topology(
            profile_name="EASystem-Kernel",
            focus="topic",
        )
        assert "error" in missing_focus_topic

        focus_param_without_mode = profile_composed_topology(
            profile_name="EASystem-Kernel",
            focus_relation="contains",
        )
        assert "error" in focus_param_without_mode


class TestI18nService:
    """I18n service functions."""

    def test_audit_i18n_returns_report(self):
        result = audit_i18n(lang="ko")
        assert "lang" in result
        assert result["lang"] == "ko"
        assert result["scope"] == "m2"
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

    def test_audit_profile_i18n_returns_report(self):
        result = audit_profile_i18n(name="EASystem-Kernel", lang="ko")
        assert result["scope"] == "m1"
        assert result["profile"] == "EASystem-Kernel"
        assert result["lang"] == "ko"
        assert "total_schema_items" in result
        assert "total_translated" in result
        assert "missing_count" in result
        assert "orphan_count" in result
        assert "stale_count" in result
        assert isinstance(result["missing"], list)
        if result["missing"]:
            first = result["missing"][0]
            assert "identifier" in first
            assert first["identifier"].startswith("m1:EASystem-Kernel:")

    def test_audit_profile_i18n_unknown_profile(self):
        result = audit_profile_i18n(name="NonExistentProfile", lang="ko")
        assert "error" in result
