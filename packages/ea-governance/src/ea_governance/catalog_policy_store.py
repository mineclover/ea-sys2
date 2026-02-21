"""Catalog-level auto-express policy model, evaluation, and persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ea_ops.events import FeedbackLayer, ServiceOpsSeverity


def _now_iso() -> str:
    return datetime.now(UTC).isoformat() + "Z"


def _dedupe(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


@dataclass(frozen=True)
class CatalogAutoExpressPolicy:
    """Catalog-specific policy that gates needs auto-expression."""

    catalog_id: str
    enabled: bool = True
    allowed_severities: tuple[ServiceOpsSeverity, ...] = (
        ServiceOpsSeverity.LOW,
        ServiceOpsSeverity.MEDIUM,
        ServiceOpsSeverity.HIGH,
        ServiceOpsSeverity.CRITICAL,
    )
    allowed_event_names: tuple[str, ...] = ()
    allowed_feeds_back_to: tuple[FeedbackLayer, ...] = (FeedbackLayer.NEEDS,)
    stakeholder_event_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    updated_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        catalog_id = self.catalog_id.strip()
        if not catalog_id:
            raise ValueError("catalog_id must be a non-empty string")
        object.__setattr__(self, "catalog_id", catalog_id)

        severities = tuple(ServiceOpsSeverity(item) for item in self.allowed_severities)
        if not severities:
            raise ValueError("allowed_severities must not be empty")
        object.__setattr__(self, "allowed_severities", severities)

        event_names = tuple(
            item.strip()
            for item in self.allowed_event_names
            if str(item).strip()
        )
        if len(set(event_names)) != len(event_names):
            raise ValueError("allowed_event_names must not contain duplicates")
        object.__setattr__(self, "allowed_event_names", event_names)

        destinations = tuple(FeedbackLayer(item) for item in self.allowed_feeds_back_to)
        if not destinations:
            raise ValueError("allowed_feeds_back_to must not be empty")
        object.__setattr__(self, "allowed_feeds_back_to", destinations)

        normalized_map: dict[str, tuple[str, ...]] = {}
        for stakeholder_id, event_names_for_stakeholder in self.stakeholder_event_map.items():
            normalized_stakeholder_id = str(stakeholder_id).strip()
            if not normalized_stakeholder_id:
                raise ValueError("stakeholder_event_map keys must be non-empty")

            normalized_events = tuple(
                item.strip()
                for item in event_names_for_stakeholder
                if str(item).strip()
            )
            if not normalized_events:
                raise ValueError(
                    "stakeholder_event_map values must include at least one event name"
                )
            if len(set(normalized_events)) != len(normalized_events):
                raise ValueError(
                    "stakeholder_event_map values must not contain duplicate event names"
                )

            normalized_map[normalized_stakeholder_id] = normalized_events

        object.__setattr__(self, "stakeholder_event_map", normalized_map)

    def to_payload(self) -> dict[str, object]:
        return {
            "catalog_id": self.catalog_id,
            "enabled": self.enabled,
            "allowed_severities": [item.value for item in self.allowed_severities],
            "allowed_event_names": list(self.allowed_event_names),
            "allowed_feeds_back_to": [item.value for item in self.allowed_feeds_back_to],
            "stakeholder_event_map": {
                key: list(value)
                for key, value in self.stakeholder_event_map.items()
            },
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> CatalogAutoExpressPolicy:
        raw_map = payload.get("stakeholder_event_map", {})
        stakeholder_event_map: dict[str, tuple[str, ...]] = {}
        if isinstance(raw_map, dict):
            for key, value in raw_map.items():
                if isinstance(value, (list, tuple)):
                    stakeholder_event_map[str(key)] = tuple(str(item) for item in value)

        return cls(
            catalog_id=str(payload.get("catalog_id", "")),
            enabled=bool(payload.get("enabled", True)),
            allowed_severities=tuple(
                ServiceOpsSeverity(str(item))
                for item in payload.get("allowed_severities", [])
                if str(item).strip()
            ),
            allowed_event_names=tuple(
                str(item)
                for item in payload.get("allowed_event_names", [])
                if str(item).strip()
            ),
            allowed_feeds_back_to=tuple(
                FeedbackLayer(str(item))
                for item in payload.get("allowed_feeds_back_to", [])
                if str(item).strip()
            ),
            stakeholder_event_map=stakeholder_event_map,
            updated_at=str(payload.get("updated_at", _now_iso())),
        )


@dataclass(frozen=True)
class AutoExpressPolicyDecision:
    """Decision output of catalog auto-express policy evaluation."""

    requested: bool
    allowed: bool
    reason_codes: tuple[str, ...]
    policy_found: bool
    catalog_id: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "allowed": self.allowed,
            "reason_codes": list(self.reason_codes),
            "policy_found": self.policy_found,
            "catalog_id": self.catalog_id,
        }


def evaluate_catalog_auto_express_policy(
    policy: CatalogAutoExpressPolicy | None,
    *,
    requested: bool,
    event_name: str,
    severity: ServiceOpsSeverity,
    feeds_back_to: FeedbackLayer,
    stakeholder_id: str | None,
) -> AutoExpressPolicyDecision:
    """Evaluate whether auto-expression is allowed by a catalog policy."""

    if not requested:
        return AutoExpressPolicyDecision(
            requested=False,
            allowed=False,
            reason_codes=(),
            policy_found=policy is not None,
            catalog_id=policy.catalog_id if policy is not None else None,
        )

    reasons: list[str] = []
    if feeds_back_to != FeedbackLayer.NEEDS:
        reasons.append("feeds_back_to_not_needs")

    if policy is None:
        reasons.append("policy_not_found")
        return AutoExpressPolicyDecision(
            requested=True,
            allowed=False,
            reason_codes=_dedupe(reasons),
            policy_found=False,
            catalog_id=None,
        )

    if not policy.enabled:
        reasons.append("policy_disabled")
    if severity not in policy.allowed_severities:
        reasons.append("severity_not_allowed")
    if (
        policy.allowed_event_names
        and event_name not in policy.allowed_event_names
    ):
        reasons.append("event_name_not_allowed")
    if feeds_back_to not in policy.allowed_feeds_back_to:
        reasons.append("feeds_back_to_not_allowed")

    if policy.stakeholder_event_map:
        normalized_stakeholder = (
            str(stakeholder_id).strip()
            if stakeholder_id is not None
            else ""
        )
        if not normalized_stakeholder:
            reasons.append("stakeholder_required")
        else:
            mapped_events = policy.stakeholder_event_map.get(normalized_stakeholder)
            if mapped_events is None:
                reasons.append("stakeholder_unmapped")
            elif "*" not in mapped_events and event_name not in mapped_events:
                reasons.append("stakeholder_event_not_allowed")

    deduped_reasons = _dedupe(reasons)
    return AutoExpressPolicyDecision(
        requested=True,
        allowed=len(deduped_reasons) == 0,
        reason_codes=deduped_reasons,
        policy_found=True,
        catalog_id=policy.catalog_id,
    )


class InMemoryCatalogAutoExpressPolicyStore:
    """In-memory policy store used by tests and local workflows."""

    __slots__ = ("_policies",)

    def __init__(self) -> None:
        self._policies: dict[str, CatalogAutoExpressPolicy] = {}

    def save_policy(self, policy: CatalogAutoExpressPolicy) -> str:
        self._policies[policy.catalog_id] = policy
        return policy.catalog_id

    def get_policy(self, catalog_id: str) -> CatalogAutoExpressPolicy | None:
        return self._policies.get(catalog_id)

    def list_policies(self) -> list[CatalogAutoExpressPolicy]:
        return [self._policies[key] for key in sorted(self._policies.keys())]


class SQLiteCatalogAutoExpressPolicyStore:
    """SQLite policy table keyed by catalog id."""

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

                CREATE TABLE IF NOT EXISTS catalog_auto_express_policies (
                    catalog_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    allowed_severities_json TEXT NOT NULL DEFAULT '[]',
                    allowed_event_names_json TEXT NOT NULL DEFAULT '[]',
                    allowed_feeds_back_to_json TEXT NOT NULL DEFAULT '[]',
                    stakeholder_event_map_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_catalog_auto_express_updated
                    ON catalog_auto_express_policies(updated_at);
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

    def save_policy(self, policy: CatalogAutoExpressPolicy) -> str:
        payload = policy.to_payload()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO catalog_auto_express_policies (
                    catalog_id,
                    enabled,
                    allowed_severities_json,
                    allowed_event_names_json,
                    allowed_feeds_back_to_json,
                    stakeholder_event_map_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(catalog_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    allowed_severities_json = excluded.allowed_severities_json,
                    allowed_event_names_json = excluded.allowed_event_names_json,
                    allowed_feeds_back_to_json = excluded.allowed_feeds_back_to_json,
                    stakeholder_event_map_json = excluded.stakeholder_event_map_json,
                    updated_at = excluded.updated_at
                """,
                (
                    policy.catalog_id,
                    1 if policy.enabled else 0,
                    json.dumps(payload["allowed_severities"], ensure_ascii=False),
                    json.dumps(payload["allowed_event_names"], ensure_ascii=False),
                    json.dumps(payload["allowed_feeds_back_to"], ensure_ascii=False),
                    json.dumps(payload["stakeholder_event_map"], ensure_ascii=False),
                    str(payload["updated_at"]),
                ),
            )
            conn.commit()
        return policy.catalog_id

    def get_policy(self, catalog_id: str) -> CatalogAutoExpressPolicy | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT
                    catalog_id,
                    enabled,
                    allowed_severities_json,
                    allowed_event_names_json,
                    allowed_feeds_back_to_json,
                    stakeholder_event_map_json,
                    updated_at
                FROM catalog_auto_express_policies
                WHERE catalog_id = ?
                """,
                (catalog_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_policy(row)

    def list_policies(self) -> list[CatalogAutoExpressPolicy]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    catalog_id,
                    enabled,
                    allowed_severities_json,
                    allowed_event_names_json,
                    allowed_feeds_back_to_json,
                    stakeholder_event_map_json,
                    updated_at
                FROM catalog_auto_express_policies
                ORDER BY catalog_id ASC
                """
            ).fetchall()
        return [self._row_to_policy(row) for row in rows]

    @staticmethod
    def _row_to_policy(row: sqlite3.Row) -> CatalogAutoExpressPolicy:
        payload = {
            "catalog_id": str(row["catalog_id"]),
            "enabled": bool(int(row["enabled"])),
            "allowed_severities": json.loads(str(row["allowed_severities_json"])),
            "allowed_event_names": json.loads(str(row["allowed_event_names_json"])),
            "allowed_feeds_back_to": json.loads(str(row["allowed_feeds_back_to_json"])),
            "stakeholder_event_map": json.loads(str(row["stakeholder_event_map_json"])),
            "updated_at": str(row["updated_at"]),
        }
        return CatalogAutoExpressPolicy.from_payload(payload)
