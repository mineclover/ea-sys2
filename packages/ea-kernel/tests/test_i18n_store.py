"""Tests for i18n_store — translation storage + audit."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from ea_kernel.i18n_store import (
    I18nAuditReport,
    InMemoryI18nStore,
    SQLiteI18nStore,
    TranslationEntry,
)
from ea_kernel.schema_loader import load_kernel_schema

SPECS_DIR = Path(__file__).resolve().parent.parent / "src" / "ea_kernel" / "specs"


def _make_entry(
    kind: str = "entity",
    name: str = "element",
    lang: str = "ko",
    field: str = "display_name",
    value: str = "요소",
    en_source: str = "Element",
) -> TranslationEntry:
    return TranslationEntry(
        target_kind=kind,
        target_name=name,
        lang=lang,
        field=field,
        value=value,
        en_source=en_source,
        version=1,
        created_by="test",
        created_at="",
        updated_at="",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# InMemoryI18nStore
# ═══════════════════════════════════════════════════════════════════════════════


class TestInMemoryI18nStore:
    """InMemoryI18nStore 기본 동작."""

    def test_upsert_and_get(self):
        store = InMemoryI18nStore()
        entry = _make_entry()
        result = store.upsert(entry)
        assert result.version == 1
        assert result.value == "요소"

        got = store.get("entity", "element", "ko", "display_name")
        assert got is not None
        assert got.value == "요소"
        assert got.version == 1

    def test_upsert_increments_version(self):
        store = InMemoryI18nStore()
        store.upsert(_make_entry(value="요소"))
        result = store.upsert(_make_entry(value="요소 (수정)"))
        assert result.version == 2
        assert result.value == "요소 (수정)"

    def test_list_translations_filters_by_lang(self):
        store = InMemoryI18nStore()
        store.upsert(_make_entry(lang="ko", name="element"))
        store.upsert(_make_entry(lang="ko", name="namespace", value="이름공간"))
        store.upsert(_make_entry(lang="ja", name="element", value="要素"))

        ko = store.list_translations("ko")
        assert len(ko) == 2
        ja = store.list_translations("ja")
        assert len(ja) == 1

    def test_list_translations_filters_by_kind(self):
        store = InMemoryI18nStore()
        store.upsert(_make_entry(kind="entity", name="element"))
        store.upsert(_make_entry(kind="relation", name="membership", value="소속", en_source="Membership"))

        entities = store.list_translations("ko", kind="entity")
        assert len(entities) == 1
        relations = store.list_translations("ko", kind="relation")
        assert len(relations) == 1

    def test_history_returns_all_versions(self):
        store = InMemoryI18nStore()
        store.upsert(_make_entry(value="v1"))
        store.upsert(_make_entry(value="v2"))
        store.upsert(_make_entry(value="v3"))

        hist = store.history("entity", "element", "ko", "display_name")
        assert len(hist) == 3
        # newest first
        assert hist[0].version == 3
        assert hist[0].value == "v3"
        assert hist[2].version == 1
        assert hist[2].value == "v1"

    def test_delete(self):
        store = InMemoryI18nStore()
        store.upsert(_make_entry())
        assert store.delete("entity", "element", "ko", "display_name") is True
        assert store.get("entity", "element", "ko", "display_name") is None
        assert store.delete("entity", "element", "ko", "display_name") is False

    def test_import_from_toml(self):
        store = InMemoryI18nStore()
        ko_path = SPECS_DIR / "kernel_schema.ko.toml"
        count = store.import_from_toml(ko_path, "ko")
        # 15 entities + 14 relations, each with display_name + description = 58
        assert count == 58

    def test_audit_clean(self):
        """Complete translation → is_clean."""
        store = InMemoryI18nStore()
        _, schema, *_ = load_kernel_schema()
        ko_path = SPECS_DIR / "kernel_schema.ko.toml"
        store.import_from_toml(ko_path, "ko")

        report = store.audit(schema, "ko")
        assert isinstance(report, I18nAuditReport)
        assert report.total_schema_items == 58
        assert len(report.missing) == 0
        assert len(report.orphan) == 0
        # coverage should be 1.0
        assert report.coverage == 1.0

    def test_audit_missing(self):
        """Empty store → all missing."""
        store = InMemoryI18nStore()
        _, schema, *_ = load_kernel_schema()
        report = store.audit(schema, "ko")
        assert len(report.missing) == 58
        assert report.total_translated == 0

    def test_audit_orphan(self):
        """Entry for non-existent schema item → orphan."""
        store = InMemoryI18nStore()
        _, schema, *_ = load_kernel_schema()
        ko_path = SPECS_DIR / "kernel_schema.ko.toml"
        store.import_from_toml(ko_path, "ko")

        # Add an orphan entry
        store.upsert(_make_entry(kind="entity", name="ghost", value="유령", en_source="Ghost"))
        report = store.audit(schema, "ko")
        assert len(report.orphan) == 1
        assert report.orphan[0].name == "ghost"

    def test_audit_stale(self):
        """en_source mismatch → stale."""
        store = InMemoryI18nStore()
        _, schema, *_ = load_kernel_schema()

        # Insert with wrong en_source
        store.upsert(_make_entry(
            kind="entity", name="element", field="description",
            value="모든 커널 요소의 루트", en_source="OLD description",
        ))
        report = store.audit(schema, "ko")
        stale = [e for e in report.stale if e.name == "element" and e.field == "description"]
        assert len(stale) == 1
        assert stale[0].en_recorded == "OLD description"


# ═══════════════════════════════════════════════════════════════════════════════
# SQLiteI18nStore
# ═══════════════════════════════════════════════════════════════════════════════


class TestSQLiteI18nStore:
    """SQLiteI18nStore persistence and history."""

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "i18n.db"

            store1 = SQLiteI18nStore(db_path)
            store1.upsert(_make_entry())

            store2 = SQLiteI18nStore(db_path)
            got = store2.get("entity", "element", "ko", "display_name")
            assert got is not None
            assert got.value == "요소"

    def test_upsert_and_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "i18n.db"
            store = SQLiteI18nStore(db_path)

            store.upsert(_make_entry(value="v1"))
            store.upsert(_make_entry(value="v2"))
            store.upsert(_make_entry(value="v3"))

            hist = store.history("entity", "element", "ko", "display_name")
            assert len(hist) == 3
            assert hist[0].version == 3
            assert hist[0].value == "v3"
            assert hist[2].version == 1
            assert hist[2].value == "v1"

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "i18n.db"
            store = SQLiteI18nStore(db_path)
            store.upsert(_make_entry())
            assert store.delete("entity", "element", "ko", "display_name") is True
            assert store.get("entity", "element", "ko", "display_name") is None

    def test_import_from_toml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "i18n.db"
            store = SQLiteI18nStore(db_path)
            ko_path = SPECS_DIR / "kernel_schema.ko.toml"
            count = store.import_from_toml(ko_path, "ko")
            assert count == 58

            all_ko = store.list_translations("ko")
            assert len(all_ko) == 58
