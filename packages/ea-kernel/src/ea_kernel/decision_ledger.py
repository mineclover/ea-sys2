"""Append-only decision ledger with corpus feedback.

Phase 3: Records modeling decisions (accept, override, create, delete)
and detects override patterns that become empirical corpus entries.

Phase 1 Enhancement (Governance Lifecycle):
- Optional DecisionStore port for persistent storage
- Corpus version tracking for judgment reproducibility
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ea_kernel.types import (
    DecisionRecord,
    KernelValidityRule,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
    RuleMetadata,
)

if TYPE_CHECKING:
    from ea_kernel.decision_store import DecisionStore
    from ea_kernel.rule_corpus import RuleCorpus


class DecisionLedger:
    """Append-only ledger of modeling decisions with corpus feedback.

    v2.5.0 breaking: record() mutates self and returns self (was immutable).

    v2.6.0 (Governance Lifecycle Phase 1):
    - Optional DecisionStore for persistent storage
    - Corpus version tracking for judgment reproducibility
    - If store is provided, decisions are automatically persisted
    - If store is None, existing in-memory behavior is preserved
    """

    __slots__ = ("_records", "_corpus", "_triple_index", "_store", "_corpus_version_id")

    def __init__(
        self,
        corpus: RuleCorpus | None = None,
        *,
        store: DecisionStore | None = None,
        corpus_version_id: str = "",
    ) -> None:
        """Initialize DecisionLedger.

        Args:
            corpus: Optional RuleCorpus for judgment context
            store: Optional DecisionStore for persistent storage (Phase 1)
            corpus_version_id: Current corpus version ID for tracking (Phase 1)
        """
        self._records: list[DecisionRecord] = []
        self._corpus = corpus
        self._triple_index: dict[tuple[str, str, str], list[DecisionRecord]] = {}
        self._store = store
        self._corpus_version_id = corpus_version_id

    # ── Recording ──────────────────────────────────────────────────

    def record(
        self,
        decision: DecisionRecord,
        *,
        persist: bool = True,
    ) -> DecisionLedger:
        """Append decision and return self (mutable).

        Breaking change (v2.5.0): previously returned a new ledger.
        The ``ledger = ledger.record(d)`` pattern still works.

        Phase 1 Enhancement:
        - If store is provided and persist=True, decision is also persisted
        - persist=False skips persistence (useful for replaying from store)

        Args:
            decision: DecisionRecord to record
            persist: If True and store exists, persist to store. Default True.

        Returns:
            self for method chaining
        """
        self._records.append(decision)
        self._triple_index.setdefault(decision.subject_triple, []).append(decision)

        # Persist to store if available
        if self._store is not None and persist:
            self._store.store(decision, corpus_version_id=self._corpus_version_id)

        return self

    # ── Query ──────────────────────────────────────────────────────

    def decisions_for(
        self, source: str, target: str, relation: str,
    ) -> tuple[DecisionRecord, ...]:
        """All decisions for a given triple — O(1) lookup."""
        return tuple(self._triple_index.get((source, target, relation), ()))

    def overrides(self) -> tuple[DecisionRecord, ...]:
        """All override decisions."""
        return tuple(d for d in self._records if d.decision_type == "override")

    def by_actor(self, actor_prefix: str) -> tuple[DecisionRecord, ...]:
        """Decisions by actor (prefix match: 'human:' or 'ai:')."""
        return tuple(d for d in self._records if d.actor.startswith(actor_prefix))

    def by_time_range(self, start: str, end: str) -> tuple[DecisionRecord, ...]:
        """Decisions within ISO 8601 time range (string comparison)."""
        return tuple(
            d for d in self._records
            if start <= d.timestamp <= end
        )

    # ── Pattern detection ──────────────────────────────────────────

    def override_patterns(
        self, min_count: int = 3,
    ) -> tuple[tuple[tuple[str, str, str], int], ...]:
        """Detect repeated override patterns — (triple, count) pairs."""
        triple_counts: dict[tuple[str, str, str], int] = {}
        for d in self._records:
            if d.decision_type == "override":
                triple_counts[d.subject_triple] = (
                    triple_counts.get(d.subject_triple, 0) + 1
                )

        patterns = [
            (triple, count)
            for triple, count in triple_counts.items()
            if count >= min_count
        ]
        # Sort by count descending, then by triple for stability
        patterns.sort(key=lambda p: (-p[1], p[0]))
        return tuple(patterns)

    # ── Corpus feedback ────────────────────────────────────────────

    def to_empirical_entries(
        self, min_count: int = 3,
    ) -> tuple[RuleCorpusEntry, ...]:
        """Convert repeated override patterns to EMPIRICAL corpus entries."""
        patterns = self.override_patterns(min_count=min_count)
        entries: list[RuleCorpusEntry] = []

        for triple, count in patterns:
            source, target, relation = triple
            rule_id = f"empirical-{source}-{target}-{relation}"
            rule = KernelValidityRule(
                id=rule_id,
                source_pattern=source,
                target_pattern=target,
                relationship_name=relation,
                valid=True,  # Overrides are typically allowing what was denied
                priority=20,
                notes=f"Empirical: overridden {count} times",
            )
            meta = RuleMetadata(
                domain="empirical",
                tags=("override_pattern", relation),
                category=RuleCategory.EMPIRICAL,
                confidence=RuleConfidence.EMPIRICAL,
                source=f"decision_ledger (n={count})",
                established_version="2.3.0",
                rationale=f"Pattern detected: {source}→{target} via {relation} overridden {count} times",
            )
            entries.append(RuleCorpusEntry(rule=rule, metadata=meta))

        return tuple(entries)

    # ── Properties ─────────────────────────────────────────────────

    @property
    def records(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._records)

    @property
    def count(self) -> int:
        return len(self._records)

    # ── Phase 1: Store integration ─────────────────────────────────

    @property
    def store(self) -> DecisionStore | None:
        """Get the attached DecisionStore (Phase 1)."""
        return self._store

    @property
    def corpus_version_id(self) -> str:
        """Get the current corpus version ID (Phase 1)."""
        return self._corpus_version_id

    @corpus_version_id.setter
    def corpus_version_id(self, value: str) -> None:
        """Update the current corpus version ID (Phase 1)."""
        self._corpus_version_id = value

    def with_store(self, store: DecisionStore) -> DecisionLedger:
        """Return a new DecisionLedger with the given store attached.

        Args:
            store: DecisionStore to attach

        Returns:
            New DecisionLedger with store attached, sharing the same in-memory state
        """
        new_ledger = DecisionLedger(
            corpus=self._corpus,
            store=store,
            corpus_version_id=self._corpus_version_id,
        )
        new_ledger._records = self._records
        new_ledger._triple_index = self._triple_index
        return new_ledger

    def replay_from_store(
        self,
        corpus_version_id: str | None = None,
    ) -> DecisionLedger:
        """Replay decisions from the attached store into in-memory state.

        Useful for:
        - Reconstructing ledger state from persistent storage
        - Loading decisions from a specific corpus version

        Args:
            corpus_version_id: If provided, only replay decisions for this version

        Returns:
            self for method chaining

        Raises:
            ValueError: If no store is attached
        """
        if self._store is None:
            msg = "Cannot replay without a store"
            raise ValueError(msg)

        from ea_kernel.governance_types import DecisionQueryOptions

        options = None
        if corpus_version_id:
            options = DecisionQueryOptions(corpus_version_id=corpus_version_id)

        stored_records = self._store.query(options)

        for stored in stored_records:
            # Replay without persisting again
            self.record(stored.record, persist=False)

        return self

    def statistics_for(
        self,
        source: str,
        target: str,
        relation: str,
    ) -> object:
        """Get judgment statistics for a triple.

        Delegates to store if available, otherwise returns basic in-memory stats.

        Returns:
            JudgmentStatistics if store is attached, else dict with basic counts
        """
        if self._store is not None:
            return self._store.statistics_for(source, target, relation)

        # Fallback: basic in-memory statistics
        triple = (source, target, relation)
        decisions = self._triple_index.get(triple, [])

        allow_count = sum(
            1 for d in decisions
            if d.judgment and d.judgment.verdict
        )
        deny_count = sum(
            1 for d in decisions
            if d.judgment and not d.judgment.verdict
        )
        override_count = sum(
            1 for d in decisions
            if d.decision_type == "override"
        )

        return {
            "source": source,
            "target": target,
            "relation": relation,
            "total_judgments": len(decisions),
            "allow_count": allow_count,
            "deny_count": deny_count,
            "override_count": override_count,
        }
