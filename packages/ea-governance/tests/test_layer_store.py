from __future__ import annotations

from pathlib import Path

import pytest
from ea_governance.layer_store import ALLOWED_LAYERS, GovernanceLayerStore


def test_layer_store_saves_and_reads_payload(tmp_path: Path):
    store = GovernanceLayerStore(tmp_path / "decision.db", layer="decision")

    model_id = store.save_payload("decision-meta-v1", {"stages": ["context", "option", "evaluate"]})
    assert model_id == "decision-meta-v1"

    loaded = store.get_payload("decision-meta-v1")
    assert loaded is not None
    assert loaded["stages"] == ["context", "option", "evaluate"]

    snapshots = store.list_snapshots()
    assert len(snapshots) == 1
    assert snapshots[0].layer == "decision"


def test_layer_store_requires_supported_layer(tmp_path: Path):
    with pytest.raises(ValueError, match="Unsupported layer"):
        GovernanceLayerStore(tmp_path / "bad.db", layer="bad-layer")


def test_allowed_layers_contract():
    assert set(ALLOWED_LAYERS) == {
        "infra",
        "governance",
        "decision",
        "needs",
        "kernel",
        "flow",
    }
