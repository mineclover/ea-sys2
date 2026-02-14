"""Tests for RuleVerifier — group-based rule verification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.rule_verifier import RuleVerifier
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.spec_loader import load_kernel_rules_with_metadata
from ea_kernel.types import (
    GroupVerificationResult,
    RuleCategory,
    RuleGroup,
    RuleVerificationEntry,
    VerificationReport,
)


@pytest.fixture
def verifier():
    _, _, metadata_map = load_kernel_rules_with_metadata()
    corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map=metadata_map)
    return RuleVerifier(KERNEL_SPEC, corpus)


# ═════════════════════════════════════════════════════════════════════════════
# 1. verify_group
# ═════════════════════════════════════════════════════════════════════════════

class TestVerifyGroup:
    def test_membership_group_passes(self, verifier):
        result = verifier.verify_group(RuleGroup.MEMBERSHIP)
        assert isinstance(result, GroupVerificationResult)
        assert result.group == RuleGroup.MEMBERSHIP
        assert result.pass_rate == 1.0

    def test_specialization_group_passes(self, verifier):
        result = verifier.verify_group(RuleGroup.SPECIALIZATION)
        assert result.group == RuleGroup.SPECIALIZATION
        assert result.pass_rate == 1.0

    def test_all_groups_pass(self, verifier):
        for group in RuleGroup:
            result = verifier.verify_group(group)
            assert result.pass_rate == 1.0, (
                f"Group {group.value} failed: "
                f"{result.failed_rules}/{result.total_rules} failures"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 2. verify_all
# ═════════════════════════════════════════════════════════════════════════════

class TestVerifyAll:
    def test_full_report_structure(self, verifier):
        report = verifier.verify_all()
        assert isinstance(report, VerificationReport)
        assert isinstance(report.group_results, tuple)
        assert isinstance(report.timestamp, str)
        assert report.total_groups > 0

    def test_overall_pass_rate_100(self, verifier):
        report = verifier.verify_all()
        assert report.overall_pass_rate == 1.0

    def test_all_groups_present(self, verifier):
        report = verifier.verify_all()
        groups_in_report = {g.group for g in report.group_results}
        for group in RuleGroup:
            assert group in groups_in_report

    def test_total_rules_matches(self, verifier):
        report = verifier.verify_all()
        assert report.total_rules == report.total_passed


# ═════════════════════════════════════════════════════════════════════════════
# 3. verify_category
# ═════════════════════════════════════════════════════════════════════════════

class TestVerifyCategory:
    def test_structural_category(self, verifier):
        report = verifier.verify_category(RuleCategory.STRUCTURAL)
        assert isinstance(report, VerificationReport)
        assert report.total_groups > 0
        assert report.overall_pass_rate == 1.0

    def test_behavioral_category(self, verifier):
        report = verifier.verify_category(RuleCategory.BEHAVIORAL)
        assert isinstance(report, VerificationReport)
        assert report.total_groups > 0
        assert report.overall_pass_rate == 1.0


# ═════════════════════════════════════════════════════════════════════════════
# 4. GroupVerificationResult type
# ═════════════════════════════════════════════════════════════════════════════

class TestGroupVerificationResult:
    def test_frozen(self, verifier):
        result = verifier.verify_group(RuleGroup.MEMBERSHIP)
        with pytest.raises(AttributeError):
            result.group = RuleGroup.FLOW  # type: ignore[misc]

    def test_pass_rate_calculation(self, verifier):
        result = verifier.verify_group(RuleGroup.MEMBERSHIP)
        if result.total_rules > 0:
            expected_rate = result.passed_rules / result.total_rules
            assert result.pass_rate == expected_rate


# ═════════════════════════════════════════════════════════════════════════════
# 5. rules_in_group
# ═════════════════════════════════════════════════════════════════════════════

class TestRulesInGroup:
    def test_returns_entries(self, verifier):
        entries = verifier.rules_in_group(RuleGroup.MEMBERSHIP)
        assert len(entries) >= 2
        for e in entries:
            assert e.metadata.group == RuleGroup.MEMBERSHIP

    def test_all_groups_have_rules(self, verifier):
        for group in RuleGroup:
            entries = verifier.rules_in_group(group)
            assert len(entries) > 0, f"Group {group.value} has no rules"
