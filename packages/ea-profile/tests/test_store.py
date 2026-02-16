"""Tests for ea_profile.store — InMemoryProfileStore and SQLiteProfileStore."""

import pytest

from ea_profile.builder import ProfileBuilder
from ea_profile.store import InMemoryProfileStore, SQLiteProfileStore, StoragePort
from ea_profile.types import ProfileOrigin, ProfileStoreError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(name: str = "TestProfile", version: str = "1.0"):
    b = ProfileBuilder(name, version=version, kernel_version="1.0")
    b.element("Elem1", kernel_type="structure", layer="Business", category="Structure")
    b.element("Elem2", kernel_type="item", layer="Business", category="Structure")
    b.relation("Rel1", kernel_relation="association")
    return b.build()


def _store_scenarios(store: StoragePort):
    """Run shared scenarios that both InMemory and SQLite must satisfy."""
    profile_v1 = _make_profile("MyProfile", "1.0")
    profile_v2 = _make_profile("MyProfile", "2.0")

    # Store v1
    pv1 = store.store(profile_v1, author="alice", description="initial")
    assert pv1.profile_name == "MyProfile"
    assert pv1.version == "1.0"
    assert pv1.author == "alice"
    assert pv1.parent_id is None  # first version, no parent

    # Store v2 — auto parent
    pv2 = store.store(profile_v2, author="bob", description="update")
    assert pv2.parent_id == pv1.id

    # get
    got = store.get(pv1.id)
    assert got is not None
    assert got.id == pv1.id

    # get_latest
    latest = store.get_latest("MyProfile")
    assert latest is not None
    assert latest.version == "2.0"

    # list_versions ascending
    versions = store.list_versions("MyProfile", ascending=True)
    assert len(versions) == 2
    assert versions[0].version == "1.0"
    assert versions[1].version == "2.0"

    # list_versions descending
    versions_desc = store.list_versions("MyProfile", ascending=False)
    assert versions_desc[0].version == "2.0"

    # list_profiles
    profiles = store.list_profiles()
    assert "MyProfile" in profiles

    # get_by_version
    by_ver = store.get_by_version("MyProfile", "1.0")
    assert by_ver is not None
    assert by_ver.id == pv1.id

    # get_by_version not found
    assert store.get_by_version("MyProfile", "999") is None

    # tag
    tag_obj = store.tag(pv1.id, "stable")
    assert tag_obj.name == "stable"
    assert tag_obj.version_id == pv1.id

    # get_by_tag
    by_tag = store.get_by_tag("MyProfile", "stable")
    assert by_tag is not None
    assert by_tag.id == pv1.id

    # get_by_tag not found
    assert store.get_by_tag("MyProfile", "nonexistent") is None

    # list_tags by version
    tags_for_v1 = store.list_tags(version_id=pv1.id)
    assert len(tags_for_v1) == 1

    # list_tags by profile
    tags_for_profile = store.list_tags(profile_name="MyProfile")
    assert len(tags_for_profile) == 1

    # list_tags all
    all_tags = store.list_tags()
    assert len(all_tags) >= 1

    # tag reassign (upsert)
    store.tag(pv2.id, "stable")
    updated_by_tag = store.get_by_tag("MyProfile", "stable")
    assert updated_by_tag is not None
    assert updated_by_tag.id == pv2.id

    # delete
    assert store.delete(pv1.id) is True
    assert store.get(pv1.id) is None
    # parent_id cleared
    refreshed_v2 = store.get(pv2.id)
    assert refreshed_v2 is not None
    assert refreshed_v2.parent_id is None

    # delete nonexistent
    assert store.delete("nonexistent") is False

    # duplicate version error
    profile_v2_dup = _make_profile("MyProfile", "2.0")
    with pytest.raises(ProfileStoreError):
        store.store(profile_v2_dup)


# ---------------------------------------------------------------------------
# InMemoryProfileStore
# ---------------------------------------------------------------------------

class TestInMemoryProfileStore:
    def test_shared_scenarios(self):
        store = InMemoryProfileStore()
        store.initialize()
        _store_scenarios(store)
        store.close()

    def test_tag_nonexistent_version_raises(self):
        store = InMemoryProfileStore()
        store.initialize()
        with pytest.raises(ProfileStoreError):
            store.tag("nonexistent", "tag")

    def test_origin_stored(self):
        store = InMemoryProfileStore()
        store.initialize()
        profile = _make_profile()
        pv = store.store(profile, origin=ProfileOrigin.TOML)
        assert pv.origin == "toml"

    def test_empty_queries(self):
        store = InMemoryProfileStore()
        store.initialize()
        assert store.get("x") is None
        assert store.get_latest("x") is None
        assert store.list_versions("x") == []
        assert store.list_profiles() == []
        assert store.get_by_version("x", "1") is None
        assert store.get_by_tag("x", "t") is None
        assert store.list_tags() == []


# ---------------------------------------------------------------------------
# SQLiteProfileStore
# ---------------------------------------------------------------------------

class TestSQLiteProfileStore:
    def test_shared_scenarios(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        _store_scenarios(store)
        store.close()

    def test_require_init(self):
        store = SQLiteProfileStore(":memory:")
        with pytest.raises(ProfileStoreError):
            store.get("x")

    def test_tag_nonexistent_version_raises(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        with pytest.raises(ProfileStoreError):
            store.tag("nonexistent", "tag")

    def test_origin_stored(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        profile = _make_profile()
        pv = store.store(profile, origin=ProfileOrigin.TOML)
        assert pv.origin == "toml"
