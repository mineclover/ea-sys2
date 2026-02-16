"""StoragePort ABC + InMemoryProfileStore + SQLiteProfileStore for profile persistence.

Follows the RuleVersionStore conventions: WAL mode, foreign keys,
UUID4 IDs, SHA256 content hashes, ISO 8601 timestamps.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from ea_profile.serializer import compute_content_hash, dict_to_profile, profile_to_dict
from ea_profile.types import (
    AuditResult,
    KernelProfile,
    ProfileOrigin,
    ProfileStoreError,
    ProfileTag,
    ProfileVersion,
)

# Type alias for the optional pre-store audit hook.
# Receives a profile, returns an AuditResult. If not passed, the store skips audit.
StoreAuditHook = Callable[[KernelProfile], AuditResult]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class StoragePort(ABC):
    """Abstract storage port for profile persistence."""

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def store(self, profile: KernelProfile, *,
              author: str = "", description: str = "",
              parent_id: str | None = None,
              origin: ProfileOrigin | None = None) -> ProfileVersion: ...

    @abstractmethod
    def get(self, version_id: str) -> ProfileVersion | None: ...

    @abstractmethod
    def get_latest(self, profile_name: str) -> ProfileVersion | None: ...

    @abstractmethod
    def list_versions(self, profile_name: str, *,
                      ascending: bool = True) -> list[ProfileVersion]: ...

    @abstractmethod
    def list_profiles(self) -> list[str]: ...

    @abstractmethod
    def tag(self, version_id: str, tag_name: str) -> ProfileTag: ...

    @abstractmethod
    def get_by_version(self, profile_name: str,
                       version: str) -> ProfileVersion | None: ...

    @abstractmethod
    def get_by_tag(self, profile_name: str,
                   tag_name: str) -> ProfileVersion | None: ...

    @abstractmethod
    def list_tags(self, version_id: str | None = None,
                  profile_name: str | None = None) -> list[ProfileTag]: ...

    @abstractmethod
    def delete(self, version_id: str) -> bool: ...


class InMemoryProfileStore(StoragePort):
    """Dict-based in-memory profile store for testing."""

    __slots__ = ("_versions", "_by_name", "_tags", "_audit_hook")

    def __init__(self, audit_hook: StoreAuditHook | None = None) -> None:
        self._versions: dict[str, ProfileVersion] = {}
        self._by_name: dict[str, list[str]] = {}  # profile_name → [version_id, ...]
        self._tags: dict[tuple[str, str], ProfileTag] = {}  # (profile_name, tag_name) → tag
        self._audit_hook = audit_hook

    # ── Lifecycle ─────────────────────────────────────────────────

    def initialize(self) -> None:
        pass

    def close(self) -> None:
        pass

    # ── Store ─────────────────────────────────────────────────────

    def store(self, profile: KernelProfile, *,
              author: str = "", description: str = "",
              parent_id: str | None = None,
              origin: ProfileOrigin | None = None) -> ProfileVersion:
        if self._audit_hook is not None:
            result = self._audit_hook(profile)
            if not result.passed:
                errors = [f.message for f in result.findings if f.severity.value == "error"]
                raise ProfileStoreError(
                    f"Audit failed for '{profile.name}': {'; '.join(errors[:3])}"
                )

        data = profile_to_dict(profile)
        ch = compute_content_hash(profile)
        vid = uuid.uuid4().hex
        now = _now_iso()
        origin_str = origin.value if origin is not None else ""

        # Duplicate check
        for existing in self._by_name.get(profile.name, []):
            if self._versions[existing].version == profile.version:
                raise ProfileStoreError(
                    f"Profile '{profile.name}' version '{profile.version}' already exists"
                )

        # Auto parent: latest version for this profile if not specified
        if parent_id is None:
            name_ids = self._by_name.get(profile.name, [])
            if name_ids:
                parent_id = name_ids[-1]

        pv = ProfileVersion(
            id=vid, profile_name=profile.name, version=profile.version,
            content_hash=ch, data=data, created_at=now,
            parent_id=parent_id, author=author, description=description,
            origin=origin_str,
        )
        self._versions[vid] = pv
        self._by_name.setdefault(profile.name, []).append(vid)
        return pv

    # ── Retrieve ──────────────────────────────────────────────────

    def get(self, version_id: str) -> ProfileVersion | None:
        return self._versions.get(version_id)

    def get_latest(self, profile_name: str) -> ProfileVersion | None:
        ids = self._by_name.get(profile_name, [])
        if not ids:
            return None
        # Return the one with the latest created_at
        return max(
            (self._versions[vid] for vid in ids),
            key=lambda v: v.created_at,
        )

    def list_versions(self, profile_name: str, *,
                      ascending: bool = True) -> list[ProfileVersion]:
        ids = self._by_name.get(profile_name, [])
        versions = [self._versions[vid] for vid in ids]
        return sorted(versions, key=lambda v: v.created_at, reverse=not ascending)

    def list_profiles(self) -> list[str]:
        return sorted(self._by_name.keys())

    def get_by_version(self, profile_name: str,
                       version: str) -> ProfileVersion | None:
        for vid in self._by_name.get(profile_name, []):
            pv = self._versions[vid]
            if pv.version == version:
                return pv
        return None

    # ── Tags ──────────────────────────────────────────────────────

    def tag(self, version_id: str, tag_name: str) -> ProfileTag:
        pv = self.get(version_id)
        if pv is None:
            raise ProfileStoreError(f"Version not found: {version_id}")
        now = _now_iso()
        tag_obj = ProfileTag(
            name=tag_name, profile_name=pv.profile_name,
            version_id=version_id, created_at=now,
        )
        self._tags[(pv.profile_name, tag_name)] = tag_obj
        return tag_obj

    def get_by_tag(self, profile_name: str,
                   tag_name: str) -> ProfileVersion | None:
        tag_obj = self._tags.get((profile_name, tag_name))
        if tag_obj is None:
            return None
        return self._versions.get(tag_obj.version_id)

    def list_tags(self, version_id: str | None = None,
                  profile_name: str | None = None) -> list[ProfileTag]:
        if version_id is not None:
            tags = [t for t in self._tags.values() if t.version_id == version_id]
        elif profile_name is not None:
            tags = [t for t in self._tags.values() if t.profile_name == profile_name]
        else:
            tags = list(self._tags.values())
        return sorted(tags, key=lambda t: (t.profile_name, t.name))

    # ── Delete ────────────────────────────────────────────────────

    def delete(self, version_id: str) -> bool:
        pv = self._versions.pop(version_id, None)
        if pv is None:
            return False
        # Remove from name index
        name_ids = self._by_name.get(pv.profile_name, [])
        if version_id in name_ids:
            name_ids.remove(version_id)
        if not name_ids:
            self._by_name.pop(pv.profile_name, None)
        # Clear parent_id references
        for v in self._versions.values():
            if v.parent_id == version_id:
                # ProfileVersion is frozen, need to create a new one
                updated = ProfileVersion(
                    id=v.id, profile_name=v.profile_name, version=v.version,
                    content_hash=v.content_hash, data=v.data, created_at=v.created_at,
                    parent_id=None, author=v.author, description=v.description,
                    origin=v.origin,
                )
                self._versions[v.id] = updated
        # Remove associated tags
        tag_keys_to_remove = [
            key for key, t in self._tags.items() if t.version_id == version_id
        ]
        for key in tag_keys_to_remove:
            del self._tags[key]
        return True


_SCHEMA_VERSION = "1"

_DDL = """\
CREATE TABLE IF NOT EXISTS schema_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile_versions (
    id               TEXT PRIMARY KEY,
    profile_name     TEXT NOT NULL,
    version          TEXT NOT NULL,
    content_hash     TEXT NOT NULL,
    profile_data     TEXT NOT NULL,
    element_count    INTEGER NOT NULL,
    relation_count   INTEGER NOT NULL,
    rule_count       INTEGER NOT NULL,
    author           TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    origin           TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    parent_id        TEXT REFERENCES profile_versions(id),
    UNIQUE(profile_name, version)
);

CREATE TABLE IF NOT EXISTS profile_tags (
    name          TEXT NOT NULL,
    profile_name  TEXT NOT NULL,
    version_id    TEXT NOT NULL REFERENCES profile_versions(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (profile_name, name)
);

CREATE INDEX IF NOT EXISTS idx_pv_name ON profile_versions(profile_name);
CREATE INDEX IF NOT EXISTS idx_pv_hash ON profile_versions(content_hash);
CREATE INDEX IF NOT EXISTS idx_pt_version ON profile_tags(version_id);
"""


def _row_to_version(row: sqlite3.Row) -> ProfileVersion:
    return ProfileVersion(
        id=row["id"],
        profile_name=row["profile_name"],
        version=row["version"],
        content_hash=row["content_hash"],
        data=json.loads(row["profile_data"]),
        created_at=row["created_at"],
        parent_id=row["parent_id"],
        author=row["author"],
        description=row["description"],
        origin=row["origin"],
    )


def _row_to_tag(row: sqlite3.Row) -> ProfileTag:
    return ProfileTag(
        name=row["name"],
        profile_name=row["profile_name"],
        version_id=row["version_id"],
        created_at=row["created_at"],
    )


class SQLiteProfileStore(StoragePort):
    """SQLite-backed profile store."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        audit_hook: StoreAuditHook | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._initialized = False
        self._audit_hook = audit_hook

    # ── Lifecycle ─────────────────────────────────────────────────

    def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_DDL)
        self._conn.execute(
            "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
            ("schema_version", _SCHEMA_VERSION),
        )
        self._conn.commit()
        self._initialized = True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._initialized = False

    def __enter__(self) -> SQLiteProfileStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _require_init(self) -> sqlite3.Connection:
        if not self._initialized or self._conn is None:
            raise ProfileStoreError("Store not initialized. Call initialize() first.")
        return self._conn

    # ── Store ─────────────────────────────────────────────────────

    def store(self, profile: KernelProfile, *,
              author: str = "", description: str = "",
              parent_id: str | None = None,
              origin: ProfileOrigin | None = None) -> ProfileVersion:
        conn = self._require_init()

        # Run optional audit hook before persisting
        if self._audit_hook is not None:
            result = self._audit_hook(profile)
            if not result.passed:
                errors = [f.message for f in result.findings if f.severity.value == "error"]
                raise ProfileStoreError(
                    f"Audit failed for '{profile.name}': {'; '.join(errors[:3])}"
                )

        data = profile_to_dict(profile)
        ch = compute_content_hash(profile)
        vid = uuid.uuid4().hex
        now = _now_iso()
        origin_str = origin.value if origin is not None else ""

        # Auto parent: latest version for this profile if not specified
        if parent_id is None:
            row = conn.execute(
                "SELECT id FROM profile_versions WHERE profile_name = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (profile.name,),
            ).fetchone()
            if row is not None:
                parent_id = row["id"]

        try:
            conn.execute(
                """INSERT INTO profile_versions
                   (id, profile_name, version, content_hash, profile_data,
                    element_count, relation_count, rule_count,
                    author, description, origin, created_at, parent_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (vid, profile.name, profile.version, ch,
                 json.dumps(data, sort_keys=True, ensure_ascii=False),
                 len(profile.elements), len(profile.relations),
                 len(profile.validity_rules),
                 author, description, origin_str, now, parent_id),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise ProfileStoreError(
                f"Profile '{profile.name}' version '{profile.version}' already exists"
            ) from e

        return ProfileVersion(
            id=vid, profile_name=profile.name, version=profile.version,
            content_hash=ch, data=data, created_at=now,
            parent_id=parent_id, author=author, description=description,
            origin=origin_str,
        )

    # ── Retrieve ──────────────────────────────────────────────────

    def get(self, version_id: str) -> ProfileVersion | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM profile_versions WHERE id = ?", (version_id,)
        ).fetchone()
        return _row_to_version(row) if row else None

    def get_latest(self, profile_name: str) -> ProfileVersion | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM profile_versions WHERE profile_name = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (profile_name,),
        ).fetchone()
        return _row_to_version(row) if row else None

    def list_versions(self, profile_name: str, *,
                      ascending: bool = True) -> list[ProfileVersion]:
        conn = self._require_init()
        order = "ASC" if ascending else "DESC"
        rows = conn.execute(
            f"SELECT * FROM profile_versions WHERE profile_name = ? "
            f"ORDER BY created_at {order}",
            (profile_name,),
        ).fetchall()
        return [_row_to_version(r) for r in rows]

    def list_profiles(self) -> list[str]:
        conn = self._require_init()
        rows = conn.execute(
            "SELECT DISTINCT profile_name FROM profile_versions ORDER BY profile_name"
        ).fetchall()
        return [r["profile_name"] for r in rows]

    def get_by_version(self, profile_name: str,
                       version: str) -> ProfileVersion | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM profile_versions WHERE profile_name = ? AND version = ?",
            (profile_name, version),
        ).fetchone()
        return _row_to_version(row) if row else None

    # ── Tags ──────────────────────────────────────────────────────

    def tag(self, version_id: str, tag_name: str) -> ProfileTag:
        conn = self._require_init()
        pv = self.get(version_id)
        if pv is None:
            raise ProfileStoreError(f"Version not found: {version_id}")

        now = _now_iso()
        conn.execute(
            """INSERT INTO profile_tags (name, profile_name, version_id, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(profile_name, name)
               DO UPDATE SET version_id = ?, created_at = ?""",
            (tag_name, pv.profile_name, version_id, now, version_id, now),
        )
        conn.commit()
        return ProfileTag(
            name=tag_name, profile_name=pv.profile_name,
            version_id=version_id, created_at=now,
        )

    def get_by_tag(self, profile_name: str,
                   tag_name: str) -> ProfileVersion | None:
        conn = self._require_init()
        row = conn.execute(
            """SELECT pv.* FROM profile_versions pv
               JOIN profile_tags pt ON pv.id = pt.version_id
               WHERE pt.profile_name = ? AND pt.name = ?""",
            (profile_name, tag_name),
        ).fetchone()
        return _row_to_version(row) if row else None

    def list_tags(self, version_id: str | None = None,
                  profile_name: str | None = None) -> list[ProfileTag]:
        conn = self._require_init()
        if version_id is not None:
            rows = conn.execute(
                "SELECT * FROM profile_tags WHERE version_id = ? ORDER BY name",
                (version_id,),
            ).fetchall()
        elif profile_name is not None:
            rows = conn.execute(
                "SELECT * FROM profile_tags WHERE profile_name = ? ORDER BY name",
                (profile_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM profile_tags ORDER BY profile_name, name"
            ).fetchall()
        return [_row_to_tag(r) for r in rows]

    def get_by_content_hash(self, content_hash: str) -> list[ProfileVersion]:
        """Find all versions with the given content hash."""
        conn = self._require_init()
        rows = conn.execute(
            "SELECT * FROM profile_versions WHERE content_hash = ? ORDER BY created_at",
            (content_hash,),
        ).fetchall()
        return [_row_to_version(r) for r in rows]

    # ── Delete ────────────────────────────────────────────────────

    def delete(self, version_id: str) -> bool:
        conn = self._require_init()
        # Clear parent_id references
        conn.execute(
            "UPDATE profile_versions SET parent_id = NULL WHERE parent_id = ?",
            (version_id,),
        )
        cursor = conn.execute(
            "DELETE FROM profile_versions WHERE id = ?", (version_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    # ── Utility ───────────────────────────────────────────────────

    def load_profile(self, version_id: str) -> KernelProfile | None:
        """Convenience: get a version and deserialize to KernelProfile."""
        pv = self.get(version_id)
        if pv is None:
            return None
        return dict_to_profile(pv.data)
