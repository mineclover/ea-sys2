"""Tests for ea_profile.quality_gate — dead rules, conflicts, coverage."""

import pytest

from ea_profile.builder import ProfileBuilder
from ea_profile.quality_gate import check_profile_quality
from ea_profile.types import QualityReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_profile():
    """A well-formed profile that passes quality gate."""
    return (
        ProfileBuilder("QG", version="1.0", kernel_version="2.0")
        .element("A", layer="L", category="Cat", kernel_type="structure")
        .element("B", layer="L", category="Cat", kernel_type="item")
        .relation("r", kernel_relation="association")
        .allow("A", "B", "r", priority=50)
        .build()
    )


# ---------------------------------------------------------------------------
# Passing profile
# ---------------------------------------------------------------------------

class TestPassingProfile:
    def test_clean_profile_passes(self):
        p = _clean_profile()
        report = check_profile_quality(p)
        assert isinstance(report, QualityReport)
        assert report.passed is True
        assert report.dead_rules == ()
        assert report.conflicting_rules == ()
        assert report.missing_fallbacks == ()
        assert report.invalid_patterns == ()


# ---------------------------------------------------------------------------
# Dead rule detection
# ---------------------------------------------------------------------------

class TestDeadRules:
    def test_shadowed_rule_detected(self):
        p = (
            ProfileBuilder("DR", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="Cat", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r", priority=50, rule_id="low")
            .allow("*", "*", "r", priority=60, rule_id="high")
            .build()
        )
        report = check_profile_quality(p)
        assert "low" in report.dead_rules


# ---------------------------------------------------------------------------
# Conflicting rule detection
# ---------------------------------------------------------------------------

class TestConflictingRules:
    def test_same_priority_opposite_validity(self):
        p = (
            ProfileBuilder("CR", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="Cat", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r", priority=50, rule_id="allow-1")
            .deny("A", "A", "r", priority=50, rule_id="deny-1")
            .build(auto_fallback=False)
        )
        report = check_profile_quality(p)
        assert len(report.conflicting_rules) >= 1
        pair = report.conflicting_rules[0]
        assert "allow-1" in pair
        assert "deny-1" in pair


# ---------------------------------------------------------------------------
# Missing fallback detection
# ---------------------------------------------------------------------------

class TestMissingFallbacks:
    def test_no_fallback_detected(self):
        p = (
            ProfileBuilder("MF", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="Cat", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build(auto_fallback=False)
        )
        report = check_profile_quality(p)
        assert "r" in report.missing_fallbacks

    def test_with_auto_fallback_passes(self):
        p = (
            ProfileBuilder("MF", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="Cat", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build(auto_fallback=True)
        )
        report = check_profile_quality(p)
        assert report.missing_fallbacks == ()


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------

class TestCoverage:
    def test_coverage_with_schema(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _Ent:
            name: str
            is_abstract: bool = False

        @dataclass(frozen=True)
        class _Rel:
            name: str

        @dataclass(frozen=True)
        class _Schema:
            entities: tuple[_Ent, ...] = ()
            relations: tuple[_Rel, ...] = ()

        schema = _Schema(
            entities=(_Ent("structure"), _Ent("item"), _Ent("abstract_base", is_abstract=True)),
            relations=(_Rel("association"), _Rel("flow")),
        )
        p = (
            ProfileBuilder("CV", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="C1", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .build()
        )
        report = check_profile_quality(p, schema)
        # 2 concrete entities + 2 relations = 4 total
        # 1 entity used + 1 relation used = 2 used
        assert report.coverage == pytest.approx(0.5)

    def test_coverage_without_schema(self):
        p = _clean_profile()
        report = check_profile_quality(p)
        assert report.coverage == 0.0

    def test_invalid_kernel_refs(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _Ent:
            name: str
            is_abstract: bool = False

        @dataclass(frozen=True)
        class _Rel:
            name: str

        @dataclass(frozen=True)
        class _Schema:
            entities: tuple[_Ent, ...] = ()
            relations: tuple[_Rel, ...] = ()

        schema = _Schema(
            entities=(_Ent("structure"),),
            relations=(_Rel("association"),),
        )
        p = (
            ProfileBuilder("IR", version="1.0", kernel_version="2.0")
            .element("A", layer="L", category="C", kernel_type="bogus_type")
            .relation("r", kernel_relation="bogus_rel")
            .build(validate=False)
        )
        report = check_profile_quality(p, schema)
        assert report.passed is False
        assert len(report.invalid_kernel_refs) == 2
