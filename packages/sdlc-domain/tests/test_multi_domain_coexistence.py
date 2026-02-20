"""US-021: multi-domain coexistence validation on a single kernel instance."""

from __future__ import annotations

import uuid

from ea_kernel.decision_store import InMemoryDecisionStore
from ea_kernel.evidence_analyzer import EvidenceAnalyzer
from ea_kernel.profiles.ea_sys import layer_path
from ea_kernel.profiles.sdlc import profile_path
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleEvidence,
    RuleGroup,
    RuleMetadata,
)
from ea_profile.composer import extend
from ea_profile.loader import load_profile
from ea_profile.profile_validator import ProfileValidationResult, validate_profile
from ea_profile.types import KernelProfile
from sdlc_domain.sdlc_analyzer import SDLCAnalyzer
from sdlc_domain.sdlc_projection import project_governance_surface, project_sdlc_surface
from sdlc_domain.sdlc_store import InMemorySDLCStore, StoredSDLCSnapshot

GOVERNANCE_PROFILE_IDS: tuple[str, ...] = (
    "infra",
    "governance",
    "decision",
    "needs",
    "kernel",
    "flow",
    "projection",
)

SDLC_PROFILE_IDS: tuple[str, ...] = (
    "arch-decision",
    "requirements",
    "domain-model",
    "pipeline",
    "projection",
)


def _load_governance_profiles() -> dict[str, KernelProfile]:
    return {
        profile_id: load_profile(layer_path(profile_id), KERNEL_SPEC)
        for profile_id in GOVERNANCE_PROFILE_IDS
    }


def _load_sdlc_profiles() -> dict[str, KernelProfile]:
    return {
        profile_id: load_profile(profile_path(profile_id), KERNEL_SPEC)
        for profile_id in SDLC_PROFILE_IDS
    }


def _load_namespaced_profiles() -> dict[str, KernelProfile]:
    profiles: dict[str, KernelProfile] = {}

    for profile_id, profile in _load_governance_profiles().items():
        profiles[f"governance:{profile_id}"] = profile

    for profile_id, profile in _load_sdlc_profiles().items():
        profiles[f"sdlc:{profile_id}"] = profile

    return profiles


def _domain_view(
    namespaced_profiles: dict[str, KernelProfile],
    namespace: str,
) -> dict[str, KernelProfile]:
    prefix = f"{namespace}:"
    return {
        key.removeprefix(prefix): profile
        for key, profile in namespaced_profiles.items()
        if key.startswith(prefix)
    }


def _compose_domain_profile(
    *,
    name: str,
    profile_ids: tuple[str, ...],
    profiles: dict[str, KernelProfile],
) -> KernelProfile:
    ordered_profiles = tuple(profiles[profile_id] for profile_id in profile_ids)
    composed = ordered_profiles[0]

    for profile in ordered_profiles[1:]:
        composed = extend(
            composed,
            name=name,
            version="0.1.0",
            add_elements=profile.elements,
            add_relations=profile.relations,
            add_rules=profile.validity_rules,
            add_state_transitions=profile.state_transitions,
            add_artifact_types=profile.artifact_types,
            add_process_units=profile.process_units,
        )

    return composed


def _validation_result(
    *,
    name: str,
    profile_ids: tuple[str, ...],
    profiles: dict[str, KernelProfile],
) -> ProfileValidationResult:
    return validate_profile(
        _compose_domain_profile(
            name=name,
            profile_ids=profile_ids,
            profiles=profiles,
        )
    )


def _rule_entry(rule_id: str) -> RuleCorpusEntry:
    return RuleCorpusEntry(
        rule=KernelValidityRule(
            id=rule_id,
            source_pattern="*",
            target_pattern="*",
            relationship_name="flow",
            valid=True,
            priority=50,
        ),
        metadata=RuleMetadata(
            domain="governance",
            tags=("governance",),
            category=RuleCategory.BEHAVIORAL,
            confidence=RuleConfidence.COMMON,
            source="us-021-test",
            established_version="0.1.0",
            rationale="US-021 governance integration seed data",
            group=RuleGroup.FLOW,
        ),
    )


def _governance_decision_record(
    *,
    rule_id: str,
    timestamp: str,
    decision_type: str = "accept",
    winner: bool = True,
) -> DecisionRecord:
    evidence = RuleEvidence(
        entry=_rule_entry(rule_id),
        matched=True,
        is_winner=winner,
        condition_results=(),
    )

    return DecisionRecord(
        id=f"gov-{uuid.uuid4().hex}",
        timestamp=timestamp,
        actor="system:governance",
        decision_type=decision_type,
        subject_triple=("Policy", rule_id, "flow"),
        judgment=JudgmentReport(
            verdict=True,
            evidence=(evidence,),
            confidence=RuleConfidence.COMMON,
            domains=("governance",),
            conflicts=(),
        ),
    )


def _seed_governance_store(store: InMemoryDecisionStore) -> None:
    records = (
        _governance_decision_record(
            rule_id="gov-rule-001",
            timestamp="2025-02-01T00:00:00Z",
        ),
        _governance_decision_record(
            rule_id="gov-rule-002",
            timestamp="2025-02-02T00:00:00Z",
        ),
        _governance_decision_record(
            rule_id="gov-rule-002",
            timestamp="2025-02-03T00:00:00Z",
            decision_type="override",
            winner=False,
        ),
    )

    for record in records:
        store.store(record)


def _sdlc_snapshot(
    *,
    snapshot_id: str,
    lineage_id: str,
    profile_id: str,
    status: str,
    recorded_at: str,
) -> StoredSDLCSnapshot:
    return StoredSDLCSnapshot(
        storage_id="",
        snapshot_id=snapshot_id,
        lineage_id=lineage_id,
        profile_id=profile_id,
        status=status,
        recorded_at=recorded_at,
        owner="team-sdlc",
    )


def _store_sdlc_lineage(
    store: InMemorySDLCStore,
    *,
    profile_id: str,
    lineage_id: str,
    statuses: tuple[str, ...],
    start_day: int,
) -> None:
    for index, status in enumerate(statuses, start=1):
        day = start_day + index - 1
        store.store(
            _sdlc_snapshot(
                snapshot_id=f"{lineage_id}-{index}",
                lineage_id=lineage_id,
                profile_id=profile_id,
                status=status,
                recorded_at=f"2025-02-{day:02d}T00:00:00Z",
            )
        )


def _seed_sdlc_store(store: InMemorySDLCStore) -> None:
    _store_sdlc_lineage(
        store,
        profile_id="requirements",
        lineage_id="req-42",
        statuses=(
            "BACKLOG",
            "GROOMED",
            "SPRINT",
            "IN_PROGRESS",
            "REVIEW",
            "DONE",
            "CLOSED",
        ),
        start_day=1,
    )
    _store_sdlc_lineage(
        store,
        profile_id="pipeline",
        lineage_id="pipe-42",
        statuses=("QUEUED", "BUILDING", "TESTING", "STAGING", "PRODUCTION"),
        start_day=10,
    )
    _store_sdlc_lineage(
        store,
        profile_id="arch-decision",
        lineage_id="adr-42",
        statuses=("PROPOSED", "REVIEW", "ACCEPTED"),
        start_day=20,
    )


def test_single_kernel_loads_governance_and_sdlc_profiles_together() -> None:
    profiles = _load_namespaced_profiles()

    assert len(profiles) == len(GOVERNANCE_PROFILE_IDS) + len(SDLC_PROFILE_IDS)
    assert all(isinstance(profile, KernelProfile) for profile in profiles.values())


def test_profile_namespaces_are_isolated_even_when_raw_ids_overlap() -> None:
    raw_overlap = set(GOVERNANCE_PROFILE_IDS) & set(SDLC_PROFILE_IDS)
    assert raw_overlap == {"projection"}

    profiles = _load_namespaced_profiles()
    assert "governance:projection" in profiles
    assert "sdlc:projection" in profiles
    assert len(profiles) == len(set(profiles))


def test_governance_rule_validation_does_not_interfere_with_sdlc_elements() -> None:
    isolated_result = _validation_result(
        name="US-021-Governance-Isolated",
        profile_ids=GOVERNANCE_PROFILE_IDS,
        profiles=_load_governance_profiles(),
    )

    coexisting_profiles = _domain_view(_load_namespaced_profiles(), "governance")
    coexisting_result = _validation_result(
        name="US-021-Governance-Coexisting",
        profile_ids=GOVERNANCE_PROFILE_IDS,
        profiles=coexisting_profiles,
    )

    assert isolated_result == coexisting_result
    assert coexisting_result.passed is True, coexisting_result.errors


def test_sdlc_rule_validation_does_not_interfere_with_governance_elements() -> None:
    isolated_result = _validation_result(
        name="US-021-SDLC-Isolated",
        profile_ids=SDLC_PROFILE_IDS,
        profiles=_load_sdlc_profiles(),
    )

    coexisting_profiles = _domain_view(_load_namespaced_profiles(), "sdlc")
    coexisting_result = _validation_result(
        name="US-021-SDLC-Coexisting",
        profile_ids=SDLC_PROFILE_IDS,
        profiles=coexisting_profiles,
    )

    assert isolated_result == coexisting_result
    assert coexisting_result.passed is True, coexisting_result.errors


def test_multi_domain_lifecycle_store_analyze_project_runs_together() -> None:
    governance_store = InMemoryDecisionStore()
    _seed_governance_store(governance_store)
    governance_analysis = EvidenceAnalyzer(governance_store).generate_report(
        report_id="us-021-governance",
    )

    sdlc_store = InMemorySDLCStore()
    _seed_sdlc_store(sdlc_store)
    sdlc_analysis = SDLCAnalyzer(sdlc_store).generate_report(
        report_id="us-021-sdlc",
    )

    governance_surface = project_governance_surface(levels=("l0", "l1", "l2", "l3"))
    sdlc_surface = project_sdlc_surface(levels=("l0", "l1", "l2", "l3"))

    assert governance_analysis.total_decisions_analyzed == governance_store.count()
    assert governance_analysis.total_decisions_analyzed > 0
    assert sdlc_analysis.total_snapshots_analyzed == sdlc_store.count()
    assert sdlc_analysis.total_snapshots_analyzed > 0

    assert governance_surface.surface_summary["total_artifacts"] > 0
    assert sdlc_surface.surface_summary["total_artifacts"] > 0

    governance_types = set(governance_surface.surface_summary["by_type"])
    sdlc_types = set(sdlc_surface.surface_summary["by_type"])
    assert "configuration" in governance_types
    assert "repository" in sdlc_types
    assert "repository" not in governance_types
