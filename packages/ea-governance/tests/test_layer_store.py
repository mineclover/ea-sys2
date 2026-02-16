from __future__ import annotations

from pathlib import Path

import pytest
from ea_governance.layer_store import (
    ALLOWED_LAYERS,
    GovernanceLayerStore,
    InMemoryGovernanceLayerStore,
    SQLiteGovernanceLayerStore,
)


def test_sqlite_layer_store_saves_and_reads_payload(tmp_path: Path):
    store = SQLiteGovernanceLayerStore(tmp_path / "decision.db", layer="decision")

    model_id = store.save_payload("decision-meta-v1", {"stages": ["context", "option", "evaluate"]})
    assert model_id == "decision-meta-v1"

    loaded = store.get_payload("decision-meta-v1")
    assert loaded is not None
    assert loaded["stages"] == ["context", "option", "evaluate"]

    snapshots = store.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].layer == "decision"


def test_sqlite_layer_store_requires_supported_layer(tmp_path: Path):
    with pytest.raises(ValueError, match="Unsupported layer"):
        SQLiteGovernanceLayerStore(tmp_path / "bad.db", layer="bad-layer")


def test_inmemory_layer_store_saves_and_reads_payload():
    store = InMemoryGovernanceLayerStore(layer="decision")

    model_id = store.save_payload("decision-meta-v1", {"stages": ["context", "option", "evaluate"]})
    assert model_id == "decision-meta-v1"

    loaded = store.get_payload("decision-meta-v1")
    assert loaded is not None
    assert loaded["stages"] == ["context", "option", "evaluate"]

    snapshots = store.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].layer == "decision"


def test_inmemory_layer_store_requires_supported_layer():
    with pytest.raises(ValueError, match="Unsupported layer"):
        InMemoryGovernanceLayerStore(layer="bad-layer")


def test_inmemory_layer_store_upsert():
    store = InMemoryGovernanceLayerStore(layer="kernel")
    store.save_payload("m1", {"v": 1})
    store.save_payload("m1", {"v": 2})

    loaded = store.get_payload("m1")
    assert loaded is not None
    assert loaded["v"] == 2

    assert len(store.list_snapshots()) == 1


def test_inmemory_layer_store_get_missing():
    store = InMemoryGovernanceLayerStore(layer="kernel")
    assert store.get_payload("nonexistent") is None


def test_abc_is_abstract():
    with pytest.raises(TypeError):
        GovernanceLayerStore()  # type: ignore[abstract]


def test_allowed_layers_contract():
    assert set(ALLOWED_LAYERS) == {
        "infra",
        "governance",
        "decision",
        "needs",
        "kernel",
        "flow",
    }
