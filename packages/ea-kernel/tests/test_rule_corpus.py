"""Tests for Phase 0.5 Rule Corpus Model."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from ea_kernel.profile_builder import ProfileBuilder
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.spec_loader import load_kernel_rules_with_metadata
from ea_kernel.types import (
    JudgmentReport,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleEvidence,
    RuleGroup,
    RuleMetadata,
)

# ═════════════════════════════════════════════════════════════════════════════
# 1. Type tests
# ═════════════════════════════════════════════════════════════════════════════

class TestTypes:
    def test_rule_metadata_frozen(self):
        meta = RuleMetadata(
            domain="kernel", tags=("a",), category=RuleCategory.STRUCTURAL,
            confidence=RuleConfidence.UNIVERSAL, source="test",
            established_version="1.0", rationale="test",
        )
        with pytest.raises(AttributeError):
            meta.domain = "other"  # type: ignore[misc]

    def test_rule_corpus_entry_frozen(self):
        rule = KernelValidityRule(
            id="test-01", source_pattern="*", target_pattern="*",
            relationship_name="association",
        )
        meta = RuleMetadata(
            domain="kernel", tags=(), category=RuleCategory.STRUCTURAL,
            confidence=RuleConfidence.COMMON, source="test",
            established_version="1.0", rationale="",
        )
        entry = RuleCorpusEntry(rule=rule, metadata=meta)
        with pytest.raises(AttributeError):
            entry.rule = rule  # type: ignore[misc]

    def test_rule_metadata_equality(self):
        kwargs = {
            "domain": "kernel",
            "tags": ("x",),
            "category": RuleCategory.STRUCTURAL,
            "confidence": RuleConfidence.COMMON,
            "source": "s",
            "established_version": "1.0",
            "rationale": "r",
        }
        assert RuleMetadata(**kwargs) == RuleMetadata(**kwargs)

    def test_rule_category_enum(self):
        assert RuleCategory.STRUCTURAL.value == "structural"
        assert RuleCategory.BEHAVIORAL.value == "behavioral"
        assert RuleCategory.DOMAIN.value == "domain"
        assert RuleCategory.EMPIRICAL.value == "empirical"

    def test_rule_confidence_enum(self):
        assert RuleConfidence.UNIVERSAL.value == "universal"
        assert RuleConfidence.COMMON.value == "common"
        assert RuleConfidence.CONTEXTUAL.value == "contextual"
        assert RuleConfidence.EMPIRICAL.value == "empirical"

    def test_judgment_report_frozen(self):
        report = JudgmentReport(
            verdict=True, evidence=(), confidence=RuleConfidence.COMMON,
            domains=(), conflicts=(),
        )
        with pytest.raises(AttributeError):
            report.verdict = False  # type: ignore[misc]

    def test_rule_evidence_frozen(self):
        rule = KernelValidityRule(
            id="t", source_pattern="*", target_pattern="*",
            relationship_name="association",
        )
        meta = RuleMetadata(
            domain="k", tags=(), category=RuleCategory.STRUCTURAL,
            confidence=RuleConfidence.COMMON, source="", established_version="",
            rationale="",
        )
        ev = RuleEvidence(
            entry=RuleCorpusEntry(rule=rule, metadata=meta),
            matched=True, is_winner=True, condition_results=(),
        )
        with pytest.raises(AttributeError):
            ev.matched = False  # type: ignore[misc]


# ═════════════════════════════════════════════════════════════════════════════
# 2. from_kernel_spec
# ═════════════════════════════════════════════════════════════════════════════

class TestFromKernelSpec:
    def test_all_rules_converted(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        assert len(corpus.entries) == len(KERNEL_SPEC.validity_rules)

    def test_all_entries_have_metadata(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        for entry in corpus.entries:
            assert entry.metadata is not None
            assert isinstance(entry.metadata, RuleMetadata)

    def test_entries_preserve_rule_identity(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        rule_ids = {e.rule.id for e in corpus.entries}
        expected_ids = {r.id for r in KERNEL_SPEC.validity_rules}
        assert rule_ids == expected_ids

    def test_with_explicit_metadata_map(self):
        explicit_meta = RuleMetadata(
            domain="test", tags=("custom",), category=RuleCategory.DOMAIN,
            confidence=RuleConfidence.CONTEXTUAL, source="test-src",
            established_version="2.0", rationale="explicit test",
        )
        corpus = RuleCorpus.from_kernel_spec(
            KERNEL_SPEC, metadata_map={"mem-01": explicit_meta},
        )
        mem01 = next(e for e in corpus.entries if e.rule.id == "mem-01")
        assert mem01.metadata == explicit_meta
        assert mem01.metadata.domain == "test"


# ═════════════════════════════════════════════════════════════════════════════
# 3. infer_metadata
# ═════════════════════════════════════════════════════════════════════════════

class TestInferMetadata:
    def test_l2_relation_is_structural(self):
        rule = KernelValidityRule(
            id="t", source_pattern="*", target_pattern="*",
            relationship_name="membership", priority=40,
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.category == RuleCategory.STRUCTURAL

    def test_l3_relation_is_behavioral(self):
        rule = KernelValidityRule(
            id="t", source_pattern="*", target_pattern="*",
            relationship_name="flow", priority=40,
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.category == RuleCategory.BEHAVIORAL

    def test_high_priority_deny_is_universal(self):
        rule = KernelValidityRule(
            id="t", source_pattern="item", target_pattern="structure",
            relationship_name="specialization", valid=False, priority=80,
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.confidence == RuleConfidence.UNIVERSAL

    def test_fallback_deny_is_universal(self):
        rule = KernelValidityRule(
            id="fallback-flow", source_pattern="*", target_pattern="*",
            relationship_name="flow", valid=False, priority=1,
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.confidence == RuleConfidence.UNIVERSAL

    def test_allow_is_common(self):
        rule = KernelValidityRule(
            id="t", source_pattern="metatype*", target_pattern="metatype*",
            relationship_name="association", priority=40,
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.confidence == RuleConfidence.COMMON

    def test_domain_is_kernel(self):
        rule = KernelValidityRule(
            id="t", source_pattern="*", target_pattern="*",
            relationship_name="association",
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.domain == "kernel"

    def test_tags_contain_relation_name(self):
        rule = KernelValidityRule(
            id="t", source_pattern="*", target_pattern="*",
            relationship_name="succession",
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert "succession" in meta.tags

    def test_unknown_relation_is_domain_category(self):
        rule = KernelValidityRule(
            id="t", source_pattern="*", target_pattern="*",
            relationship_name="custom_rel",
        )
        meta = RuleCorpus.infer_metadata(rule)
        assert meta.category == RuleCategory.DOMAIN


# ═════════════════════════════════════════════════════════════════════════════
# 4. Query methods
# ═════════════════════════════════════════════════════════════════════════════

class TestQuery:
    @pytest.fixture
    def corpus(self):
        return RuleCorpus.from_kernel_spec(KERNEL_SPEC)

    def test_by_domain_kernel(self, corpus):
        kernel_entries = corpus.by_domain("kernel")
        assert len(kernel_entries) == len(corpus.entries)

    def test_by_domain_nonexistent(self, corpus):
        assert corpus.by_domain("nonexistent") == ()

    def test_by_tag_membership(self, corpus):
        entries = corpus.by_tag("membership")
        assert len(entries) > 0
        for e in entries:
            assert e.rule.relationship_name == "membership"

    def test_by_category_structural(self, corpus):
        structural = corpus.by_category(RuleCategory.STRUCTURAL)
        assert len(structural) > 0
        for e in structural:
            assert e.metadata.category == RuleCategory.STRUCTURAL

    def test_by_category_behavioral(self, corpus):
        behavioral = corpus.by_category(RuleCategory.BEHAVIORAL)
        assert len(behavioral) > 0
        for e in behavioral:
            assert e.metadata.category == RuleCategory.BEHAVIORAL

    def test_by_confidence_universal(self, corpus):
        universal = corpus.by_confidence(RuleConfidence.UNIVERSAL)
        assert len(universal) > 0
        for e in universal:
            assert e.metadata.confidence == RuleConfidence.UNIVERSAL

    def test_structural_and_behavioral_cover_all(self, corpus):
        structural = corpus.by_category(RuleCategory.STRUCTURAL)
        behavioral = corpus.by_category(RuleCategory.BEHAVIORAL)
        assert len(structural) + len(behavioral) == len(corpus.entries)


# ═════════════════════════════════════════════════════════════════════════════
# 5. Conflict detection
# ═════════════════════════════════════════════════════════════════════════════

class TestConflictDetection:
    def test_no_conflict_within_single_domain(self):
        """Intra-domain allow/deny coexistence is normal, not a conflict."""
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        # structure→structure association has both allow (assoc-01/02) and fallback deny
        # but all within kernel domain — no cross-domain conflict
        conflicts = corpus.detect_conflicts("structure", "structure", "association")
        assert len(conflicts) == 0

    def test_cross_domain_conflict_detected(self):
        """When a profile allows what kernel denies, detect the conflict."""
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)

        # Kernel denies item→structure specialization (spec-09)
        # Add a profile rule that allows it
        profile_rule = KernelValidityRule(
            id="prof-spec-01",
            source_pattern="item",
            target_pattern="structure",
            relationship_name="specialization",
            valid=True,
            priority=40,
        )
        extended = corpus.with_profile_rules(
            "test-profile", (profile_rule,),
        )

        # Need to also inject the rule into the schema for matching
        # Since we can't modify the frozen schema, we test conflict detection
        # on the corpus level with a custom schema
        from ea_kernel.types import KernelSchema
        extended_schema = KernelSchema(
            attributes=KERNEL_SPEC.attributes,
            entities=KERNEL_SPEC.entities,
            relations=KERNEL_SPEC.relations,
            validity_rules=(*KERNEL_SPEC.validity_rules, profile_rule),
            layer_constraints=KERNEL_SPEC.layer_constraints,
        )
        extended_corpus = RuleCorpus(extended.entries, extended_schema)
        conflicts = extended_corpus.detect_conflicts("item", "structure", "specialization")
        assert len(conflicts) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 6. judge() — verdict consistency with validate_relationship()
# ═════════════════════════════════════════════════════════════════════════════

class TestJudge:
    @pytest.fixture
    def corpus(self):
        return RuleCorpus.from_kernel_spec(KERNEL_SPEC)

    def test_judge_allow_matches_validate(self, corpus):
        # structure→structure association should be allowed
        validation = KERNEL_SPEC.validate_relationship(
            "structure", "structure", "association",
        )
        report = corpus.judge("structure", "structure", "association")
        assert report.verdict == validation.valid
        assert report.verdict is True

    def test_judge_deny_matches_validate(self, corpus):
        # item→structure specialization should be denied
        validation = KERNEL_SPEC.validate_relationship(
            "item", "structure", "specialization",
        )
        report = corpus.judge("item", "structure", "specialization")
        assert report.verdict == validation.valid
        assert report.verdict is False

    def test_judge_deny_by_default_matches(self, corpus):
        # Unknown pattern should be denied
        validation = KERNEL_SPEC.validate_relationship(
            "package", "item", "connector",
        )
        report = corpus.judge("package", "item", "connector")
        assert report.verdict == validation.valid

    def test_judge_returns_evidence(self, corpus):
        report = corpus.judge("structure", "structure", "association")
        assert isinstance(report.evidence, tuple)
        assert len(report.evidence) > 0

    def test_judge_has_winner(self, corpus):
        report = corpus.judge("structure", "structure", "association")
        winners = [e for e in report.evidence if e.is_winner]
        assert len(winners) == 1

    def test_judge_winner_is_matched(self, corpus):
        report = corpus.judge("structure", "structure", "association")
        for ev in report.evidence:
            if ev.is_winner:
                assert ev.matched is True

    def test_judge_confidence_present(self, corpus):
        report = corpus.judge("structure", "structure", "association")
        assert isinstance(report.confidence, RuleConfidence)

    def test_judge_domains_present(self, corpus):
        report = corpus.judge("structure", "structure", "association")
        assert "kernel" in report.domains

    def test_judge_condition_results(self, corpus):
        # mem-01 has LAYER_ORDER condition
        report = corpus.judge("namespace", "feature", "membership")
        # Find the evidence for mem-01 (it's the winner — namespace* matches namespace)
        # The condition evaluation should be recorded
        matched_with_conditions = [
            e for e in report.evidence
            if e.matched and e.condition_results
        ]
        assert len(matched_with_conditions) > 0

    def test_judge_multiple_triples(self, corpus):
        """Verify verdict consistency for various triples."""
        triples = [
            ("feature", "metatype", "feature_typing"),
            ("step", "step", "succession"),
            ("event", "step", "triggering"),
            ("state", "expression", "guarding"),
            ("port", "port", "interaction"),  # denied
        ]
        for source, target, relation in triples:
            validation = KERNEL_SPEC.validate_relationship(source, target, relation)
            report = corpus.judge(source, target, relation)
            assert report.verdict == validation.valid, (
                f"Mismatch for {source}→{target} via {relation}: "
                f"validate={validation.valid}, judge={report.verdict}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 7. TOML metadata loading
# ═════════════════════════════════════════════════════════════════════════════

class TestTomlMetadata:
    def test_load_with_metadata_returns_three_values(self):
        rules, constraints, metadata_map = load_kernel_rules_with_metadata()
        assert isinstance(rules, tuple)
        assert isinstance(constraints, tuple)
        assert isinstance(metadata_map, dict)

    def test_all_explicit_metadata_entries(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        assert len(metadata_map) == 67

    def test_mem01_metadata(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        meta = metadata_map["mem-01"]
        assert meta.category == RuleCategory.STRUCTURAL
        assert meta.confidence == RuleConfidence.UNIVERSAL
        assert meta.domain == "kernel"
        assert "containment" in meta.tags

    def test_flow01_metadata(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        meta = metadata_map["flow-01"]
        assert meta.category == RuleCategory.BEHAVIORAL
        assert meta.confidence == RuleConfidence.COMMON

    def test_explicit_metadata_overrides_inference(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map=metadata_map)
        mem01 = next(e for e in corpus.entries if e.rule.id == "mem-01")
        assert mem01.metadata.source == "UML 2.5.1 §7.4 Namespaces"
        assert "containment" in mem01.metadata.tags

    def test_rules_without_metadata_get_inferred(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map=metadata_map)
        # fallback rules have no explicit metadata — they get inferred
        fb = next(e for e in corpus.entries if e.rule.id == "fallback-membership")
        assert fb.metadata.domain == "kernel"
        assert fb.metadata.source == "kernel spec"

    def test_trans01_metadata(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        meta = metadata_map["trans-01"]
        assert meta.category == RuleCategory.BEHAVIORAL
        assert meta.confidence == RuleConfidence.UNIVERSAL
        assert meta.domain == "kernel"
        assert "state-machine" in meta.tags


# ═════════════════════════════════════════════════════════════════════════════
# 7.5. Transition Corpus Tests
# ═════════════════════════════════════════════════════════════════════════════

class TestTransitionCorpus:
    """Verify transition rules in corpus."""

    @pytest.fixture
    def corpus(self):
        return RuleCorpus.from_kernel_spec(KERNEL_SPEC)

    def test_transition_rule_in_corpus(self, corpus):
        trans_entries = [e for e in corpus.entries if e.rule.id == "trans-01"]
        assert len(trans_entries) == 1

    def test_transition_fallback_in_corpus(self, corpus):
        fallback = [e for e in corpus.entries if e.rule.id == "fallback-transition"]
        assert len(fallback) == 1
        assert fallback[0].metadata.confidence == RuleConfidence.UNIVERSAL

    def test_judge_state_state_transition(self, corpus):
        report = corpus.judge("state", "state", "transition")
        assert report.verdict is True
        assert len(report.evidence) > 0

    def test_judge_feature_state_transition_denied(self, corpus):
        report = corpus.judge("feature", "state", "transition")
        assert report.verdict is False

    def test_transition_metadata_map_includes_trans01(self):
        _rules, _constraints, metadata_map = load_kernel_rules_with_metadata()
        assert "trans-01" in metadata_map


# ═════════════════════════════════════════════════════════════════════════════
# 8. ProfileBuilder.build_with_corpus()
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildWithCorpus:
    def test_returns_profile_and_entries(self):
        profile, entries = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build_with_corpus(validate=False)
        )
        assert profile.name == "Test"
        assert isinstance(entries, tuple)
        assert all(isinstance(e, RuleCorpusEntry) for e in entries)

    def test_entries_match_rules_count(self):
        profile, entries = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build_with_corpus(validate=False)
        )
        assert len(entries) == len(profile.validity_rules)

    def test_explicit_metadata_preserved(self):
        explicit_meta = RuleMetadata(
            domain="myprof", tags=("custom",), category=RuleCategory.DOMAIN,
            confidence=RuleConfidence.CONTEXTUAL, source="manual",
            established_version="1.0", rationale="test",
        )
        _profile, entries = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r", rule_id="my-rule", metadata=explicit_meta)
            .build_with_corpus(validate=False)
        )
        my_entry = next(e for e in entries if e.rule.id == "my-rule")
        assert my_entry.metadata == explicit_meta

    def test_fallback_rules_get_inferred_metadata(self):
        _profile, entries = (
            ProfileBuilder("Test", version="1.0", kernel_version="2.5.0")
            .element("A", layer="L", category="C", kernel_type="item")
            .relation("r", kernel_relation="association")
            .allow("A", "A", "r")
            .build_with_corpus(validate=False)
        )
        fallback_entries = [e for e in entries if e.rule.priority == 1]
        assert len(fallback_entries) == 1
        assert fallback_entries[0].metadata.confidence == RuleConfidence.UNIVERSAL


# ═════════════════════════════════════════════════════════════════════════════
# 9. with_profile_rules
# ═════════════════════════════════════════════════════════════════════════════

class TestWithProfileRules:
    def test_immutable_extension(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        original_count = len(corpus.entries)

        new_rule = KernelValidityRule(
            id="prof-01", source_pattern="*", target_pattern="*",
            relationship_name="association", valid=True, priority=30,
        )
        extended = corpus.with_profile_rules("test-profile", (new_rule,))

        assert len(corpus.entries) == original_count  # original unchanged
        assert len(extended.entries) == original_count + 1

    def test_profile_rules_get_profile_domain(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        new_rule = KernelValidityRule(
            id="prof-01", source_pattern="*", target_pattern="*",
            relationship_name="association", valid=True, priority=30,
        )
        extended = corpus.with_profile_rules("myprofile", (new_rule,))
        prof_entry = next(e for e in extended.entries if e.rule.id == "prof-01")
        assert prof_entry.metadata.domain == "myprofile"
        assert prof_entry.metadata.source == "profile:myprofile"

    def test_profile_explicit_metadata(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        new_rule = KernelValidityRule(
            id="prof-01", source_pattern="*", target_pattern="*",
            relationship_name="association", valid=True, priority=30,
        )
        explicit = RuleMetadata(
            domain="custom", tags=("x",), category=RuleCategory.EMPIRICAL,
            confidence=RuleConfidence.EMPIRICAL, source="custom",
            established_version="1.0", rationale="custom",
        )
        extended = corpus.with_profile_rules(
            "myprofile", (new_rule,), metadata_map={"prof-01": explicit},
        )
        prof_entry = next(e for e in extended.entries if e.rule.id == "prof-01")
        assert prof_entry.metadata == explicit


# ═════════════════════════════════════════════════════════════════════════════
# 10. Group query
# ═════════════════════════════════════════════════════════════════════════════

class TestGroupQuery:
    @pytest.fixture
    def corpus(self):
        _, _, metadata_map = load_kernel_rules_with_metadata()
        return RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map=metadata_map)

    def test_by_group_membership(self, corpus):
        entries = corpus.by_group(RuleGroup.MEMBERSHIP)
        # 2 explicit + 1 fallback = 3
        assert len(entries) >= 2
        for e in entries:
            assert e.metadata.group == RuleGroup.MEMBERSHIP

    def test_by_group_specialization(self, corpus):
        entries = corpus.by_group(RuleGroup.SPECIALIZATION)
        # 15 explicit + 1 fallback = 16
        assert len(entries) >= 15
        for e in entries:
            assert e.metadata.group == RuleGroup.SPECIALIZATION

    def test_group_summary_covers_all_groups(self, corpus):
        summary = corpus.group_summary()
        assert len(summary) == len(RuleGroup)
        for group in RuleGroup:
            assert group in summary
            assert summary[group] > 0

    def test_all_metadata_have_group(self, corpus):
        for entry in corpus.entries:
            assert isinstance(entry.metadata.group, RuleGroup)

    def test_group_derived_from_relation(self, corpus):
        for entry in corpus.entries:
            rel = entry.rule.relationship_name
            expected_group = RuleGroup(rel)
            assert entry.metadata.group == expected_group
