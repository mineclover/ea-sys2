"""I18n Translation Store — 번역 저장소 + 감사.

Persistent storage for kernel schema translations with versioning and audit.
Provides:
- TranslationEntry / I18nAuditEntry / I18nAuditReport: 데이터 타입
- I18nStore ABC: 번역 저장소 인터페이스
- InMemoryI18nStore: 테스트용 인메모리 구현
- SQLiteI18nStore: SQLite 기반 영속 저장소

References:
- rule_asset_store.py: 동일 패턴의 저장소 설계
- schema_loader.py: TOML 패치 로딩 / audit_i18n_patch()
"""

from __future__ import annotations

import sqlite3
import tomllib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ea_kernel.types import KernelSchema

# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TranslationEntry:
    """번역 단위 레코드."""

    target_kind: str    # "entity" | "relation"
    target_name: str    # "element", "membership", ...
    lang: str           # "ko", "ja", ...
    field: str          # "display_name" | "description"
    value: str          # "요소" (번역문)
    en_source: str      # 번역 시점의 영문 원본
    version: int        # 자동 증가
    created_by: str     # "toml_import" | "manual" | ...
    created_at: str     # ISO 8601
    updated_at: str


@dataclass(frozen=True)
class I18nAuditEntry:
    """감사 소견 단일 항목."""

    kind: str           # "entity" | "relation"
    name: str
    issue: str          # "missing" | "orphan" | "stale"
    field: str | None   # stale: "description" / "display_name"
    en_current: str     # 현재 스키마 영문
    en_recorded: str    # 저장된 en_source (missing이면 "")


@dataclass(frozen=True)
class I18nAuditReport:
    """감사 보고서."""

    lang: str
    missing: tuple[I18nAuditEntry, ...]
    orphan: tuple[I18nAuditEntry, ...]
    stale: tuple[I18nAuditEntry, ...]
    total_schema_items: int
    total_translated: int

    @property
    def coverage(self) -> float:
        if self.total_schema_items == 0:
            return 1.0
        return self.total_translated / self.total_schema_items

    @property
    def total_issues(self) -> int:
        return len(self.missing) + len(self.orphan) + len(self.stale)

    @property
    def is_clean(self) -> bool:
        return self.total_issues == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Helper: schema item extraction
# ═══════════════════════════════════════════════════════════════════════════════


def _schema_items(schema: KernelSchema) -> dict[tuple[str, str], dict[str, str]]:
    """Extract (kind, name) → {field: en_value} from schema.

    Always includes both ``display_name`` and ``description`` for every
    entity/relation so that 29 schema items × 2 fields = 58 translation slots.
    """
    items: dict[tuple[str, str], dict[str, str]] = {}
    for e in schema.entities:
        en_desc = e.description if isinstance(e.description, str) else e.description.get("en", "")
        en_dn = e.display_name if isinstance(e.display_name, str) else (e.display_name.get("en", "") if isinstance(e.display_name, dict) else "")
        items[("entity", e.name)] = {
            "description": en_desc,
            "display_name": en_dn,
        }
    for r in schema.relations:
        en_desc = r.description if isinstance(r.description, str) else r.description.get("en", "")
        en_dn = r.display_name if isinstance(r.display_name, str) else (r.display_name.get("en", "") if isinstance(r.display_name, dict) else "")
        items[("relation", r.name)] = {
            "description": en_desc,
            "display_name": en_dn,
        }
    return items


# ═══════════════════════════════════════════════════════════════════════════════
# I18nStore ABC
# ═══════════════════════════════════════════════════════════════════════════════


class I18nStore(ABC):
    """번역 저장소 인터페이스."""

    @abstractmethod
    def upsert(self, entry: TranslationEntry) -> TranslationEntry:
        """생성 또는 갱신 — version 자동 증가."""

    @abstractmethod
    def get(self, kind: str, name: str, lang: str, field: str) -> TranslationEntry | None:
        """단일 번역 조회 (최신 버전)."""

    @abstractmethod
    def list_translations(self, lang: str, kind: str | None = None) -> tuple[TranslationEntry, ...]:
        """언어별 번역 목록."""

    @abstractmethod
    def history(self, kind: str, name: str, lang: str, field: str) -> tuple[TranslationEntry, ...]:
        """번역 이력 (모든 버전, 최신 먼저)."""

    @abstractmethod
    def delete(self, kind: str, name: str, lang: str, field: str) -> bool:
        """번역 삭제."""

    @abstractmethod
    def import_from_toml(self, toml_path: Path, lang: str, created_by: str = "toml_import") -> int:
        """TOML 패치 파일에서 bulk import. 반환: import된 항목 수."""

    @abstractmethod
    def audit(self, schema: KernelSchema, lang: str) -> I18nAuditReport:
        """스키마 대비 번역 감사."""


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryI18nStore
# ═══════════════════════════════════════════════════════════════════════════════


class InMemoryI18nStore(I18nStore):
    """테스트용 인메모리 구현."""

    __slots__ = ("_current", "_history")

    def __init__(self) -> None:
        # key: (kind, name, lang, field)
        self._current: dict[tuple[str, str, str, str], TranslationEntry] = {}
        self._history: dict[tuple[str, str, str, str], list[TranslationEntry]] = {}

    def upsert(self, entry: TranslationEntry) -> TranslationEntry:
        key = (entry.target_kind, entry.target_name, entry.lang, entry.field)
        now = datetime.now(UTC).isoformat() + "Z"

        existing = self._current.get(key)
        if existing is not None:
            new_version = existing.version + 1
            # Archive old version
            self._history.setdefault(key, []).append(existing)
        else:
            new_version = 1

        updated = TranslationEntry(
            target_kind=entry.target_kind,
            target_name=entry.target_name,
            lang=entry.lang,
            field=entry.field,
            value=entry.value,
            en_source=entry.en_source,
            version=new_version,
            created_by=entry.created_by,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self._current[key] = updated
        return updated

    def get(self, kind: str, name: str, lang: str, field: str) -> TranslationEntry | None:
        return self._current.get((kind, name, lang, field))

    def list_translations(self, lang: str, kind: str | None = None) -> tuple[TranslationEntry, ...]:
        results = [
            e for e in self._current.values()
            if e.lang == lang and (kind is None or e.target_kind == kind)
        ]
        return tuple(sorted(results, key=lambda e: (e.target_kind, e.target_name, e.field)))

    def history(self, kind: str, name: str, lang: str, field: str) -> tuple[TranslationEntry, ...]:
        key = (kind, name, lang, field)
        past = list(self._history.get(key, []))
        current = self._current.get(key)
        if current is not None:
            past.append(current)
        # newest first
        return tuple(sorted(past, key=lambda e: e.version, reverse=True))

    def delete(self, kind: str, name: str, lang: str, field: str) -> bool:
        key = (kind, name, lang, field)
        if key in self._current:
            del self._current[key]
            self._history.pop(key, None)
            return True
        return False

    def import_from_toml(self, toml_path: Path, lang: str, created_by: str = "toml_import") -> int:
        doc = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        count = 0
        now = datetime.now(UTC).isoformat() + "Z"

        for section, kind in (("entities", "entity"), ("relations", "relation")):
            for item_name, fields in doc.get(section, {}).items():
                if not isinstance(fields, dict):
                    continue
                for field_name in ("display_name", "description"):
                    if field_name not in fields:
                        continue
                    en_key = f"_en_{field_name}"
                    en_source = fields.get(en_key, "")
                    entry = TranslationEntry(
                        target_kind=kind,
                        target_name=item_name,
                        lang=lang,
                        field=field_name,
                        value=fields[field_name],
                        en_source=en_source,
                        version=1,
                        created_by=created_by,
                        created_at=now,
                        updated_at=now,
                    )
                    self.upsert(entry)
                    count += 1
        return count

    def audit(self, schema: KernelSchema, lang: str) -> I18nAuditReport:
        schema_items = _schema_items(schema)
        missing: list[I18nAuditEntry] = []
        stale: list[I18nAuditEntry] = []
        orphan: list[I18nAuditEntry] = []

        # Track which DB keys are accounted for
        schema_keys: set[tuple[str, str, str, str]] = set()

        for (kind, name), en_fields in schema_items.items():
            for field_name, en_value in en_fields.items():
                schema_keys.add((kind, name, lang, field_name))
                entry = self.get(kind, name, lang, field_name)
                if entry is None:
                    missing.append(I18nAuditEntry(
                        kind=kind, name=name, issue="missing",
                        field=field_name, en_current=en_value, en_recorded="",
                    ))
                elif entry.en_source and entry.en_source != en_value:
                    stale.append(I18nAuditEntry(
                        kind=kind, name=name, issue="stale",
                        field=field_name, en_current=en_value, en_recorded=entry.en_source,
                    ))

        # Orphan: in DB but not in schema
        for key, entry in self._current.items():
            if entry.lang != lang:
                continue
            if key not in schema_keys:
                orphan.append(I18nAuditEntry(
                    kind=entry.target_kind, name=entry.target_name, issue="orphan",
                    field=entry.field, en_current="", en_recorded=entry.en_source,
                ))

        total_slots = sum(len(fields) for fields in schema_items.values())
        translated = total_slots - len(missing)

        return I18nAuditReport(
            lang=lang,
            missing=tuple(missing),
            orphan=tuple(orphan),
            stale=tuple(stale),
            total_schema_items=total_slots,
            total_translated=translated,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteI18nStore
# ═══════════════════════════════════════════════════════════════════════════════


class SQLiteI18nStore(I18nStore):
    """SQLite 기반 번역 저장소."""

    __slots__ = ("_db_path",)

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._init_schema()

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
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS translations (
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT NOT NULL,
                    en_source TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1,
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (kind, name, lang, field)
                );

                CREATE TABLE IF NOT EXISTS translation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL,
                    lang TEXT NOT NULL,
                    field TEXT NOT NULL,
                    value TEXT NOT NULL,
                    en_source TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL,
                    created_by TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
            """)
            conn.commit()

    def upsert(self, entry: TranslationEntry) -> TranslationEntry:
        now = datetime.now(UTC).isoformat() + "Z"

        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT version, created_at FROM translations WHERE kind=? AND name=? AND lang=? AND field=?",
                (entry.target_kind, entry.target_name, entry.lang, entry.field),
            )
            row = cursor.fetchone()

            if row is not None:
                old_version = row["version"]
                new_version = old_version + 1
                created_at = row["created_at"]

                # Archive current to history before overwriting
                conn.execute(
                    """INSERT INTO translation_history
                       (kind, name, lang, field, value, en_source, version, created_by, created_at)
                       SELECT kind, name, lang, field, value, en_source, version, created_by, created_at
                       FROM translations WHERE kind=? AND name=? AND lang=? AND field=?""",
                    (entry.target_kind, entry.target_name, entry.lang, entry.field),
                )

                conn.execute(
                    """UPDATE translations SET value=?, en_source=?, version=?, created_by=?, updated_at=?
                       WHERE kind=? AND name=? AND lang=? AND field=?""",
                    (entry.value, entry.en_source, new_version, entry.created_by, now,
                     entry.target_kind, entry.target_name, entry.lang, entry.field),
                )
            else:
                new_version = 1
                created_at = now
                conn.execute(
                    """INSERT INTO translations (kind, name, lang, field, value, en_source, version, created_by, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (entry.target_kind, entry.target_name, entry.lang, entry.field,
                     entry.value, entry.en_source, new_version, entry.created_by, created_at, now),
                )

            conn.commit()

        return TranslationEntry(
            target_kind=entry.target_kind,
            target_name=entry.target_name,
            lang=entry.lang,
            field=entry.field,
            value=entry.value,
            en_source=entry.en_source,
            version=new_version,
            created_by=entry.created_by,
            created_at=created_at,
            updated_at=now,
        )

    def get(self, kind: str, name: str, lang: str, field: str) -> TranslationEntry | None:
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM translations WHERE kind=? AND name=? AND lang=? AND field=?",
                (kind, name, lang, field),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)

    def list_translations(self, lang: str, kind: str | None = None) -> tuple[TranslationEntry, ...]:
        with self._connection() as conn:
            if kind is not None:
                cursor = conn.execute(
                    "SELECT * FROM translations WHERE lang=? AND kind=? ORDER BY kind, name, field",
                    (lang, kind),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM translations WHERE lang=? ORDER BY kind, name, field",
                    (lang,),
                )
            return tuple(self._row_to_entry(row) for row in cursor.fetchall())

    def history(self, kind: str, name: str, lang: str, field: str) -> tuple[TranslationEntry, ...]:
        with self._connection() as conn:
            # History entries (older versions)
            cursor = conn.execute(
                """SELECT kind, name, lang, field, value, en_source, version, created_by, created_at, created_at as updated_at
                   FROM translation_history
                   WHERE kind=? AND name=? AND lang=? AND field=?
                   ORDER BY version DESC""",
                (kind, name, lang, field),
            )
            past = [self._row_to_entry(row) for row in cursor.fetchall()]

            # Current version
            current = self.get(kind, name, lang, field)
            if current is not None:
                past.insert(0, current)  # newest first

            return tuple(past)

    def delete(self, kind: str, name: str, lang: str, field: str) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM translations WHERE kind=? AND name=? AND lang=? AND field=?",
                (kind, name, lang, field),
            )
            conn.execute(
                "DELETE FROM translation_history WHERE kind=? AND name=? AND lang=? AND field=?",
                (kind, name, lang, field),
            )
            conn.commit()
            return cursor.rowcount > 0

    def import_from_toml(self, toml_path: Path, lang: str, created_by: str = "toml_import") -> int:
        doc = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        count = 0
        now = datetime.now(UTC).isoformat() + "Z"

        for section, kind in (("entities", "entity"), ("relations", "relation")):
            for item_name, fields in doc.get(section, {}).items():
                if not isinstance(fields, dict):
                    continue
                for field_name in ("display_name", "description"):
                    if field_name not in fields:
                        continue
                    en_key = f"_en_{field_name}"
                    en_source = fields.get(en_key, "")
                    entry = TranslationEntry(
                        target_kind=kind,
                        target_name=item_name,
                        lang=lang,
                        field=field_name,
                        value=fields[field_name],
                        en_source=en_source,
                        version=1,
                        created_by=created_by,
                        created_at=now,
                        updated_at=now,
                    )
                    self.upsert(entry)
                    count += 1
        return count

    def audit(self, schema: KernelSchema, lang: str) -> I18nAuditReport:
        schema_items = _schema_items(schema)
        missing: list[I18nAuditEntry] = []
        stale: list[I18nAuditEntry] = []
        orphan: list[I18nAuditEntry] = []

        schema_keys: set[tuple[str, str, str]] = set()

        for (kind, name), en_fields in schema_items.items():
            for field_name, en_value in en_fields.items():
                schema_keys.add((kind, name, field_name))
                entry = self.get(kind, name, lang, field_name)
                if entry is None:
                    missing.append(I18nAuditEntry(
                        kind=kind, name=name, issue="missing",
                        field=field_name, en_current=en_value, en_recorded="",
                    ))
                elif entry.en_source and entry.en_source != en_value:
                    stale.append(I18nAuditEntry(
                        kind=kind, name=name, issue="stale",
                        field=field_name, en_current=en_value, en_recorded=entry.en_source,
                    ))

        # Orphan detection
        all_translations = self.list_translations(lang)
        for entry in all_translations:
            if (entry.target_kind, entry.target_name, entry.field) not in schema_keys:
                orphan.append(I18nAuditEntry(
                    kind=entry.target_kind, name=entry.target_name, issue="orphan",
                    field=entry.field, en_current="", en_recorded=entry.en_source,
                ))

        total_slots = sum(len(fields) for fields in schema_items.values())
        translated = total_slots - len(missing)

        return I18nAuditReport(
            lang=lang,
            missing=tuple(missing),
            orphan=tuple(orphan),
            stale=tuple(stale),
            total_schema_items=total_slots,
            total_translated=translated,
        )

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> TranslationEntry:
        return TranslationEntry(
            target_kind=row["kind"],
            target_name=row["name"],
            lang=row["lang"],
            field=row["field"],
            value=row["value"],
            en_source=row["en_source"],
            version=row["version"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
