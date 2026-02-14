"""BPMN 2.0 kernel profile. Data from bpmn.toml."""

from pathlib import Path

from ea_kernel.profile_loader import load_profile

BPMN_PROFILE = load_profile(Path(__file__).parent / "bpmn.toml")
ALL_ELEMENTS = BPMN_PROFILE.elements
ALL_RELATIONS = BPMN_PROFILE.relations
ALL_RULES = BPMN_PROFILE.validity_rules
