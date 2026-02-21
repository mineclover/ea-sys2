"""Tests for ea_trace.chain."""

import pytest
from ea_trace.chain import (
    LineageError,
    TraceLink,
    TraceNodeRef,
    compose_lineage,
    missing_required_relations,
    replay_lineage_nodes,
)


def _node(node_type: str, node_id: str) -> TraceNodeRef:
    return TraceNodeRef(node_type=node_type, node_id=node_id)


def test_compose_lineage_finds_expected_path():
    decision = _node("decision_record", "d-1")
    need = _node("need_record", "n-1")
    kernel = _node("kernel_change", "k-1")
    flow = _node("flow_execution", "f-1")
    projection = _node("surface_artifact", "p-1")

    links = [
        TraceLink(decision, need, "derived_from"),
        TraceLink(need, kernel, "satisfies"),
        TraceLink(kernel, flow, "implements"),
        TraceLink(flow, projection, "exposed_as"),
    ]

    chain = compose_lineage(links, decision, projection)
    assert [link.relation for link in chain] == [
        "derived_from",
        "satisfies",
        "implements",
        "exposed_as",
    ]


def test_compose_lineage_raises_when_unreachable():
    decision = _node("decision_record", "d-1")
    need = _node("need_record", "n-1")
    detached_projection = _node("surface_artifact", "p-404")

    links = [TraceLink(decision, need, "derived_from")]

    with pytest.raises(LineageError):
        compose_lineage(links, decision, detached_projection)


def test_replay_lineage_nodes_returns_bfs_reachability():
    decision = _node("decision_record", "d-1")
    need = _node("need_record", "n-1")
    kernel = _node("kernel_change", "k-1")
    flow = _node("flow_execution", "f-1")

    links = [
        TraceLink(decision, need, "derived_from"),
        TraceLink(need, kernel, "satisfies"),
        TraceLink(kernel, flow, "implements"),
    ]

    replayed = replay_lineage_nodes(links, decision)
    assert [node.node_type for node in replayed] == [
        "decision_record",
        "need_record",
        "kernel_change",
        "flow_execution",
    ]


def test_missing_required_relations_reports_gaps():
    decision = _node("decision_record", "d-1")
    need = _node("need_record", "n-1")
    links = [TraceLink(decision, need, "derived_from")]

    missing = missing_required_relations(
        links,
        required_relations=["derived_from", "informed_by"],
    )
    assert missing == {"informed_by"}
