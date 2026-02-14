"""Rule Corpus — metadata-enriched rule collection with evidence-based judgment.

Phase 0.5: parallel path to validate_relationship() that provides
rich evidence, domain-aware conflict detection, and query capabilities.
"""

from __future__ import annotations

from ea_kernel.types import (
    JudgmentReport,
    KernelSchema,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleEvidence,
    RuleGroup,
    RuleMetadata,
)


# Relations by layer — used for metadata inference
_L2_RELATIONS = frozenset({
    "membership", "ownership", "specialization", "feature_typing",
    "association", "connector", "redefinition", "subsetting",
})
_L3_RELATIONS = frozenset({
    "flow", "succession", "interaction", "triggering", "guarding", "transition",
})



class RuleCorpus:
    """Rule corpus — metadata attachment, querying, and evidence-based judgment."""

    __slots__ = ("_entries", "_schema", "_by_id", "_entries_by_rel")

    def __init__(
        self,
        entries: tuple[RuleCorpusEntry, ...],
        schema: KernelSchema,
    ) -> None:
        self._entries = entries
        self._schema = schema
        self._by_id: dict[str, RuleCorpusEntry] = {e.rule.id: e for e in entries}
        # Index entries by relation name for fast filtering
        rel_idx: dict[str, list[RuleCorpusEntry]] = {}
        for e in entries:
            rel_idx.setdefault(e.rule.relationship_name, []).append(e)
        self._entries_by_rel: dict[str, tuple[RuleCorpusEntry, ...]] = {
            k: tuple(v) for k, v in rel_idx.items()
        }

    @property
    def entries(self) -> tuple[RuleCorpusEntry, ...]:
        return self._entries

    @property
    def schema(self) -> KernelSchema:
        return self._schema

    # ── Factory ───────────────────────────────────────────────────

    @classmethod
    def from_kernel_spec(
        cls,
        schema: KernelSchema,
        metadata_map: dict[str, RuleMetadata] | None = None,
    ) -> RuleCorpus:
        """Build a corpus from a validated kernel schema.

        Rules with entries in metadata_map use explicit metadata;
        others get inferred metadata via infer_metadata().
        """
        metadata_map = metadata_map or {}
        entries: list[RuleCorpusEntry] = []
        for rule in schema.validity_rules:
            meta = metadata_map.get(rule.id)
            if meta is None:
                meta = cls.infer_metadata(rule)
            entries.append(RuleCorpusEntry(rule=rule, metadata=meta))
        return cls(tuple(entries), schema)

    # ── Metadata inference ────────────────────────────────────────

    @staticmethod
    def infer_metadata(rule: KernelValidityRule) -> RuleMetadata:
        """Infer metadata from rule structure when not explicitly provided."""
        rel = rule.relationship_name

        # Group: derive from relation name
        group = RuleGroup.from_relation(rel)

        # Category: L2 → structural, L3 → behavioral
        if rel in _L2_RELATIONS:
            category = RuleCategory.STRUCTURAL
        elif rel in _L3_RELATIONS:
            category = RuleCategory.BEHAVIORAL
        else:
            category = RuleCategory.DOMAIN

        # Confidence: deny rules with high priority or fallbacks → UNIVERSAL
        if not rule.valid and rule.priority >= 80:
            confidence = RuleConfidence.UNIVERSAL
        elif not rule.valid and rule.priority == 1:
            confidence = RuleConfidence.UNIVERSAL
        else:
            confidence = RuleConfidence.COMMON

        # Tags from relation name
        tags = (rel,)

        return RuleMetadata(
            domain="kernel",
            tags=tags,
            category=category,
            confidence=confidence,
            source="kernel spec",
            established_version="2.5.0",
            rationale=rule.notes,
            group=group,
        )

    # ── Immutable extension ───────────────────────────────────────

    def with_profile_rules(
        self,
        profile_name: str,
        rules: tuple[KernelValidityRule, ...],
        metadata_map: dict[str, RuleMetadata] | None = None,
    ) -> RuleCorpus:
        """Return a new corpus with additional profile rules."""
        metadata_map = metadata_map or {}
        new_entries: list[RuleCorpusEntry] = []
        for rule in rules:
            meta = metadata_map.get(rule.id)
            if meta is None:
                inferred = self.infer_metadata(rule)
                meta = RuleMetadata(
                    domain=profile_name,
                    tags=inferred.tags,
                    category=inferred.category,
                    confidence=inferred.confidence,
                    source=f"profile:{profile_name}",
                    established_version=inferred.established_version,
                    rationale=inferred.rationale,
                    group=inferred.group,
                )
            new_entries.append(RuleCorpusEntry(rule=rule, metadata=meta))
        return RuleCorpus((*self._entries, *new_entries), self._schema)

    # ── Query ─────────────────────────────────────────────────────

    def by_domain(self, domain: str) -> tuple[RuleCorpusEntry, ...]:
        return tuple(e for e in self._entries if e.metadata.domain == domain)

    def by_tag(self, tag: str) -> tuple[RuleCorpusEntry, ...]:
        return tuple(e for e in self._entries if tag in e.metadata.tags)

    def by_category(self, category: RuleCategory) -> tuple[RuleCorpusEntry, ...]:
        return tuple(e for e in self._entries if e.metadata.category == category)

    def by_confidence(self, confidence: RuleConfidence) -> tuple[RuleCorpusEntry, ...]:
        return tuple(e for e in self._entries if e.metadata.confidence == confidence)

    def by_group(self, group: RuleGroup) -> tuple[RuleCorpusEntry, ...]:
        return tuple(e for e in self._entries if e.metadata.group == group)

    def group_summary(self) -> dict[RuleGroup, int]:
        counts: dict[RuleGroup, int] = {}
        for e in self._entries:
            g = e.metadata.group
            counts[g] = counts.get(g, 0) + 1
        return counts

    # ── Conflict detection ────────────────────────────────────────

    def detect_conflicts(
        self, source: str, target: str, relation: str,
    ) -> tuple[str, ...]:
        """Detect cross-domain conflicts for a given triple."""
        matched = self._schema.find_matching_rules(source, target, relation)
        matched_ids = {r.id for r in matched}
        return self._detect_conflicts_from_matched(
            source, target, relation, matched_ids,
        )

    def _detect_conflicts_from_matched(
        self,
        source: str,
        target: str,
        relation: str,
        matched_ids: set[str],
    ) -> tuple[str, ...]:
        """Internal: detect conflicts using pre-computed matched rule IDs."""
        # Group matched entries by domain — only scan relation-specific entries
        domain_entries: dict[str, list[RuleCorpusEntry]] = {}
        for entry in self._entries_by_rel.get(relation, ()):
            if entry.rule.id not in matched_ids:
                continue
            domain = entry.metadata.domain
            domain_entries.setdefault(domain, []).append(entry)

        if len(domain_entries) < 2:
            return ()

        # For each domain, determine the domain-local winner (highest priority)
        domain_winners: dict[str, bool] = {}
        for domain, entries in domain_entries.items():
            best = max(
                entries,
                key=lambda e: (e.rule.priority, not e.rule.valid),
            )
            domain_winners[domain] = best.rule.valid

        # Find cross-domain disagreements
        allow_domains = sorted(d for d, v in domain_winners.items() if v)
        deny_domains = sorted(d for d, v in domain_winners.items() if not v)

        if allow_domains and deny_domains:
            conflicts: list[str] = []
            for ad in allow_domains:
                for dd in deny_domains:
                    conflicts.append(
                        f"Domain '{ad}' allows but '{dd}' denies "
                        f"{source}→{target} via {relation}"
                    )
            return tuple(conflicts)

        return ()

    # ── Judgment ──────────────────────────────────────────────────

    def judge(
        self, source: str, target: str, relation: str,
    ) -> JudgmentReport:
        """Evidence-based judgment — parallel path to validate_relationship().

        Produces the same verdict as schema.validate_relationship()
        but wraps it with full evidence, confidence, and domain info.

        v2.5.0: optimized — find_matching_rules() called once, verdict computed
        directly from rules + layer constraints instead of re-calling
        validate_relationship(). detect_conflicts() reuses matched_ids.
        """
        schema = self._schema

        # ① find_matching_rules once
        matched_rules = schema.find_matching_rules(source, target, relation)
        matched_ids = {r.id for r in matched_rules}
        winner_id = matched_rules[0].id if matched_rules else None

        # ② Compute verdict directly (same logic as validate_relationship)
        #    Check layer constraints first
        verdict: bool
        layer_blocked = False
        src_e = schema.get_entity(source)
        tgt_e = schema.get_entity(target)

        if src_e is None or tgt_e is None:
            verdict = False
        else:
            for lc in schema.layer_constraints:
                if relation not in lc.forbidden_relations:
                    continue
                if src_e.layer != lc.source_layer or tgt_e.layer != lc.target_layer:
                    continue
                exempt = False
                for ap_src, ap_tgt in lc.allowed_pairs:
                    if (schema.entity_matches(source, ap_src)
                            and schema.entity_matches(target, ap_tgt)):
                        exempt = True
                        break
                if not exempt:
                    layer_blocked = True
                    break

            if layer_blocked:
                verdict = False
            elif not matched_rules:
                verdict = False  # deny-by-default
            else:
                top = matched_rules[0]
                # Check conditions on top-priority rule
                cond_pass = True
                for cond in top.conditions:
                    ok, _msg = schema._check_condition(cond, source, target)
                    if not ok:
                        cond_pass = False
                        break
                verdict = top.valid if cond_pass else False

        # ③ Build evidence — only scan relation-specific entries
        evidence_list: list[RuleEvidence] = []
        domains_seen: set[str] = set()

        for entry in self._entries_by_rel.get(relation, ()):
            is_matched = entry.rule.id in matched_ids
            is_winner = entry.rule.id == winner_id

            condition_results: list[tuple[str, bool]] = []
            if is_matched:
                domains_seen.add(entry.metadata.domain)
                for cond in entry.rule.conditions:
                    ok, _msg = schema._check_condition(cond, source, target)
                    condition_results.append((cond.condition_type.value, ok))

            evidence_list.append(RuleEvidence(
                entry=entry,
                matched=is_matched,
                is_winner=is_winner,
                condition_results=tuple(condition_results),
            ))

        # Determine confidence from the winner
        if winner_id and winner_id in self._by_id:
            confidence = self._by_id[winner_id].metadata.confidence
        else:
            confidence = RuleConfidence.COMMON

        # Detect conflicts — reuse matched_ids
        conflicts = self._detect_conflicts_from_matched(
            source, target, relation, matched_ids,
        )

        return JudgmentReport(
            verdict=verdict,
            evidence=tuple(evidence_list),
            confidence=confidence,
            domains=tuple(sorted(domains_seen)),
            conflicts=conflicts,
        )
