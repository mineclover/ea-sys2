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

def _sample_profile(
    with_metadata: bool = True,
    with_state_transitions: bool = False,
    with_artifact_types: bool = False,
    with_layer_stack: bool = False,
):
    b = (
        ProfileBuilder("Ser", version="1.0", kernel_version="2.0")
        .element("A", layer="L", category="C", kernel_type="structure")
        .element("B", layer="L", category="C", kernel_type="item")
        .relation("r", kernel_relation="association")
        .allow("A", "B", "r", conditions=(RuleCondition("same_layer"),))
    )
    if with_state_transitions:
        b.add_state_transition(
            "draft",
            "approved",
            guard_condition="has_review",
            description="Review complete",
        )
    if with_artifact_types:
        b.add_artifact_type(
            "api_endpoint",
            "function",
            description="HTTP endpoint artifact",
            kernel_element_pattern="*Endpoint*",
        )
    if with_layer_stack:
        b.set_layer_stack(
            definition_flow="top_down",
            runtime_flow="bottom_up",
            feedback_flow="closed_loop",
        )
        b.add_layer_definition(
            "Domain",
            1,
            responsibility="Define intent",
            model_perspective="why",
        )
        b.add_layer_definition(
            "Application",
            2,
            depends_on=("Domain",),
            responsibility="Coordinate use cases",
            model_perspective="how",
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

    def test_state_transitions_round_trip(self):
        original = _sample_profile(with_state_transitions=True)
        d = profile_to_dict(original)
        restored = dict_to_profile(d)
        assert len(restored.state_transitions) == 1
        transition = restored.state_transitions[0]
        assert transition.from_state == "draft"
        assert transition.to_state == "approved"
        assert transition.guard_condition == "has_review"

    def test_artifact_types_round_trip(self):
        original = _sample_profile(with_artifact_types=True)
        d = profile_to_dict(original)
        restored = dict_to_profile(d)
        assert len(restored.artifact_types) == 1
        artifact_type = restored.artifact_types[0]
        assert artifact_type.name == "api_endpoint"
        assert artifact_type.tier == "function"
        assert artifact_type.description == "HTTP endpoint artifact"
        assert artifact_type.kernel_element_pattern == "*Endpoint*"

    def test_layer_stack_round_trip(self):
        original = _sample_profile(with_layer_stack=True)
        d = profile_to_dict(original)
        restored = dict_to_profile(d)
        assert restored.layer_stack is not None
        assert restored.layer_stack.definition_flow == "top_down"
        assert restored.layer_stack.runtime_flow == "bottom_up"
        assert restored.layer_stack.feedback_flow == "closed_loop"
        assert len(restored.layer_stack.layers) == 2
        assert restored.layer_stack.layers[1].depends_on == ("Domain",)


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
