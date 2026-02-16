"""Re-export from ea_profile for backward compatibility.

bootstrap() and bootstrap_all() remain here as they depend on
ea_kernel.profiles (kernel-specific built-in profiles).
"""

from ea_profile.registry import *  # noqa: F401, F403
from ea_profile.registry import ProfileRegistry as _ProfileRegistry


class ProfileRegistry(_ProfileRegistry):
    """Kernel-aware profile registry with bootstrap support."""

    def bootstrap_all(self) -> None:
        """Bootstrap built-in profiles and load any persisted profiles.

        Convenience for: bootstrap() + load_from_store().
        """
        self.bootstrap()
        self.load_from_store()

    def bootstrap(self) -> None:
        """Load all built-in profiles into the registry.

        Includes 5 framework profiles + 6 EA-sys layer profiles
        + 2 governance stack profiles.
        """
        from contextlib import suppress
        from dataclasses import replace

        from ea_kernel.profiles.archimate import ARCHIMATE_PROFILE
        from ea_kernel.profiles.bpmn import BPMN_PROFILE
        from ea_kernel.profiles.sysml2 import SYSML2_PROFILE
        from ea_kernel.profiles.togaf import TOGAF_PROFILE
        from ea_kernel.profiles.zachman import ZACHMAN_PROFILE
        from ea_profile.types import ProfileOrigin, ProfileStoreError

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

        # EA-sys layer profiles (6 layers, each with unique registry name)
        from ea_kernel.profiles.ea_sys import LAYER_ORDER, layer_path
        from ea_profile.loader import load_profile

        layer_name_map = {
            "infra": "EASystem-Infra",
            "governance": "EASystem-Governance",
            "decision": "EASystem-Decision",
            "needs": "EASystem-Needs",
            "kernel": "EASystem-Kernel",
            "flow": "EASystem-Flow",
            "web-kernel-viz": "EASystem-WebKernelViz",
            "development": "EASystem-Development",
        }
        for layer_key in LAYER_ORDER:
            reg_name = layer_name_map[layer_key]
            if reg_name in self._profiles:
                continue
            try:
                profile = load_profile(layer_path(layer_key))
                profile = replace(profile, name=reg_name)
                self._profiles[reg_name] = profile
                self._origins[reg_name] = ProfileOrigin.TOML
            except Exception:
                pass  # skip if TOML load fails

        # Governance profile stack (meta-model + external)
        from ea_kernel.profiles.governance_profile_stack import (
            PROFILE_FILE_MAP,
            profile_path,
        )

        gov_name_map = {
            "meta": "GovernanceStack-Meta",
            "external": "GovernanceStack-External",
        }
        for profile_id in PROFILE_FILE_MAP:
            reg_name = gov_name_map.get(profile_id, f"GovernanceStack-{profile_id}")
            if reg_name in self._profiles:
                continue
            try:
                profile = load_profile(profile_path(profile_id))
                profile = replace(profile, name=reg_name)
                self._profiles[reg_name] = profile
                self._origins[reg_name] = ProfileOrigin.TOML
            except Exception:
                pass  # skip if TOML load fails
