"""Cross-profile integration tests.

Validates that all EA System layer profiles load correctly via their
respective M1 pipelines (schema → condition_registry → profile_bridge)
and share consistent structural conventions.
"""

from __future__ import annotations

import pytest

from ea_kernel.profiles.ea_sys import PROFILE_DIR, LAYER_FILE_MAP
from ea_kernel.spec import KERNEL_SPEC
from ea_profile.loader import load_profile
from ea_profile.types import KernelProfile

# ── Core layers (exclude web-kernel-viz for M1 pipeline tests) ──

CORE_LAYERS = ("infra", "governance", "decision", "needs", "kernel", "flow")
MODEL_PORT_NAMES = {
    "InfraModelPort", "GovernanceModelPort", "DecisionModelPort",
    "NeedsModelPort", "KernelModelPort", "FlowModelPort",
}

# 10 shared relations across ea_sys profiles
SHARED_RELATIONS = {
    "contains", "registers", "coordinates", "depends_on",
    "produces", "consumes", "next", "triggers",
    "constrains", "available_in",
}


# ── Module-scoped fixtures (cache profile loading) ──

@pytest.fixture(scope="module")
def loaded_profiles() -> dict[str, KernelProfile]:
    """Load all 6 core ea_sys profiles once."""
    profiles = {}
    for layer in CORE_LAYERS:
        path = PROFILE_DIR / LAYER_FILE_MAP[layer]
        profiles[layer] = load_profile(path, KERNEL_SPEC)
    return profiles


# ============================================================
# Group 1 — Profile Loading
# ============================================================

class TestProfileLoading:
    """All 6 core ea_sys profiles load via load_profile(path, KERNEL_SPEC)."""

    @pytest.mark.parametrize("layer", CORE_LAYERS)
    def test_load_profile_succeeds(self, loaded_profiles, layer):
        profile = loaded_profiles[layer]
        assert isinstance(profile, KernelProfile)
        assert profile.name == "EASystemLayerModel"

    def test_needs_bridge_loading(self):
        """Needs bridge loads ea_sys profile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_needs.profile_bridge import load_needs_profile
        path = PROFILE_DIR / LAYER_FILE_MAP["needs"]
        profile = load_needs_profile(path, validate=False)
        assert isinstance(profile, KernelProfile)

    def test_governance_bridge_loading(self):
        """Governance bridge loads ea_sys profile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_governance.profile_bridge import load_governance_profile
        path = PROFILE_DIR / LAYER_FILE_MAP["governance"]
        profile = load_governance_profile(path, validate=False)
        assert isinstance(profile, KernelProfile)

    def test_decision_bridge_loading(self):
        """Decision bridge loads ea_sys profile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_decision.profile_bridge import load_decision_profile
        path = PROFILE_DIR / LAYER_FILE_MAP["decision"]
        profile = load_decision_profile(path, validate=False)
        assert isinstance(profile, KernelProfile)

    def test_flow_bridge_loading(self):
        """Flow bridge loads ea_sys profile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_flow.profile_bridge import load_flow_profile
        path = PROFILE_DIR / LAYER_FILE_MAP["flow"]
        profile = load_flow_profile(path, validate=False)
        assert isinstance(profile, KernelProfile)

    def test_infra_bridge_loading(self):
        """Infra bridge loads ea_sys profile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_infra.profile_bridge import load_infra_profile
        path = PROFILE_DIR / LAYER_FILE_MAP["infra"]
        profile = load_infra_profile(path, validate=False)
        assert isinstance(profile, KernelProfile)

    def test_all_profiles_share_10_relations(self, loaded_profiles):
        """Every core profile defines the same 10 relation names."""
        for layer, profile in loaded_profiles.items():
            rel_names = {r.name for r in profile.relations}
            assert rel_names == SHARED_RELATIONS, (
                f"{layer} relations {rel_names} != expected {SHARED_RELATIONS}"
            )


# ============================================================
# Group 2 — Rule Compilation
# ============================================================

class TestRuleCompilation:
    """compile_profile_rules_for_runtime succeeds for all core layers."""

    @pytest.mark.parametrize("layer", CORE_LAYERS)
    def test_compile_rules(self, loaded_profiles, layer):
        from ea_kernel.profile_rule_compiler import compile_profile_rules_for_runtime

        profile = loaded_profiles[layer]
        result = compile_profile_rules_for_runtime(profile)
        assert result.stats.source_rule_count > 0
        assert result.stats.compiled_rule_count >= result.stats.source_rule_count


# ============================================================
# Group 3 — Cross-Profile Consistency
# ============================================================

class TestCrossProfileConsistency:
    """Structural consistency across all core profiles."""

    def test_all_profiles_have_6_model_ports(self, loaded_profiles):
        """Each profile contains all 6 ModelPort elements."""
        for layer, profile in loaded_profiles.items():
            element_names = {e.name for e in profile.elements}
            missing = MODEL_PORT_NAMES - element_names
            assert not missing, f"{layer} missing ModelPort elements: {missing}"

    def test_model_port_category_is_interface(self, loaded_profiles):
        """ModelPort elements always have category='Interface'."""
        for layer, profile in loaded_profiles.items():
            for elem in profile.elements:
                if elem.name in MODEL_PORT_NAMES:
                    assert elem.category == "Interface", (
                        f"{layer}/{elem.name} category={elem.category}, expected Interface"
                    )

    def test_model_port_layer_assignment_consistent(self, loaded_profiles):
        """ModelPort layer assignments are consistent across profiles."""
        expected_layers = {
            "InfraModelPort": "Infra",
            "GovernanceModelPort": "Governance",
            "DecisionModelPort": "Decision",
            "NeedsModelPort": "Needs",
            "KernelModelPort": "Kernel",
            "FlowModelPort": "Flow",
        }
        for layer, profile in loaded_profiles.items():
            for elem in profile.elements:
                if elem.name in expected_layers:
                    assert elem.layer == expected_layers[elem.name], (
                        f"{layer}/{elem.name} layer={elem.layer}, "
                        f"expected {expected_layers[elem.name]}"
                    )

    def test_shared_element_category_consistency(self, loaded_profiles):
        """Elements appearing in multiple profiles have consistent category."""
        element_categories: dict[str, dict[str, str]] = {}
        for layer, profile in loaded_profiles.items():
            for elem in profile.elements:
                element_categories.setdefault(elem.name, {})[layer] = elem.category

        for elem_name, layer_cats in element_categories.items():
            if len(layer_cats) > 1:
                cats = set(layer_cats.values())
                assert len(cats) == 1, (
                    f"Element '{elem_name}' has inconsistent categories: {layer_cats}"
                )

    def test_relation_kernel_mapping_consistent(self, loaded_profiles):
        """The 10 shared relation kernel_relation mappings are identical across profiles."""
        relation_mappings: dict[str, dict[str, str]] = {}
        for layer, profile in loaded_profiles.items():
            for rel in profile.relations:
                if rel.name in SHARED_RELATIONS:
                    relation_mappings.setdefault(rel.name, {})[layer] = rel.kernel_relation

        for rel_name, layer_mappings in relation_mappings.items():
            mappings = set(layer_mappings.values())
            assert len(mappings) == 1, (
                f"Relation '{rel_name}' has inconsistent kernel_relation: {layer_mappings}"
            )


# ============================================================
# Group 4 — Pipeline Smoke
# ============================================================

class TestPipelineSmoke:
    """Full pipeline smoke tests: load → compile → verify rule counts."""

    def test_needs_pipeline(self):
        """Needs bridge load → compile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_needs.profile_bridge import load_needs_profile
        from ea_kernel.profile_rule_compiler import compile_profile_rules_for_runtime

        profile = load_needs_profile(PROFILE_DIR / LAYER_FILE_MAP["needs"], validate=False)
        result = compile_profile_rules_for_runtime(profile)
        assert result.stats.source_rule_count > 0
        assert result.stats.compiled_rule_count >= result.stats.source_rule_count

    def test_governance_pipeline(self):
        """Governance bridge load → compile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_governance.profile_bridge import load_governance_profile
        from ea_kernel.profile_rule_compiler import compile_profile_rules_for_runtime

        profile = load_governance_profile(PROFILE_DIR / LAYER_FILE_MAP["governance"], validate=False)
        result = compile_profile_rules_for_runtime(profile)
        assert result.stats.source_rule_count > 0
        assert result.stats.compiled_rule_count >= result.stats.source_rule_count

    def test_decision_pipeline(self):
        """Decision bridge load → compile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_decision.profile_bridge import load_decision_profile
        from ea_kernel.profile_rule_compiler import compile_profile_rules_for_runtime

        profile = load_decision_profile(PROFILE_DIR / LAYER_FILE_MAP["decision"], validate=False)
        result = compile_profile_rules_for_runtime(profile)
        assert result.stats.source_rule_count > 0
        assert result.stats.compiled_rule_count >= result.stats.source_rule_count

    def test_flow_pipeline(self):
        """Flow bridge load → compile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_flow.profile_bridge import load_flow_profile
        from ea_kernel.profile_rule_compiler import compile_profile_rules_for_runtime

        profile = load_flow_profile(PROFILE_DIR / LAYER_FILE_MAP["flow"], validate=False)
        result = compile_profile_rules_for_runtime(profile)
        assert result.stats.source_rule_count > 0
        assert result.stats.compiled_rule_count >= result.stats.source_rule_count

    def test_infra_pipeline(self):
        """Infra bridge load → compile (validate=False: ea_sys uses kernel vocabulary)."""
        from ea_infra.profile_bridge import load_infra_profile
        from ea_kernel.profile_rule_compiler import compile_profile_rules_for_runtime

        profile = load_infra_profile(PROFILE_DIR / LAYER_FILE_MAP["infra"], validate=False)
        result = compile_profile_rules_for_runtime(profile)
        assert result.stats.source_rule_count > 0
        assert result.stats.compiled_rule_count >= result.stats.source_rule_count


# ============================================================
# Group 5 — Condition Registry
# ============================================================

class TestConditionRegistry:
    """Layer condition registries correctly extend kernel defaults."""

    def test_kernel_default_count(self):
        from ea_profile.types import ConditionRegistry

        reg = ConditionRegistry.kernel_default()
        assert len(reg._map) == 5

    def test_needs_condition_count(self):
        from ea_needs.condition_registry import needs_condition_registry

        reg = needs_condition_registry()
        assert len(reg._map) == 9  # 5 kernel + 4 needs

    def test_governance_condition_count(self):
        from ea_governance.condition_registry import governance_condition_registry

        reg = governance_condition_registry()
        assert len(reg._map) == 8  # 5 kernel + 3 unique governance (SAME_LAYER overlaps)

    def test_decision_condition_count(self):
        from ea_decision.condition_registry import decision_condition_registry

        reg = decision_condition_registry()
        assert len(reg._map) == 10  # 5 kernel + 5 decision

    def test_flow_condition_count(self):
        from ea_flow.condition_registry import flow_condition_registry

        reg = flow_condition_registry()
        assert len(reg._map) == 9  # 5 kernel + 4 flow

    def test_infra_condition_count(self):
        from ea_infra.condition_registry import infra_condition_registry

        reg = infra_condition_registry()
        assert len(reg._map) == 8  # 5 kernel + 3 infra

    def test_kernel_defaults_preserved_in_layer_registries(self):
        from ea_profile.types import ConditionRegistry
        from ea_needs.condition_registry import needs_condition_registry
        from ea_governance.condition_registry import governance_condition_registry
        from ea_decision.condition_registry import decision_condition_registry
        from ea_flow.condition_registry import flow_condition_registry
        from ea_infra.condition_registry import infra_condition_registry

        kernel_reg = ConditionRegistry.kernel_default()
        kernel_keys = set(kernel_reg._map.keys())

        for name, factory in [
            ("needs", needs_condition_registry),
            ("governance", governance_condition_registry),
            ("decision", decision_condition_registry),
            ("flow", flow_condition_registry),
            ("infra", infra_condition_registry),
        ]:
            layer_reg = factory()
            for key in kernel_keys:
                assert key in layer_reg._map, (
                    f"{name} registry missing kernel default key: {key}"
                )
                assert layer_reg._map[key] == kernel_reg._map[key], (
                    f"{name} registry has different value for kernel key: {key}"
                )
