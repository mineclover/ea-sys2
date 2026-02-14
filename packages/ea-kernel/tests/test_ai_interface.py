"""Tests for Phase 4 AIDecisionInterface — AI agent interaction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from ea_kernel.ai_interface import AIDecisionInterface
from ea_kernel.decision_ledger import DecisionLedger
from ea_kernel.graph_view import TopologyGraph
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.types import (
    DecisionContext,
    DecisionRecord,
    InstanceElement,
    InstanceRelation,
    Recommendation,
    RuleConfidence,
)

# ═════════════════════════════════════════════════════════════════════════════
# 1. Factory
# ═════════════════════════════════════════════════════════════════════════════

class TestFromKernel:
    def test_from_kernel_creates_interface(self):
        ai = AIDecisionInterface.from_kernel()
        assert ai is not None

    def test_from_kernel_has_corpus(self):
        ai = AIDecisionInterface.from_kernel()
        assert ai._corpus is not None

    def test_from_kernel_has_graph(self):
        ai = AIDecisionInterface.from_kernel()
        assert ai._graph is not None

    def test_from_kernel_has_ledger(self):
        ai = AIDecisionInterface.from_kernel()
        assert ai._ledger is not None


# ═════════════════════════════════════════════════════════════════════════════
# 2. Build context
# ═════════════════════════════════════════════════════════════════════════════

class TestBuildContext:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_returns_decision_context(self, ai):
        ctx = ai.build_context("structure", "item", "association")
        assert isinstance(ctx, DecisionContext)

    def test_context_has_triple(self, ai):
        ctx = ai.build_context("structure", "item", "association")
        assert ctx.subject_triple == ("structure", "item", "association")

    def test_context_has_judgment(self, ai):
        ctx = ai.build_context("structure", "item", "association")
        assert ctx.judgment is not None
        assert ctx.judgment.verdict is True

    def test_context_denied_triple(self, ai):
        ctx = ai.build_context("item", "structure", "specialization")
        assert ctx.judgment.verdict is False

    def test_context_with_graph(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        graph = TopologyGraph(KERNEL_SPEC)
        ai = AIDecisionInterface(corpus, graph=graph)
        ctx = ai.build_context("structure", "item", "association")
        assert isinstance(ctx, DecisionContext)

    def test_context_with_ledger(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        ledger = DecisionLedger(corpus)
        ai = AIDecisionInterface(corpus, ledger=ledger)
        ctx = ai.build_context("structure", "item", "association")
        assert ctx.related_decisions == ()

    def test_context_with_all_components(self):
        ai = AIDecisionInterface.from_kernel()
        ctx = ai.build_context("structure", "item", "association")
        assert ctx.judgment is not None
        assert isinstance(ctx.related_decisions, tuple)
        assert isinstance(ctx.reachable_paths, tuple)


# ═════════════════════════════════════════════════════════════════════════════
# 3. Recommend relations
# ═════════════════════════════════════════════════════════════════════════════

class TestRecommendRelations:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_returns_recommendations(self, ai):
        recs = ai.recommend_relations("structure", "item")
        assert len(recs) > 0

    def test_recommendations_are_typed(self, ai):
        recs = ai.recommend_relations("structure", "item")
        assert all(isinstance(r, Recommendation) for r in recs)

    def test_recommendations_have_score(self, ai):
        recs = ai.recommend_relations("structure", "item")
        for rec in recs:
            assert 0.0 <= rec.score <= 1.0

    def test_recommendations_sorted_by_score(self, ai):
        recs = ai.recommend_relations("structure", "item")
        if len(recs) > 1:
            for i in range(len(recs) - 1):
                assert recs[i].score >= recs[i + 1].score

    def test_top_k_limit(self, ai):
        recs = ai.recommend_relations("structure", "item", top_k=2)
        assert len(recs) <= 2

    def test_recommendation_has_triple(self, ai):
        recs = ai.recommend_relations("structure", "item")
        for rec in recs:
            assert rec.triple[0] == "structure"
            assert rec.triple[1] == "item"

    def test_recommendation_has_rationale(self, ai):
        recs = ai.recommend_relations("structure", "item")
        for rec in recs:
            assert len(rec.rationale) > 0

    def test_recommendation_has_judgment(self, ai):
        recs = ai.recommend_relations("structure", "item")
        for rec in recs:
            assert rec.judgment is not None


# ═════════════════════════════════════════════════════════════════════════════
# 4. Recommend targets
# ═════════════════════════════════════════════════════════════════════════════

class TestRecommendTargets:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_returns_recommendations(self, ai):
        recs = ai.recommend_targets("structure", "association")
        assert len(recs) > 0

    def test_top_k(self, ai):
        recs = ai.recommend_targets("structure", "association", top_k=3)
        assert len(recs) <= 3

    def test_targets_are_concrete(self, ai):
        recs = ai.recommend_targets("structure", "association")
        for rec in recs:
            entity = KERNEL_SPEC.get_entity(rec.triple[1])
            assert entity is not None
            assert not entity.is_abstract

    def test_sorted_by_score(self, ai):
        recs = ai.recommend_targets("structure", "association")
        if len(recs) > 1:
            for i in range(len(recs) - 1):
                assert recs[i].score >= recs[i + 1].score

    def test_recommendation_triple_format(self, ai):
        recs = ai.recommend_targets("structure", "association")
        for rec in recs:
            assert rec.triple[0] == "structure"
            assert rec.triple[2] == "association"


# ═════════════════════════════════════════════════════════════════════════════
# 5. Explain
# ═════════════════════════════════════════════════════════════════════════════

class TestExplain:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_explain_allowed(self, ai):
        explanation = ai.explain("structure", "item", "association")
        assert "ALLOWED" in explanation

    def test_explain_denied(self, ai):
        explanation = ai.explain("item", "structure", "specialization")
        assert "DENIED" in explanation

    def test_explain_has_confidence(self, ai):
        explanation = ai.explain("structure", "item", "association")
        assert "Confidence" in explanation

    def test_explain_has_winning_rule(self, ai):
        explanation = ai.explain("structure", "item", "association")
        assert "Winning rule" in explanation

    def test_explain_is_string(self, ai):
        explanation = ai.explain("structure", "item", "association")
        assert isinstance(explanation, str)
        assert len(explanation) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 6. Partial components
# ═════════════════════════════════════════════════════════════════════════════

class TestPartialComponents:
    def test_corpus_only(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        ai = AIDecisionInterface(corpus)
        ctx = ai.build_context("structure", "item", "association")
        assert ctx.judgment is not None
        assert ctx.reachable_paths == ()

    def test_with_graph_only(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        graph = TopologyGraph(KERNEL_SPEC)
        ai = AIDecisionInterface(corpus, graph=graph)
        ctx = ai.build_context("structure", "item", "association")
        assert isinstance(ctx.reachable_paths, tuple)

    def test_recommend_without_ledger(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        ai = AIDecisionInterface(corpus)
        recs = ai.recommend_relations("structure", "item")
        assert len(recs) > 0


# ═════════════════════════════════════════════════════════════════════════════
# 7. Validate model with context
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateModelWithContext:
    @pytest.fixture
    def ai(self):
        return AIDecisionInterface.from_kernel()

    def test_valid_model(self, ai):
        elements = (
            InstanceElement(id="e1", entity_type="structure", name="A"),
            InstanceElement(id="e2", entity_type="item", name="B"),
        )
        relations = (
            InstanceRelation(
                id="r1", relation_type="association",
                source_id="e1", target_id="e2",
            ),
        )
        results = ai.validate_model_with_context(elements, relations)
        assert len(results) > 0
        for _cr, ctx in results:
            assert isinstance(ctx, DecisionContext)

    def test_empty_model(self, ai):
        results = ai.validate_model_with_context((), ())
        assert results == ()


# ═════════════════════════════════════════════════════════════════════════════
# 8. Type tests
# ═════════════════════════════════════════════════════════════════════════════

class TestTypes:
    def test_decision_context_frozen(self):
        from ea_kernel.types import JudgmentReport
        judgment = JudgmentReport(
            verdict=True, evidence=(),
            confidence=RuleConfidence.COMMON,
            domains=(), conflicts=(),
        )
        ctx = DecisionContext(
            subject_triple=("a", "b", "c"),
            judgment=judgment,
            related_decisions=(),
        )
        with pytest.raises(AttributeError):
            ctx.subject_triple = ("x", "y", "z")  # type: ignore[misc]

    def test_recommendation_frozen(self):
        from ea_kernel.types import JudgmentReport
        judgment = JudgmentReport(
            verdict=True, evidence=(),
            confidence=RuleConfidence.COMMON,
            domains=(), conflicts=(),
        )
        rec = Recommendation(
            triple=("a", "b", "c"),
            score=0.8,
            judgment=judgment,
            rationale="test",
        )
        with pytest.raises(AttributeError):
            rec.score = 0.5  # type: ignore[misc]

    def test_decision_context_defaults(self):
        from ea_kernel.types import JudgmentReport
        judgment = JudgmentReport(
            verdict=True, evidence=(),
            confidence=RuleConfidence.COMMON,
            domains=(), conflicts=(),
        )
        ctx = DecisionContext(
            subject_triple=("a", "b", "c"),
            judgment=judgment,
            related_decisions=(),
        )
        assert ctx.reachable_paths == ()


# ═════════════════════════════════════════════════════════════════════════════
# 9. Score range
# ═════════════════════════════════════════════════════════════════════════════

class TestScoreRange:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_all_scores_in_range(self, ai):
        recs = ai.recommend_relations("structure", "item")
        for rec in recs:
            assert 0.0 <= rec.score <= 1.0

    def test_target_scores_in_range(self, ai):
        recs = ai.recommend_targets("structure", "association")
        for rec in recs:
            assert 0.0 <= rec.score <= 1.0

    def test_denied_triples_not_recommended(self, ai):
        recs = ai.recommend_relations("item", "structure")
        # All recommended should have positive score (verdict=True)
        for rec in recs:
            assert rec.score > 0.0
            assert rec.judgment.verdict is True


# ═════════════════════════════════════════════════════════════════════════════
# 10. Explain additional
# ═════════════════════════════════════════════════════════════════════════════

class TestExplainAdditional:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_explain_structure(self, ai):
        exp = ai.explain("structure", "item", "association")
        assert "structure" in exp
        assert "item" in exp
        assert "association" in exp

    def test_explain_different_relations(self, ai):
        exp1 = ai.explain("structure", "item", "association")
        exp2 = ai.explain("structure", "structure", "specialization")
        assert "ALLOWED" in exp1
        assert "ALLOWED" in exp2

    def test_explain_with_ledger(self):
        from ea_kernel.decision_ledger import DecisionLedger
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        ledger = DecisionLedger(corpus)
        d = DecisionRecord(
            id="d1", timestamp="2024-01-01T00:00:00Z",
            actor="human:alice", decision_type="override",
            subject_triple=("structure", "item", "association"),
        )
        ledger = ledger.record(d)
        ai = AIDecisionInterface(corpus, ledger=ledger)
        exp = ai.explain("structure", "item", "association")
        assert "Override history" in exp


# ═════════════════════════════════════════════════════════════════════════════
# 11. Validate model edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestValidateModelEdgeCases:
    @pytest.fixture
    def ai(self):
        return AIDecisionInterface.from_kernel()

    def test_invalid_element_produces_context(self, ai):
        elements = (
            InstanceElement(id="e1", entity_type="nonexistent", name="Bad"),
        )
        results = ai.validate_model_with_context(elements, ())
        assert len(results) > 0
        cr, ctx = results[0]
        assert cr.valid is False
        assert isinstance(ctx, DecisionContext)

    def test_multiple_relations_validated(self, ai):
        elements = (
            InstanceElement(id="e1", entity_type="structure", name="A"),
            InstanceElement(id="e2", entity_type="item", name="B"),
            InstanceElement(id="e3", entity_type="structure", name="C"),
        )
        relations = (
            InstanceRelation(
                id="r1", relation_type="association",
                source_id="e1", target_id="e2",
            ),
            InstanceRelation(
                id="r2", relation_type="specialization",
                source_id="e1", target_id="e3",
            ),
        )
        results = ai.validate_model_with_context(elements, relations)
        # 3 element checks + 2 relation checks = 5
        assert len(results) >= 5


# ═════════════════════════════════════════════════════════════════════════════
# 12. Recommend targets — additional
# ═════════════════════════════════════════════════════════════════════════════

class TestRecommendTargetsAdditional:
    @pytest.fixture
    def ai(self):
        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        return AIDecisionInterface(corpus)

    def test_targets_for_succession(self, ai):
        recs = ai.recommend_targets("step", "succession")
        assert len(recs) > 0
        targets = {r.triple[1] for r in recs}
        assert "step" in targets or "action" in targets

    def test_targets_for_transition(self, ai):
        recs = ai.recommend_targets("state", "transition")
        assert len(recs) > 0

    def test_top_k_1_returns_single(self, ai):
        recs = ai.recommend_targets("structure", "association", top_k=1)
        assert len(recs) == 1
