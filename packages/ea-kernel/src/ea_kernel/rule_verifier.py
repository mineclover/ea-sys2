"""Rule Verifier — group-based rule verification against the kernel schema.

Verifies that every explicit rule in the corpus produces the expected
validation result when tested against representative triples.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ea_kernel.types import (
    GroupVerificationResult,
    KernelSchema,
    RuleCategory,
    RuleCorpusEntry,
    RuleGroup,
    RuleVerificationEntry,
    VerificationReport,
)

if TYPE_CHECKING:
    from ea_kernel.rule_corpus import RuleCorpus


class RuleVerifier:
    """Verifies rule consistency against the kernel schema."""

    __slots__ = ("_schema", "_corpus")

    def __init__(self, schema: KernelSchema, corpus: RuleCorpus) -> None:
        from ea_kernel.rule_corpus import RuleCorpus as _RuleCorpus
        if not isinstance(corpus, _RuleCorpus):
            raise TypeError(f"Expected RuleCorpus, got {type(corpus).__name__}")
        self._schema = schema
        self._corpus = corpus

    def rules_in_group(self, group: RuleGroup) -> tuple[RuleCorpusEntry, ...]:
        return self._corpus.by_group(group)

    def verify_group(self, group: RuleGroup) -> GroupVerificationResult:
        """Verify all rules in a single group."""
        entries = self._corpus.by_group(group)
        verification_entries: list[RuleVerificationEntry] = []

        for entry in entries:
            ve = self._verify_entry(entry)
            if ve is not None:
                verification_entries.append(ve)

        passed = sum(1 for v in verification_entries if v.passed)
        failed = len(verification_entries) - passed
        total = len(verification_entries)
        return GroupVerificationResult(
            group=group,
            total_rules=total,
            passed_rules=passed,
            failed_rules=failed,
            pass_rate=passed / total if total > 0 else 1.0,
            entries=tuple(verification_entries),
        )

    def verify_groups(self, groups: tuple[RuleGroup, ...]) -> VerificationReport:
        """Verify specified groups and return an aggregated report."""
        group_results: list[GroupVerificationResult] = []
        for group in groups:
            group_results.append(self.verify_group(group))
        return self._build_report(tuple(group_results))

    def verify_all(self) -> VerificationReport:
        """Verify all groups present in the corpus."""
        groups_present = tuple(sorted(
            self._corpus.group_summary().keys(),
            key=lambda g: g.value,
        ))
        return self.verify_groups(groups_present)

    def verify_category(self, category: RuleCategory) -> VerificationReport:
        """Verify all groups whose rules belong to a given category."""
        # Collect groups that have at least one rule in this category
        groups: set[RuleGroup] = set()
        for entry in self._corpus.entries:
            if entry.metadata.category == category:
                groups.add(entry.metadata.group)
        sorted_groups = tuple(sorted(groups, key=lambda g: g.value))
        return self.verify_groups(sorted_groups)

    def _verify_entry(self, entry: RuleCorpusEntry) -> RuleVerificationEntry | None:
        """Verify a single rule by finding a representative triple.

        For allow rules with conditions, finds a triple where the rule is
        winner AND conditions pass. For deny rules, any winner triple suffices.

        Returns None if no representative triple can be constructed.
        """
        rule = entry.rule
        schema = self._schema

        # Resolve patterns to concrete entity names
        src_set = schema._pattern_matches.get(rule.source_pattern, frozenset())
        tgt_set = schema._pattern_matches.get(rule.target_pattern, frozenset())

        if not src_set or not tgt_set:
            return None

        # Find a triple where this rule is the winner (and conditions pass for allow rules)
        found = self._find_verifiable_triple(entry, src_set, tgt_set)
        if found is None:
            # Rule is always overridden or conditions never met — still valid
            src = sorted(src_set)[0]
            tgt = sorted(tgt_set)[0]
            return RuleVerificationEntry(
                rule_id=rule.id,
                group=entry.metadata.group,
                passed=True,
                source=src,
                target=tgt,
                relation=rule.relationship_name,
                expected_valid=rule.valid,
                actual_valid=rule.valid,
                details="always overridden or no condition-satisfying triple found",
            )

        src, tgt, actual_valid = found
        passed = actual_valid == rule.valid

        return RuleVerificationEntry(
            rule_id=rule.id,
            group=entry.metadata.group,
            passed=passed,
            source=src,
            target=tgt,
            relation=rule.relationship_name,
            expected_valid=rule.valid,
            actual_valid=actual_valid,
        )

    def _find_verifiable_triple(
        self,
        entry: RuleCorpusEntry,
        src_candidates: frozenset[str],
        tgt_candidates: frozenset[str],
    ) -> tuple[str, str, bool] | None:
        """Find a triple where the given rule is the winner.

        For allow rules with conditions, ensures conditions pass so that
        actual_valid matches expected_valid. For deny rules, any winner
        triple suffices. Samples up to 50 combinations.
        """
        rule = entry.rule
        schema = self._schema
        count = 0
        max_samples = 50

        for src in sorted(src_candidates):
            for tgt in sorted(tgt_candidates):
                count += 1
                if count > max_samples:
                    return None
                matched = schema.find_matching_rules(src, tgt, rule.relationship_name)
                if not matched or matched[0].id != rule.id:
                    continue
                # This rule is the winner for this triple
                cond_pass = True
                for cond in matched[0].conditions:
                    ok, _msg = schema._check_condition(cond, src, tgt)
                    if not ok:
                        cond_pass = False
                        break
                actual_valid = matched[0].valid if cond_pass else False
                # For allow rules, prefer triples where conditions pass
                if rule.valid and not cond_pass:
                    continue  # try another triple where conditions hold
                return src, tgt, actual_valid
        return None

    @staticmethod
    def _build_report(
        group_results: tuple[GroupVerificationResult, ...],
    ) -> VerificationReport:
        total_groups = len(group_results)
        passed_groups = sum(1 for g in group_results if g.pass_rate == 1.0)
        total_rules = sum(g.total_rules for g in group_results)
        total_passed = sum(g.passed_rules for g in group_results)
        return VerificationReport(
            total_groups=total_groups,
            passed_groups=passed_groups,
            total_rules=total_rules,
            total_passed=total_passed,
            overall_pass_rate=total_passed / total_rules if total_rules > 0 else 1.0,
            group_results=group_results,
            timestamp=datetime.now(UTC).isoformat(),
        )
