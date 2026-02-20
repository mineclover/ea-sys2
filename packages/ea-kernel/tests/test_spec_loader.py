"""Tests for the TOML-based kernel rule loader."""

from pathlib import Path
from textwrap import dedent

import pytest
from ea_kernel.spec_loader import (
    RuleLoadError,
    load_kernel_rules,
)
from ea_kernel.types import (
    KernelConditionType,
    KernelValidityRule,
    Layer,
    LayerConstraint,
    RuleGroup,
)

SCRATCHPAD = Path(__file__).parent / "_scratch"


@pytest.fixture(autouse=True)
def _scratch_dir(tmp_path):
    """Provide a temp dir for custom TOML files."""
    global SCRATCHPAD
    SCRATCHPAD = tmp_path


def _write_toml(content: str) -> Path:
    """Write TOML content to a temp file and return its path."""
    p = SCRATCHPAD / "test_rules.toml"
    p.write_text(dedent(content))
    return p


# ═════════════════════════════════════════════════════════════════════════════
# 1. Basic Loading
# ═════════════════════════════════════════════════════════════════════════════

class TestLoaderBasic:
    """Verify load_kernel_rules() returns correct types and counts."""

    def test_returns_tuple_pair(self):
        rules, constraints = load_kernel_rules()
        assert isinstance(rules, tuple)
        assert isinstance(constraints, tuple)

    def test_total_rule_count(self):
        """69 explicit + 14 fallback = 83 total."""
        rules, _ = load_kernel_rules()
        assert len(rules) == 83

    def test_explicit_rule_count(self):
        rules, _ = load_kernel_rules()
        explicit = [r for r in rules if not r.id.startswith("fallback-")]
        assert len(explicit) == 69

    def test_fallback_count(self):
        rules, _ = load_kernel_rules()
        fallbacks = [r for r in rules if r.id.startswith("fallback-")]
        assert len(fallbacks) == len(RuleGroup)

    def test_fallback_properties(self):
        rules, _ = load_kernel_rules()
        for r in rules:
            if r.id.startswith("fallback-"):
                assert r.valid is False
                assert r.priority == 1
                assert r.source_pattern == "*"
                assert r.target_pattern == "*"

    def test_constraint_count(self):
        _, constraints = load_kernel_rules()
        assert len(constraints) == 2

    def test_all_rules_are_validity_rules(self):
        rules, _ = load_kernel_rules()
        for r in rules:
            assert isinstance(r, KernelValidityRule)

    def test_all_constraints_are_layer_constraints(self):
        _, constraints = load_kernel_rules()
        for c in constraints:
            assert isinstance(c, LayerConstraint)

    def test_unique_rule_ids(self):
        rules, _ = load_kernel_rules()
        ids = [r.id for r in rules]
        assert len(ids) == len(set(ids))


# ═════════════════════════════════════════════════════════════════════════════
# 2. Round-Trip Field Verification
# ═════════════════════════════════════════════════════════════════════════════

class TestRoundTrip:
    """Verify specific rules have correct field values."""

    @pytest.fixture(autouse=True)
    def _load(self):
        self.rules, self.constraints = load_kernel_rules()
        self.by_id = {r.id: r for r in self.rules}

    def test_mem_01_fields(self):
        r = self.by_id["mem-01"]
        assert r.source_pattern == "namespace*"
        assert r.target_pattern == "element*"
        assert r.relationship_name == "membership"
        assert r.valid is True
        assert r.priority == 40
        assert len(r.conditions) == 1
        assert r.conditions[0].condition_type == KernelConditionType.LAYER_ORDER

    def test_own_03_same_branch_condition(self):
        r = self.by_id["own-03"]
        assert r.conditions[0].condition_type == KernelConditionType.SAME_ENTITY_BRANCH
        assert r.priority == 70

    def test_own_04_deny_rule(self):
        r = self.by_id["own-04"]
        assert r.valid is False
        assert r.priority == 80
        assert r.source_pattern == "item"
        assert r.target_pattern == "structure"

    def test_spec_03_same_branch_condition(self):
        r = self.by_id["spec-03"]
        assert r.conditions[0].condition_type == KernelConditionType.SAME_ENTITY_BRANCH

    def test_assoc_01_fields(self):
        r = self.by_id["assoc-01"]
        assert r.source_pattern == "metatype*"
        assert r.target_pattern == "metatype*"
        assert r.relationship_name == "association"
        assert r.valid is True
        assert r.priority == 40

    def test_trig_03_high_priority_deny(self):
        r = self.by_id["trig-03"]
        assert r.valid is False
        assert r.priority == 90

    def test_succ_05_expression_gateway(self):
        r = self.by_id["succ-05"]
        assert r.source_pattern == "expression"
        assert r.target_pattern == "step*"
        assert r.priority == 50

    def test_layer_constraint_association(self):
        c = self.constraints[0]
        assert c.id == "lc-00-l4-l4-association"
        assert c.source_layer == Layer.L4
        assert c.target_layer == Layer.L4
        assert c.forbidden_relations == ("association",)
        assert c.allowed_pairs == (("step*", "state"), ("state", "step*"))
        assert c.priority == 90

    def test_layer_constraint_connector(self):
        c = self.constraints[1]
        assert c.id == "lc-01-l4-l4-connector"
        assert c.forbidden_relations == ("connector",)
        assert c.allowed_pairs == ()

    def test_default_valid_is_true(self):
        """Rules without explicit valid field default to True."""
        r = self.by_id["mem-02"]
        assert r.valid is True

    def test_default_conditions_empty(self):
        """Rules without conditions field have empty conditions."""
        r = self.by_id["mem-02"]
        assert r.conditions == ()


# ═════════════════════════════════════════════════════════════════════════════
# 3. Error Handling
# ═════════════════════════════════════════════════════════════════════════════

class TestLoaderErrors:
    """Verify loader raises RuleLoadError for invalid input."""

    def test_file_not_found(self):
        with pytest.raises(RuleLoadError, match="not found"):
            load_kernel_rules(Path("/nonexistent/path.toml"))

    def test_missing_source_field(self):
        p = _write_toml("""\
            [rules.bad-01]
            target = "feature"
            relation = "membership"
        """)
        with pytest.raises(RuleLoadError, match="source"):
            load_kernel_rules(p)

    def test_missing_target_field(self):
        p = _write_toml("""\
            [rules.bad-01]
            source = "feature"
            relation = "membership"
        """)
        with pytest.raises(RuleLoadError, match="target"):
            load_kernel_rules(p)

    def test_missing_relation_field(self):
        p = _write_toml("""\
            [rules.bad-01]
            source = "feature"
            target = "feature"
        """)
        with pytest.raises(RuleLoadError, match="relation"):
            load_kernel_rules(p)

    def test_unknown_condition(self):
        p = _write_toml("""\
            [rules.bad-01]
            source = "feature"
            target = "feature"
            relation = "membership"
            conditions = ["NONEXISTENT"]
        """)
        with pytest.raises(RuleLoadError, match="Unknown condition"):
            load_kernel_rules(p)

    def test_explicit_count_mismatch(self):
        p = _write_toml("""\
            [meta]
            total_explicit_rules = 99

            [rules.ok-01]
            source = "feature"
            target = "feature"
            relation = "membership"
        """)
        with pytest.raises(RuleLoadError, match="Expected 99"):
            load_kernel_rules(p)

    def test_constraint_count_mismatch(self):
        p = _write_toml("""\
            [meta]
            total_layer_constraints = 5
        """)
        with pytest.raises(RuleLoadError, match="Expected 5"):
            load_kernel_rules(p)

    def test_duplicate_constraint_ids(self):
        p = _write_toml("""\
            [[layer_constraints]]
            id = "lc-dup"
            source_layer = "L4"
            target_layer = "L4"
            forbidden = ["association"]

            [[layer_constraints]]
            id = "lc-dup"
            source_layer = "L4"
            target_layer = "L4"
            forbidden = ["connector"]
        """)
        with pytest.raises(RuleLoadError, match="unique id"):
            load_kernel_rules(p)

    def test_invalid_layer_in_constraint(self):
        p = _write_toml("""\
            [[layer_constraints]]
            source_layer = "L9"
            target_layer = "L4"
            forbidden = ["association"]
        """)
        with pytest.raises(RuleLoadError, match="invalid source_layer"):
            load_kernel_rules(p)

    def test_dict_condition_unknown_type(self):
        p = _write_toml("""\
            [rules.bad-01]
            source = "feature"
            target = "feature"
            relation = "membership"
            conditions = [{type = "NONEXISTENT"}]
        """)
        with pytest.raises(RuleLoadError, match="Unknown condition type"):
            load_kernel_rules(p)


# ═════════════════════════════════════════════════════════════════════════════
# 4. Custom TOML Loading
# ═════════════════════════════════════════════════════════════════════════════

class TestCustomToml:
    """Verify loader works with custom TOML paths."""

    def test_minimal_valid_toml(self):
        p = _write_toml("""\
            [rules.test-01]
            source = "feature"
            target = "feature"
            relation = "membership"
        """)
        rules, constraints = load_kernel_rules(p)
        assert len(rules) == 1
        assert len(constraints) == 0
        assert rules[0].id == "test-01"

    def test_with_fallbacks(self):
        p = _write_toml("""\
            [meta]
            fallback_relations = ["membership", "ownership"]

            [rules.test-01]
            source = "feature"
            target = "feature"
            relation = "membership"
        """)
        rules, _ = load_kernel_rules(p)
        assert len(rules) == 3  # 1 explicit + 2 fallbacks
        fallbacks = [r for r in rules if r.id.startswith("fallback-")]
        assert len(fallbacks) == 2

    def test_dict_condition_with_params(self):
        p = _write_toml("""\
            [rules.test-01]
            source = "feature"
            target = "feature"
            relation = "membership"
            conditions = [{type = "LAYER_ORDER", params = {min_gap = "2"}}]
        """)
        rules, _ = load_kernel_rules(p)
        cond = rules[0].conditions[0]
        assert cond.condition_type == KernelConditionType.LAYER_ORDER
        assert ("min_gap", "2") in cond.parameters

    def test_no_count_verification_when_absent(self):
        """When meta counts are absent, no verification is performed."""
        p = _write_toml("""\
            [rules.test-01]
            source = "a"
            target = "b"
            relation = "c"
        """)
        # Should not raise — no count in meta
        rules, _ = load_kernel_rules(p)
        assert len(rules) == 1
