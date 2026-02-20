"""Tests for SDLC domain-model profile metadata."""

from ea_kernel.profiles.sdlc import profile_path
from ea_kernel.spec import KERNEL_SPEC
from ea_profile.loader import load_profile
from ea_profile.profile_validator import validate_profile
from ea_profile.quality_gate import check_profile_quality
from ea_profile.types import KernelProfile


def _rule_pairs(
    profile: KernelProfile,
    relation: str,
    *,
    valid: bool,
) -> set[tuple[str, str]]:
    return {
        (rule.source_pattern, rule.target_pattern)
        for rule in profile.validity_rules
        if rule.relationship_name == relation and rule.valid is valid and rule.priority > 1
    }


def test_sdlc_domain_model_profile_defines_required_elements_and_relations() -> None:
    profile = load_profile(profile_path("domain-model"), KERNEL_SPEC)

    element_names = {element.name for element in profile.elements}
    assert {
        "Module",
        "Interface",
        "Endpoint",
        "DataModel",
        "Repository",
        "Service",
    } <= element_names

    relation_names = {relation.name for relation in profile.relations}
    assert relation_names == {
        "implements",
        "calls",
        "stores",
        "exposes",
        "depends_on",
    }


def test_sdlc_domain_model_profile_enforces_repository_mediated_data_access() -> None:
    profile = load_profile(profile_path("domain-model"), KERNEL_SPEC)

    allow_depends_on = _rule_pairs(profile, "depends_on", valid=True)
    allow_stores = _rule_pairs(profile, "stores", valid=True)
    deny_depends_on = _rule_pairs(profile, "depends_on", valid=False)
    deny_calls = _rule_pairs(profile, "calls", valid=False)
    deny_stores = _rule_pairs(profile, "stores", valid=False)

    assert ("Service", "Repository") in allow_depends_on
    assert ("Repository", "DataModel") in allow_stores

    assert ("Service", "DataModel") in deny_depends_on
    assert ("Service", "DataModel") in deny_calls
    assert ("Service", "DataModel") in deny_stores


def test_sdlc_domain_model_profile_passes_validator_and_kernel_rule_checks() -> None:
    profile = load_profile(profile_path("domain-model"), KERNEL_SPEC)

    validation_result = validate_profile(profile)
    quality_result = check_profile_quality(profile, KERNEL_SPEC)

    assert validation_result.passed is True, validation_result.errors
    assert quality_result.passed is True, (
        f"Quality gate failed:\n"
        f"  dead_rules={quality_result.dead_rules}\n"
        f"  conflicting_rules={quality_result.conflicting_rules}\n"
        f"  missing_fallbacks={quality_result.missing_fallbacks}\n"
        f"  invalid_patterns={quality_result.invalid_patterns}\n"
        f"  invalid_kernel_refs={quality_result.invalid_kernel_refs}"
    )
