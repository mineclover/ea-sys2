"""Tests for profile_registry — In-memory + persistence hybrid registry."""

from __future__ import annotations

import pytest

from ea_kernel.profile_types import KernelProfile, ProfileElement, ProfileOrigin, ProfileRegistryError, ProfileRelation
from ea_kernel.profile_registry import ProfileRegistry
from ea_kernel.profile_store import SQLiteProfileStore


def _make_profile(name: str = "Test") -> KernelProfile:
    return KernelProfile(
        name=name,
        version="1.0",
        kernel_version="2.5.0",
        elements=(ProfileElement("E1", "structure", "L1", "C1"),),
        relations=(ProfileRelation("r1", "association"),),
    )


class TestRegistration:
    def test_register_and_get(self):
        reg = ProfileRegistry()
        p = _make_profile()
        reg.register(p)
        assert reg.get("Test") == p

    def test_get_not_found(self):
        reg = ProfileRegistry()
        assert reg.get("Nonexistent") is None

    def test_duplicate_raises(self):
        reg = ProfileRegistry()
        reg.register(_make_profile())
        with pytest.raises(ProfileRegistryError, match="already registered"):
            reg.register(_make_profile())

    def test_list_names(self):
        reg = ProfileRegistry()
        reg.register(_make_profile("B"))
        reg.register(_make_profile("A"))
        assert reg.list_names() == ["A", "B"]

    def test_list_all(self):
        reg = ProfileRegistry()
        pa = _make_profile("A")
        pb = _make_profile("B")
        reg.register(pb)
        reg.register(pa)
        all_profiles = reg.list_all()
        assert [p.name for p in all_profiles] == ["A", "B"]

    def test_unregister(self):
        reg = ProfileRegistry()
        reg.register(_make_profile())
        assert reg.unregister("Test") is True
        assert reg.get("Test") is None

    def test_unregister_not_found(self):
        reg = ProfileRegistry()
        assert reg.unregister("Nope") is False


class TestOriginTracking:
    def test_default_origin(self):
        reg = ProfileRegistry()
        reg.register(_make_profile())
        assert reg.origin("Test") == ProfileOrigin.BUILDER

    def test_custom_origin(self):
        reg = ProfileRegistry()
        reg.register(_make_profile(), origin=ProfileOrigin.TOML)
        assert reg.origin("Test") == ProfileOrigin.TOML

    def test_origin_not_found(self):
        reg = ProfileRegistry()
        assert reg.origin("Nope") is None

    def test_unregister_clears_origin(self):
        reg = ProfileRegistry()
        reg.register(_make_profile())
        reg.unregister("Test")
        assert reg.origin("Test") is None


class TestBootstrap:
    def test_bootstrap_loads_five(self):
        reg = ProfileRegistry()
        reg.bootstrap()
        names = reg.list_names()
        assert len(names) == 5

    def test_bootstrap_origin_is_builtin(self):
        reg = ProfileRegistry()
        reg.bootstrap()
        for name in reg.list_names():
            assert reg.origin(name) == ProfileOrigin.BUILTIN

    def test_bootstrap_idempotent(self):
        reg = ProfileRegistry()
        reg.bootstrap()
        reg.bootstrap()  # should not raise
        assert len(reg.list_names()) == 5

    def test_bootstrap_does_not_overwrite(self):
        reg = ProfileRegistry()
        custom = _make_profile("ArchiMate 3.2")
        reg.register(custom, origin=ProfileOrigin.BUILDER)
        reg.bootstrap()
        # Custom version should still be there
        assert reg.origin("ArchiMate 3.2") == ProfileOrigin.BUILDER


class TestStoreIntegration:
    def test_register_persists(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        reg = ProfileRegistry(store=store)
        p = _make_profile()
        reg.register(p)
        assert len(store.list_profiles()) == 1
        latest = store.get_latest("Test")
        assert latest is not None
        assert latest.version == "1.0"
        store.close()

    def test_register_persists_origin(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        reg = ProfileRegistry(store=store)
        reg.register(_make_profile(), origin=ProfileOrigin.TOML)
        pv = store.get_latest("Test")
        assert pv.origin == "toml"
        store.close()

    def test_bootstrap_persists_to_store(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        reg = ProfileRegistry(store=store)
        reg.bootstrap()
        assert len(store.list_profiles()) == 5
        store.close()

    def test_bootstrap_idempotent_with_store(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        reg = ProfileRegistry(store=store)
        reg.bootstrap()
        reg2 = ProfileRegistry(store=store)
        reg2.bootstrap()  # same store, should not crash
        assert len(store.list_profiles()) == 5
        store.close()


class TestLoadFromStore:
    def test_load_from_store(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        store.store(_make_profile("X"))
        store.store(_make_profile("Y"))

        reg = ProfileRegistry(store=store)
        loaded = reg.load_from_store()
        assert loaded == 2
        assert reg.get("X") is not None
        assert reg.get("Y") is not None
        store.close()

    def test_load_from_store_skips_existing(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        store.store(_make_profile("X"))

        reg = ProfileRegistry(store=store)
        reg.register(_make_profile("X"), origin=ProfileOrigin.BUILDER)
        loaded = reg.load_from_store()
        assert loaded == 0  # X already registered
        assert reg.origin("X") == ProfileOrigin.BUILDER  # not overwritten
        store.close()

    def test_load_from_store_restores_origin(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        store.store(_make_profile("X"), origin=ProfileOrigin.TOML)

        reg = ProfileRegistry(store=store)
        reg.load_from_store()
        assert reg.origin("X") == ProfileOrigin.TOML
        store.close()

    def test_load_from_store_no_store(self):
        reg = ProfileRegistry()
        assert reg.load_from_store() == 0

    def test_bootstrap_all(self):
        store = SQLiteProfileStore(":memory:")
        store.initialize()
        store.store(_make_profile("Custom"))

        reg = ProfileRegistry(store=store)
        reg.bootstrap_all()
        assert len(reg.list_names()) == 6  # 5 builtin + 1 custom
        assert reg.get("Custom") is not None
        assert reg.origin("Custom") == ProfileOrigin.STORE
        store.close()

    def test_bootstrap_all_process_restart(self):
        """Simulate process restart: bootstrap_all on existing Store."""
        store = SQLiteProfileStore(":memory:")
        store.initialize()

        # Process 1
        reg1 = ProfileRegistry(store=store)
        reg1.bootstrap()
        reg1.register(_make_profile("Custom"), origin=ProfileOrigin.BUILDER)

        # Process 2 (new registry, same store)
        reg2 = ProfileRegistry(store=store)
        reg2.bootstrap_all()
        assert len(reg2.list_names()) == 6
        assert reg2.get("Custom") is not None
        store.close()
