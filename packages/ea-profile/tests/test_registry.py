"""Tests for ea_profile.registry module."""

import pytest

from ea_profile.registry import ProfileRegistry
from ea_profile.types import ProfileOrigin, ProfileRegistryError
from ea_profile.builder import ProfileBuilder
from ea_profile.store import SQLiteProfileStore


def _make_profile(name="TestProfile", version="1.0"):
    """Build a test profile."""
    b = ProfileBuilder(name, version=version, kernel_version="1.0")
    b.element("ElemA", kernel_type="structure", layer="Business", category="Structure")
    b.element("ElemB", kernel_type="item", layer="Business", category="Structure")
    b.element("ElemC", kernel_type="step", layer="Application", category="Behavior")
    b.relation("Rel1", kernel_relation="association")
    b.relation("Rel2", kernel_relation="composition")
    b.allow("@Structure", "@Structure", "Rel1", priority=50, rule_id="r-01")
    b.deny("@Behavior", "@Structure", "Rel1", priority=40, rule_id="r-02")
    b.deny("*", "*", "Rel1", priority=0, notes="fallback", rule_id="fb-Rel1-deny")
    return b.build()


class TestProfileRegistry:
    """Test ProfileRegistry class."""

    def test_register_and_get(self):
        """Test registering and retrieving a profile."""
        registry = ProfileRegistry()
        profile = _make_profile("MyProfile", "1.0")

        registry.register(profile)
        retrieved = registry.get("MyProfile")

        assert retrieved is not None
        assert retrieved.name == "MyProfile"
        assert retrieved.version == "1.0"

    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate name raises ProfileRegistryError."""
        registry = ProfileRegistry()
        profile1 = _make_profile("Duplicate", "1.0")
        profile2 = _make_profile("Duplicate", "2.0")

        registry.register(profile1)

        with pytest.raises(ProfileRegistryError) as exc_info:
            registry.register(profile2)

        assert "Duplicate" in str(exc_info.value)

    def test_list_names_returns_sorted(self):
        """Test list_names returns sorted list of profile names."""
        registry = ProfileRegistry()
        profile_c = _make_profile("ProfileC", "1.0")
        profile_a = _make_profile("ProfileA", "1.0")
        profile_b = _make_profile("ProfileB", "1.0")

        registry.register(profile_c)
        registry.register(profile_a)
        registry.register(profile_b)

        names = registry.list_names()

        assert names == ["ProfileA", "ProfileB", "ProfileC"]

    def test_list_all_returns_sorted_profiles(self):
        """Test list_all returns sorted list of profiles."""
        registry = ProfileRegistry()
        profile_c = _make_profile("ProfileC", "1.0")
        profile_a = _make_profile("ProfileA", "1.0")
        profile_b = _make_profile("ProfileB", "1.0")

        registry.register(profile_c)
        registry.register(profile_a)
        registry.register(profile_b)

        profiles = registry.list_all()

        assert len(profiles) == 3
        assert profiles[0].name == "ProfileA"
        assert profiles[1].name == "ProfileB"
        assert profiles[2].name == "ProfileC"

    def test_unregister_returns_true_when_exists(self):
        """Test unregister returns True when profile exists."""
        registry = ProfileRegistry()
        profile = _make_profile("ToRemove", "1.0")
        registry.register(profile)

        result = registry.unregister("ToRemove")

        assert result is True
        assert registry.get("ToRemove") is None

    def test_unregister_returns_false_when_not_exists(self):
        """Test unregister returns False when profile does not exist."""
        registry = ProfileRegistry()

        result = registry.unregister("NonExistent")

        assert result is False

    def test_origin_returns_registered_origin(self):
        """Test origin returns the registered origin."""
        registry = ProfileRegistry()
        profile = _make_profile("WithOrigin", "1.0")

        registry.register(profile, origin=ProfileOrigin.BUILDER)
        origin = registry.origin("WithOrigin")

        assert origin == ProfileOrigin.BUILDER

    def test_origin_returns_none_for_unknown(self):
        """Test origin returns None for unknown profile."""
        registry = ProfileRegistry()

        origin = registry.origin("Unknown")

        assert origin is None

    def test_register_without_store_in_memory_only(self):
        """Test register without store keeps profile in memory only."""
        registry = ProfileRegistry()
        profile = _make_profile("InMemory", "1.0")

        registry.register(profile)
        retrieved = registry.get("InMemory")

        assert retrieved is not None
        assert retrieved.name == "InMemory"

    def test_register_with_store_persists(self, tmp_path):
        """Test register with store persists the profile."""
        db_path = tmp_path / "profiles.db"
        store = SQLiteProfileStore(str(db_path))
        store.initialize()
        registry = ProfileRegistry(store=store)
        profile = _make_profile("Persisted", "1.0")

        registry.register(profile)

        # Verify it's persisted by loading from store directly
        pv = store.get_by_version("Persisted", "1.0")
        assert pv is not None
        assert pv.profile_name == "Persisted"

    def test_load_from_store(self, tmp_path):
        """Test load_from_store loads persisted profiles into new registry."""
        db_path = tmp_path / "profiles.db"
        store = SQLiteProfileStore(str(db_path))
        store.initialize()

        # First registry: register and persist
        registry1 = ProfileRegistry(store=store)
        profile1 = _make_profile("Profile1", "1.0")
        profile2 = _make_profile("Profile2", "1.0")
        registry1.register(profile1)
        registry1.register(profile2)

        # Second registry: load from store
        registry2 = ProfileRegistry(store=store)
        count = registry2.load_from_store()

        assert count == 2
        assert registry2.get("Profile1") is not None
        assert registry2.get("Profile2") is not None

    def test_load_from_store_skips_already_registered(self, tmp_path):
        """Test load_from_store skips already registered profiles."""
        db_path = tmp_path / "profiles.db"
        store = SQLiteProfileStore(str(db_path))
        store.initialize()

        # Register and persist profiles
        registry1 = ProfileRegistry(store=store)
        profile1 = _make_profile("Profile1", "1.0")
        profile2 = _make_profile("Profile2", "1.0")
        registry1.register(profile1)
        registry1.register(profile2)

        # New registry: register one profile, then load from store
        registry2 = ProfileRegistry(store=store)
        registry2.register(profile1)  # Already registered
        count = registry2.load_from_store()

        # Should only load Profile2 (Profile1 was already registered)
        assert count == 1
        assert registry2.get("Profile1") is not None
        assert registry2.get("Profile2") is not None

    def test_load_from_store_returns_zero_when_no_store(self):
        """Test load_from_store returns 0 when no store is configured."""
        registry = ProfileRegistry()  # No store

        count = registry.load_from_store()

        assert count == 0
