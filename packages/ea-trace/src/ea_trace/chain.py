"""Trace chain composition and lineage replay helpers."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TraceNodeRef:
    """Typed reference to a lineage node."""

    node_type: str
    node_id: str

    def key(self) -> str:
        """Return stable key used for graph traversal."""
        return f"{self.node_type}:{self.node_id}"


@dataclass(frozen=True)
class TraceLink:
    """Directed edge in a lineage graph."""

    source: TraceNodeRef
    target: TraceNodeRef
    relation: str
    required: bool = True


class LineageError(ValueError):
    """Raised when a requested lineage cannot be composed."""


def _build_adjacency(links: Iterable[TraceLink]) -> dict[str, list[TraceLink]]:
    adjacency: dict[str, list[TraceLink]] = defaultdict(list)
    for link in links:
        adjacency[link.source.key()].append(link)
    return adjacency


def compose_lineage(
    links: Iterable[TraceLink],
    start: TraceNodeRef,
    end: TraceNodeRef,
) -> list[TraceLink]:
    """Find a directed lineage path from start to end using BFS."""

    if start.key() == end.key():
        return []

    adjacency = _build_adjacency(links)
    queue: deque[str] = deque([start.key()])
    visited = {start.key()}
    previous: dict[str, tuple[str, TraceLink]] = {}
    nodes_by_key = {start.key(): start, end.key(): end}

    while queue:
        current_key = queue.popleft()
        for link in adjacency.get(current_key, []):
            next_key = link.target.key()
            nodes_by_key[next_key] = link.target
            if next_key in visited:
                continue
            visited.add(next_key)
            previous[next_key] = (current_key, link)
            if next_key == end.key():
                queue.clear()
                break
            queue.append(next_key)

    if end.key() not in previous:
        raise LineageError(
            f"cannot compose lineage from {start.key()} to {end.key()}"
        )

    path: list[TraceLink] = []
    cursor = end.key()
    while cursor != start.key():
        parent_key, link = previous[cursor]
        path.append(link)
        cursor = parent_key
    path.reverse()
    return path


def replay_lineage_nodes(
    links: Iterable[TraceLink],
    start: TraceNodeRef,
) -> list[TraceNodeRef]:
    """Replay reachable lineage nodes in BFS order from the given start node."""

    adjacency = _build_adjacency(links)
    queue: deque[TraceNodeRef] = deque([start])
    visited = {start.key()}
    ordered = [start]

    while queue:
        current = queue.popleft()
        for link in adjacency.get(current.key(), []):
            next_node = link.target
            next_key = next_node.key()
            if next_key in visited:
                continue
            visited.add(next_key)
            ordered.append(next_node)
            queue.append(next_node)

    return ordered


def missing_required_relations(
    links: Iterable[TraceLink],
    required_relations: Sequence[str],
) -> set[str]:
    """Return missing relations from required_relations."""

    found_relations = {link.relation for link in links}
    return {relation for relation in required_relations if relation not in found_relations}
