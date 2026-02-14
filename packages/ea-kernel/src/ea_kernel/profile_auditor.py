"""Profile Auditor — post-build validation for profiles and registries.

Bridges the gap between build-time quality gate and runtime:
- audit_profile: full audit of a single profile against the kernel
- audit_registry: batch audit of all registered profiles
- detect_drift: find profile breakages when kernel schema changes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ea_kernel.profile_quality_gate import check_profile_quality
from ea_kernel.profile_types import (
    AuditFinding,
    AuditResult,
    AuditSeverity,
    DriftEntry,
    KernelProfile,
    QualityReport,
    RegistryAuditReport,
)
from ea_kernel.types import KernelSchema

if TYPE_CHECKING:
    from ea_kernel.profile_registry import ProfileRegistry


class ProfileAuditor:
    """Audits profiles against a kernel schema."""

    __slots__ = ("_kernel",)

    def __init__(self, kernel: KernelSchema) -> None:
        self._kernel = kernel

    @property
    def kernel(self) -> KernelSchema:
        return self._kernel

    # ── Single profile audit ───────────────────────────────────

    def audit_profile(self, profile: KernelProfile) -> AuditResult:
        """Run a full audit on a single profile.

        Wraps check_profile_quality and converts findings
        to severity-tagged AuditFinding entries, plus direction
        consistency checks.
        """
        qr = check_profile_quality(profile, self._kernel)
        findings = _quality_to_findings(qr)
        findings.extend(_check_direction_consistency(profile))

        return AuditResult(
            profile_name=profile.name,
            passed=qr.passed,
            findings=tuple(findings),
            quality=qr,
        )

    # ── Registry audit ─────────────────────────────────────────

    def audit_registry(self, registry: ProfileRegistry) -> RegistryAuditReport:
        """Audit all profiles in a registry."""
        from ea_kernel.profile_registry import ProfileRegistry as _PR
        if not isinstance(registry, _PR):
            raise TypeError(f"Expected ProfileRegistry, got {type(registry).__name__}")

        results: list[AuditResult] = []
        for profile in registry.list_all():
            results.append(self.audit_profile(profile))

        passed = sum(1 for r in results if r.passed)
        return RegistryAuditReport(
            total_profiles=len(results),
            passed_profiles=passed,
            results=tuple(results),
        )

    # ── Drift detection ────────────────────────────────────────

    def detect_drift(
        self,
        profile: KernelProfile,
        new_kernel: KernelSchema,
    ) -> tuple[DriftEntry, ...]:
        """Detect profile breakages when migrating to a new kernel.

        Compares the profile's kernel references against both
        the current kernel (self._kernel) and the new kernel.
        Reports references that were valid but are now broken.
        """
        old_entities = {e.name for e in self._kernel.entities}
        new_entities = {e.name for e in new_kernel.entities}
        old_relations = {r.name for r in self._kernel.relations}
        new_relations = {r.name for r in new_kernel.relations}

        entries: list[DriftEntry] = []

        # Check element kernel_type references
        for elem in profile.elements:
            was_valid = elem.kernel_type in old_entities
            now_valid = elem.kernel_type in new_entities
            if was_valid and not now_valid:
                entries.append(DriftEntry(
                    category="broken_type_ref",
                    message=(
                        f"Element '{elem.name}' references kernel type "
                        f"'{elem.kernel_type}' which was removed"
                    ),
                    element_or_rule=f"element:{elem.name}",
                ))

        # Check relation kernel_relation references
        for rel in profile.relations:
            was_valid = rel.kernel_relation in old_relations
            now_valid = rel.kernel_relation in new_relations
            if was_valid and not now_valid:
                entries.append(DriftEntry(
                    category="broken_relation_ref",
                    message=(
                        f"Relation '{rel.name}' references kernel relation "
                        f"'{rel.kernel_relation}' which was removed"
                    ),
                    element_or_rule=f"relation:{rel.name}",
                ))

        # Check validity rule patterns against new kernel's pattern_matches
        for rule in profile.validity_rules:
            if rule.source_pattern == "*" or rule.target_pattern == "*":
                continue
            # Check if patterns still resolve in new kernel
            src_old = new_kernel._pattern_matches.get(rule.source_pattern, frozenset())
            tgt_old = new_kernel._pattern_matches.get(rule.target_pattern, frozenset())
            if not src_old and rule.source_pattern in (
                e.name for e in self._kernel.entities
            ):
                entries.append(DriftEntry(
                    category="rule_pattern_broken",
                    message=(
                        f"Rule '{rule.id}' source pattern '{rule.source_pattern}' "
                        f"no longer resolves in new kernel"
                    ),
                    element_or_rule=f"rule:{rule.id}",
                ))
            if not tgt_old and rule.target_pattern in (
                e.name for e in self._kernel.entities
            ):
                entries.append(DriftEntry(
                    category="rule_pattern_broken",
                    message=(
                        f"Rule '{rule.id}' target pattern '{rule.target_pattern}' "
                        f"no longer resolves in new kernel"
                    ),
                    element_or_rule=f"rule:{rule.id}",
                ))

        return tuple(entries)


# ── Internal helpers ───────────────────────────────────────────

def _check_direction_consistency(
    profile: KernelProfile,
) -> list[AuditFinding]:
    """Check direction consistency for relations sharing the same kernel_relation.

    Rules:
    - If all relations for a kernel_relation have direction="" → OK
    - If direction is set, relations with the same kernel_relation and same
      direction are flagged as WARNING (duplicate direction).
    """
    findings: list[AuditFinding] = []

    # Group relations by kernel_relation
    groups: dict[str, list[tuple[str, str]]] = {}
    for rel in profile.relations:
        groups.setdefault(rel.kernel_relation, []).append(
            (rel.name, rel.direction)
        )

    for kernel_rel, members in groups.items():
        directed = [(name, d) for name, d in members if d]
        if not directed:
            continue
        # Check for duplicate directions within the same kernel_relation
        seen_dirs: dict[str, list[str]] = {}
        for name, d in directed:
            seen_dirs.setdefault(d, []).append(name)
        for d, names in seen_dirs.items():
            if len(names) > 1:
                findings.append(AuditFinding(
                    severity=AuditSeverity.WARNING,
                    category="direction_inconsistency",
                    message=(
                        f"Relations {names} all map to kernel '{kernel_rel}' "
                        f"with same direction '{d}'"
                    ),
                ))

    return findings


def _quality_to_findings(qr: QualityReport) -> list[AuditFinding]:
    """Convert a QualityReport to a list of AuditFindings."""
    findings: list[AuditFinding] = []

    for ref in qr.invalid_kernel_refs:
        findings.append(AuditFinding(
            severity=AuditSeverity.ERROR,
            category="invalid_kernel_ref",
            message=f"Invalid kernel reference: {ref}",
        ))

    for pat in qr.invalid_patterns:
        findings.append(AuditFinding(
            severity=AuditSeverity.ERROR,
            category="invalid_pattern",
            message=f"Pattern does not resolve: {pat}",
        ))

    for pair in qr.conflicting_rules:
        findings.append(AuditFinding(
            severity=AuditSeverity.ERROR,
            category="conflicting_rules",
            message=f"Rules conflict at same priority: {pair[0]} vs {pair[1]}",
            rule_id=pair[0],
        ))

    for rule_id in qr.dead_rules:
        findings.append(AuditFinding(
            severity=AuditSeverity.WARNING,
            category="dead_rule",
            message=f"Rule always shadowed by higher-priority rule: {rule_id}",
            rule_id=rule_id,
        ))

    for rel in qr.missing_fallbacks:
        findings.append(AuditFinding(
            severity=AuditSeverity.INFO,
            category="missing_fallback",
            message=f"No deny-by-default fallback for relation: {rel}",
        ))

    if qr.coverage < 0.3:
        findings.append(AuditFinding(
            severity=AuditSeverity.WARNING,
            category="low_coverage",
            message=f"Low kernel coverage: {qr.coverage:.0%}",
        ))

    return findings
