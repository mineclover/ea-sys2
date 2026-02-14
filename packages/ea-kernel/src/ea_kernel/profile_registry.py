"""Central registry for profile discovery and access.

In-memory cache backed by optional StoragePort for persistence.
"""

from __future__ import annotations

from contextlib import suppress

from ea_kernel.profile_store import StoragePort
from ea_kernel.profile_types import (
    KernelProfile,
    ProfileOrigin,
    ProfileRegistryError,
    ProfileStoreError,
)


class ProfileRegistry:
    """Central registry for profile discovery and access."""

    def __init__(self, store: StoragePort | None = None) -> None:
        self._profiles: dict[str, KernelProfile] = {}
        self._origins: dict[str, ProfileOrigin] = {}
        self._store = store

    # ── Register ──────────────────────────────────────────────────

    def register(self, profile: KernelProfile, *,
                 origin: ProfileOrigin = ProfileOrigin.BUILDER) -> None:
        """Register a profile in the registry (and persist if store present).

        If the same (profile_name, version) already exists in the store,
        the store write is skipped (the data is already persisted).
        """
        if profile.name in self._profiles:
            raise ProfileRegistryError(
                f"Profile already registered: '{profile.name}'"
            )
        self._profiles[profile.name] = profile
        self._origins[profile.name] = origin

        if self._store is not None:
            with suppress(ProfileStoreError):
                self._store.store(profile, origin=origin)

    def get(self, name: str) -> KernelProfile | None:
        return self._profiles.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._profiles.keys())

    def list_all(self) -> list[KernelProfile]:
        return [self._profiles[n] for n in sorted(self._profiles.keys())]

    def unregister(self, name: str) -> bool:
        if name not in self._profiles:
            return False
        del self._profiles[name]
        del self._origins[name]
        return True

    def origin(self, name: str) -> ProfileOrigin | None:
        return self._origins.get(name)

    # ── Store sync ─────────────────────────────────────────────────

    def load_from_store(self) -> int:
        """Load all latest profile versions from the store into the registry.

        Skips profiles already registered. Returns the number loaded.
        """
        if self._store is None:
            return 0
        loaded = 0
        for name in self._store.list_profiles():
            if name in self._profiles:
                continue
            pv = self._store.get_latest(name)
            if pv is None:
                continue
            from ea_kernel.profile_serializer import dict_to_profile
            profile = dict_to_profile(pv.data)
            self._profiles[name] = profile
            if pv.origin:
                try:
                    self._origins[name] = ProfileOrigin(pv.origin)
                except ValueError:
                    self._origins[name] = ProfileOrigin.STORE
            else:
                self._origins[name] = ProfileOrigin.STORE
            loaded += 1
        return loaded

    def bootstrap_all(self) -> None:
        """Bootstrap built-in profiles and load any persisted profiles.

        Convenience for: bootstrap() + load_from_store().
        """
        self.bootstrap()
        self.load_from_store()

    # ── Bootstrap ─────────────────────────────────────────────────

    def bootstrap(self) -> None:
        """Load all 5 built-in profiles into the registry."""
        from ea_kernel.profiles.archimate import ARCHIMATE_PROFILE
        from ea_kernel.profiles.bpmn import BPMN_PROFILE
        from ea_kernel.profiles.sysml2 import SYSML2_PROFILE
        from ea_kernel.profiles.togaf import TOGAF_PROFILE
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE

        for profile in (
            ARCHIMATE_PROFILE,
            TOGAF_PROFILE,
            ZACHMAN_PROFILE,
            BPMN_PROFILE,
            SYSML2_PROFILE,
        ):
            if profile.name not in self._profiles:
                self._profiles[profile.name] = profile
                self._origins[profile.name] = ProfileOrigin.BUILTIN
                if self._store is not None:
                    with suppress(ProfileStoreError):
                        self._store.store(profile, origin=ProfileOrigin.BUILTIN)
