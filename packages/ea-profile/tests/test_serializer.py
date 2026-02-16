"""Tests for ea_profile.serializer — dict/JSON round-trip and content hashing."""

from ea_profile.builder import ProfileBuilder
from ea_profile.serializer import (
    compute_content_hash,
    dict_to_profile,
    json_to_profile,
    profile_to_dict,
    profile_to_json,
)
from ea_profile.types import RuleCondition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_profile(with_metadata: bool = True):
    b = (
        ProfileBuilder("Ser", version="1.0", kernel_version="2.0")
        .element("A", layer="L", category="C", kernel_type="structure")
        .element("B", layer="L", category="C", kernel_type="item")
        .relation("r", kernel_relation="association")
        .allow("A", "B", "r", conditions=(RuleCondition("same_layer"),))
    )
    if with_metadata:
        b.metadata(standard="StdX", organization="OrgX")
    return b.build()


# ---------------------------------------------------------------------------
# Dict round-trip
# ---------------------------------------------------------------------------

class TestDictRoundTrip:
    def test_round_trip(self):
        original = _sample_profile()
        d = profile_to_dict(original)
        restored = dict_to_profile(d)
        assert restored.name == original.name
        assert restored.version == original.version
        assert restored.kernel_version == original.kernel_version
        assert len(restored.elements) == len(original.elements)
        assert len(restored.relations) == len(original.relations)
        assert len(restored.validity_rules) == len(original.validity_rules)

    def test_metadata_round_trip(self):
        original = _sample_profile(with_metadata=True)
        d = profile_to_dict(original)
        restored = dict_to_profile(d)
        assert restored.metadata is not None
        assert restored.metadata.standard == "StdX"
        assert restored.metadata.organization == "OrgX"

    def test_no_metadata_round_trip(self):
        original = _sample_profile(with_metadata=False)
        d = profile_to_dict(original)
        restored = dict_to_profile(d)
        assert restored.metadata is None


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------

class TestJsonRoundTrip:
    def test_round_trip(self):
        original = _sample_profile()
        json_str = profile_to_json(original)
        restored = json_to_profile(json_str)
        assert restored.name == original.name
        assert len(restored.elements) == len(original.elements)
        assert len(restored.validity_rules) == len(original.validity_rules)

    def test_json_is_string(self):
        p = _sample_profile()
        json_str = profile_to_json(p)
        assert isinstance(json_str, str)
        assert '"name": "Ser"' in json_str


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_deterministic(self):
        p = _sample_profile()
        h1 = compute_content_hash(p)
        h2 = compute_content_hash(p)
        assert h1 == h2

    def test_different_for_different_profiles(self):
        p1 = _sample_profile()
        p2 = (
            ProfileBuilder("Other", version="2.0", kernel_version="2.0")
            .element("X", layer="L", category="C", kernel_type="structure")
            .relation("r", kernel_relation="association")
            .build()
        )
        assert compute_content_hash(p1) != compute_content_hash(p2)

    def test_hash_is_hex_string(self):
        p = _sample_profile()
        h = compute_content_hash(p)
        assert len(h) == 64  # SHA256 hex
        assert all(c in "0123456789abcdef" for c in h)
