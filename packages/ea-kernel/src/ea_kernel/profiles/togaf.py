"""TOGAF 10 kernel profile. Data from togaf.toml."""

from pathlib import Path

from ea_kernel.profile_loader import load_profile

TOGAF_PROFILE = load_profile(Path(__file__).parent / "togaf.toml")
ALL_ELEMENTS = TOGAF_PROFILE.elements
ALL_RELATIONS = TOGAF_PROFILE.relations
ALL_RULES = TOGAF_PROFILE.validity_rules
