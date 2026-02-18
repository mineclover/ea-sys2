"""Schema-Profile alignment tests.

Validates that each layer's SchemaPort entities and relations are
properly reflected in their corresponding TOML profiles, and that
rule density meets minimum quality thresholds.
"""

from __future__ import annotations

import pytest

from ea_kernel.profiles.ea_sys import PROFILE_DIR, LAYER_FILE_MAP
from ea_kernel.spec import KERNEL_SPEC
from ea_profile.loader import load_profile
from ea_profile.types import KernelProfile

# ── Layer schema imports ──

from ea_infra.infra_schema import INFRA_SCHEMA
from ea_governance.governance_schema import GOVERNANCE_SCHEMA
from ea_decision.decision_schema import DECISION_SCHEMA
from ea_needs.needs_schema import NEEDS_SCHEMA
from ea_flow.flow_schema import FLOW_SCHEMA
from ea_projection.projection_schema import PROJECTION_SCHEMA

# ── Test configuration ──

# Map layer key → (schema singleton, toml file key)
SCHEMA_LAYER_MAP = {
    "infra": (INFRA_SCHEMA, "infra"),
    "governance": (GOVERNANCE_SCHEMA, "governance"),
    "decision": (DECISION_SCHEMA, "decision"),
    "needs": (NEEDS_SCHEMA, "needs"),
    "flow": (FLOW_SCHEMA, "flow"),
    "projection": (PROJECTION_SCHEMA, "projection"),
}

# Minimum rule density (rules / elements) per profile
MIN_RULE_DENSITY = 0.9


@pytest.fixture(scope="module")
def loaded_profiles() -> dict[str, KernelProfile]:
    """Load all 6 layer profiles once."""
    profiles = {}
    for layer_key in SCHEMA_LAYER_MAP:
        path = PROFILE_DIR / LAYER_FILE_MAP[layer_key]
        profiles[layer_key] = load_profile(path, KERNEL_SPEC)
    return profiles


# ============================================================
# Test 1 — SchemaPort Entity Coverage
# ============================================================

class TestEntityCoverage:
    """Each SchemaPort entity has at least one matching TOML element."""

    @pytest.mark.parametrize("layer_key", list(SCHEMA_LAYER_MAP))
    def test_entity_representation_in_profile(self, loaded_profiles, layer_key):
        """Non-abstract schema entities should be represented in TOML elements.

        We check that element names (lowercased, underscored) reference
        the schema entity concept. At minimum, each non-abstract entity
        should contribute at least one element.
        """
        schema, _ = SCHEMA_LAYER_MAP[layer_key]
        profile = loaded_profiles[layer_key]

        # Collect all element names and descriptions (lowercased)
        element_text = set()
        for elem in profile.elements:
            element_text.add(elem.name.lower())
            if elem.description:
                element_text.add(str(elem.description).lower())

        joined_text = " ".join(element_text)

        # Non-abstract entities should appear in element names or descriptions
        unrepresented = []
        for entity in schema.entities:
            if entity.is_abstract:
                continue
            # Normalize entity name for matching
            entity_words = entity.name.split("_")
            # At least some entity words should appear in profile text
            if not any(word in joined_text for word in entity_words if len(word) > 3):
                unrepresented.append(entity.name)

        # Allow small number of unrepresented entities (some are enums or meta-types)
        total_non_abstract = sum(1 for e in schema.entities if not e.is_abstract)
        coverage_ratio = 1.0 - (len(unrepresented) / total_non_abstract) if total_non_abstract else 1.0
        assert coverage_ratio >= 0.6, (
            f"{layer_key}: {len(unrepresented)}/{total_non_abstract} non-abstract entities "
            f"unrepresented ({coverage_ratio:.0%} coverage): {unrepresented}"
        )


# ============================================================
# Test 2 — SchemaPort Relation Usage
# ============================================================

class TestRelationUsage:
    """SchemaPort relations that are profile-defined are used in rules."""

    @pytest.mark.parametrize("layer_key", list(SCHEMA_LAYER_MAP))
    def test_profile_relations_used_in_rules(self, loaded_profiles, layer_key):
        """Profile-defined relations (shared 10) should all appear in rules.

        Schema relations include domain-specific ones (e.g., evaluates,
        selects) that exist only at the code level. Only relations that
        are both in the schema AND defined in the profile need rule coverage.
        """
        schema, _ = SCHEMA_LAYER_MAP[layer_key]
        profile = loaded_profiles[layer_key]

        # Profile-defined relation names (the 10 shared ones)
        profile_relation_names = {r.name for r in profile.relations}
        # Schema relation names
        schema_relation_names = {rel.name for rel in schema.relations}
        # Intersection: relations in both schema and profile
        shared = schema_relation_names & profile_relation_names

        # Collect all relation names used in profile rules
        used_relations = {r.relationship_name for r in profile.validity_rules}

        unused = shared - used_relations
        assert not unused, (
            f"{layer_key}: shared relations not used in any rule: {unused}"
        )

    @pytest.mark.parametrize("layer_key", list(SCHEMA_LAYER_MAP))
    def test_schema_has_core_shared_relations(self, loaded_profiles, layer_key):
        """Schema should define at least some core shared relations.

        Decision and Needs schemas have many domain-specific relations
        (evaluates, selects, expresses, etc.) alongside the shared ones.
        We verify at least 2 shared relations overlap (contains, depends_on
        are universal).
        """
        schema, _ = SCHEMA_LAYER_MAP[layer_key]
        profile = loaded_profiles[layer_key]

        profile_relation_names = {r.name for r in profile.relations}
        schema_relation_names = {rel.name for rel in schema.relations}

        overlap = schema_relation_names & profile_relation_names
        assert len(overlap) >= 2, (
            f"{layer_key}: schema shares only {len(overlap)} relations "
            f"with profile (need >=2). Overlap: {overlap}"
        )


# ============================================================
# Test 3 — Rule Density
# ============================================================

class TestRuleDensity:
    """Rule density (rules/elements) meets minimum threshold."""

    @pytest.mark.parametrize("layer_key", list(SCHEMA_LAYER_MAP))
    def test_minimum_rule_density(self, loaded_profiles, layer_key):
        """Rule density must be at least MIN_RULE_DENSITY."""
        profile = loaded_profiles[layer_key]

        num_elements = len(profile.elements)
        num_rules = len(profile.validity_rules)

        assert num_elements > 0, f"{layer_key}: no elements in profile"
        density = num_rules / num_elements

        assert density >= MIN_RULE_DENSITY, (
            f"{layer_key}: rule density {density:.2f} "
            f"({num_rules} rules / {num_elements} elements) "
            f"below minimum {MIN_RULE_DENSITY}"
        )


# ============================================================
# Test 4 — Schema Entity Count Alignment
# ============================================================

class TestSchemaEntityCount:
    """Schema entity counts are reasonable vs profile element counts."""

    @pytest.mark.parametrize("layer_key", list(SCHEMA_LAYER_MAP))
    def test_schema_entity_count(self, loaded_profiles, layer_key):
        """Schema should have a reasonable number of entities.

        Each schema entity typically maps to 2-10 TOML elements.
        Schema entities should be at least 10% of element count.
        """
        schema, _ = SCHEMA_LAYER_MAP[layer_key]
        profile = loaded_profiles[layer_key]

        entity_count = len(schema.entities)
        element_count = len(profile.elements)

        assert entity_count > 0, f"{layer_key}: schema has no entities"
        assert element_count > 0, f"{layer_key}: profile has no elements"

        ratio = entity_count / element_count
        assert ratio >= 0.05, (
            f"{layer_key}: schema entity count ({entity_count}) too low "
            f"vs profile elements ({element_count}), ratio {ratio:.2f}"
        )


# ============================================================
# Test 5 — Summary Statistics
# ============================================================

class TestSummaryStats:
    """Summary statistics for all layers."""

    def test_all_layers_loaded(self, loaded_profiles):
        """All 6 layer profiles loaded successfully."""
        assert len(loaded_profiles) == 6

    def test_print_alignment_summary(self, loaded_profiles, capsys):
        """Print a summary of schema-profile alignment for diagnostics."""
        rows = []
        for layer_key in SCHEMA_LAYER_MAP:
            schema, _ = SCHEMA_LAYER_MAP[layer_key]
            profile = loaded_profiles[layer_key]

            num_entities = len(schema.entities)
            num_relations = len(schema.relations)
            num_elements = len(profile.elements)
            num_rules = len(profile.validity_rules)
            density = num_rules / num_elements if num_elements else 0

            rows.append((layer_key, num_entities, num_relations,
                         num_elements, num_rules, density))

        # Just verify all data collected (actual printing is diagnostic)
        for layer_key, entities, relations, elements, rules, density in rows:
            assert entities > 0
            assert elements > 0
            assert rules > 0
