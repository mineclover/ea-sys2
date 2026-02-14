"""Tests for profile_backup — TOML backup/version/restore system."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from ea_kernel.profile_backup import MANAGED_FILES, BackupStore
from ea_kernel.profile_types import BackupError, BackupFileEntry, BackupSnapshot

# ── Fixtures ──────────────────────────────────────────────────────

SRC_DIR = Path(__file__).parent.parent / "src" / "ea_kernel"


@pytest.fixture()
def toml_dir(tmp_path: Path) -> Path:
    """Copy all 7 managed TOML files to a temporary directory."""
    for _, rel_path in MANAGED_FILES:
        src = SRC_DIR / rel_path
        dst = tmp_path / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return tmp_path


@pytest.fixture()
def store() -> BackupStore:
    """In-memory BackupStore, initialized."""
    s = BackupStore(":memory:")
    s.initialize()
    yield s
    s.close()


# ── TestBackupStoreLifecycle ──────────────────────────────────────

class TestBackupStoreLifecycle:
    def test_initialize_and_close(self) -> None:
        s = BackupStore(":memory:")
        s.initialize()
        assert s._initialized is True
        s.close()
        assert s._initialized is False

    def test_context_manager(self) -> None:
        with BackupStore(":memory:") as s:
            assert s._initialized is True
        assert s._initialized is False

    def test_require_init_raises(self) -> None:
        s = BackupStore(":memory:")
        with pytest.raises(BackupError, match="not initialized"):
            s.get_latest()


# ── TestBackup ────────────────────────────────────────────────────

class TestBackup:
    def test_backup_captures_7_files(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(
            version="v1", author="test", description="initial",
            base_dir=toml_dir,
        )
        assert isinstance(snap, BackupSnapshot)
        assert snap.version == "v1"
        assert snap.author == "test"
        assert snap.description == "initial"
        assert snap.parent_id is None
        assert len(snap.files) == 7
        assert len(snap.id) == 32  # uuid4 hex
        assert len(snap.content_hash) == 64  # sha256

    def test_backup_file_entries(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        keys = {e.file_key for e in snap.files}
        expected = {k for k, _ in MANAGED_FILES}
        assert keys == expected
        for entry in snap.files:
            assert isinstance(entry, BackupFileEntry)
            assert entry.size_bytes > 0
            assert len(entry.content_hash) == 64
            assert len(entry.content) > 0

    def test_backup_duplicate_raises(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        store.backup(version="v1", base_dir=toml_dir)
        with pytest.raises(BackupError, match="No changes"):
            store.backup(version="v2", base_dir=toml_dir)

    def test_backup_auto_version(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(base_dir=toml_dir)
        # Auto version is an ISO timestamp
        assert "T" in snap.version

    def test_backup_auto_chaining(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap1 = store.backup(version="v1", base_dir=toml_dir)
        # Modify a file so hash changes
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        content = schema_path.read_text()
        schema_path.write_text(content + "\n# modified\n")
        snap2 = store.backup(version="v2", base_dir=toml_dir)
        assert snap2.parent_id == snap1.id

    def test_backup_missing_file_raises(
        self, store: BackupStore, tmp_path: Path,
    ) -> None:
        with pytest.raises(BackupError, match="not found"):
            store.backup(version="v1", base_dir=tmp_path)

    def test_backup_version_unique(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        store.backup(version="v1", base_dir=toml_dir)
        # Modify to avoid "No changes" error
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        content = schema_path.read_text()
        schema_path.write_text(content + "\n# v2\n")
        with pytest.raises(BackupError, match="already exists"):
            store.backup(version="v1", base_dir=toml_dir)


# ── TestRestore ───────────────────────────────────────────────────

class TestRestore:
    def test_restore_round_trip(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        # Mutate a file
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        original = schema_path.read_text()
        schema_path.write_text("# destroyed\n")
        # Restore
        changed = store.restore(snap.id, base_dir=toml_dir)
        assert "kernel_schema" in changed
        assert schema_path.read_text() == original

    def test_restore_dry_run(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        # Mutate
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        schema_path.write_text("# destroyed\n")
        # Dry run: files not restored
        changed = store.restore(snap.id, base_dir=toml_dir, dry_run=True)
        assert "kernel_schema" in changed
        assert schema_path.read_text() == "# destroyed\n"

    def test_restore_no_changes(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        changed = store.restore(snap.id, base_dir=toml_dir)
        assert changed == []

    def test_restore_not_found(self, store: BackupStore) -> None:
        with pytest.raises(BackupError, match="not found"):
            store.restore("nonexistent")

    def test_restore_creates_directories(
        self, store: BackupStore, toml_dir: Path, tmp_path: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        # Restore to a fresh directory
        target = tmp_path / "fresh"
        changed = store.restore(snap.id, base_dir=target)
        assert len(changed) == 7
        for _, rel_path in MANAGED_FILES:
            assert (target / rel_path).exists()


# ── TestQuery ─────────────────────────────────────────────────────

class TestQuery:
    def test_get(self, store: BackupStore, toml_dir: Path) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        fetched = store.get(snap.id)
        assert fetched is not None
        assert fetched.id == snap.id
        assert fetched.version == "v1"
        assert len(fetched.files) == 7

    def test_get_none(self, store: BackupStore) -> None:
        assert store.get("nonexistent") is None

    def test_get_latest(self, store: BackupStore, toml_dir: Path) -> None:
        store.backup(version="v1", base_dir=toml_dir)
        # Modify and create v2
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        schema_path.write_text(schema_path.read_text() + "\n# v2\n")
        store.backup(version="v2", base_dir=toml_dir)
        latest = store.get_latest()
        assert latest is not None
        assert latest.version == "v2"

    def test_get_latest_empty(self, store: BackupStore) -> None:
        assert store.get_latest() is None

    def test_get_by_version(self, store: BackupStore, toml_dir: Path) -> None:
        store.backup(version="v1", base_dir=toml_dir)
        found = store.get_by_version("v1")
        assert found is not None
        assert found.version == "v1"

    def test_get_by_version_none(self, store: BackupStore) -> None:
        assert store.get_by_version("nonexistent") is None

    def test_list_snapshots(self, store: BackupStore, toml_dir: Path) -> None:
        store.backup(version="v1", base_dir=toml_dir)
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        schema_path.write_text(schema_path.read_text() + "\n# v2\n")
        store.backup(version="v2", base_dir=toml_dir)
        asc = store.list_snapshots(ascending=True)
        assert len(asc) == 2
        assert asc[0].version == "v1"
        assert asc[1].version == "v2"
        desc = store.list_snapshots(ascending=False)
        assert desc[0].version == "v2"
        assert desc[1].version == "v1"

    def test_get_file(self, store: BackupStore, toml_dir: Path) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        entry = store.get_file(snap.id, "kernel_schema")
        assert entry is not None
        assert entry.file_key == "kernel_schema"
        assert entry.file_path == "specs/kernel_schema.toml"

    def test_get_file_none(self, store: BackupStore, toml_dir: Path) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        assert store.get_file(snap.id, "nonexistent") is None

    def test_download(self, store: BackupStore, toml_dir: Path) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        contents = store.download(snap.id)
        assert len(contents) == 7
        assert "kernel_schema" in contents
        assert "archimate" in contents
        assert len(contents["kernel_schema"]) > 0

    def test_download_not_found(self, store: BackupStore) -> None:
        with pytest.raises(BackupError, match="not found"):
            store.download("nonexistent")


# ── TestDiff ──────────────────────────────────────────────────────

class TestDiff:
    def test_diff_snapshots_identical(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap1 = store.backup(version="v1", base_dir=toml_dir)
        # Force a second snapshot by modifying and reverting
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        original = schema_path.read_text()
        schema_path.write_text(original + "\n# temp\n")
        snap2 = store.backup(version="v2", base_dir=toml_dir)
        schema_path.write_text(original)

        diff = store.diff_snapshots(snap1.id, snap2.id)
        # kernel_schema was modified between v1 and v2
        assert diff["kernel_schema"] == "modified"
        # Others should be unchanged
        assert diff["archimate"] == "unchanged"

    def test_diff_snapshots_not_found(self, store: BackupStore) -> None:
        with pytest.raises(BackupError, match="not found"):
            store.diff_snapshots("a", "b")

    def test_diff_with_disk_unchanged(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        diff = store.diff_with_disk(snap.id, base_dir=toml_dir)
        assert all(v == "unchanged" for v in diff.values())

    def test_diff_with_disk_modified(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        schema_path.write_text("# modified\n")
        diff = store.diff_with_disk(snap.id, base_dir=toml_dir)
        assert diff["kernel_schema"] == "modified"
        assert diff["archimate"] == "unchanged"

    def test_diff_with_disk_missing(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        (toml_dir / "specs" / "kernel_schema.toml").unlink()
        diff = store.diff_with_disk(snap.id, base_dir=toml_dir)
        assert diff["kernel_schema"] == "missing"

    def test_diff_with_disk_not_found(self, store: BackupStore) -> None:
        with pytest.raises(BackupError, match="not found"):
            store.diff_with_disk("nonexistent")


# ── TestDelete ────────────────────────────────────────────────────

class TestDelete:
    def test_delete_snapshot(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        assert store.delete(snap.id) is True
        assert store.get(snap.id) is None

    def test_delete_cascade_files(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        sid = snap.id
        assert store.delete(sid) is True
        # Files should also be gone (CASCADE)
        assert store.get_file(sid, "kernel_schema") is None

    def test_delete_clears_parent_ref(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap1 = store.backup(version="v1", base_dir=toml_dir)
        schema_path = toml_dir / "specs" / "kernel_schema.toml"
        schema_path.write_text(schema_path.read_text() + "\n# v2\n")
        snap2 = store.backup(version="v2", base_dir=toml_dir)
        assert snap2.parent_id == snap1.id
        # Delete parent
        store.delete(snap1.id)
        refreshed = store.get(snap2.id)
        assert refreshed is not None
        assert refreshed.parent_id is None

    def test_delete_nonexistent(self, store: BackupStore) -> None:
        assert store.delete("nonexistent") is False

    def test_list_empty_after_delete(
        self, store: BackupStore, toml_dir: Path,
    ) -> None:
        snap = store.backup(version="v1", base_dir=toml_dir)
        store.delete(snap.id)
        assert store.list_snapshots() == []
