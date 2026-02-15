"""Profile-level topology graph navigation.

Builds a navigable graph from a KernelProfile where:
- Nodes = profile elements (by name)
- Edges = expanded validity rules (valid=True only)

Pattern rules (@Category, #Layer, *) are expanded into concrete
element-to-element edges. This enables experience discovery traversal
at the profile level — complementing TopologyGraph which operates on
kernel schema types.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from ea_kernel.profile_types import KernelProfile, match_pattern


@dataclass(frozen=True)
class ProfileEdge:
    """A concrete edge between two profile elements."""
    source: str
    target: str
    relation: str
    rule_id: str
    priority: int


@dataclass(frozen=True)
class ProfilePath:
    """An ordered sequence of edges forming a path."""
    edges: tuple[ProfileEdge, ...]


class ProfileTopologyGraph:
    """Navigable graph view of a profile's element topology.

    Expands validity-rule patterns into concrete element-to-element edges,
    then provides reachability, path-finding, and impact analysis.
    """

    __slots__ = ("_profile", "_outgoing", "_incoming", "_nodes")

    def __init__(self, profile: KernelProfile) -> None:
        self._profile = profile
        self._outgoing: dict[str, list[ProfileEdge]] = {}
        self._incoming: dict[str, list[ProfileEdge]] = {}
        self._nodes: set[str] = set()
        self._build()

    # ── Edge queries ───────────────────────────────────────────────

    def outgoing(
        self, element: str, relation: str | None = None,
    ) -> tuple[ProfileEdge, ...]:
        edges = self._outgoing.get(element, [])
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        return tuple(edges)

    def incoming(
        self, element: str, relation: str | None = None,
    ) -> tuple[ProfileEdge, ...]:
        edges = self._incoming.get(element, [])
        if relation is not None:
            edges = [e for e in edges if e.relation == relation]
        return tuple(edges)

    def neighbors(self, element: str) -> tuple[str, ...]:
        seen: set[str] = set()
        for edge in self._outgoing.get(element, []):
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
    ) -> tuple[ProfilePath, ...]:
        """BFS path enumeration from source to target."""
        if source not in self._nodes or target not in self._nodes:
            return ()

        paths: list[ProfilePath] = []
        queue: deque[tuple[str, list[ProfileEdge]]] = deque()
        queue.append((source, []))

        while queue:
            node, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            for edge in self._outgoing.get(node, []):
                if relation_filter is not None and edge.relation not in relation_filter:
                    continue

                visited = {source}
                for e in path:
                    visited.add(e.target)
                if edge.target in visited and edge.target != target:
                    continue

                new_path = path + [edge]

                if edge.target == target:
                    paths.append(ProfilePath(edges=tuple(new_path)))
                elif edge.target not in visited:
                    queue.append((edge.target, new_path))

        return tuple(paths)

    # ── Reachability ───────────────────────────────────────────────

    def reachable(
        self,
        source: str,
        *,
        max_depth: int = 3,
        relation_filter: frozenset[str] | None = None,
    ) -> tuple[str, ...]:
        """All elements reachable from source within depth."""
        if source not in self._nodes:
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
        element: str,
        *,
        direction: str = "outgoing",
        max_depth: int = 3,
    ) -> dict[str, tuple[ProfilePath, ...]]:
        """Map of reachable element -> paths leading to it."""
        result: dict[str, list[ProfilePath]] = {}

        if direction in ("outgoing", "both"):
            targets = self.reachable(element, max_depth=max_depth)
            for t in targets:
                paths = self.find_paths(element, t, max_depth=max_depth)
                if paths:
                    result.setdefault(t, []).extend(paths)

        if direction in ("incoming", "both"):
            for src in self._nodes:
                if src == element:
                    continue
                paths = self.find_paths(src, element, max_depth=max_depth)
                if paths:
                    result.setdefault(src, []).extend(paths)

        return {k: tuple(v) for k, v in result.items()}

    def relation_distribution(self) -> dict[str, int]:
        """Count of edges per relation type."""
        counts: dict[str, int] = {}
        for edges in self._outgoing.values():
            for edge in edges:
                counts[edge.relation] = counts.get(edge.relation, 0) + 1
        return counts

    @property
    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted(self._nodes))

    @property
    def edge_count(self) -> int:
        return sum(len(edges) for edges in self._outgoing.values())

    # ── Graph construction ─────────────────────────────────────────

    def _build(self) -> None:
        """Expand validity rules into concrete edges."""
        profile = self._profile

        for elem in profile.elements:
            self._nodes.add(elem.name)

        for rule in profile.validity_rules:
            if not rule.valid:
                continue

            sources = [
                e.name for e in profile.elements
                if match_pattern(e, rule.source_pattern)
            ]
            targets = [
                e.name for e in profile.elements
                if match_pattern(e, rule.target_pattern)
            ]

            for src in sources:
                for tgt in targets:
                    if src == tgt:
                        continue
                    edge = ProfileEdge(
                        source=src,
                        target=tgt,
                        relation=rule.relationship_name,
                        rule_id=rule.id,
                        priority=rule.priority,
                    )
                    self._outgoing.setdefault(src, []).append(edge)
                    self._incoming.setdefault(tgt, []).append(edge)
