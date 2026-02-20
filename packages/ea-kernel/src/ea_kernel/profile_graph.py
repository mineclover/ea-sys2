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

    __slots__ = ("_profile", "_outgoing", "_incoming", "_nodes", "_container_of")

    def __init__(self, profile: KernelProfile) -> None:
        self._profile = profile
        self._outgoing: dict[str, list[ProfileEdge]] = {}
        self._incoming: dict[str, list[ProfileEdge]] = {}
        self._nodes: set[str] = set()
        self._container_of: dict[str, str] = {}  # child → parent
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

    # ── Containment depth ────────────────────────────────────────────

    def containment_depths(self) -> dict[str, int]:
        """Return containment depth for all elements (0=root)."""
        depths: dict[str, int] = {}
        for name in self._nodes:
            d = 0
            current = name
            visited: set[str] = set()
            while current in self._container_of:
                if current in visited:
                    break  # guard against cycles
                visited.add(current)
                current = self._container_of[current]
                d += 1
            depths[name] = d
        return depths

    # ── Graph construction ─────────────────────────────────────────

    def _build(self) -> None:
        """Expand validity rules into concrete edges (scope-aware).

        Pass 1: Identify containment relationships → build container_of map.
        Pass 2: Expand all rules with scope checks.
        """
        profile = self._profile

        for elem in profile.elements:
            self._nodes.add(elem.name)

        # Pass 1: Build containment map from containment relations
        containment_rels: set[str] = set()
        for rel in profile.relations:
            if rel.kernel_relation in ("membership", "ownership"):
                containment_rels.add(rel.name)

        # Collect containment edges — process higher-priority rules first
        # so instance-level rules (priority 60+) set containment before
        # category-level rules (priority 50) which would create spurious mappings.
        containment_rules = sorted(
            (r for r in profile.validity_rules
             if r.valid and r.relationship_name in containment_rels),
            key=lambda r: -r.priority,
        )
        for rule in containment_rules:

            containers = [
                e.name for e in profile.elements
                if match_pattern(e, rule.source_pattern)
            ]
            children = [
                e.name for e in profile.elements
                if match_pattern(e, rule.target_pattern)
            ]

            for container in containers:
                for child in children:
                    if container == child:
                        continue
                    # Only set if not already assigned (first match wins)
                    if child not in self._container_of:
                        # Guard: reject if this would create a cycle
                        if not self._would_create_cycle(child, container):
                            self._container_of[child] = container

        # Pass 2: Expand all valid rules with scope checks
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

            scope = getattr(rule, "scope", "")

            for src in sources:
                for tgt in targets:
                    if src == tgt:
                        continue
                    if scope == "sibling" and not self._are_siblings(src, tgt):
                        continue
                    if scope == "subtree" and not self._in_same_subtree(src, tgt):
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

    def _would_create_cycle(self, child: str, parent: str) -> bool:
        """Check if setting container_of[child]=parent would create a cycle."""
        current = parent
        visited: set[str] = set()
        while current in self._container_of:
            if current == child:
                return True
            if current in visited:
                break
            visited.add(current)
            current = self._container_of[current]
        return current == child

    def _are_siblings(self, a: str, b: str) -> bool:
        """True if a and b share the same immediate container."""
        pa = self._container_of.get(a)
        pb = self._container_of.get(b)
        return pa is not None and pa == pb

    def _in_same_subtree(self, a: str, b: str) -> bool:
        """True if a and b share the same root in the containment tree."""
        return self._root_of(a) == self._root_of(b)

    def _root_of(self, name: str) -> str:
        """Walk up the containment chain to find the root."""
        current = name
        visited: set[str] = set()
        while current in self._container_of:
            if current in visited:
                break  # guard against cycles
            visited.add(current)
            current = self._container_of[current]
        return current
