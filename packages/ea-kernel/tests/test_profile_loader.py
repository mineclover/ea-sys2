"""Tests for v2 TOML profile loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from ea_kernel.definition import KERNEL_SCHEMA
from ea_kernel.profile_loader import load_profile_from_content, ProfileLoadError


# ═════════════════════════════════════════════════════════════════════════════
# 1. Valid TOML profiles
# ═════════════════════════════════════════════════════════════════════════════

MINIMAL_TOML = """\
[profile]
name = "Minimal"
version = "1.0"
kernel_version = "2.5.0"

[categories]
Thing = "item"

[[elements]]
name = "Widget"
layer = "Core"
category = "Thing"

[[relations]]
name = "uses"
kernel_relation = "association"

[[rules]]
source = "Widget"
target = "Widget"
relation = "uses"
priority = 40
notes = "Widget self-use"
"""


class TestValidLoad:
    def test_minimal(self):
        p = load_profile_from_content(MINIMAL_TOML)
        assert p.name == "Minimal"
        assert p.version == "1.0"
        assert len(p.elements) == 1
        assert len(p.relations) == 1
        assert p.get_element("Widget").kernel_type == "item"

    def test_with_metadata(self):
        toml = """\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"
id_prefix = "tst"
standard = "Test Standard"
organization = "Test Corp"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "item"

[[relations]]
name = "r"
kernel_relation = "association"
"""
        p = load_profile_from_content(toml)
        assert p.metadata is not None
        assert p.metadata.standard == "Test Standard"
        assert p.metadata.organization == "Test Corp"

    def test_deny_rule(self):
        toml = """\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "item"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
source = "A"
target = "A"
relation = "r"
valid = false
priority = 80
notes = "Denied"
"""
        p = load_profile_from_content(toml)
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 1
        assert explicit[0].valid is False

    def test_auto_fallback_generated(self):
        p = load_profile_from_content(MINIMAL_TOML)
        fallbacks = [r for r in p.validity_rules if r.priority == 1]
        assert len(fallbacks) == 1
        assert fallbacks[0].relationship_name == "uses"

    def test_category_mapping(self):
        toml = """\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[categories]
Data = "item"
Process = "step"

[[elements]]
name = "Widget"
layer = "Core"
category = "Data"

[[elements]]
name = "Task"
layer = "Core"
category = "Process"

[[relations]]
name = "r"
kernel_relation = "association"
"""
        p = load_profile_from_content(toml)
        assert p.get_element("Widget").kernel_type == "item"
        assert p.get_element("Task").kernel_type == "step"

    def test_with_kernel_validation(self):
        p = load_profile_from_content(MINIMAL_TOML, KERNEL_SCHEMA)
        assert len(p.elements) == 1

    def test_multiple_rules(self):
        toml = """\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[categories]
A = "item"
B = "step"

[[elements]]
name = "X"
layer = "L"
category = "A"

[[elements]]
name = "Y"
layer = "L"
category = "B"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
source = "@A"
target = "@B"
relation = "r"
priority = 40

[[rules]]
source = "@B"
target = "@A"
relation = "r"
priority = 40
"""
        p = load_profile_from_content(toml)
        explicit = [r for r in p.validity_rules if r.priority > 1]
        assert len(explicit) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 2. Error cases
# ═════════════════════════════════════════════════════════════════════════════

class TestLoadErrors:
    def test_invalid_toml(self):
        with pytest.raises(ProfileLoadError, match="Invalid TOML"):
            load_profile_from_content("not valid {{{{ toml")

    def test_missing_name(self):
        with pytest.raises(ProfileLoadError, match="profile.name"):
            load_profile_from_content("""\
[profile]
version = "1.0"
kernel_version = "2.5.0"
""")

    def test_missing_version(self):
        with pytest.raises(ProfileLoadError, match="profile.version"):
            load_profile_from_content("""\
[profile]
name = "Test"
kernel_version = "2.5.0"
""")

    def test_missing_kernel_version(self):
        with pytest.raises(ProfileLoadError, match="profile.kernel_version"):
            load_profile_from_content("""\
[profile]
name = "Test"
version = "1.0"
""")

    def test_element_missing_name(self):
        with pytest.raises(ProfileLoadError, match="name"):
            load_profile_from_content("""\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[[elements]]
layer = "L"
category = "C"
kernel_type = "item"

[[relations]]
name = "r"
kernel_relation = "association"
""")

    def test_element_missing_layer(self):
        with pytest.raises(ProfileLoadError, match="layer"):
            load_profile_from_content("""\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[[elements]]
name = "A"
category = "C"
kernel_type = "item"

[[relations]]
name = "r"
kernel_relation = "association"
""")

    def test_relation_missing_kernel_relation(self):
        with pytest.raises(ProfileLoadError, match="kernel_relation"):
            load_profile_from_content("""\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "item"

[[relations]]
name = "r"
""")

    def test_rule_missing_source(self):
        with pytest.raises(ProfileLoadError, match="source, target, relation"):
            load_profile_from_content("""\
[profile]
name = "Test"
version = "1.0"
kernel_version = "2.5.0"

[[elements]]
name = "A"
layer = "L"
category = "C"
kernel_type = "item"

[[relations]]
name = "r"
kernel_relation = "association"

[[rules]]
target = "A"
relation = "r"
""")

    def test_file_not_found(self):
        from ea_kernel.profile_loader import load_profile
        with pytest.raises(ProfileLoadError, match="not found"):
            load_profile(Path("/nonexistent/file.toml"))
