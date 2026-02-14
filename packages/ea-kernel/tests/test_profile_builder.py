"""Tests for v2 ProfileBuilder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.profile_types import KernelProfile, ProfileBuildError, ProfileElement, ProfileRelation
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import KernelConditionType, KernelRuleCondition, KernelValidityRule
from ea_kernel.profile_builder import ProfileBuilder


# ═════════════════════════════════════════════════════════════════════════════
# 1. Basic construction
# ═════════════════════════════════════════════════════════════════════════════

class TestBasicConstruction:
    def test_minimal_profile(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("Widget", layer="Core", category="Thing", kernel_type="structure")
            .relation("uses", kernel_relation="association")
            .allow("Widget", "Widget", "uses")
            .build(validate=False)
        )
        assert p.name == "Test"
        assert p.version == "1.0"
        assert p.kernel_version == "2.5.0"
        assert len(p.elements) == 1
        assert len(p.relations) == 1

    def test_metadata(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .metadata(standard="Test Std", organization="ACME")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .build(validate=False)
        )
        assert p.metadata is not None
        assert p.metadata.standard == "Test Std"
        assert p.metadata.organization == "ACME"

    def test_id_prefix(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .id_prefix("tst")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build(validate=False)
        )
        rule_ids = [r.id for r in p.validity_rules if r.priority > 1]
        assert all(rid.startswith("tst-") for rid in rule_ids)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Element methods
# ═════════════════════════════════════════════════════════════════════════════

class TestElements:
    def test_element_with_category_mapping(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .category_mapping({"Behavior": "step"})
            .element("Process", layer="Core", category="Behavior")
            .relation("r", kernel_relation="association")
            .build(validate=False)
        )
        assert p.get_element("Process").kernel_type == "step"

    def test_element_without_mapping_raises(self):
        with pytest.raises(ProfileBuildError, match="not in category_mapping"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("Process", layer="Core", category="Unknown")
            )

    def test_elements_bulk(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .category_mapping({"A": "item", "B": "step"})
            .elements_bulk([
                {"name": "X", "layer": "L1", "category": "A"},
                {"name": "Y", "layer": "L2", "category": "B"},
            ])
            .relation("r", kernel_relation="association")
            .build(validate=False)
        )
        assert len(p.elements) == 2
        assert p.get_element("X").kernel_type == "item"
        assert p.get_element("Y").kernel_type == "step"

    def test_elements_from_matrix(self):
        naming = lambda layer, cat: f"{layer}{cat}"
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .elements_from_matrix(
                layers=["L1", "L2", "L3"],
                categories={"A": "item", "B": "step"},
                naming=naming,
            )
            .relation("r", kernel_relation="association")
            .build(validate=False)
        )
        assert len(p.elements) == 6  # 3 layers × 2 categories
        assert p.get_element("L1A") is not None
        assert p.get_element("L3B") is not None
        assert p.get_element("L1A").kernel_type == "item"
        assert p.get_element("L3B").kernel_type == "step"

    def test_elements_from_matrix_with_descriptions(self):
        naming = lambda l, c: f"{l}{c}"
        descs = lambda l, c: f"{c} at {l}"
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .elements_from_matrix(
                layers=["Row1"],
                categories={"Col1": "item"},
                naming=naming,
                descriptions=descs,
            )
            .relation("r", kernel_relation="association")
            .build(validate=False)
        )
        assert p.get_element("Row1Col1").description == "Col1 at Row1"


# ═════════════════════════════════════════════════════════════════════════════
# 3. Relation methods
# ═════════════════════════════════════════════════════════════════════════════

class TestRelations:
    def test_single_relation(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("uses", kernel_relation="association", description="Uses rel")
            .build(validate=False)
        )
        rel = p.get_relation("uses")
        assert rel.kernel_relation == "association"
        assert rel.description == "Uses rel"

    def test_relations_bulk(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relations(
                ("uses", "association"),
                ("flow", "flow", "Data flow"),
            )
            .build(validate=False)
        )
        assert len(p.relations) == 2
        assert p.get_relation("flow").description == "Data flow"


# ═════════════════════════════════════════════════════════════════════════════
# 4. Rule methods
# ═════════════════════════════════════════════════════════════════════════════

class TestRules:
    def test_allow_rule(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r", priority=50, notes="test note")
            .build(validate=False)
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 1
        assert explicit[0].valid is True
        assert explicit[0].priority == 50
        assert explicit[0].notes == "test note"

    def test_deny_rule(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .deny("A", "A", "r", priority=80)
            .build(validate=False)
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 1
        assert explicit[0].valid is False

    def test_allow_same_category(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow_same_category("r", priority=50)
            .build(validate=False)
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 1
        assert explicit[0].source_pattern == "*"
        assert explicit[0].target_pattern == "*"
        assert len(explicit[0].conditions) == 1
        assert explicit[0].conditions[0].condition_type == KernelConditionType.SAME_CATEGORY

    def test_allow_same_layer(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow_same_layer("r")
            .build(validate=False)
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert explicit[0].conditions[0].condition_type == KernelConditionType.SAME_LAYER

    def test_rule_group(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .category_mapping({"X": "item", "Y": "step"})
            .element("A", layer="L", category="X")
            .element("B", layer="L", category="Y")
            .relation("r", kernel_relation="association")
            .rule_group("r", [("@X", "@Y"), ("@Y", "@X")], priority=40)
            .build(validate=False)
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 2

    def test_custom_rule_id(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r", rule_id="custom-01")
            .build(validate=False)
        )
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert explicit[0].id == "custom-01"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Auto-fallback
# ═════════════════════════════════════════════════════════════════════════════

class TestAutoFallback:
    def test_auto_fallback_generated(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build(validate=False)
        )
        fallbacks = [r for r in p.validity_rules if r.priority == 1]
        assert len(fallbacks) == 1
        assert fallbacks[0].valid is False
        assert fallbacks[0].relationship_name == "r"

    def test_no_duplicate_fallback(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .deny("*", "*", "r", priority=1, rule_id="my-fb")
            .build(validate=False)
        )
        fallbacks = [r for r in p.validity_rules if r.priority == 1]
        assert len(fallbacks) == 1
        assert fallbacks[0].id == "my-fb"

    def test_auto_fallback_disabled(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build(validate=False, auto_fallback=False)
        )
        fallbacks = [r for r in p.validity_rules if r.priority == 1]
        assert len(fallbacks) == 0

    def test_multiple_relations_get_fallbacks(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relations(("r1", "association"), ("r2", "flow"), ("r3", "succession"))
            .allow("A", "A", "r1")
            .build(validate=False)
        )
        fallback_rels = {r.relationship_name for r in p.validity_rules if r.priority == 1}
        assert fallback_rels == {"r1", "r2", "r3"}


# ═════════════════════════════════════════════════════════════════════════════
# 6. Build-time validation
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildValidation:
    def test_duplicate_element_names(self):
        with pytest.raises(ProfileBuildError, match="Duplicate element"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .element("A", layer="L2", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .build()
            )

    def test_duplicate_relation_names(self):
        with pytest.raises(ProfileBuildError, match="Duplicate relation"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .relation("r", kernel_relation="flow")
                .build()
            )

    def test_duplicate_rule_ids(self):
        with pytest.raises(ProfileBuildError, match="Duplicate rule"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .allow("A", "A", "r", rule_id="dup-01")
                .allow("A", "A", "r", rule_id="dup-01")
                .build()
            )

    def test_invalid_kernel_type(self):
        with pytest.raises(ProfileBuildError, match="unknown kernel type"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="nonexistent")
                .relation("r", kernel_relation="association")
                .build(KERNEL_SCHEMA)
            )

    def test_invalid_kernel_relation(self):
        with pytest.raises(ProfileBuildError, match="unknown kernel relation"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="nonexistent")
                .build(KERNEL_SCHEMA)
            )

    def test_invalid_category_pattern(self):
        with pytest.raises(ProfileBuildError, match="unknown category"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .allow("@NonExistent", "A", "r")
                .build()
            )

    def test_invalid_layer_pattern(self):
        with pytest.raises(ProfileBuildError, match="unknown layer"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .allow("#NoLayer", "A", "r")
                .build()
            )

    def test_invalid_exact_pattern(self):
        with pytest.raises(ProfileBuildError, match="unknown element"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .allow("NonExistentElement", "A", "r")
                .build()
            )

    def test_invalid_rule_relation_ref(self):
        with pytest.raises(ProfileBuildError, match="unknown relation"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .element("A", layer="L", category="C", kernel_type="item")
                .relation("r", kernel_relation="association")
                .allow("A", "A", "nonexistent_rel")
                .build()
            )

    def test_category_consistency_error(self):
        with pytest.raises(ProfileBuildError, match="maps to"):
            (
                ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
                .category_mapping({"C": "item"})
                .element("A", layer="L", category="C", kernel_type="step")
                .relation("r", kernel_relation="association")
                .build()
            )

    def test_valid_profile_passes(self):
        """A well-formed profile should build without error."""
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .category_mapping({"Data": "item", "Process": "step"})
            .element("Widget", layer="Core", category="Data")
            .element("Task", layer="Core", category="Process")
            .relation("uses", kernel_relation="association")
            .allow("@Data", "@Process", "uses")
            .allow("@Process", "@Data", "uses")
            .build(KERNEL_SCHEMA)
        )
        assert len(p.elements) == 2
        assert len(p.relations) == 1

    def test_wildcard_pattern_passes(self):
        """Wildcard '*' should not trigger pattern validation errors."""
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("*", "*", "r")
            .build()
        )
        assert len(p.validity_rules) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 7. Zachman equivalence
# ═════════════════════════════════════════════════════════════════════════════

class TestZachmanEquivalence:
    """Verify builder-created Zachman profile matches legacy profile."""

    _PERSPECTIVES = ("Scope", "Enterprise", "System", "Technology", "Detail", "Operational")
    _CATEGORIES = {
        "What": "item",
        "How": "step",
        "Where": "package",
        "Who": "structure",
        "When": "event",
        "Why": "state",
    }

    _NAME_MAP = {
        "What": "Data",
        "How": "Process",
        "Where": "Network",
        "Who": "Organization",
        "When": "Schedule",
        "Why": "Strategy",
    }

    @staticmethod
    def _zachman_name(layer: str, category: str) -> str:
        name_map = {
            "What": "Data", "How": "Process", "Where": "Network",
            "Who": "Organization", "When": "Schedule", "Why": "Strategy",
        }
        return f"{layer}{name_map[category]}"

    def _build_zachman(self) -> KernelProfile:
        return (
            ProfileBuilder("Zachman", version="6.0", kernel_version="2.5.0")
            .id_prefix("zf")
            .metadata(
                standard="Zachman Framework 6.0",
                organization="Zachman International",
            )
            .elements_from_matrix(
                layers=list(self._PERSPECTIVES),
                categories=self._CATEGORIES,
                naming=self._zachman_name,
            )
            .relations(
                ("transforms_to", "specialization", "Vertical refinement between perspectives"),
                ("derives_from", "specialization", "Derivation from higher abstraction"),
                ("composition", "ownership", "Part-whole structural relationship"),
                ("aggregation", "membership", "Grouping without lifecycle dependency"),
                ("uses", "association", "Element uses another element"),
                ("located_at", "association", "Element is located at a place"),
                ("performed_by", "association", "Process performed by organizational unit"),
                ("triggered_by", "succession", "Process or event triggered by a schedule"),
                ("motivated_by", "association", "Element motivated by strategy"),
                ("flow", "flow", "Data or process flow between elements"),
                ("triggers", "succession", "Temporal causal relationship"),
                ("association", "association", "General unspecified relationship"),
            )
            .allow_same_category(
                "transforms_to", priority=50,
                notes="Vertical transformation within same interrogative column",
                rule_id="zf-trans-01",
            )
            .rule_group("derives_from", [
                ("@What", "@What"), ("@How", "@How"), ("@Where", "@Where"),
                ("@Who", "@Who"), ("@When", "@When"), ("@Why", "@Why"),
            ], priority=40)
            .rule_group("composition", [
                ("@What", "@What"), ("@Where", "@Where"), ("@Who", "@Who"),
            ], priority=40)
            .rule_group("aggregation", [
                ("@Where", "@What"), ("@Where", "@How"), ("@Where", "@Who"),
            ], priority=40)
            .allow("@How", "@What", "uses", priority=50, notes="Process uses data")
            .allow("@Who", "@What", "uses", priority=50, notes="Organization uses data")
            .allow("@Who", "@Where", "located_at", priority=50, notes="Organization located at network")
            .allow("@What", "@Where", "located_at", priority=50, notes="Data located at network")
            .allow("@How", "@Who", "performed_by", priority=50, notes="Process performed by organization")
            .allow("@How", "@When", "triggered_by", priority=50, notes="Process triggered by schedule")
            .allow("@When", "@When", "triggered_by", priority=40, notes="Schedule triggered by schedule")
            .allow("@How", "@Why", "motivated_by", priority=50, notes="Process motivated by strategy")
            .allow("@Who", "@Why", "motivated_by", priority=50, notes="Organization motivated by strategy")
            .allow("@What", "@Why", "motivated_by", priority=50, notes="Data motivated by strategy")
            .rule_group("flow", [
                ("@How", "@How"), ("@What", "@How"), ("@How", "@What"),
            ], priority=40)
            .rule_group("triggers", [
                ("@When", "@How"), ("@When", "@When"), ("@How", "@How"),
            ], priority=40)
            .allow("*", "*", "association", priority=40, notes="General association between any elements")
            .build(KERNEL_SCHEMA)
        )

    def test_element_count(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        assert len(bp.elements) == len(ZACHMAN_PROFILE.elements)

    def test_element_names_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        builder_names = sorted(e.name for e in bp.elements)
        legacy_names = sorted(e.name for e in ZACHMAN_PROFILE.elements)
        assert builder_names == legacy_names

    def test_element_types_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        builder_map = {e.name: e.kernel_type for e in bp.elements}
        legacy_map = {e.name: e.kernel_type for e in ZACHMAN_PROFILE.elements}
        assert builder_map == legacy_map

    def test_element_categories_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        builder_map = {e.name: e.category for e in bp.elements}
        legacy_map = {e.name: e.category for e in ZACHMAN_PROFILE.elements}
        assert builder_map == legacy_map

    def test_element_layers_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        builder_map = {e.name: e.layer for e in bp.elements}
        legacy_map = {e.name: e.layer for e in ZACHMAN_PROFILE.elements}
        assert builder_map == legacy_map

    def test_relation_count(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        assert len(bp.relations) == len(ZACHMAN_PROFILE.relations)

    def test_relation_mappings_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        builder_map = {r.name: r.kernel_relation for r in bp.relations}
        legacy_map = {r.name: r.kernel_relation for r in ZACHMAN_PROFILE.relations}
        assert builder_map == legacy_map

    def test_rule_count_comparable(self):
        """Builder profile should have same number of explicit + fallback rules."""
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        # Count explicit rules (priority > 1) and fallbacks separately
        bp_explicit = len([r for r in bp.validity_rules if r.priority > 1])
        legacy_explicit = len([r for r in ZACHMAN_PROFILE.validity_rules if r.priority > 1])
        assert bp_explicit == legacy_explicit

        bp_fallback = len([r for r in bp.validity_rules if r.priority == 1])
        legacy_fallback = len([r for r in ZACHMAN_PROFILE.validity_rules if r.priority == 1])
        assert bp_fallback == legacy_fallback

    def test_fallback_relations_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        bp_fb_rels = sorted(r.relationship_name for r in bp.validity_rules if r.priority == 1)
        legacy_fb_rels = sorted(r.relationship_name for r in ZACHMAN_PROFILE.validity_rules if r.priority == 1)
        assert bp_fb_rels == legacy_fb_rels

    def test_same_category_condition_present(self):
        bp = self._build_zachman()
        conditioned = [r for r in bp.validity_rules if r.conditions]
        assert len(conditioned) >= 1
        trans_rule = [r for r in conditioned if r.relationship_name == "transforms_to"]
        assert len(trans_rule) == 1
        assert trans_rule[0].conditions[0].condition_type == KernelConditionType.SAME_CATEGORY

    def test_profile_metadata_match(self):
        bp = self._build_zachman()
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        assert bp.metadata.standard == ZACHMAN_PROFILE.metadata.standard
        assert bp.metadata.organization == ZACHMAN_PROFILE.metadata.organization
