"""Topology graph navigation and path finding.

Phase 2: Graph view of kernel topology enabling path enumeration,
reachability analysis, and impact assessment for AI agents.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from ea_kernel.types import (
    GraphEdge,
    GraphPath,
    KernelSchema,
    RuleConfidence,
)

if TYPE_CHECKING:
    from ea_kernel.rule_corpus import RuleCorpus


# Confidence ordering for min-confidence calculation
_CONFIDENCE_ORDER: dict[RuleConfidence, int] = {
    RuleConfidence.EMPIRICAL: 0,
    RuleConfidence.CONTEXTUAL: 1,
    RuleConfidence.COMMON: 2,
    RuleConfidence.UNIVERSAL: 3,
}


def _min_confidence(a: RuleConfidence, b: RuleConfidence) -> RuleConfidence:
    return a if _CONFIDENCE_ORDER[a] <= _CONFIDENCE_ORDER[b] else b


class TopologyGraph:
    """Navigable graph view of kernel topology."""

    __slots__ = ("_outgoing", "_incoming", "_schema", "_corpus", "_entities", "_domain")


    def __init__(
        self,
        schema: KernelSchema,
        corpus: RuleCorpus | None = None,
        domain: str | None = None,
    ) -> None:
        self._schema = schema
        self._corpus = corpus
        self._domain = domain
        self._outgoing: dict[str, list[GraphEdge]] = {}
        self._incoming: dict[str, list[GraphEdge]] = {}
        self._entities: set[str] = set()
        self._build_adjacency()

    @classmethod
    def from_spec(cls, corpus: RuleCorpus | None = None, domain: str | None = None) -> TopologyGraph:
        """Build from KERNEL_SPEC."""
        from ea_kernel.spec import KERNEL_SPEC
        return cls(KERNEL_SPEC, corpus, domain)

    # ... (methods outgoing, incoming, neighbors, find_paths, reachable, impact_analysis, relation_distribution, entities, edge_count unchanged) ...
    # Wait, need to check if I can keep them or if I need to copy paste.
    # replace_file_content needs context. I'll include adjacent methods to anchor.

    # ── Edge queries ───────────────────────────────────────────────

    def outgoing(
        self, entity: str, relation: str | None = None,
    ) -> tuple[GraphEdge, ...]:
        """All outgoing edges from entity, optionally filtered by relation."""
        edges = self._outgoing.get(entity, [])
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        return tuple(edges)

    def incoming(
        self, entity: str, relation: str | None = None,
    ) -> tuple[GraphEdge, ...]:
        """All incoming edges to entity."""
        edges = self._incoming.get(entity, [])
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        return tuple(edges)

    def neighbors(self, entity: str) -> tuple[str, ...]:
        """All directly connected entities (via outgoing edges)."""
        seen: set[str] = set()
        for edge in self._outgoing.get(entity, []):
            seen.add(edge.target)
        return tuple(sorted(seen))

    # ── Path finding ───────────────────────────────────────────────

    def find_paths(
        self,
        source: str,
        target: str,
        *,
        max_depth: int = 5,
        relation_filter: frozenset[str] | None = None,
        valid_only: bool = True,
    ) -> tuple[GraphPath, ...]:
        """BFS path enumeration from source to target."""
        if source not in self._entities or target not in self._entities:
            return ()

        paths: list[GraphPath] = []
        # BFS with path tracking: queue of (current_node, path_edges)
        queue: deque[tuple[str, list[GraphEdge]]] = deque()
        queue.append((source, []))

        while queue:
            node, path = queue.popleft()

            if len(path) >= max_depth:
                continue

            for edge in self._outgoing.get(node, []):
                if relation_filter is not None and edge.relation not in relation_filter:
                    continue
                if valid_only and edge.judgment is not None and not edge.judgment.verdict:
                    continue

                # Avoid cycles in this path
                visited = {source}
                for e in path:
                    visited.add(e.target)
                if edge.target in visited and edge.target != target:
                    continue

                new_path = path + [edge]

                if edge.target == target:
                    # Compute total confidence
                    confidence = RuleConfidence.UNIVERSAL
                    for e in new_path:
                        if e.judgment is not None:
                            confidence = _min_confidence(confidence, e.judgment.confidence)
                    paths.append(GraphPath(
                        edges=tuple(new_path),
                        total_confidence=confidence,
                    ))
                elif edge.target not in visited:
                    queue.append((edge.target, new_path))

        return tuple(paths)

    def reachable(
        self,
        source: str,
        *,
        max_depth: int = 3,
        relation_filter: frozenset[str] | None = None,
    ) -> tuple[str, ...]:
        """All entities reachable from source within depth."""
        if source not in self._entities:
            return ()

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        queue.append((source, 0))

        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in self._outgoing.get(node, []):
                if relation_filter is not None and edge.relation not in relation_filter:
                    continue
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, depth + 1))

        return tuple(sorted(visited))

    # ── Analysis ───────────────────────────────────────────────────

    def impact_analysis(
        self,
        entity: str,
        *,
        direction: str = "outgoing",
        max_depth: int = 3,
    ) -> dict[str, tuple[GraphPath, ...]]:
        """Map of reachable entity → paths leading to it."""
        result: dict[str, list[GraphPath]] = {}

        if direction in ("outgoing", "both"):
            targets = self.reachable(entity, max_depth=max_depth)
            for t in targets:
                paths = self.find_paths(entity, t, max_depth=max_depth)
                if paths:
                    result.setdefault(t, []).extend(paths)

        if direction in ("incoming", "both"):
            # Find entities that can reach this one
            for src in self._entities:
                if src == entity:
                    continue
                paths = self.find_paths(src, entity, max_depth=max_depth)
                if paths:
                    result.setdefault(src, []).extend(paths)

        return {k: tuple(v) for k, v in result.items()}

    def relation_distribution(self) -> dict[str, int]:
        """Count of valid edges per relation type."""
        counts: dict[str, int] = {}
        for edges in self._outgoing.values():
            for edge in edges:
                counts[edge.relation] = counts.get(edge.relation, 0) + 1
        return counts

    @property
    def entities(self) -> tuple[str, ...]:
        return tuple(sorted(self._entities))

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._outgoing.values())


    @property
    def metadata(self) -> dict[str, str]:
        """Graph metadata including version and rule stats."""
        from datetime import UTC, datetime

        # Collect relevant rules to determine version
        versions = set()
        rule_count = 0

        # 1. From Corpus (if available) - rich metadata
        if self._corpus:
            entries = self._corpus.entries
            if self._domain:
                entries = tuple(e for e in entries if e.metadata.domain == self._domain)

            rule_count += len(entries)
            for e in entries:
                if e.metadata.established_version:
                    versions.add(e.metadata.established_version)

        # 2. From Schema (if no corpus or domain includes kernel)
        # Note: KernelSchema rules don't carry rich metadata directly in the object model usually,
        # but if we are in "kernel" mode and have no corpus, we might want to show a hardcoded version?
        # Or rely on what we found in corpus (which includes kernel rules typically).
        if not self._corpus and (self._domain is None or self._domain == "kernel"):
             rule_count += len(self._schema.validity_rules)
             # Fallback/Default for kernel
             versions.add("1.0.0")

        # Determine latest version
        latest_version = sorted(versions)[-1] if versions else "0.0.0"

        return {
            "generated_at": datetime.now(UTC).isoformat() + "Z",
            "domain": self._domain or "System",
            "rule_count": str(rule_count),
            "version": latest_version,
            "entities": str(len(self.entities)),
            "edges": str(self.edge_count),
        }

    # ── Graph construction ─────────────────────────────────────────

    def _build_adjacency(self) -> None:
        """Build adjacency lists from schema entities and validity rules."""
        schema = self._schema
        corpus = self._corpus
        target_domain = self._domain

        # Collect non-abstract entity names (and those relevant to domain if specified?)
        # For now, collect all concrete entities from schema.
        # Future: if domain defines new entities aka Logic Blobs, add them.
        for entity in schema.entities:
            if not entity.is_abstract:
                self._entities.add(entity.name)

        entity_list = tuple(sorted(self._entities))
        if not entity_list:
            return

        if corpus is None:
            relation_names = tuple(r.name for r in schema.relations)
            for source in entity_list:
                for target in entity_list:
                    for rel_name in relation_names:
                        k_result = schema.validate_relationship(source, target, rel_name)
                        if not k_result.valid:
                            continue
                        edge = GraphEdge(
                            source=source,
                            target=target,
                            relation=rel_name,
                            judgment=None,
                        )
                        self._outgoing.setdefault(source, []).append(edge)
                        self._incoming.setdefault(target, []).append(edge)
            return

        # Corpus-backed mode: use single evidence judgment path to avoid
        # duplicated schema+corpus validation for each triple.
        relation_names = tuple(r.name for r in schema.relations)
        active_entities = entity_list

        if target_domain is not None:
            domain_entries = tuple(
                entry for entry in corpus.entries if entry.metadata.domain == target_domain
            )
            if not domain_entries:
                return

            schema_relations = set(relation_names)
            domain_relations = {
                entry.rule.relationship_name
                for entry in domain_entries
                if entry.rule.relationship_name in schema_relations
            }
            if not domain_relations:
                return
            relation_names = tuple(sorted(domain_relations))

            domain_entities: set[str] = set()
            for entry in domain_entries:
                for pattern in (entry.rule.source_pattern, entry.rule.target_pattern):
                    matched = schema._pattern_matches.get(pattern)
                    if matched is not None:
                        domain_entities.update(matched)
                    else:
                        for entity_name in entity_list:
                            if schema.entity_matches(entity_name, pattern):
                                domain_entities.add(entity_name)

            if not domain_entities:
                return
            active_entities = tuple(sorted(domain_entities))

        for source in active_entities:
            for target in active_entities:
                for rel_name in relation_names:
                    judgment = corpus.judge(source, target, rel_name)
                    if not judgment.verdict:
                        continue

                    if target_domain is not None:
                        winner_domain = "kernel"
                        for ev in judgment.evidence:
                            if ev.is_winner:
                                winner_domain = ev.entry.metadata.domain
                                break
                        if winner_domain != target_domain:
                            continue

                    edge = GraphEdge(
                        source=source,
                        target=target,
                        relation=rel_name,
                        judgment=judgment,
                    )
                    self._outgoing.setdefault(source, []).append(edge)
                    self._incoming.setdefault(target, []).append(edge)
