"""SysML 2.0 kernel profile. Data from sysml2.toml."""

from pathlib import Path

from ea_kernel.profile_loader import load_profile

SYSML2_PROFILE = load_profile(Path(__file__).parent / "sysml2.toml")
ALL_ELEMENTS = SYSML2_PROFILE.elements
ALL_RELATIONS = SYSML2_PROFILE.relations
ALL_RULES = SYSML2_PROFILE.validity_rules
