"""Kernel governance DB migration runner.

K1 scope:
- Provide central migration planning/apply API.
- Keep current store-level schema bootstrap behavior intact.
- Normalize schema version tracking for versions.db.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MigrationStep:
    """Single migration step for one database target."""

    version: int
    description: str
    apply: Callable[[Path], None]


@dataclass(frozen=True)
class MigrationTarget:
    """Database target metadata."""

    name: str
    filename: str
    steps: tuple[MigrationStep, ...]


@dataclass(frozen=True)
class MigrationPlanItem:
    """Planned migration item returned to callers."""

    target: str
    db_path: Path
    from_version: int
    to_version: int
    description: str


def _bootstrap_rules(db_path: Path) -> None:
    from ea_kernel.rule_asset_store import SQLiteRuleAssetStore

    SQLiteRuleAssetStore(db_path)


def _bootstrap_decisions(db_path: Path) -> None:
    from ea_kernel.decision_store import SQLiteDecisionStore

    SQLiteDecisionStore(db_path)


def _bootstrap_versions(db_path: Path) -> None:
    from ea_kernel.corpus_version_store import SQLiteCorpusVersionStore

    SQLiteCorpusVersionStore(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
        conn.commit()


def _bootstrap_profiles(db_path: Path) -> None:
    from ea_kernel.profile_store import SQLiteProfileStore

    store = SQLiteProfileStore(db_path)
    store.initialize()
    store.close()


def _profiles_add_model_registry(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_info (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_registry (
                model_id           TEXT PRIMARY KEY,
                model_name         TEXT NOT NULL UNIQUE,
                owner              TEXT NOT NULL DEFAULT '',
                status             TEXT NOT NULL DEFAULT 'registered'
                    CHECK (status IN ('registered', 'active', 'disabled')),
                active_version_id  TEXT,
                created_at         TEXT NOT NULL,
                updated_at         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_versions (
                version_id         TEXT PRIMARY KEY,
                model_id           TEXT NOT NULL REFERENCES model_registry(model_id) ON DELETE CASCADE,
                version            TEXT NOT NULL,
                content_hash       TEXT NOT NULL,
                profile_data       TEXT NOT NULL,
                parent_version_id  TEXT REFERENCES model_versions(version_id),
                created_by         TEXT NOT NULL DEFAULT '',
                created_at         TEXT NOT NULL,
                UNIQUE(model_id, version)
            );

            CREATE TABLE IF NOT EXISTS validation_runs (
                run_id          TEXT PRIMARY KEY,
                model_id        TEXT NOT NULL REFERENCES model_registry(model_id) ON DELETE CASCADE,
                version_id      TEXT NOT NULL REFERENCES model_versions(version_id) ON DELETE CASCADE,
                validator       TEXT NOT NULL,
                passed          INTEGER NOT NULL CHECK (passed IN (0, 1)),
                errors_json     TEXT NOT NULL DEFAULT '[]',
                context_json    TEXT NOT NULL DEFAULT '{}',
                created_at      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mr_status
                ON model_registry(status);
            CREATE INDEX IF NOT EXISTS idx_mv_model
                ON model_versions(model_id);
            CREATE INDEX IF NOT EXISTS idx_mv_hash
                ON model_versions(content_hash);
            CREATE INDEX IF NOT EXISTS idx_vr_model_version_created
                ON validation_runs(model_id, version_id, created_at DESC);
            """
        )
        row = conn.execute(
            "SELECT value FROM schema_info WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_info (key, value) VALUES ('schema_version', '2')"
            )
        else:
            try:
                current = int(row[0])
            except ValueError:
                current = 0
            if current < 2:
                conn.execute(
                    "UPDATE schema_info SET value = '2' WHERE key = 'schema_version'"
                )
        conn.commit()


_TARGETS: tuple[MigrationTarget, ...] = (
    MigrationTarget(
        name="rules",
        filename="rules.db",
        steps=(
            MigrationStep(
                version=1,
                description="Bootstrap rule lifecycle schema",
                apply=_bootstrap_rules,
            ),
        ),
    ),
    MigrationTarget(
        name="decisions",
        filename="decisions.db",
        steps=(
            MigrationStep(
                version=1,
                description="Bootstrap decision recording schema",
                apply=_bootstrap_decisions,
            ),
        ),
    ),
    MigrationTarget(
        name="versions",
        filename="versions.db",
        steps=(
            MigrationStep(
                version=1,
                description="Bootstrap corpus version schema + schema_version table",
                apply=_bootstrap_versions,
            ),
        ),
    ),
    MigrationTarget(
        name="profiles",
        filename="profiles.db",
        steps=(
            MigrationStep(
                version=1,
                description="Bootstrap profile registration schema",
                apply=_bootstrap_profiles,
            ),
            MigrationStep(
                version=2,
                description="Add model registry/version/validation tables",
                apply=_profiles_add_model_registry,
            ),
        ),
    ),
)


def _read_current_version(db_path: Path) -> int:
    """Read schema version from either schema_version or schema_info."""
    if not db_path.exists():
        return 0

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        has_schema_version = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if has_schema_version is not None:
            row = conn.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
            if row is None or row["version"] is None:
                return 0
            return int(row["version"])

        has_schema_info = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_info'"
        ).fetchone()
        if has_schema_info is not None:
            row = conn.execute(
                "SELECT value FROM schema_info WHERE key = 'schema_version'"
            ).fetchone()
            if row is None or row["value"] is None:
                return 0
            try:
                return int(row["value"])
            except ValueError:
                return 0

    return 0


def _iter_pending_migrations(data_dir: Path) -> Iterable[tuple[MigrationPlanItem, Callable[[Path], None]]]:
    for target in _TARGETS:
        db_path = data_dir / target.filename
        current = _read_current_version(db_path)
        for step in target.steps:
            if step.version > current:
                item = MigrationPlanItem(
                    target=target.name,
                    db_path=db_path,
                    from_version=current,
                    to_version=step.version,
                    description=step.description,
                )
                yield item, step.apply
                current = step.version


def plan_kernel_governance_migrations(data_dir: str | Path) -> tuple[MigrationPlanItem, ...]:
    """Plan pending migrations for kernel governance DBs."""
    root = Path(data_dir)
    return tuple(item for item, _ in _iter_pending_migrations(root))


def apply_kernel_governance_migrations(
    data_dir: str | Path,
    *,
    dry_run: bool = False,
) -> tuple[MigrationPlanItem, ...]:
    """Apply pending migrations, or only plan if dry_run=True."""
    root = Path(data_dir)
    plan = tuple(_iter_pending_migrations(root))
    items = tuple(item for item, _ in plan)
    if dry_run:
        return items

    root.mkdir(parents=True, exist_ok=True)
    for item, apply_fn in plan:
        apply_fn(item.db_path)
    return items


def format_migration_plan(items: tuple[MigrationPlanItem, ...]) -> str:
    """Render migration plan to stable text format."""
    if not items:
        return "[ok] kernel governance db is already up-to-date"

    lines = ["[plan] kernel governance db migrations"]
    for item in items:
        lines.append(
            f"- {item.target}: v{item.from_version} -> v{item.to_version} ({item.db_path.name}) "
            f"{item.description}"
        )
    return "\n".join(lines)
