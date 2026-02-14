from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ea_kernel.client.rule_query import RuleQueryClient, _escape, _row_to_dict


@dataclass(frozen=True)
class _FakeAttrType:
    label: str
    value_type: str

    def get_label(self) -> str:
        return self.label

    def get_value_type(self) -> str:
        return self.value_type


@dataclass(frozen=True)
class _FakeAttr:
    label: str
    value_type: str
    value: Any

    def get_type(self) -> _FakeAttrType:
        return _FakeAttrType(self.label, self.value_type)

    def get_boolean(self) -> bool:
        return bool(self.value)

    def get_integer(self) -> int:
        return int(self.value)

    def get_string(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class _FakeEntity:
    attrs: tuple[_FakeAttr, ...]

    def get_has(self) -> tuple[_FakeAttr, ...]:
        return self.attrs


class _FakeKernelDBClient:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.last_query: str | None = None

    def execute_read(self, query: str) -> list[Any]:
        self.last_query = query
        return self.rows


def _fake_row(*attrs: _FakeAttr) -> dict[str, Any]:
    return {"r": _FakeEntity(attrs)}


def test_escape_handles_backslash_quote_and_newline() -> None:
    raw = 'path\\name "quoted"\nline2'
    assert _escape(raw) == 'path\\\\name \\"quoted\\"\\nline2'


def test_row_to_dict_flattens_single_values_and_keeps_multivalue_lists() -> None:
    row = _fake_row(
        _FakeAttr("rule_id", "string", "r-1"),
        _FakeAttr("rule_priority", "integer", 50),
        _FakeAttr("rule_valid", "boolean", True),
        _FakeAttr("rule_tag", "string", "kernel"),
        _FakeAttr("rule_tag", "string", "governance"),
    )

    result = _row_to_dict(row)

    assert result["rule_id"] == "r-1"
    assert result["rule_priority"] == 50
    assert result["rule_valid"] is True
    assert result["rule_tag"] == ["kernel", "governance"]


def test_query_axes_build_expected_typeql_and_parse_rows() -> None:
    rows = [_fake_row(_FakeAttr("rule_id", "string", "r-domain"))]
    client = _FakeKernelDBClient(rows)
    query = RuleQueryClient(client)

    result = query.by_domain('ops "a"\nline')

    assert result[0]["rule_id"] == "r-domain"
    assert client.last_query is not None
    assert 'has rule_domain "ops \\"a\\"\\nline"' in client.last_query
    assert client.last_query.startswith("match $r isa validity_rule")


def test_rules_for_relationship_uses_relationship_name_axis() -> None:
    client = _FakeKernelDBClient([_fake_row(_FakeAttr("rule_id", "string", "r-rel"))])
    query = RuleQueryClient(client)

    _ = query.rules_for_relationship("specialization")

    assert client.last_query is not None
    assert 'has relationship_name "specialization"' in client.last_query


def test_total_count_returns_first_count_result() -> None:
    client = _FakeKernelDBClient([3])
    query = RuleQueryClient(client)

    assert query.total_count() == 3
    assert client.last_query == "match $r isa validity_rule; select $r; count;"


def test_total_count_returns_zero_for_empty_result() -> None:
    client = _FakeKernelDBClient([])
    query = RuleQueryClient(client)
    assert query.total_count() == 0
