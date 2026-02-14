"""TOML backup/version/restore system for managed kernel files.

Manages snapshots of the 7 TOML source-of-truth files:
  - specs/kernel_schema.toml, specs/kernel_rules.toml
  - profiles/{archimate,togaf,zachman,sysml2,bpmn}.toml

Uses SQLite for snapshot storage. Follows the same conventions as
profile_store.py: WAL mode, foreign keys, UUID4 IDs, SHA256 hashes.

Only depends on profile_types.py. Loaders are lazy-imported in validate().
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ea_kernel.profile_types import BackupError, BackupFileEntry, BackupSnapshot

# ── Managed Files ─────────────────────────────────────────────────

MANAGED_FILES: tuple[tuple[str, str], ...] = (
    ("kernel_schema", "specs/kernel_schema.toml"),
    ("kernel_rules", "specs/kernel_rules.toml"),
    ("archimate", "profiles/archimate.toml"),
    ("togaf", "profiles/togaf.toml"),
    ("zachman", "profiles/zachman.toml"),
    ("sysml2", "profiles/sysml2.toml"),
    ("bpmn", "profiles/bpmn.toml"),
)

# ── SQL DDL ───────────────────────────────────────────────────────

_DDL = """\
CREATE TABLE IF NOT EXISTS backup_snapshots (
    id            TEXT PRIMARY KEY,
    version       TEXT NOT NULL UNIQUE,
    content_hash  TEXT NOT NULL,
    author        TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    parent_id     TEXT REFERENCES backup_snapshots(id),
    file_count    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_files (
    id            TEXT PRIMARY KEY,
    snapshot_id   TEXT NOT NULL REFERENCES backup_snapshots(id) ON DELETE CASCADE,
    file_key      TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    content       TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    UNIQUE(snapshot_id, file_key)
);

CREATE INDEX IF NOT EXISTS idx_bs_created ON backup_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_bf_snapshot ON backup_files(snapshot_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _composite_hash(file_hashes: list[str]) -> str:
    combined = "".join(sorted(file_hashes))
    return hashlib.sha256(combined.encode()).hexdigest()


def _row_to_snapshot(row: sqlite3.Row, files: tuple[BackupFileEntry, ...]) -> BackupSnapshot:
    return BackupSnapshot(
        id=row["id"],
        version=row["version"],
        created_at=row["created_at"],
        author=row["author"],
        description=row["description"],
        parent_id=row["parent_id"],
        content_hash=row["content_hash"],
        files=files,
    )


def _row_to_file_entry(row: sqlite3.Row) -> BackupFileEntry:
    return BackupFileEntry(
        file_key=row["file_key"],
        file_path=row["file_path"],
        content_hash=row["content_hash"],
        content=row["content"],
        size_bytes=row["size_bytes"],
    )


# ── BackupStore ───────────────────────────────────────────────────

class BackupStore:
    """SQLite-backed backup store for managed TOML files."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._initialized = False

    # ── Lifecycle ─────────────────────────────────────────────────

    def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_DDL)
        self._conn.commit()
        self._initialized = True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        self._initialized = False

    def __enter__(self) -> BackupStore:
        self.initialize()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _require_init(self) -> sqlite3.Connection:
        if not self._initialized or self._conn is None:
            raise BackupError("Store not initialized. Call initialize() first.")
        return self._conn

    # ── Core: backup ──────────────────────────────────────────────

    def backup(
        self,
        *,
        version: str | None = None,
        author: str = "",
        description: str = "",
        base_dir: Path | None = None,
    ) -> BackupSnapshot:
        """Create a snapshot of all 7 managed TOML files.

        Raises BackupError if no changes since the last snapshot,
        or if any managed file is missing.
        """
        conn = self._require_init()
        base = base_dir or Path(__file__).parent

        # Read all files and compute hashes
        entries: list[BackupFileEntry] = []
        file_hashes: list[str] = []
        for file_key, rel_path in MANAGED_FILES:
            full_path = base / rel_path
            if not full_path.exists():
                raise BackupError(f"Managed file not found: {rel_path}")
            content = full_path.read_text(encoding="utf-8")
            h = _sha256(content)
            entries.append(BackupFileEntry(
                file_key=file_key,
                file_path=rel_path,
                content_hash=h,
                content=content,
                size_bytes=len(content.encode("utf-8")),
            ))
            file_hashes.append(h)

        composite = _composite_hash(file_hashes)

        # Check for duplicate: same composite hash as latest
        latest = self.get_latest()
        if latest is not None and latest.content_hash == composite:
            raise BackupError("No changes since last snapshot")

        # Auto version
        if version is None:
            version = _now_iso()

        # Auto parent chaining
        parent_id = latest.id if latest is not None else None

        snap_id = uuid.uuid4().hex
        now = _now_iso()

        try:
            conn.execute(
                """INSERT INTO backup_snapshots
                   (id, version, content_hash, author, description,
                    created_at, parent_id, file_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (snap_id, version, composite, author, description,
                 now, parent_id, len(entries)),
            )
            for entry in entries:
                conn.execute(
                    """INSERT INTO backup_files
                       (id, snapshot_id, file_key, file_path,
                        content_hash, content, size_bytes)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (uuid.uuid4().hex, snap_id, entry.file_key,
                     entry.file_path, entry.content_hash,
                     entry.content, entry.size_bytes),
                )
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.rollback()
            raise BackupError(f"Snapshot version already exists: {version}") from e

        return BackupSnapshot(
            id=snap_id,
            version=version,
            created_at=now,
            author=author,
            description=description,
            parent_id=parent_id,
            content_hash=composite,
            files=tuple(entries),
        )

    # ── Core: restore ─────────────────────────────────────────────

    def restore(
        self,
        snapshot_id: str,
        *,
        base_dir: Path | None = None,
        dry_run: bool = False,
    ) -> list[str]:
        """Restore TOML files from a snapshot.

        dry_run=True returns the list of file_keys that would change.
        Actual restore uses atomic write (tmp + os.replace).
        """
        snap = self.get(snapshot_id)
        if snap is None:
            raise BackupError(f"Snapshot not found: {snapshot_id}")

        base = base_dir or Path(__file__).parent

        # Determine which files differ from disk
        changed: list[str] = []
        for entry in snap.files:
            full_path = base / entry.file_path
            if full_path.exists():
                disk_content = full_path.read_text(encoding="utf-8")
                if _sha256(disk_content) == entry.content_hash:
                    continue
            changed.append(entry.file_key)

        if dry_run:
            return changed

        # Atomic write: write all to .tmp first, then replace
        tmp_paths: list[tuple[Path, Path]] = []
        try:
            for entry in snap.files:
                full_path = base / entry.file_path
                tmp_path = full_path.with_suffix(full_path.suffix + ".tmp")
                full_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_text(entry.content, encoding="utf-8")
                tmp_paths.append((tmp_path, full_path))

            # All writes succeeded — atomic replace
            for tmp_path, final_path in tmp_paths:
                os.replace(tmp_path, final_path)
        except Exception:
            # Cleanup any leftover .tmp files
            for tmp_path, _ in tmp_paths:
                if tmp_path.exists():
                    tmp_path.unlink()
            raise

        # Post-restore validation
        self.validate(base_dir=base)

        return changed

    # ── Core: validate ────────────────────────────────────────────

    def validate(self, base_dir: Path | None = None) -> dict[str, bool]:
        """Validate current disk TOML files using their respective loaders."""
        base = base_dir or Path(__file__).parent
        results: dict[str, bool] = {}

        for file_key, rel_path in MANAGED_FILES:
            full_path = base / rel_path
            if not full_path.exists():
                results[file_key] = False
                continue
            try:
                if file_key == "kernel_schema":
                    from ea_kernel.schema_loader import load_kernel_schema
                    load_kernel_schema(full_path)
                elif file_key == "kernel_rules":
                    from ea_kernel.spec_loader import load_kernel_rules
                    load_kernel_rules(full_path)
                else:
                    # Profile files
                    from ea_kernel.profile_loader import load_profile_from_content
                    content = full_path.read_text(encoding="utf-8")
                    load_profile_from_content(content)
                results[file_key] = True
            except Exception:
                results[file_key] = False

        return results

    # ── Query ─────────────────────────────────────────────────────

    def get(self, snapshot_id: str) -> BackupSnapshot | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM backup_snapshots WHERE id = ?", (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        files = self._load_files(conn, snapshot_id)
        return _row_to_snapshot(row, files)

    def get_latest(self) -> BackupSnapshot | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM backup_snapshots ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        if row is None:
            return None
        files = self._load_files(conn, row["id"])
        return _row_to_snapshot(row, files)

    def get_by_version(self, version: str) -> BackupSnapshot | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM backup_snapshots WHERE version = ?", (version,),
        ).fetchone()
        if row is None:
            return None
        files = self._load_files(conn, row["id"])
        return _row_to_snapshot(row, files)

    def list_snapshots(self, *, ascending: bool = True) -> list[BackupSnapshot]:
        conn = self._require_init()
        order = "ASC" if ascending else "DESC"
        rows = conn.execute(
            f"SELECT * FROM backup_snapshots ORDER BY created_at {order}",
        ).fetchall()
        result: list[BackupSnapshot] = []
        for row in rows:
            files = self._load_files(conn, row["id"])
            result.append(_row_to_snapshot(row, files))
        return result

    def get_file(self, snapshot_id: str, file_key: str) -> BackupFileEntry | None:
        conn = self._require_init()
        row = conn.execute(
            "SELECT * FROM backup_files WHERE snapshot_id = ? AND file_key = ?",
            (snapshot_id, file_key),
        ).fetchone()
        return _row_to_file_entry(row) if row else None

    def download(self, snapshot_id: str) -> dict[str, str]:
        """Return all TOML contents as {file_key: content}."""
        snap = self.get(snapshot_id)
        if snap is None:
            raise BackupError(f"Snapshot not found: {snapshot_id}")
        return {entry.file_key: entry.content for entry in snap.files}

    # ── Diff ──────────────────────────────────────────────────────

    def diff_snapshots(self, id_a: str, id_b: str) -> dict[str, str]:
        """Compare two snapshots. Returns {file_key: "unchanged"|"modified"}."""
        snap_a = self.get(id_a)
        snap_b = self.get(id_b)
        if snap_a is None:
            raise BackupError(f"Snapshot not found: {id_a}")
        if snap_b is None:
            raise BackupError(f"Snapshot not found: {id_b}")

        hashes_a = {e.file_key: e.content_hash for e in snap_a.files}
        hashes_b = {e.file_key: e.content_hash for e in snap_b.files}

        result: dict[str, str] = {}
        all_keys = sorted(set(hashes_a) | set(hashes_b))
        for key in all_keys:
            if hashes_a.get(key) == hashes_b.get(key):
                result[key] = "unchanged"
            else:
                result[key] = "modified"
        return result

    def diff_with_disk(
        self,
        snapshot_id: str,
        *,
        base_dir: Path | None = None,
    ) -> dict[str, str]:
        """Compare a snapshot against current disk files."""
        snap = self.get(snapshot_id)
        if snap is None:
            raise BackupError(f"Snapshot not found: {snapshot_id}")

        base = base_dir or Path(__file__).parent
        result: dict[str, str] = {}
        for entry in snap.files:
            full_path = base / entry.file_path
            if not full_path.exists():
                result[entry.file_key] = "missing"
                continue
            disk_content = full_path.read_text(encoding="utf-8")
            disk_hash = _sha256(disk_content)
            if disk_hash == entry.content_hash:
                result[entry.file_key] = "unchanged"
            else:
                result[entry.file_key] = "modified"
        return result

    # ── Delete ────────────────────────────────────────────────────

    def delete(self, snapshot_id: str) -> bool:
        conn = self._require_init()
        # Clear parent_id references
        conn.execute(
            "UPDATE backup_snapshots SET parent_id = NULL WHERE parent_id = ?",
            (snapshot_id,),
        )
        cursor = conn.execute(
            "DELETE FROM backup_snapshots WHERE id = ?", (snapshot_id,),
        )
        conn.commit()
        return cursor.rowcount > 0

    # ── Internal ──────────────────────────────────────────────────

    def _load_files(
        self, conn: sqlite3.Connection, snapshot_id: str,
    ) -> tuple[BackupFileEntry, ...]:
        rows = conn.execute(
            "SELECT * FROM backup_files WHERE snapshot_id = ? ORDER BY file_key",
            (snapshot_id,),
        ).fetchall()
        return tuple(_row_to_file_entry(r) for r in rows)
