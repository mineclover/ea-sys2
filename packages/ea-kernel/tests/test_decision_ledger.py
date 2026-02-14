"""Tests for Phase 3 DecisionLedger — decision recording and pattern detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from ea_kernel.decision_ledger import DecisionLedger
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import (
    DecisionRecord,
    JudgmentReport,
    RuleCategory,
    RuleConfidence,
    RuleCorpusEntry,
)


def _make_decision(
    *,
    id: str = "d1",
    timestamp: str = "2024-01-01T00:00:00Z",
    actor: str = "human:alice",
    decision_type: str = "accept",
    triple: tuple[str, str, str] = ("structure", "item", "association"),
    override_reason: str = "",
) -> DecisionRecord:
    return DecisionRecord(
        id=id,
        timestamp=timestamp,
        actor=actor,
        decision_type=decision_type,
        subject_triple=triple,
        override_reason=override_reason,
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1. Recording
# ═════════════════════════════════════════════════════════════════════════════

class TestRecording:
    def test_empty_ledger(self):
        ledger = DecisionLedger()
        assert ledger.count == 0
        assert ledger.records == ()

    def test_record_appends(self):
        ledger = DecisionLedger()
        d = _make_decision()
        new_ledger = ledger.record(d)
        assert new_ledger.count == 1
        assert new_ledger.records[0] == d

    def test_mutable_record(self):
        ledger = DecisionLedger()
        d = _make_decision()
        new_ledger = ledger.record(d)
        # v2.5.0: record() mutates and returns self
        assert new_ledger is ledger
        assert ledger.count == 1

    def test_multiple_records(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1")
        d2 = _make_decision(id="d2")
        ledger = ledger.record(d1).record(d2)
        assert ledger.count == 2

    def test_order_preserved(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1", timestamp="2024-01-01T00:00:00Z")
        d2 = _make_decision(id="d2", timestamp="2024-01-02T00:00:00Z")
        ledger = ledger.record(d1).record(d2)
        assert ledger.records[0].id == "d1"
        assert ledger.records[1].id == "d2"


# ═════════════════════════════════════════════════════════════════════════════
# 2. Query — decisions_for
# ═════════════════════════════════════════════════════════════════════════════

class TestDecisionsFor:
    def test_find_by_triple(self):
        ledger = DecisionLedger()
        d = _make_decision(triple=("structure", "item", "association"))
        ledger = ledger.record(d)
        results = ledger.decisions_for("structure", "item", "association")
        assert len(results) == 1

    def test_no_match(self):
        ledger = DecisionLedger()
        d = _make_decision(triple=("structure", "item", "association"))
        ledger = ledger.record(d)
        results = ledger.decisions_for("item", "structure", "association")
        assert len(results) == 0

    def test_multiple_for_same_triple(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        d1 = _make_decision(id="d1", triple=triple)
        d2 = _make_decision(id="d2", triple=triple)
        ledger = ledger.record(d1).record(d2)
        results = ledger.decisions_for("structure", "item", "association")
        assert len(results) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 3. Query — overrides
# ═════════════════════════════════════════════════════════════════════════════

class TestOverrides:
    def test_filter_overrides(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1", decision_type="accept")
        d2 = _make_decision(id="d2", decision_type="override")
        ledger = ledger.record(d1).record(d2)
        overrides = ledger.overrides()
        assert len(overrides) == 1
        assert overrides[0].decision_type == "override"

    def test_no_overrides(self):
        ledger = DecisionLedger()
        d = _make_decision(decision_type="accept")
        ledger = ledger.record(d)
        assert len(ledger.overrides()) == 0


# ═════════════════════════════════════════════════════════════════════════════
# 4. Query — by_actor
# ═════════════════════════════════════════════════════════════════════════════

class TestByActor:
    def test_human_actor(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1", actor="human:alice")
        d2 = _make_decision(id="d2", actor="ai:claude")
        ledger = ledger.record(d1).record(d2)
        humans = ledger.by_actor("human:")
        assert len(humans) == 1
        assert humans[0].actor == "human:alice"

    def test_ai_actor(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1", actor="human:alice")
        d2 = _make_decision(id="d2", actor="ai:claude")
        ledger = ledger.record(d1).record(d2)
        ai = ledger.by_actor("ai:")
        assert len(ai) == 1
        assert ai[0].actor == "ai:claude"

    def test_prefix_match(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1", actor="human:alice")
        d2 = _make_decision(id="d2", actor="human:bob")
        ledger = ledger.record(d1).record(d2)
        humans = ledger.by_actor("human:")
        assert len(humans) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 5. Query — by_time_range
# ═════════════════════════════════════════════════════════════════════════════

class TestByTimeRange:
    def test_within_range(self):
        ledger = DecisionLedger()
        d = _make_decision(timestamp="2024-06-15T12:00:00Z")
        ledger = ledger.record(d)
        results = ledger.by_time_range("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z")
        assert len(results) == 1

    def test_outside_range(self):
        ledger = DecisionLedger()
        d = _make_decision(timestamp="2023-06-15T12:00:00Z")
        ledger = ledger.record(d)
        results = ledger.by_time_range("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z")
        assert len(results) == 0

    def test_boundary_inclusive(self):
        ledger = DecisionLedger()
        d = _make_decision(timestamp="2024-01-01T00:00:00Z")
        ledger = ledger.record(d)
        results = ledger.by_time_range("2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z")
        assert len(results) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 6. Override patterns
# ═════════════════════════════════════════════════════════════════════════════

class TestOverridePatterns:
    def test_detect_pattern(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(5):
            d = _make_decision(
                id=f"d{i}",
                decision_type="override",
                triple=triple,
                timestamp=f"2024-01-0{i+1}T00:00:00Z",
            )
            ledger = ledger.record(d)
        patterns = ledger.override_patterns(min_count=3)
        assert len(patterns) == 1
        assert patterns[0] == (triple, 5)

    def test_below_threshold(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(2):
            d = _make_decision(
                id=f"d{i}",
                decision_type="override",
                triple=triple,
            )
            ledger = ledger.record(d)
        patterns = ledger.override_patterns(min_count=3)
        assert len(patterns) == 0

    def test_multiple_patterns(self):
        ledger = DecisionLedger()
        t1 = ("structure", "item", "association")
        t2 = ("step", "step", "succession")
        for i in range(3):
            ledger = ledger.record(_make_decision(
                id=f"a{i}", decision_type="override", triple=t1,
            ))
        for i in range(4):
            ledger = ledger.record(_make_decision(
                id=f"b{i}", decision_type="override", triple=t2,
            ))
        patterns = ledger.override_patterns(min_count=3)
        assert len(patterns) == 2
        # Sorted by count descending
        assert patterns[0][1] >= patterns[1][1]

    def test_non_override_not_counted(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"d{i}",
                decision_type="accept",
                triple=triple,
            ))
        patterns = ledger.override_patterns(min_count=3)
        assert len(patterns) == 0


# ═════════════════════════════════════════════════════════════════════════════
# 7. Corpus feedback — to_empirical_entries
# ═════════════════════════════════════════════════════════════════════════════

class TestToEmpiricalEntries:
    def test_generates_entries(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert len(entries) == 1
        assert isinstance(entries[0], RuleCorpusEntry)

    def test_empirical_metadata(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        entry = entries[0]
        assert entry.metadata.category == RuleCategory.EMPIRICAL
        assert entry.metadata.confidence == RuleConfidence.EMPIRICAL
        assert entry.metadata.domain == "empirical"
        assert "override_pattern" in entry.metadata.tags

    def test_rule_is_allow(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert entries[0].rule.valid is True

    def test_no_entries_below_threshold(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(2):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert len(entries) == 0

    def test_entry_rule_id_format(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(3):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert entries[0].rule.id.startswith("empirical-")

    def test_entry_source_includes_count(self):
        ledger = DecisionLedger()
        triple = ("structure", "item", "association")
        for i in range(4):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert "n=4" in entries[0].metadata.source


# ═════════════════════════════════════════════════════════════════════════════
# 8. DecisionRecord type tests
# ═════════════════════════════════════════════════════════════════════════════

class TestDecisionRecord:
    def test_frozen(self):
        d = _make_decision()
        with pytest.raises(AttributeError):
            d.id = "d2"  # type: ignore[misc]

    def test_defaults(self):
        d = DecisionRecord(
            id="d1",
            timestamp="2024-01-01T00:00:00Z",
            actor="human:alice",
            decision_type="accept",
            subject_triple=("a", "b", "c"),
        )
        assert d.judgment is None
        assert d.override_reason == ""
        assert d.context == ()

    def test_with_judgment(self):
        judgment = JudgmentReport(
            verdict=True, evidence=(),
            confidence=RuleConfidence.COMMON,
            domains=(), conflicts=(),
        )
        d = DecisionRecord(
            id="d1",
            timestamp="2024-01-01T00:00:00Z",
            actor="ai:claude",
            decision_type="accept",
            subject_triple=("a", "b", "c"),
            judgment=judgment,
        )
        assert d.judgment is not None
        assert d.judgment.verdict is True

    def test_with_context(self):
        d = DecisionRecord(
            id="d1",
            timestamp="2024-01-01T00:00:00Z",
            actor="human:alice",
            decision_type="override",
            subject_triple=("a", "b", "c"),
            override_reason="Business requirement",
            context=(("project", "X"), ("phase", "design")),
        )
        assert d.override_reason == "Business requirement"
        assert len(d.context) == 2

    def test_equality(self):
        d1 = _make_decision(id="d1")
        d2 = _make_decision(id="d1")
        assert d1 == d2


# ═════════════════════════════════════════════════════════════════════════════
# 9. Ledger chaining
# ═════════════════════════════════════════════════════════════════════════════

class TestLedgerChaining:
    def test_chain_preserves_order(self):
        ledger = DecisionLedger()
        ids = [f"d{i}" for i in range(10)]
        for id_ in ids:
            ledger = ledger.record(_make_decision(id=id_))
        assert ledger.count == 10
        assert [r.id for r in ledger.records] == ids

    def test_chaining_returns_self(self):
        ledger = DecisionLedger()
        d1 = _make_decision(id="d1")
        d2 = _make_decision(id="d2")
        d3 = _make_decision(id="d3")
        result = ledger.record(d1).record(d2).record(d3)
        # v2.5.0: all record() calls mutate the same ledger
        assert result is ledger
        assert ledger.count == 3
        assert ledger.records[0].id == "d1"
        assert ledger.records[1].id == "d2"
        assert ledger.records[2].id == "d3"


# ═════════════════════════════════════════════════════════════════════════════
# 10. Mixed decision types
# ═════════════════════════════════════════════════════════════════════════════

class TestMixedDecisionTypes:
    def test_all_decision_types(self):
        ledger = DecisionLedger()
        for dtype in ("accept", "override", "create", "delete"):
            ledger = ledger.record(_make_decision(
                id=f"d-{dtype}", decision_type=dtype,
            ))
        assert ledger.count == 4
        assert len(ledger.overrides()) == 1

    def test_decisions_for_mixed_types(self):
        triple = ("structure", "item", "association")
        ledger = DecisionLedger()
        ledger = ledger.record(_make_decision(
            id="d1", decision_type="accept", triple=triple,
        ))
        ledger = ledger.record(_make_decision(
            id="d2", decision_type="override", triple=triple,
        ))
        results = ledger.decisions_for("structure", "item", "association")
        assert len(results) == 2

    def test_create_delete_not_counted_as_override(self):
        triple = ("structure", "item", "association")
        ledger = DecisionLedger()
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="create", triple=triple,
            ))
        patterns = ledger.override_patterns(min_count=3)
        assert len(patterns) == 0


# ═════════════════════════════════════════════════════════════════════════════
# 11. Time range edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestTimeRangeEdgeCases:
    def test_multiple_in_range(self):
        ledger = DecisionLedger()
        for month in range(1, 7):
            ts = f"2024-{month:02d}-15T12:00:00Z"
            ledger = ledger.record(_make_decision(id=f"d{month}", timestamp=ts))
        results = ledger.by_time_range("2024-03-01T00:00:00Z", "2024-05-31T23:59:59Z")
        assert len(results) == 3

    def test_empty_range_returns_empty(self):
        ledger = DecisionLedger()
        ledger = ledger.record(_make_decision(timestamp="2024-06-15T12:00:00Z"))
        results = ledger.by_time_range("2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z")
        assert len(results) == 0

    def test_precise_timestamp_match(self):
        ts = "2024-07-04T10:30:00Z"
        ledger = DecisionLedger()
        ledger = ledger.record(_make_decision(timestamp=ts))
        results = ledger.by_time_range(ts, ts)
        assert len(results) == 1


# ═════════════════════════════════════════════════════════════════════════════
# 12. Multiple actors
# ═════════════════════════════════════════════════════════════════════════════

class TestMultipleActors:
    def test_many_actors(self):
        ledger = DecisionLedger()
        actors = ["human:alice", "human:bob", "ai:claude", "ai:gpt"]
        for i, actor in enumerate(actors):
            ledger = ledger.record(_make_decision(id=f"d{i}", actor=actor))
        assert len(ledger.by_actor("human:")) == 2
        assert len(ledger.by_actor("ai:")) == 2
        assert len(ledger.by_actor("human:alice")) == 1

    def test_no_actor_match(self):
        ledger = DecisionLedger()
        ledger = ledger.record(_make_decision(actor="human:alice"))
        assert len(ledger.by_actor("system:")) == 0


# ═════════════════════════════════════════════════════════════════════════════
# 13. Empirical entries — additional
# ═════════════════════════════════════════════════════════════════════════════

class TestEmpiricalEntriesAdditional:
    def test_multiple_empirical_entries(self):
        ledger = DecisionLedger()
        t1 = ("structure", "item", "association")
        t2 = ("step", "action", "succession")
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"a{i}", decision_type="override", triple=t1,
            ))
            ledger = ledger.record(_make_decision(
                id=f"b{i}", decision_type="override", triple=t2,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert len(entries) == 2
        ids = {e.rule.id for e in entries}
        assert "empirical-structure-item-association" in ids
        assert "empirical-step-action-succession" in ids

    def test_entry_rule_triple_matches(self):
        ledger = DecisionLedger()
        triple = ("feature", "port", "association")
        for i in range(4):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override", triple=triple,
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert len(entries) == 1
        rule = entries[0].rule
        assert rule.source_pattern == "feature"
        assert rule.target_pattern == "port"
        assert rule.relationship_name == "association"

    def test_entry_established_version(self):
        ledger = DecisionLedger()
        for i in range(3):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override",
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert entries[0].metadata.established_version == "2.3.0"

    def test_entry_rationale_contains_count(self):
        ledger = DecisionLedger()
        for i in range(7):
            ledger = ledger.record(_make_decision(
                id=f"d{i}", decision_type="override",
            ))
        entries = ledger.to_empirical_entries(min_count=3)
        assert "7" in entries[0].metadata.rationale


# ═════════════════════════════════════════════════════════════════════════════
# 14. Override pattern sorting
# ═════════════════════════════════════════════════════════════════════════════

class TestOverridePatternSorting:
    def test_sorted_by_count_descending(self):
        ledger = DecisionLedger()
        t1 = ("a", "b", "c")
        t2 = ("d", "e", "f")
        for i in range(3):
            ledger = ledger.record(_make_decision(
                id=f"a{i}", decision_type="override", triple=t1,
            ))
        for i in range(5):
            ledger = ledger.record(_make_decision(
                id=f"b{i}", decision_type="override", triple=t2,
            ))
        patterns = ledger.override_patterns(min_count=3)
        assert len(patterns) == 2
        assert patterns[0][1] > patterns[1][1]
        assert patterns[0][0] == t2

    def test_min_count_1(self):
        ledger = DecisionLedger()
        ledger = ledger.record(_make_decision(
            id="d1", decision_type="override",
        ))
        patterns = ledger.override_patterns(min_count=1)
        assert len(patterns) == 1
        assert patterns[0][1] == 1
