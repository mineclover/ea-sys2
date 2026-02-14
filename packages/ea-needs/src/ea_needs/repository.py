"""Persistence repository for NeedCatalog (N3).

Needs core keeps persistence lightweight (JSON/file).
DB-backed persistence is managed by the governance layer.
"""

from __future__ import annotations

from pathlib import Path

from ea_needs.catalog import NeedCatalog


class NeedRepository:
    """File-based repository for NeedCatalog persistence."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.catalog_dir = self.data_dir / "catalogs"
        self.catalog_dir.mkdir(parents=True, exist_ok=True)

    def save_catalog(self, catalog: NeedCatalog) -> str:
        """Persist a NeedCatalog to a JSON file."""
        file_path = self.catalog_dir / f"{catalog.id}.json"
        file_path.write_text(catalog.to_json(), encoding="utf-8")
        return catalog.id

    def get_catalog(self, catalog_id: str) -> NeedCatalog | None:
        """Retrieve a NeedCatalog by ID."""
        file_path = self.catalog_dir / f"{catalog_id}.json"
        if not file_path.exists():
            return None
        return NeedCatalog.from_json(file_path.read_text(encoding="utf-8"))

    def list_catalogs(self) -> list[NeedCatalog]:
        """List all persisted catalogs."""
        catalogs: list[NeedCatalog] = []
        for file_path in sorted(self.catalog_dir.glob("*.json")):
            catalogs.append(NeedCatalog.from_json(file_path.read_text(encoding="utf-8")))
        return catalogs
