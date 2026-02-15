"""Tests for profile_auditor — ProfileAuditor + store audit hook."""

from __future__ import annotations

import pytest
from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.profile_auditor import ProfileAuditor
from ea_kernel.profile_registry import ProfileRegistry
from ea_kernel.profile_store import SQLiteProfileStore
from ea_kernel.profile_types import (
    AuditFinding,
    AuditResult,
    AuditSeverity,
    DriftEntry,
    KernelProfile,
    ProfileElement,
    ProfileMetadata,
    ProfileRelation,
    ProfileStoreError,
    RegistryAuditReport,
)
from ea_kernel.types import KernelSchema, KernelValidityRule

# ── Fixtures ───────────────────────────────────────────────────

def _make_valid_profile() -> KernelProfile:
    """A minimal profile with valid kernel refs."""
    return KernelProfile(
        name="TestAudit",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("Widget", "structure", "Core", "Thing"),
            ProfileElement("Action", "step", "Core", "Behavior"),
        ),
        relations=(ProfileRelation("uses", "association"),),
        validity_rules=(
            KernelValidityRule(
                id="ta-allow-01", source_pattern="@Thing",
                target_pattern="@Behavior", relationship_name="uses",
                valid=True, priority=40,
            ),
            KernelValidityRule(
                id="ta-fallback-uses", source_pattern="*",
                target_pattern="*", relationship_name="uses",
                valid=False, priority=1,
            ),
        ),
        metadata=ProfileMetadata(standard="Test 1.0", organization="Test Org"),
    )


def _make_invalid_profile() -> KernelProfile:
    """A profile with invalid kernel refs."""
    return KernelProfile(
        name="InvalidAudit",
        version="1.0",
        kernel_version="2.5.0",
        elements=(
            ProfileElement("Widget", "nonexistent_entity", "Core", "Thing"),
        ),
        relations=(ProfileRelation("uses", "nonexistent_relation"),),
        validity_rules=(
            KernelValidityRule(
                id="inv-fallback-uses", source_pattern="*",
                target_pattern="*", relationship_name="uses",
                valid=False, priority=1,
            ),
        ),
    )


@pytest.fixture
def auditor():
    return ProfileAuditor(KERNEL_SCHEMA)


# ── ProfileAuditor.audit_profile ──────────────────────────────

class TestAuditProfile:
    def test_valid_profile_passes(self, auditor):
        result = auditor.audit_profile(_make_valid_profile())
        assert isinstance(result, AuditResult)
        assert result.passed is True
        assert result.profile_name == "TestAudit"

    def test_invalid_profile_fails(self, auditor):
        result = auditor.audit_profile(_make_invalid_profile())
        assert result.passed is False
        error_findings = [
            f for f in result.findings
            if f.severity == AuditSeverity.ERROR
        ]
        assert len(error_findings) > 0

    def test_invalid_kernel_ref_is_error_severity(self, auditor):
        result = auditor.audit_profile(_make_invalid_profile())
        ref_findings = [
            f for f in result.findings
            if f.category == "invalid_kernel_ref"
        ]
        assert len(ref_findings) > 0
        assert all(f.severity == AuditSeverity.ERROR for f in ref_findings)

    def test_quality_report_attached(self, auditor):
        result = auditor.audit_profile(_make_valid_profile())
        assert result.quality is not None
        assert isinstance(result.quality.coverage, float)

    def test_findings_are_tuple(self, auditor):
        result = auditor.audit_profile(_make_valid_profile())
        assert isinstance(result.findings, tuple)


# ── ProfileAuditor.audit_registry ─────────────────────────────

class TestAuditRegistry:
    def test_all_builtins_pass(self, auditor):
        registry = ProfileRegistry()
        registry.bootstrap()
        report = auditor.audit_registry(registry)
        assert isinstance(report, RegistryAuditReport)
        # 5 framework + 7 EA-sys layer + 2 governance stack = 14
        assert report.total_profiles == 14
        assert report.passed_profiles == 14

    def test_empty_registry(self, auditor):
        registry = ProfileRegistry()
        report = auditor.audit_registry(registry)
        assert report.total_profiles == 0
        assert report.passed_profiles == 0

    def test_mixed_registry(self, auditor):
        registry = ProfileRegistry()
        registry.register(_make_valid_profile())
        registry.register(_make_invalid_profile())
        report = auditor.audit_registry(registry)
        assert report.total_profiles == 2
        assert report.passed_profiles == 1

    def test_type_check(self, auditor):
        with pytest.raises(TypeError, match="ProfileRegistry"):
            auditor.audit_registry("not a registry")  # type: ignore[arg-type]


# ── ProfileAuditor.detect_drift ───────────────────────────────

class TestDetectDrift:
    def _make_shrunk_kernel(self) -> KernelSchema:
        """Build a kernel missing some entities/relations."""
        # Keep only a subset of entities, removing 'step'
        kept_entities = tuple(
            e for e in KERNEL_SCHEMA.entities if e.name != "step"
        )
        kept_relations = tuple(
            r for r in KERNEL_SCHEMA.relations if r.name != "association"
        )
        return KernelSchema(
            attributes=KERNEL_SCHEMA.attributes,
            entities=kept_entities,
            relations=kept_relations,
            validity_rules=KERNEL_SCHEMA.validity_rules,
            layer_constraints=KERNEL_SCHEMA.layer_constraints,
        )

    def test_no_drift_same_kernel(self, auditor):
        profile = _make_valid_profile()
        drift = auditor.detect_drift(profile, KERNEL_SCHEMA)
        assert drift == ()

    def test_broken_type_ref(self, auditor):
        profile = _make_valid_profile()
        new_kernel = self._make_shrunk_kernel()
        drift = auditor.detect_drift(profile, new_kernel)
        type_drifts = [d for d in drift if d.category == "broken_type_ref"]
        assert len(type_drifts) >= 1
        assert any("step" in d.message for d in type_drifts)

    def test_broken_relation_ref(self, auditor):
        profile = _make_valid_profile()
        new_kernel = self._make_shrunk_kernel()
        drift = auditor.detect_drift(profile, new_kernel)
        rel_drifts = [d for d in drift if d.category == "broken_relation_ref"]
        assert len(rel_drifts) >= 1
        assert any("association" in d.message for d in rel_drifts)

    def test_drift_entries_are_tuple(self, auditor):
        profile = _make_valid_profile()
        drift = auditor.detect_drift(profile, KERNEL_SCHEMA)
        assert isinstance(drift, tuple)


# ── Store audit hook ──────────────────────────────────────────

class TestStoreAuditHook:
    def test_store_without_hook(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        pv = store.store(_make_valid_profile())
        assert pv.profile_name == "TestAudit"
        store.close()

    def test_store_with_hook_passing(self):
        auditor = ProfileAuditor(KERNEL_SCHEMA)
        store = SQLiteProfileStore(":memory:", audit_hook=auditor.audit_profile)
        store.initialize()
        pv = store.store(_make_valid_profile())
        assert pv.profile_name == "TestAudit"
        store.close()

    def test_store_with_hook_failing(self):
        auditor = ProfileAuditor(KERNEL_SCHEMA)
        store = SQLiteProfileStore(":memory:", audit_hook=auditor.audit_profile)
        store.initialize()
        with pytest.raises(ProfileStoreError, match="Audit failed"):
            store.store(_make_invalid_profile())
        store.close()

    def test_hook_blocks_persist(self):
        auditor = ProfileAuditor(KERNEL_SCHEMA)
        store = SQLiteProfileStore(":memory:", audit_hook=auditor.audit_profile)
        store.initialize()
        with pytest.raises(ProfileStoreError):
            store.store(_make_invalid_profile())
        assert store.list_profiles() == []
        store.close()


# ── Type immutability ─────────────────────────────────────────

class TestAuditTypes:
    def test_audit_finding_frozen(self):
        f = AuditFinding(
            severity=AuditSeverity.ERROR,
            category="test",
            message="test",
        )
        with pytest.raises(AttributeError):
            f.severity = AuditSeverity.WARNING  # type: ignore[misc]

    def test_drift_entry_frozen(self):
        d = DriftEntry(
            category="test",
            message="test",
            element_or_rule="test",
        )
        with pytest.raises(AttributeError):
            d.category = "other"  # type: ignore[misc]

    def test_audit_result_frozen(self):
        from ea_kernel.profile_types import QualityReport
        qr = QualityReport(
            passed=True, dead_rules=(), conflicting_rules=(),
            missing_fallbacks=(), invalid_patterns=(),
            invalid_kernel_refs=(), coverage=1.0,
        )
        ar = AuditResult(
            profile_name="t", passed=True, findings=(), quality=qr,
        )
        with pytest.raises(AttributeError):
            ar.passed = False  # type: ignore[misc]
