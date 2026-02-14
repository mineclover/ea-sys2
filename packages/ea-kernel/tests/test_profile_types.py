"""Tests for v2 profile types."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ea_kernel.profile_types import (
    PatternType,
    ProfileBuildError,
    QualityReport,
    ValidationCategory,
)


class TestPatternType:
    def test_wildcard(self):
        assert PatternType.WILDCARD == "wildcard"

    def test_category(self):
        assert PatternType.CATEGORY == "category"

    def test_layer(self):
        assert PatternType.LAYER == "layer"

    def test_exact(self):
        assert PatternType.EXACT == "exact"


class TestValidationCategory:
    def test_all_categories(self):
        assert len(ValidationCategory) == 6
        assert ValidationCategory.ALLOWED == "allowed"
        assert ValidationCategory.EXPLICIT_DENY == "explicit_deny"


class TestProfileBuildError:
    def test_single_error(self):
        err = ProfileBuildError(["error1"])
        assert "1 build error" in str(err)
        assert err.errors == ["error1"]

    def test_multiple_errors(self):
        err = ProfileBuildError(["e1", "e2", "e3", "e4"])
        assert "4 build error" in str(err)
        assert len(err.errors) == 4

    def test_is_exception(self):
        assert issubclass(ProfileBuildError, Exception)


class TestQualityReport:
    def test_passed_report(self):
        r = QualityReport(
            passed=True,
            dead_rules=(),
            conflicting_rules=(),
            missing_fallbacks=(),
            invalid_patterns=(),
            invalid_kernel_refs=(),
            coverage=0.8,
        )
        assert r.passed is True
        assert r.coverage == 0.8

    def test_failed_report(self):
        r = QualityReport(
            passed=False,
            dead_rules=("rule-1",),
            conflicting_rules=(("a", "b"),),
            missing_fallbacks=("rel1",),
            invalid_patterns=("@Bad",),
            invalid_kernel_refs=("fake_type",),
            coverage=0.5,
        )
        assert r.passed is False
        assert len(r.dead_rules) == 1
