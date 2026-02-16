"""Governance-managed needs store built on layer-scoped store contracts."""

from __future__ import annotations

import json

from ea_needs.catalog import NeedCatalog

from ea_governance.layer_store import GovernanceLayerStore


class GovernanceNeedsStore:
    """Needs catalog store implemented via layer-scoped governance store."""

    def __init__(self, layer_store: GovernanceLayerStore):
        self._layer_store = layer_store

    def save_catalog(self, catalog: NeedCatalog) -> str:
        payload = json.loads(catalog.to_json())
        return self._layer_store.save_payload(model_id=catalog.id, payload=payload)

    def get_catalog(self, catalog_id: str) -> NeedCatalog | None:
        payload = self._layer_store.get_payload(catalog_id)
        if payload is None:
            return None
        return NeedCatalog.from_json(json.dumps(payload, ensure_ascii=False))

    def list_catalogs(self) -> list[NeedCatalog]:
        snapshots = self._layer_store.list_snapshots()
        return [
            NeedCatalog.from_json(json.dumps(snapshot.payload, ensure_ascii=False))
            for snapshot in snapshots
        ]
