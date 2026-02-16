"""Tests for ea_decision.registry module."""

from ea_decision.pattern import DecisionComplexity, DecisionPattern
from ea_decision.registry import DecisionRegistry, _as_pattern_key


class TestAsPatternKey:
    """Test _as_pattern_key helper."""

    def test_str_input(self):
        assert _as_pattern_key("simple") == "simple"

    def test_dict_with_en(self):
        assert _as_pattern_key({"en": "English", "ko": "한국어"}) == "English"

    def test_dict_without_en(self):
        result = _as_pattern_key({"ko": "한국어", "ja": "日本語"})
        # Falls back to first value
        assert result in ("한국어", "日本語")

    def test_empty_dict(self):
        assert _as_pattern_key({}) == ""


def _make_pattern(name="TestPattern", complexity=DecisionComplexity.TRIVIAL):
    """Create a minimal DecisionPattern for testing."""
    return DecisionPattern(
        name=name,
        description="Test description",
        complexity=complexity,
    )


class TestDecisionRegistry:
    """Test DecisionRegistry class."""

    def test_register_and_get(self):
        reg = DecisionRegistry()
        p = _make_pattern("MyPattern")
        reg.register(p)
        assert reg.get_pattern("MyPattern") is p

    def test_get_pattern_not_found(self):
        reg = DecisionRegistry()
        assert reg.get_pattern("NonExistent") is None

    def test_register_i18n_name(self):
        reg = DecisionRegistry()
        p = DecisionPattern(
            name={"en": "EnglishName", "ko": "한국어이름"},
            description="desc",
            complexity=DecisionComplexity.STRUCTURAL,
        )
        reg.register(p)
        # Registered under English name
        assert reg.get_pattern("EnglishName") is p

    def test_register_overwrites(self):
        reg = DecisionRegistry()
        p1 = _make_pattern("Same")
        p2 = DecisionPattern(
            name="Same",
            description="Newer",
            complexity=DecisionComplexity.STRATEGIC,
        )
        reg.register(p1)
        reg.register(p2)
        assert reg.get_pattern("Same") is p2

    def test_list_patterns_returns_copy(self):
        reg = DecisionRegistry()
        p1 = _make_pattern("A")
        p2 = _make_pattern("B")
        reg.register(p1)
        reg.register(p2)

        patterns = reg.list_patterns()
        assert len(patterns) == 2
        assert "A" in patterns
        assert "B" in patterns

        # Modifying copy doesn't affect registry
        patterns.pop("A")
        assert reg.get_pattern("A") is p1

    def test_list_patterns_empty(self):
        reg = DecisionRegistry()
        assert reg.list_patterns() == {}

    def test_multiple_patterns(self):
        reg = DecisionRegistry()
        patterns = [_make_pattern(f"P{i}") for i in range(5)]
        for p in patterns:
            reg.register(p)

        listed = reg.list_patterns()
        assert len(listed) == 5
        for i in range(5):
            assert reg.get_pattern(f"P{i}") is not None
