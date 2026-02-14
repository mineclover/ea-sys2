"""Tests for profile_store — StoragePort + SQLiteProfileStore."""

from __future__ import annotations

import pytest
from ea_kernel.profile_serializer import compute_content_hash, profile_to_dict
from ea_kernel.profile_store import SQLiteProfileStore
from ea_kernel.profile_types import (
    KernelProfile,
    ProfileElement,
    ProfileMetadata,
    ProfileOrigin,
    ProfileRelation,
    ProfileStoreError,
)
from ea_kernel.types import KernelValidityRule


def _make_profile(name: str = "Test", version: str = "1.0") -> KernelProfile:
    return KernelProfile(
        name=name,
        version=version,
        kernel_version="2.5.0",
        elements=(
            ProfileElement("E1", "structure", "L1", "C1", "desc"),
            ProfileElement("E2", "step", "L2", "C2"),
        ),
        relations=(ProfileRelation("r1", "association"),),
        validity_rules=(
            KernelValidityRule(
                id="t-allow-01", source_pattern="@C1", target_pattern="@C2",
                relationship_name="r1", valid=True, priority=40,
            ),
        ),
        metadata=ProfileMetadata(standard="Test 1.0", organization="Org"),
    )


@pytest.fixture
def store():
    s = SQLiteProfileStore(":memory:")
    s.initialize()
    yield s
    s.close()


class TestStoreLifecycle:
    def test_uninitialized_raises(self):
        s = SQLiteProfileStore()
        with pytest.raises(ProfileStoreError, match="not initialized"):
            s.list_profiles()

    def test_context_manager(self):
        with SQLiteProfileStore(":memory:") as s:
            s.initialize()
            s.store(_make_profile())
            assert len(s.list_profiles()) == 1


class TestStoreCRUD:
    def test_store_and_get(self, store):
        p = _make_profile()
        pv = store.store(p, author="tester", description="initial")
        assert pv.profile_name == "Test"
        assert pv.version == "1.0"
        assert pv.content_hash == compute_content_hash(p)
        assert pv.author == "tester"
        assert pv.description == "initial"
        assert pv.parent_id is None

        retrieved = store.get(pv.id)
        assert retrieved is not None
        assert retrieved.id == pv.id
        assert retrieved.data == profile_to_dict(p)

    def test_get_latest(self, store):
        p1 = _make_profile(version="1.0")
        p2 = _make_profile(version="2.0")
        store.store(p1)
        pv2 = store.store(p2)
        latest = store.get_latest("Test")
        assert latest is not None
        assert latest.version == "2.0"
        assert latest.id == pv2.id

    def test_get_latest_not_found(self, store):
        assert store.get_latest("Nonexistent") is None

    def test_list_versions(self, store):
        store.store(_make_profile(version="1.0"))
        store.store(_make_profile(version="2.0"))
        versions = store.list_versions("Test")
        assert len(versions) == 2
        assert versions[0].version == "1.0"
        assert versions[1].version == "2.0"

    def test_list_versions_descending(self, store):
        store.store(_make_profile(version="1.0"))
        store.store(_make_profile(version="2.0"))
        versions = store.list_versions("Test", ascending=False)
        assert versions[0].version == "2.0"

    def test_list_profiles(self, store):
        store.store(_make_profile("A"))
        store.store(_make_profile("B"))
        names = store.list_profiles()
        assert names == ["A", "B"]

    def test_duplicate_version_raises(self, store):
        store.store(_make_profile(version="1.0"))
        with pytest.raises(ProfileStoreError, match="already exists"):
            store.store(_make_profile(version="1.0"))


class TestVersionChain:
    def test_auto_parent(self, store):
        pv1 = store.store(_make_profile(version="1.0"))
        pv2 = store.store(_make_profile(version="2.0"))
        assert pv2.parent_id == pv1.id

    def test_explicit_parent(self, store):
        pv1 = store.store(_make_profile(version="1.0"))
        pv2 = store.store(_make_profile(version="2.0"), parent_id=pv1.id)
        assert pv2.parent_id == pv1.id


class TestTags:
    def test_tag_and_retrieve(self, store):
        pv = store.store(_make_profile())
        tag = store.tag(pv.id, "stable")
        assert tag.name == "stable"
        assert tag.profile_name == "Test"

        retrieved = store.get_by_tag("Test", "stable")
        assert retrieved is not None
        assert retrieved.id == pv.id

    def test_tag_nonexistent_raises(self, store):
        with pytest.raises(ProfileStoreError, match="not found"):
            store.tag("nonexistent", "stable")

    def test_tag_upsert(self, store):
        pv1 = store.store(_make_profile(version="1.0"))
        pv2 = store.store(_make_profile(version="2.0"))
        store.tag(pv1.id, "latest")
        store.tag(pv2.id, "latest")
        retrieved = store.get_by_tag("Test", "latest")
        assert retrieved is not None
        assert retrieved.id == pv2.id

    def test_get_by_tag_not_found(self, store):
        assert store.get_by_tag("Test", "nope") is None


class TestDelete:
    def test_delete_version(self, store):
        pv = store.store(_make_profile())
        assert store.delete(pv.id) is True
        assert store.get(pv.id) is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nope") is False

    def test_delete_clears_parent_refs(self, store):
        pv1 = store.store(_make_profile(version="1.0"))
        pv2 = store.store(_make_profile(version="2.0"))
        assert pv2.parent_id == pv1.id
        store.delete(pv1.id)
        refreshed = store.get(pv2.id)
        assert refreshed is not None
        assert refreshed.parent_id is None

    def test_delete_cascades_tags(self, store):
        pv = store.store(_make_profile())
        store.tag(pv.id, "tagged")
        store.delete(pv.id)
        assert store.get_by_tag("Test", "tagged") is None


class TestGetByVersion:
    def test_found(self, store):
        store.store(_make_profile(version="1.0"))
        pv = store.get_by_version("Test", "1.0")
        assert pv is not None
        assert pv.version == "1.0"

    def test_not_found(self, store):
        assert store.get_by_version("Test", "999") is None

    def test_cross_profile_isolation(self, store):
        store.store(_make_profile("A", "1.0"))
        store.store(_make_profile("B", "1.0"))
        pv = store.get_by_version("A", "1.0")
        assert pv is not None
        assert pv.profile_name == "A"


class TestListTags:
    def test_list_all(self, store):
        pv = store.store(_make_profile())
        store.tag(pv.id, "stable")
        store.tag(pv.id, "latest")
        tags = store.list_tags()
        assert len(tags) == 2
        names = {t.name for t in tags}
        assert names == {"stable", "latest"}

    def test_list_by_version_id(self, store):
        pv1 = store.store(_make_profile(version="1.0"))
        pv2 = store.store(_make_profile(version="2.0"))
        store.tag(pv1.id, "old")
        store.tag(pv2.id, "new")
        tags = store.list_tags(version_id=pv1.id)
        assert len(tags) == 1
        assert tags[0].name == "old"

    def test_list_by_profile_name(self, store):
        pv_a = store.store(_make_profile("A"))
        pv_b = store.store(_make_profile("B"))
        store.tag(pv_a.id, "stable")
        store.tag(pv_b.id, "stable")
        tags = store.list_tags(profile_name="A")
        assert len(tags) == 1
        assert tags[0].profile_name == "A"

    def test_empty(self, store):
        assert store.list_tags() == []


class TestGetByContentHash:
    def test_found(self, store):
        p = _make_profile()
        pv = store.store(p)
        results = store.get_by_content_hash(pv.content_hash)
        assert len(results) == 1
        assert results[0].id == pv.id

    def test_not_found(self, store):
        assert store.get_by_content_hash("nonexistent") == []


class TestOriginPersistence:
    def test_origin_stored(self, store):
        p = _make_profile()
        pv = store.store(p, origin=ProfileOrigin.TOML)
        assert pv.origin == "toml"
        retrieved = store.get(pv.id)
        assert retrieved.origin == "toml"

    def test_origin_default_empty(self, store):
        pv = store.store(_make_profile())
        assert pv.origin == ""


class TestLoadProfile:
    def test_load_profile_roundtrip(self, store):
        p = _make_profile()
        pv = store.store(p)
        loaded = store.load_profile(pv.id)
        assert loaded == p

    def test_load_profile_not_found(self, store):
        assert store.load_profile("nope") is None
