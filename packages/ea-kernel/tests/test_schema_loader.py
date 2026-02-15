"""Tests for schema_loader — TOML-based kernel schema loading + i18n."""

from __future__ import annotations

from pathlib import Path

import pytest

from ea_kernel.schema_loader import (
    SchemaLoadError,
    _to_i18n,
    audit_i18n_patch,
    load_kernel_schema,
    load_kernel_schema_from_package,
    load_schema_i18n,
)
from ea_kernel.types import KernelSchema, Layer


class TestLoadKernelSchema:
    """load_kernel_schema() from default specs/kernel_schema.toml."""

    def test_loads_from_default_path(self):
        version, schema, attributes, l1_entities, l2_relations, l3_relations, l4_entities = (
            load_kernel_schema()
        )
        assert isinstance(version, str) and version
        assert isinstance(schema, KernelSchema)
        assert len(attributes) > 0
        assert len(l1_entities) > 0
        assert len(l2_relations) > 0

    def test_self_verification_counts(self):
        version, schema, attributes, l1_entities, l2_relations, l3_relations, l4_entities = (
            load_kernel_schema()
        )
        # Schema TOML declares meta counts: 20 attrs, 15 entities, 14 relations
        assert len(attributes) == 20
        assert len(schema.entities) == 15
        assert len(schema.relations) == 14

    def test_entity_layer_split(self):
        _, _, _, l1_entities, _, _, l4_entities = load_kernel_schema()
        for e in l1_entities:
            assert e.layer == Layer.L1
        for e in l4_entities:
            assert e.layer == Layer.L4

    def test_relation_layer_split(self):
        _, _, _, _, l2_relations, l3_relations, _ = load_kernel_schema()
        for r in l2_relations:
            assert r.layer == Layer.L2
        for r in l3_relations:
            assert r.layer == Layer.L3

    def test_entity_fields(self):
        _, schema, _, _, _, _, _ = load_kernel_schema()
        for e in schema.entities:
            assert isinstance(e.name, str) and e.name
            assert e.layer in Layer
            assert isinstance(e.is_abstract, bool)
            assert isinstance(e.owns, tuple)
            assert isinstance(e.plays, tuple)
            # description can be str or dict
            assert isinstance(e.description, (str, dict))

    def test_relation_roles_parsed(self):
        _, schema, _, _, _, _, _ = load_kernel_schema()
        relations_with_roles = [r for r in schema.relations if r.roles]
        assert len(relations_with_roles) > 0
        for r in relations_with_roles:
            for role in r.roles:
                assert isinstance(role.name, str) and role.name
                assert isinstance(role.player, str) and role.player

    def test_invalid_path_raises(self):
        with pytest.raises(SchemaLoadError):
            load_kernel_schema(Path("/nonexistent/path/schema.toml"))

    def test_validity_rules_loaded(self):
        _, schema, _, _, _, _, _ = load_kernel_schema()
        assert len(schema.validity_rules) > 0

    def test_layer_constraints_loaded(self):
        _, schema, _, _, _, _, _ = load_kernel_schema()
        assert len(schema.layer_constraints) > 0
        for lc in schema.layer_constraints:
            assert lc.source_layer in Layer
            assert lc.target_layer in Layer
            assert isinstance(lc.id, str) and lc.id


class TestLoadSchemaI18n:
    """load_schema_i18n() locale patching."""

    @pytest.fixture()
    def base_schema(self) -> KernelSchema:
        _, schema, _, _, _, _, _ = load_kernel_schema()
        return schema

    def test_en_returns_unchanged(self, base_schema: KernelSchema):
        result = load_schema_i18n(base_schema, "en")
        assert result is base_schema  # identity — no copy

    def test_ko_patch_applies(self, base_schema: KernelSchema):
        result = load_schema_i18n(base_schema, "ko")
        # At least one entity should have a dict description after patching
        patched = [e for e in result.entities if isinstance(e.description, dict)]
        assert len(patched) > 0
        for e in patched:
            assert "ko" in e.description

    def test_missing_locale_returns_unchanged(self, base_schema: KernelSchema):
        result = load_schema_i18n(base_schema, "xx-nonexistent")
        # No patch file → return as-is
        assert result is base_schema

    def test_i18n_string_format(self, base_schema: KernelSchema):
        result = load_schema_i18n(base_schema, "ko")
        patched = [e for e in result.entities if isinstance(e.description, dict)]
        assert len(patched) > 0
        for e in patched:
            assert "en" in e.description
            assert "ko" in e.description


class TestToI18n:
    """_to_i18n() internal helper."""

    def test_string_to_dict(self):
        result = _to_i18n("hello", "ko", "안녕")
        assert result == {"en": "hello", "ko": "안녕"}

    def test_dict_merge(self):
        existing = {"en": "hello", "ko": "안녕"}
        result = _to_i18n(existing, "ja", "こんにちは")
        assert result == {"en": "hello", "ko": "안녕", "ja": "こんにちは"}


class TestAuditI18nPatch:
    """audit_i18n_patch() TOML-level audit."""

    @pytest.fixture()
    def base_schema(self) -> KernelSchema:
        _, schema, _, _, _, _, _ = load_kernel_schema()
        return schema

    def test_ko_clean_report(self, base_schema: KernelSchema):
        report = audit_i18n_patch(base_schema, "ko")
        # ko patch has all 29 items × 2 fields translated
        assert len(report.missing) == 0
        assert len(report.orphan) == 0
        assert report.total_translated == 58

    def test_stale_detected(self, base_schema: KernelSchema, tmp_path: Path):
        """_en_description 불일치 → stale 감지."""
        patch = tmp_path / "kernel_schema.test.toml"
        patch.write_text(
            '[entities.element]\n'
            '_en_display_name = "Element"\n'
            '_en_description = "OLD description"\n'
            'display_name = "요소"\n'
            'description = "루트"\n',
            encoding="utf-8",
        )
        report = audit_i18n_patch(base_schema, "test", patch_path=patch)
        stale = [e for e in report.stale if e.name == "element"]
        assert len(stale) >= 1
        assert stale[0].en_recorded == "OLD description"

    def test_nonexistent_lang_all_missing(self, base_schema: KernelSchema):
        report = audit_i18n_patch(base_schema, "xx-none")
        assert len(report.missing) == 58
        assert report.total_translated == 0
        assert report.coverage == 0.0


class TestConvenienceWrapper:
    """load_kernel_schema_from_package() wrapper."""

    def test_load_from_package(self):
        schema = load_kernel_schema_from_package()
        assert isinstance(schema, KernelSchema)
        assert len(schema.entities) > 0
        assert len(schema.relations) > 0
