"""Infra asset catalog model + repository contracts and implementations."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ea_profile.v2.types import (
    InfraAssetSpec,
    InfraAssetType,
    InfraCriticality,
    InfraEnvironment,
)


def _normalize_owner(owner: str | None) -> str | None:
    if owner is None:
        return None
    normalized = owner.strip()
    if not normalized:
        raise ValueError("owner must be a non-empty string when provided")
    return normalized


@dataclass(frozen=True)
class InfraAssetQuery:
    """Filter options for infra asset catalog reads."""

    owner: str | None = None
    environment: InfraEnvironment | None = None
    criticality: InfraCriticality | None = None
    asset_type: InfraAssetType | None = None
    limit: int = 100
    offset: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner", _normalize_owner(self.owner))
        if self.environment is not None and not isinstance(self.environment, InfraEnvironment):
            raise TypeError("environment must be InfraEnvironment")
        if self.criticality is not None and not isinstance(self.criticality, InfraCriticality):
            raise TypeError("criticality must be InfraCriticality")
        if self.asset_type is not None and not isinstance(self.asset_type, InfraAssetType):
            raise TypeError("asset_type must be InfraAssetType")
        if not isinstance(self.limit, int):
            raise TypeError("limit must be int")
        if self.limit < 0:
            raise ValueError("limit must be >= 0")
        if not isinstance(self.offset, int):
            raise TypeError("offset must be int")
        if self.offset < 0:
            raise ValueError("offset must be >= 0")


@runtime_checkable
class InfraAssetCatalogStore(Protocol):
    """Infra asset catalog repository contract."""

    def save(self, asset: InfraAssetSpec) -> str: ...

    def get(self, asset_id: str) -> InfraAssetSpec | None: ...

    def list(self, *, query: InfraAssetQuery | None = None) -> list[InfraAssetSpec]: ...

    def count(self, *, query: InfraAssetQuery | None = None) -> int: ...


def _matches_query(asset: InfraAssetSpec, query: InfraAssetQuery) -> bool:
    if query.owner is not None and asset.owner != query.owner:
        return False
    if query.environment is not None and asset.environment != query.environment:
        return False
    if query.criticality is not None and asset.criticality != query.criticality:
        return False
    return query.asset_type is None or asset.asset_type == query.asset_type


class InMemoryInfraAssetCatalogStore:
    """In-memory infra asset catalog store."""

    __slots__ = ("_assets",)

    def __init__(self) -> None:
        self._assets: dict[str, InfraAssetSpec] = {}

    def save(self, asset: InfraAssetSpec) -> str:
        if not isinstance(asset, InfraAssetSpec):
            raise TypeError("asset must be InfraAssetSpec")
        self._assets[asset.id] = asset
        return asset.id

    def get(self, asset_id: str) -> InfraAssetSpec | None:
        return self._assets.get(asset_id)

    def list(self, *, query: InfraAssetQuery | None = None) -> list[InfraAssetSpec]:
        assets = [self._assets[key] for key in sorted(self._assets.keys())]
        if query is None:
            return assets
        filtered = [asset for asset in assets if _matches_query(asset, query)]
        end = query.offset + query.limit
        return filtered[query.offset:end]

    def count(self, *, query: InfraAssetQuery | None = None) -> int:
        if query is None:
            return len(self._assets)
        return sum(1 for asset in self._assets.values() if _matches_query(asset, query))


class SQLiteInfraAssetCatalogStore:
    """SQLite-backed infra asset catalog store."""

    __slots__ = ("_db_path",)

    _SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY
                );

                CREATE TABLE IF NOT EXISTS infra_assets (
                    id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    criticality TEXT NOT NULL,
                    exposure_refs_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_infra_assets_owner
                    ON infra_assets(owner);
                CREATE INDEX IF NOT EXISTS idx_infra_assets_environment
                    ON infra_assets(environment);
                CREATE INDEX IF NOT EXISTS idx_infra_assets_criticality
                    ON infra_assets(criticality);
                CREATE INDEX IF NOT EXISTS idx_infra_assets_asset_type
                    ON infra_assets(asset_type);
                """
            )
            row = conn.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO schema_version(version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            elif int(row["version"]) < self._SCHEMA_VERSION:
                conn.execute(
                    "UPDATE schema_version SET version = ?",
                    (self._SCHEMA_VERSION,),
                )
            conn.commit()

    def save(self, asset: InfraAssetSpec) -> str:
        if not isinstance(asset, InfraAssetSpec):
            raise TypeError("asset must be InfraAssetSpec")

        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO infra_assets (
                    id,
                    asset_type,
                    owner,
                    environment,
                    criticality,
                    exposure_refs_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    asset_type = excluded.asset_type,
                    owner = excluded.owner,
                    environment = excluded.environment,
                    criticality = excluded.criticality,
                    exposure_refs_json = excluded.exposure_refs_json
                """,
                (
                    asset.id,
                    asset.asset_type.value,
                    asset.owner,
                    asset.environment.value,
                    asset.criticality.value,
                    json.dumps(list(asset.exposure_refs), ensure_ascii=False),
                ),
            )
            conn.commit()
        return asset.id

    def get(self, asset_id: str) -> InfraAssetSpec | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    asset_type,
                    owner,
                    environment,
                    criticality,
                    exposure_refs_json
                FROM infra_assets
                WHERE id = ?
                """,
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_asset(row)

    def list(self, *, query: InfraAssetQuery | None = None) -> list[InfraAssetSpec]:
        where_sql, params = self._where_clause(query)
        sql = (
            "SELECT id, asset_type, owner, environment, criticality, exposure_refs_json "
            "FROM infra_assets"
            f"{where_sql} ORDER BY id ASC"
        )
        sql_params: list[object] = list(params)
        if query is not None:
            sql += " LIMIT ? OFFSET ?"
            sql_params.extend((query.limit, query.offset))

        with self._connection() as conn:
            rows = conn.execute(sql, sql_params).fetchall()
        return [self._row_to_asset(row) for row in rows]

    def count(self, *, query: InfraAssetQuery | None = None) -> int:
        where_sql, params = self._where_clause(query)
        sql = f"SELECT COUNT(*) AS cnt FROM infra_assets{where_sql}"
        with self._connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["cnt"]) if row is not None else 0

    @staticmethod
    def _where_clause(query: InfraAssetQuery | None) -> tuple[str, list[object]]:
        if query is None:
            return "", []

        clauses: list[str] = []
        params: list[object] = []
        if query.owner is not None:
            clauses.append("owner = ?")
            params.append(query.owner)
        if query.environment is not None:
            clauses.append("environment = ?")
            params.append(query.environment.value)
        if query.criticality is not None:
            clauses.append("criticality = ?")
            params.append(query.criticality.value)
        if query.asset_type is not None:
            clauses.append("asset_type = ?")
            params.append(query.asset_type.value)
        if not clauses:
            return "", params
        return " WHERE " + " AND ".join(clauses), params

    @staticmethod
    def _row_to_asset(row: sqlite3.Row) -> InfraAssetSpec:
        refs = json.loads(str(row["exposure_refs_json"]))
        if not isinstance(refs, list):
            raise ValueError("exposure_refs_json must deserialize to list")
        return InfraAssetSpec(
            id=str(row["id"]),
            asset_type=InfraAssetType(str(row["asset_type"])),
            owner=str(row["owner"]),
            environment=InfraEnvironment(str(row["environment"])),
            criticality=InfraCriticality(str(row["criticality"])),
            exposure_refs=tuple(str(item) for item in refs),
        )
