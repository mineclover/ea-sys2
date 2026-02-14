"""Zachman Framework kernel profile. Data from zachman.toml."""

from pathlib import Path

from ea_kernel.profile_loader import load_profile

ZACHMAN_PROFILE = load_profile(Path(__file__).parent / "zachman.toml")
ALL_ELEMENTS = ZACHMAN_PROFILE.elements
ALL_RELATIONS = ZACHMAN_PROFILE.relations
ALL_RULES = ZACHMAN_PROFILE.validity_rules
