"""Layer-scoped store for governance-managed model payloads."""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, cast

from datetime import UTC, datetime


def _now() -> str:
    return datetime.now(UTC).isoformat() + "Z"

ALLOWED_LAYERS: tuple[str, ...] = (
    "infra",
    "governance",
    "decision",
    "needs",
    "kernel",
    "flow",
)


@dataclass(frozen=True)
class LayerSnapshot:
    layer: str
    model_id: str
    payload: dict[str, Any]
    updated_at: str


class GovernanceLayerStore(ABC):
    """Layer-scoped store ABC."""

    layer: str

    @abstractmethod
    def save_payload(self, model_id: str, payload: dict[str, Any]) -> str: ...

    @abstractmethod
    def get_payload(self, model_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def list_snapshots(self) -> list[LayerSnapshot]: ...


class InMemoryGovernanceLayerStore(GovernanceLayerStore):
    """In-memory implementation for testing."""

    __slots__ = ("layer", "_data")

    def __init__(self, layer: str):
        if layer not in ALLOWED_LAYERS:
            raise ValueError(
                f"Unsupported layer {layer!r}; expected one of {', '.join(ALLOWED_LAYERS)}"
            )
        self.layer = layer
        self._data: dict[str, tuple[dict[str, Any], str]] = {}

    def save_payload(self, model_id: str, payload: dict[str, Any]) -> str:
        self._data[model_id] = (payload, _now())
        return model_id

    def get_payload(self, model_id: str) -> dict[str, Any] | None:
        entry = self._data.get(model_id)
        if entry is None:
            return None
        return entry[0]

    def list_snapshots(self) -> list[LayerSnapshot]:
        snapshots: list[LayerSnapshot] = []
        for model_id in sorted(self._data):
            payload, updated_at = self._data[model_id]
            snapshots.append(
                LayerSnapshot(
                    layer=self.layer,
                    model_id=model_id,
                    payload=payload,
                    updated_at=updated_at,
                )
            )
        return snapshots


class SQLiteGovernanceLayerStore(GovernanceLayerStore):
    """SQLite-backed store bound to a single EA layer."""

    __slots__ = ("layer", "db_path")

    def __init__(self, db_path: str | Path, layer: str):
        if layer not in ALLOWED_LAYERS:
            raise ValueError(
                f"Unsupported layer {layer!r}; expected one of {', '.join(ALLOWED_LAYERS)}"
            )
        self.layer = layer
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS layer_models (
                    layer TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (layer, model_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_layer_models_updated
                ON layer_models(layer, updated_at)
                """
            )
            conn.commit()

    def save_payload(self, model_id: str, payload: dict[str, Any]) -> str:
        updated_at = _now()
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO layer_models (layer, model_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(layer, model_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (self.layer, model_id, payload_json, updated_at),
            )
            conn.commit()
        return model_id

    def get_payload(self, model_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM layer_models
                WHERE layer = ? AND model_id = ?
                """,
                (self.layer, model_id),
            ).fetchone()
        if row is None:
            return None
        return cast(dict[str, Any], json.loads(str(row[0])))

    def list_snapshots(self) -> list[LayerSnapshot]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT model_id, payload_json, updated_at
                FROM layer_models
                WHERE layer = ?
                ORDER BY model_id ASC
                """,
                (self.layer,),
            ).fetchall()

        snapshots: list[LayerSnapshot] = []
        for model_id, payload_json, updated_at in rows:
            snapshots.append(
                LayerSnapshot(
                    layer=self.layer,
                    model_id=str(model_id),
                    payload=cast(dict[str, Any], json.loads(str(payload_json))),
                    updated_at=str(updated_at),
                )
            )
        return snapshots
