"""AI decision interface for kernel interaction.

Phase 4: Structured interface for AI agents to query the kernel,
get recommendations, and receive evidence-based explanations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ea_kernel.types import (
    ConformanceResult,
    DecisionContext,
    DecisionRecord,
    GraphPath,
    InstanceElement,
    InstanceRelation,
    JudgmentReport,
    Recommendation,
    RuleConfidence,
)

if TYPE_CHECKING:
    from ea_kernel.decision_ledger import DecisionLedger
    from ea_kernel.graph_view import TopologyGraph
    from ea_kernel.rule_corpus import RuleCorpus


# Score mapping for confidence levels
_CONFIDENCE_SCORES: dict[RuleConfidence, float] = {
    RuleConfidence.UNIVERSAL: 1.0,
    RuleConfidence.COMMON: 0.7,
    RuleConfidence.CONTEXTUAL: 0.4,
    RuleConfidence.EMPIRICAL: 0.2,
}


class AIDecisionInterface:
    """Structured interface for AI agent interaction with the kernel."""

    __slots__ = ("_corpus", "_graph", "_ledger", "_judgment_cache")

    def __init__(
        self,
        corpus: RuleCorpus,
        graph: TopologyGraph | None = None,
        ledger: DecisionLedger | None = None,
    ) -> None:
        self._corpus = corpus
        self._graph = graph
        self._ledger = ledger
        self._judgment_cache: dict[tuple[str, str, str], JudgmentReport] = {}

    @classmethod
    def from_kernel(cls) -> AIDecisionInterface:
        """Build with all default kernel components."""
        from ea_kernel.decision_ledger import DecisionLedger
        from ea_kernel.graph_view import TopologyGraph
        from ea_kernel.rule_corpus import RuleCorpus
        from ea_kernel.spec import KERNEL_SPEC

        corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC)
        graph = TopologyGraph(KERNEL_SPEC, corpus)
        ledger = DecisionLedger(corpus)

        return cls(corpus, graph, ledger)

    # ── Judgment cache ──────────────────────────────────────────────

    def _cached_judge(
        self, source: str, target: str, relation: str,
    ) -> JudgmentReport:
        """Return cached judgment, computing on first access."""
        key = (source, target, relation)
        if key not in self._judgment_cache:
            self._judgment_cache[key] = self._corpus.judge(source, target, relation)
        return self._judgment_cache[key]

    # ── Context assembly ───────────────────────────────────────────

    def build_context(
        self, source: str, target: str, relation: str,
    ) -> DecisionContext:
        """Assemble full decision context for a triple."""
        judgment = self._cached_judge(source, target, relation)

        # Related decisions
        related: tuple[DecisionRecord, ...] = ()
        if self._ledger is not None:
            related = self._ledger.decisions_for(source, target, relation)

        # Reachable paths
        paths: tuple[GraphPath, ...] = ()
        if self._graph is not None:
            paths = self._graph.find_paths(source, target, max_depth=3)

        return DecisionContext(
            subject_triple=(source, target, relation),
            judgment=judgment,
            related_decisions=related,
            reachable_paths=paths,
        )

    # ── Recommendation ─────────────────────────────────────────────

    def recommend_relations(
        self, source: str, target: str, *, top_k: int = 5,
    ) -> tuple[Recommendation, ...]:
        """Rank possible relations between source and target."""
        from ea_kernel.spec import KERNEL_SPEC

        recommendations: list[Recommendation] = []

        for rel in KERNEL_SPEC.relations:
            judgment = self._cached_judge(source, target, rel.name)
            score = self._compute_score(judgment, source, target, rel.name)
            if score > 0:
                rationale = self._build_rationale(judgment, source, target, rel.name)
                recommendations.append(Recommendation(
                    triple=(source, target, rel.name),
                    score=score,
                    judgment=judgment,
                    rationale=rationale,
                ))

        recommendations.sort(key=lambda r: r.score, reverse=True)
        return tuple(recommendations[:top_k])

    def recommend_targets(
        self, source: str, relation: str, *, top_k: int = 5,
    ) -> tuple[Recommendation, ...]:
        """Rank possible target entities for source via relation."""
        from ea_kernel.spec import KERNEL_SPEC

        recommendations: list[Recommendation] = []

        for entity in KERNEL_SPEC.entities:
            if entity.is_abstract:
                continue
            judgment = self._cached_judge(source, entity.name, relation)
            score = self._compute_score(judgment, source, entity.name, relation)
            if score > 0:
                rationale = self._build_rationale(
                    judgment, source, entity.name, relation,
                )
                recommendations.append(Recommendation(
                    triple=(source, entity.name, relation),
                    score=score,
                    judgment=judgment,
                    rationale=rationale,
                ))

        recommendations.sort(key=lambda r: r.score, reverse=True)
        return tuple(recommendations[:top_k])

    # ── Explanation ────────────────────────────────────────────────

    def explain(
        self, source: str, target: str, relation: str,
    ) -> str:
        """Human-readable explanation of why a triple is allowed/denied."""
        judgment = self._cached_judge(source, target, relation)

        verdict_str = "ALLOWED" if judgment.verdict else "DENIED"
        lines = [f"{source} → {target} via {relation}: {verdict_str}"]
        lines.append(f"Confidence: {judgment.confidence.value}")

        # Winner evidence
        for ev in judgment.evidence:
            if ev.is_winner:
                rule = ev.entry.rule
                lines.append(
                    f"Winning rule: {rule.id} "
                    f"(priority={rule.priority}, valid={rule.valid})"
                )
                if rule.notes:
                    lines.append(f"  Rationale: {rule.notes}")
                break

        # Conflicts
        if judgment.conflicts:
            lines.append("Conflicts:")
            for conflict in judgment.conflicts:
                lines.append(f"  - {conflict}")

        # Override patterns
        if self._ledger is not None:
            decisions = self._ledger.decisions_for(source, target, relation)
            overrides = [d for d in decisions if d.decision_type == "override"]
            if overrides:
                lines.append(
                    f"Override history: {len(overrides)} override(s) recorded"
                )

        return "\n".join(lines)

    # ── Batch ──────────────────────────────────────────────────────

    def validate_model_with_context(
        self,
        elements: tuple[InstanceElement, ...],
        relations: tuple[InstanceRelation, ...],
    ) -> tuple[tuple[ConformanceResult, DecisionContext], ...]:
        """Validate M0 model and provide full context for each issue."""
        from ea_kernel.instance_validator import InstanceValidator

        schema = self._corpus.schema

        validator = InstanceValidator(schema)
        conformance_results = validator.validate_model(elements, relations)

        elem_map = {e.id: e for e in elements}
        paired: list[tuple[ConformanceResult, DecisionContext]] = []

        for cr in conformance_results:
            # Build context for relationship checks
            if cr.check_type == "relationship":
                # Find the relation
                rel = next(
                    (r for r in relations if r.id == cr.element_id), None,
                )
                if rel is not None:
                    src = elem_map.get(rel.source_id)
                    tgt = elem_map.get(rel.target_id)
                    if src is not None and tgt is not None:
                        ctx = self.build_context(
                            src.entity_type, tgt.entity_type, rel.relation_type,
                        )
                        paired.append((cr, ctx))
                        continue

            # Default context for non-relationship checks
            default_judgment = JudgmentReport(
                verdict=cr.valid,
                evidence=(),
                confidence=RuleConfidence.COMMON,
                domains=(),
                conflicts=(),
            )
            ctx = DecisionContext(
                subject_triple=(cr.element_id, "", cr.check_type),
                judgment=default_judgment,
                related_decisions=(),
            )
            paired.append((cr, ctx))

        return tuple(paired)

    # ── Scoring ────────────────────────────────────────────────────

    def _compute_score(
        self,
        judgment: JudgmentReport,
        source: str,
        target: str,
        relation: str,
    ) -> float:
        """Compute combined confidence score for a triple."""
        if not judgment.verdict:
            return 0.0

        base_score = _CONFIDENCE_SCORES.get(judgment.confidence, 0.5)

        # Override pattern boost
        if self._ledger is not None:
            patterns = self._ledger.override_patterns(min_count=1)
            for triple, count in patterns:
                if triple == (source, target, relation):
                    base_score = min(1.0, base_score + 0.1 * count)

        return round(base_score, 2)

    def _build_rationale(
        self,
        judgment: JudgmentReport,
        source: str,
        target: str,
        relation: str,
    ) -> str:
        """Build a rationale string for a recommendation."""
        parts: list[str] = []

        if judgment.verdict:
            parts.append(f"{source}→{target} via {relation} is valid")
        else:
            parts.append(f"{source}→{target} via {relation} is denied")

        parts.append(f"(confidence: {judgment.confidence.value})")

        # Find winning rule rationale
        for ev in judgment.evidence:
            if ev.is_winner and ev.entry.rule.notes:
                parts.append(f"— {ev.entry.rule.notes}")
                break

        return " ".join(parts)
