"""Tests for ea_profile.auditor module."""

import pytest
from dataclasses import dataclass

from ea_profile.auditor import ProfileAuditor
from ea_profile.types import AuditResult, AuditSeverity, DriftEntry, RegistryAuditReport
from ea_profile.registry import ProfileRegistry
from ea_profile.builder import ProfileBuilder


@dataclass(frozen=True)
class MockEntity:
    """Mock entity for testing."""

    name: str
    is_abstract: bool = False


@dataclass(frozen=True)
class MockRelation:
    """Mock relation for testing."""

    name: str


class MockSchema:
    """Mock schema for testing."""

    def __init__(self, entities, relations):
        self._entities = entities
        self._relations = relations

    @property
    def entities(self):
        return self._entities

    @property
    def relations(self):
        return self._relations


def _make_profile(name="TestProfile", version="1.0"):
    """Build a test profile."""
    b = ProfileBuilder(name, version=version, kernel_version="1.0")
    b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
    b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
    b.element("ElemC", kernel_type="step", layer="Application", category="Behavior")
    b.relation("Rel1", kernel_relation="association")
    b.relation("Rel2", kernel_relation="composition")
    b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
    b.deny("@Behavior", "@Structure", "Rel1", priority=40, rule_id="r-02")
    b.deny("*", "*", "Rel1", priority=0, notes="fallback", rule_id="fb-Rel1-deny")
    return b.build()


class TestProfileAuditor:
    """Test ProfileAuditor class."""

    def test_kernel_property(self):
        """Test that .kernel property returns the schema."""
        schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item")],
            relations=[MockRelation("association")],
        )
        auditor = ProfileAuditor(schema)
        assert auditor.kernel is schema

    def test_audit_profile_clean(self):
        """Test audit_profile with a clean profile passes."""
        schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        auditor = ProfileAuditor(schema)
        profile = _make_profile()

        result = auditor.audit_profile(profile)

        assert isinstance(result, AuditResult)
        assert result.profile_name == "TestProfile"
        # No ERROR findings means passed
        error_findings = [f for f in result.findings if f.severity == AuditSeverity.ERROR]
        assert len(error_findings) == 0

    def test_audit_profile_invalid_kernel_refs(self):
        """Test audit_profile with invalid kernel refs produces ERROR findings."""
        schema = MockSchema(
            entities=[MockEntity("structure")],  # Missing "item" and "step"
            relations=[MockRelation("association")],  # Missing "composition"
        )
        auditor = ProfileAuditor(schema)
        profile = _make_profile()

        result = auditor.audit_profile(profile)

        assert isinstance(result, AuditResult)
        assert result.profile_name == "TestProfile"
        # Should have ERROR findings for missing kernel refs
        error_findings = [f for f in result.findings if f.severity == AuditSeverity.ERROR]
        assert len(error_findings) > 0

    def test_audit_profile_direction_consistency(self):
        """Test audit_profile detects direction consistency issues."""
        schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item")],
            relations=[MockRelation("association")],
        )
        auditor = ProfileAuditor(schema)

        # Create profile with same kernel_relation and SAME direction
        b = ProfileBuilder("DirTest", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
        # Same kernel_relation, SAME direction → duplicate direction WARNING
        b.relation("Rel1", kernel_relation="association", direction="source_to_target")
        b.relation("Rel2", kernel_relation="association", direction="source_to_target")
        profile = b.build()

        result = auditor.audit_profile(profile)

        # Should have at least one WARNING for direction inconsistency
        warning_findings = [
            f for f in result.findings if f.severity == AuditSeverity.WARNING
        ]
        assert len(warning_findings) > 0

    def test_audit_registry(self):
        """Test audit_registry batch audits multiple profiles."""
        schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        auditor = ProfileAuditor(schema)

        registry = ProfileRegistry()
        profile1 = _make_profile("Profile1", "1.0")
        profile2 = _make_profile("Profile2", "1.0")
        registry.register(profile1)
        registry.register(profile2)

        report = auditor.audit_registry(registry)

        assert isinstance(report, RegistryAuditReport)
        assert report.total_profiles == 2
        assert len(report.results) == 2

    def test_detect_drift_no_drift(self):
        """Test detect_drift when schemas are identical."""
        old_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        new_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        auditor = ProfileAuditor(old_schema)
        profile = _make_profile()

        drift = auditor.detect_drift(profile, new_schema)

        assert isinstance(drift, tuple)
        assert len(drift) == 0

    def test_detect_drift_element_type_removed(self):
        """Test detect_drift when element type is removed."""
        old_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        new_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("step")],  # "item" removed
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        auditor = ProfileAuditor(old_schema)
        profile = _make_profile()

        drift = auditor.detect_drift(profile, new_schema)

        assert isinstance(drift, tuple)
        assert len(drift) > 0
        # Should have broken_type_ref for ElemB (whose kernel_type is "item")
        type_drift = [d for d in drift if d.category == "broken_type_ref"]
        assert len(type_drift) > 0
        assert any("ElemB" in d.element_or_rule for d in type_drift)

    def test_detect_drift_relation_removed(self):
        """Test detect_drift when relation is removed."""
        old_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association"), MockRelation("composition")],
        )
        new_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association")],  # "composition" removed
        )
        auditor = ProfileAuditor(old_schema)
        profile = _make_profile()

        drift = auditor.detect_drift(profile, new_schema)

        assert isinstance(drift, tuple)
        assert len(drift) > 0
        # Should have broken_relation_ref for Rel2 (whose kernel_relation is "composition")
        rel_drift = [d for d in drift if d.category == "broken_relation_ref"]
        assert len(rel_drift) > 0
        assert any("Rel2" in d.element_or_rule for d in rel_drift)

    def test_detect_drift_rule_pattern_broken(self):
        """Test detect_drift when rule pattern element is removed."""
        old_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item"), MockEntity("step")],
            relations=[MockRelation("association")],
        )
        new_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item")],  # "step" removed
            relations=[MockRelation("association")],
        )
        auditor = ProfileAuditor(old_schema)

        # Create profile with rule using kernel entity names as patterns
        # (validate=False to allow patterns that aren't profile element names)
        b = ProfileBuilder("RuleTest", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.element("ElemB", kernel_type="step", layer="Application", category="Behavior")
        b.relation("Rel1", kernel_relation="association")
        b.allow("step", "structure", "Rel1", priority=50, rule_id="r-01")
        profile = b.build(validate=False)

        drift = auditor.detect_drift(profile, new_schema)

        assert isinstance(drift, tuple)
        assert len(drift) > 0
        # Should have broken_type_ref for ElemB (kernel_type "step" removed)
        type_drift = [d for d in drift if d.category == "broken_type_ref"]
        assert len(type_drift) > 0
        assert any("ElemB" in d.element_or_rule for d in type_drift)

    def test_detect_drift_skips_wildcard_patterns(self):
        """Test detect_drift skips wildcard, category, and layer patterns."""
        old_schema = MockSchema(
            entities=[MockEntity("structure"), MockEntity("item")],
            relations=[MockRelation("association")],
        )
        new_schema = MockSchema(
            entities=[MockEntity("structure")],  # "item" removed
            relations=[MockRelation("association")],
        )
        auditor = ProfileAuditor(old_schema)

        # Profile uses wildcard and category patterns
        b = ProfileBuilder("PatternTest", version="1.0", kernel_version="1.0")
        b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
        b.relation("Rel1", kernel_relation="association")
        # These patterns should be skipped in drift detection
        b.allow("*", "*", "Rel1", priority=50, rule_id="r-01")
        b.allow("@Structure", "@Structure", "Rel1", priority=40, rule_id="r-02")
        b.allow("#Business", "#Business", "Rel1", priority=30, rule_id="r-03")
        profile = b.build()

        drift = auditor.detect_drift(profile, new_schema)

        # Should not report drift for wildcard/category/layer patterns
        rule_drift = [d for d in drift if d.category == "rule_pattern_broken"]
        # All rules use patterns that should be skipped
        assert len(rule_drift) == 0
