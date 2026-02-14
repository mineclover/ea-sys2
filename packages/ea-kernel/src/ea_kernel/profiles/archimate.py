"""ArchiMate 3.2 kernel profile. Data from archimate.toml."""

from pathlib import Path

from ea_kernel.profile_loader import load_profile

ARCHIMATE_PROFILE = load_profile(Path(__file__).parent / "archimate.toml")
ALL_ELEMENTS = ARCHIMATE_PROFILE.elements
ALL_RELATIONS = ARCHIMATE_PROFILE.relations
ALL_RULES = ARCHIMATE_PROFILE.validity_rules
