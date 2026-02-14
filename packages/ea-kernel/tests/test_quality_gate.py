"""Tests for v2 profile quality gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ea_kernel.profile_builder import ProfileBuilder
from ea_kernel.profile_quality_gate import check_profile_quality
from ea_kernel.spec import KERNEL_SPEC

# ═════════════════════════════════════════════════════════════════════════════
# 1. Clean profile passes
# ═════════════════════════════════════════════════════════════════════════════

class TestCleanProfile:
    def _build_clean(self):
        return (
            ProfileBuilder("Clean", version="1.0", kernel_version="2.5.0")
            .category_mapping({"Data": "item", "Process": "step"})
            .element("Widget", layer="Core", category="Data")
            .element("Task", layer="Core", category="Process")
            .relation("uses", kernel_relation="association")
            .allow("@Data", "@Process", "uses", priority=40)
            .build(KERNEL_SPEC)
        )

    def test_passes(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.passed is True

    def test_no_dead_rules(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.dead_rules == ()

    def test_no_conflicts(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.conflicting_rules == ()

    def test_no_missing_fallbacks(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.missing_fallbacks == ()

    def test_no_invalid_patterns(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.invalid_patterns == ()

    def test_no_invalid_kernel_refs(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.invalid_kernel_refs == ()

    def test_coverage_positive(self):
        p = self._build_clean()
        report = check_profile_quality(p, KERNEL_SPEC)
        assert report.coverage > 0.0


# ═════════════════════════════════════════════════════════════════════════════
# 2. Existing profiles pass
# ═════════════════════════════════════════════════════════════════════════════

class TestExistingProfiles:
    def test_zachman_passes(self):
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        report = check_profile_quality(ZACHMAN_PROFILE, KERNEL_SPEC)
        assert report.passed is True
        assert report.missing_fallbacks == ()
        assert report.invalid_patterns == ()

    def test_archimate_passes(self):
        from ea_kernel.profiles.archimate import ARCHIMATE_PROFILE
        report = check_profile_quality(ARCHIMATE_PROFILE, KERNEL_SPEC)
        assert report.passed is True

    def test_togaf_passes(self):
        from ea_kernel.profiles.togaf import TOGAF_PROFILE
        report = check_profile_quality(TOGAF_PROFILE, KERNEL_SPEC)
        assert report.passed is True

    def test_sysml2_passes(self):
        from ea_kernel.profiles.sysml2 import SYSML2_PROFILE
        report = check_profile_quality(SYSML2_PROFILE, KERNEL_SPEC)
        assert report.passed is True

    def test_bpmn_passes(self):
        from ea_kernel.profiles.bpmn import BPMN_PROFILE
        report = check_profile_quality(BPMN_PROFILE, KERNEL_SPEC)
        assert report.passed is True


# ═════════════════════════════════════════════════════════════════════════════
# 3. Detection of issues
# ═════════════════════════════════════════════════════════════════════════════

class TestIssueDetection:
    def test_detects_missing_fallback(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build(validate=False, auto_fallback=False)
        )
        report = check_profile_quality(p, KERNEL_SPEC)
        assert "r" in report.missing_fallbacks

    def test_detects_dead_rule(self):
        """A lower-priority rule shadowed by a higher-priority wildcard."""
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("*", "*", "r", priority=50)
            .allow("A", "A", "r", priority=40)
            .build(validate=False)
        )
        report = check_profile_quality(p, KERNEL_SPEC)
        # The p=40 rule is shadowed by p=50 wildcard
        assert len(report.dead_rules) >= 1

    def test_detects_conflicting_rules(self):
        p = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("*", "*", "r", priority=50, rule_id="allow-1")
            .deny("*", "*", "r", priority=50, rule_id="deny-1")
            .build(validate=False)
        )
        report = check_profile_quality(p, KERNEL_SPEC)
        assert len(report.conflicting_rules) >= 1

    def test_coverage_varies(self):
        """More kernel types used → higher coverage."""
        p_low = (
            ProfileBuilder("Low", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .build(validate=False)
        )
        p_high = (
            ProfileBuilder("High", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C1", kernel_type="item")
            .element("B", layer="L", category="C2", kernel_type="step")
            .element("C", layer="L", category="C3", kernel_type="structure")
            .element("D", layer="L", category="C4", kernel_type="event")
            .relations(("r1", "association"), ("r2", "flow"), ("r3", "succession"))
            .build(validate=False)
        )
        low_report = check_profile_quality(p_low, KERNEL_SPEC)
        high_report = check_profile_quality(p_high, KERNEL_SPEC)
        assert high_report.coverage > low_report.coverage
