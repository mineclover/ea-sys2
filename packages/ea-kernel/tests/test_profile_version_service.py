"""Tests for profile version history service functions in kernel_service."""

from __future__ import annotations

import pytest

from ea_profile.builder import ProfileBuilder
from ea_profile.store import SQLiteProfileStore


@pytest.fixture()
def store(tmp_path):
    """Create a temporary SQLite profile store."""
    db_path = tmp_path / "test_profiles.db"
    s = SQLiteProfileStore(db_path)
    s.initialize()
    return s


@pytest.fixture(autouse=True)
def _patch_store(store, monkeypatch):
    """Patch _get_profile_store to return the test store."""
    import ea_kernel.kernel_service as ks
    monkeypatch.setattr(ks, "_get_profile_store", lambda: store)


def _build_profile(name: str = "TestProfile", version: str = "1.0", *, extra_element: str | None = None):
    """Build a minimal profile for testing."""
    builder = (
        ProfileBuilder(name, version=version, kernel_version="1.0.0")
        .element("Elem_A", layer="core", category="active", kernel_type="structure")
        .element("Elem_B", layer="core", category="passive", kernel_type="item")
        .relation("rel1", kernel_relation="association")
        .allow("Elem_A", "Elem_B", "association", priority=40)
    )
    if extra_element:
        builder = builder.element(extra_element, layer="core", category="active", kernel_type="structure")
    return builder.build(validate=False)


# ── profile_version_history ──────────────────────────────────


class TestProfileVersionHistory:

    def test_empty(self):
        from ea_kernel.kernel_service import profile_version_history

        result = profile_version_history(profile_name="NonExistent")
        assert result["profile_name"] == "NonExistent"
        assert result["count"] == 0
        assert result["versions"] == []

    def test_newest_first(self, store):
        from ea_kernel.kernel_service import profile_version_history

        p1 = _build_profile(version="1.0")
        p2 = _build_profile(version="2.0")
        store.store(p1, author="alice", description="initial")
        store.store(p2, author="bob", description="update")

        result = profile_version_history(profile_name="TestProfile")
        assert result["count"] == 2
        versions = result["versions"]
        assert versions[0]["version"] == "2.0"
        assert versions[1]["version"] == "1.0"

    def test_limit(self, store):
        from ea_kernel.kernel_service import profile_version_history

        for i in range(5):
            store.store(_build_profile(version=f"{i}.0"), author="test")

        result = profile_version_history(profile_name="TestProfile", limit=3)
        assert result["count"] == 3

    def test_version_fields(self, store):
        from ea_kernel.kernel_service import profile_version_history

        store.store(_build_profile(version="1.0"), author="alice", description="first")

        result = profile_version_history(profile_name="TestProfile")
        v = result["versions"][0]
        assert "id" in v
        assert v["version"] == "1.0"
        assert v["author"] == "alice"
        assert v["description"] == "first"
        assert "content_hash" in v
        assert "created_at" in v
        # data field must NOT be present (large data prevention)
        assert "data" not in v


# ── profile_version_detail ───────────────────────────────────


class TestProfileVersionDetail:

    def test_not_found(self):
        from ea_kernel.kernel_service import profile_version_detail

        result = profile_version_detail(profile_name="X", version="99.0")
        assert "error" in result

    def test_metadata_and_counts(self, store):
        from ea_kernel.kernel_service import profile_version_detail

        store.store(_build_profile(version="1.0"), author="alice", description="init")

        result = profile_version_detail(profile_name="TestProfile", version="1.0")
        assert result["profile_name"] == "TestProfile"
        assert result["version"] == "1.0"
        assert result["author"] == "alice"
        assert result["element_count"] == 2
        assert result["relation_count"] == 1
        assert result["rule_count"] >= 1
        assert result["tags"] == []

    def test_tags_included(self, store):
        from ea_kernel.kernel_service import profile_version_detail

        pv = store.store(_build_profile(version="1.0"))
        store.tag(pv.id, "release-1.0")

        result = profile_version_detail(profile_name="TestProfile", version="1.0")
        assert len(result["tags"]) == 1
        assert result["tags"][0]["name"] == "release-1.0"


# ── profile_version_diff ─────────────────────────────────────


class TestProfileVersionDiff:

    def test_identical(self, store):
        from ea_kernel.kernel_service import profile_version_diff

        store.store(_build_profile(version="1.0"))
        store.store(_build_profile(version="2.0"))

        result = profile_version_diff(
            profile_name="TestProfile", version_a="1.0", version_b="2.0",
        )
        assert result["identical"] is True
        assert result["element_changes"] == []

    def test_element_added(self, store):
        from ea_kernel.kernel_service import profile_version_diff

        store.store(_build_profile(version="1.0"))
        store.store(_build_profile(version="2.0", extra_element="Elem_C"))

        result = profile_version_diff(
            profile_name="TestProfile", version_a="1.0", version_b="2.0",
        )
        assert result["identical"] is False
        added = [c for c in result["element_changes"] if c["type"] == "added"]
        assert len(added) == 1
        assert added[0]["name"] == "Elem_C"

    def test_version_not_found(self, store):
        from ea_kernel.kernel_service import profile_version_diff

        store.store(_build_profile(version="1.0"))

        result = profile_version_diff(
            profile_name="TestProfile", version_a="1.0", version_b="99.0",
        )
        assert "error" in result

    def test_diff_fields(self, store):
        from ea_kernel.kernel_service import profile_version_diff

        store.store(_build_profile(version="1.0"))
        store.store(_build_profile(version="2.0", extra_element="Elem_C"))

        result = profile_version_diff(
            profile_name="TestProfile", version_a="1.0", version_b="2.0",
        )
        assert result["profile_name"] == "TestProfile"
        assert result["from_version"] == "1.0"
        assert result["to_version"] == "2.0"


# ── profile_version_tags ─────────────────────────────────────


class TestProfileVersionTags:

    def test_empty(self):
        from ea_kernel.kernel_service import profile_version_tags

        result = profile_version_tags(profile_name="NonExistent")
        assert result["count"] == 0
        assert result["tags"] == []

    def test_tags_listed(self, store):
        from ea_kernel.kernel_service import profile_version_tags

        pv = store.store(_build_profile(version="1.0"))
        store.tag(pv.id, "stable")
        store.tag(pv.id, "production")

        result = profile_version_tags(profile_name="TestProfile")
        assert result["count"] == 2
        tag_names = {t["name"] for t in result["tags"]}
        assert tag_names == {"stable", "production"}
        for t in result["tags"]:
            assert "version_id" in t
            assert "created_at" in t
