"""TypeQL query wrapper for validity_rule entities.

Provides the same query axes as the Python RuleCorpus
(by_domain, by_tag, by_category, by_confidence)
plus TypeDB-specific queries (rules_for_relationship, total_count).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ea_kernel.client.connection import KernelDBClient


def _escape(s: str) -> str:
    """Escape a string for TypeQL string literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a TypeDB result row to a plain dict."""
    r = row.get("r")
    attrs: dict[str, list[Any]] = {}
    for attr in r.get_has():
        label = attr.get_type().get_label()
        vtype = attr.get_type().get_value_type()
        if vtype == "boolean":
            attrs.setdefault(label, []).append(attr.get_boolean())
        elif vtype == "integer":
            attrs.setdefault(label, []).append(attr.get_integer())
        else:
            attrs.setdefault(label, []).append(attr.get_string())
    # Flatten single-value attributes, keep multi-value as lists
    result: dict[str, Any] = {}
    for k, v in attrs.items():
        result[k] = v if len(v) > 1 else v[0]
    return result


class RuleQueryClient:
    """TypeQL query client for validity_rule entities."""

    def __init__(self, client: KernelDBClient) -> None:
        self._client = client

    def _fetch(self, where_clause: str) -> list[dict[str, Any]]:
        query = f"match $r isa validity_rule, {where_clause}; select $r;"
        rows = self._client.execute_read(query)
        return [_row_to_dict(row) for row in rows]

    def by_domain(self, domain: str) -> list[dict[str, Any]]:
        return self._fetch(f'has rule_domain "{_escape(domain)}"')

    def by_tag(self, tag: str) -> list[dict[str, Any]]:
        return self._fetch(f'has rule_tag "{_escape(tag)}"')

    def by_category(self, category: str) -> list[dict[str, Any]]:
        return self._fetch(f'has rule_category "{_escape(category)}"')

    def by_confidence(self, confidence: str) -> list[dict[str, Any]]:
        return self._fetch(f'has rule_confidence "{_escape(confidence)}"')

    def rules_for_relationship(self, rel: str) -> list[dict[str, Any]]:
        return self._fetch(f'has relationship_name "{_escape(rel)}"')

    def total_count(self) -> int:
        query = "match $r isa validity_rule; select $r; count;"
        results = self._client.execute_read(query)
        if results:
            return int(results[0])
        return 0
