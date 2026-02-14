"""Tests for MCP server tool functions and server structure."""

from __future__ import annotations

import importlib.util
import json

import pytest

pytest.importorskip("mcp")

from ea_kernel.mcp_server import (
    kernel_describe_profile,
    kernel_describe_rule,
    kernel_get_entity_names,
    kernel_judge,
    kernel_list_entities,
    kernel_list_relations,
    kernel_list_rules,
)

# ── Tier 1: Tool function unit tests (no mcp dependency needed) ──────


class TestKernelListEntities:
    def test_returns_valid_json(self):
        result = json.loads(kernel_list_entities())
        assert "total" in result
        assert "layers" in result

    def test_has_layers(self):
        result = json.loads(kernel_list_entities())
        assert len(result["layers"]) > 0

    def test_total_positive(self):
        result = json.loads(kernel_list_entities())
        assert result["total"] > 0


class TestKernelListRelations:
    def test_returns_valid_json(self):
        result = json.loads(kernel_list_relations())
        assert "total" in result
        assert "layers" in result

    def test_has_relations(self):
        result = json.loads(kernel_list_relations())
        assert result["total"] > 0


class TestKernelListRules:
    def test_summary_without_filters(self):
        result = json.loads(kernel_list_rules())
        assert "total" in result
        assert "groups" in result
        assert result["total"] > 0

    def test_filter_by_valid_group(self):
        # Get a valid group name first
        summary = json.loads(kernel_list_rules())
        group_name = summary["groups"][0]["name"]
        result = json.loads(kernel_list_rules(group=group_name))
        assert "total" in result
        assert "rules" in result

    def test_filter_by_nonexistent_group(self):
        result = json.loads(kernel_list_rules(group="nonexistent"))
        assert "error" in result
        assert "valid_groups" in result

    def test_filter_by_relation(self):
        result = json.loads(kernel_list_rules(relation="Specialization"))
        assert "total" in result


class TestKernelDescribeProfile:
    def test_existing_profile(self):
        result = json.loads(kernel_describe_profile("ArchiMate"))
        assert "name" in result
        assert result["name"] == "ArchiMate"
        assert "element_count" in result
        assert "rule_summary" in result

    def test_nonexistent_profile(self):
        result = json.loads(kernel_describe_profile("NonExistent"))
        assert "error" in result


class TestKernelDescribeRule:
    def test_existing_rule(self):
        # Get a valid rule id first
        rules_data = json.loads(kernel_list_rules())
        group_name = rules_data["groups"][0]["name"]
        group_rules = json.loads(kernel_list_rules(group=group_name))
        rule_id = group_rules["rules"][0]["id"]

        result = json.loads(kernel_describe_rule(rule_id))
        assert "id" in result
        assert "metadata" in result

    def test_nonexistent_rule(self):
        result = json.loads(kernel_describe_rule("nonexistent-rule-id"))
        assert "error" in result


class TestKernelJudge:
    def test_valid_triple(self):
        result = json.loads(kernel_judge("classifier", "classifier", "specialization"))
        assert "verdict" in result
        assert "confidence" in result
        assert "evidence" in result

    def test_invalid_source(self):
        result = json.loads(kernel_judge("FakeEntity", "classifier", "specialization"))
        assert "error" in result
        assert "valid_entities" in result

    def test_invalid_target(self):
        result = json.loads(kernel_judge("classifier", "FakeEntity", "specialization"))
        assert "error" in result

    def test_invalid_relation(self):
        result = json.loads(kernel_judge("classifier", "classifier", "FakeRelation"))
        assert "error" in result
        assert "valid_relations" in result


class TestKernelGetEntityNames:
    def test_returns_sorted_list(self):
        result = json.loads(kernel_get_entity_names())
        assert isinstance(result, list)
        assert len(result) > 0
        assert result == sorted(result)


# ── Tier 2: MCP server structure (requires mcp SDK) ─────────────────

HAS_MCP = importlib.util.find_spec("mcp.server.fastmcp") is not None


@pytest.mark.skipif(not HAS_MCP, reason="mcp SDK not installed")
class TestMCPServerStructure:
    def test_server_has_seven_tools(self):
        from ea_kernel.mcp_server import mcp
        tools = mcp._tool_manager._tools
        assert len(tools) == 7

    def test_all_tools_have_kernel_prefix(self):
        from ea_kernel.mcp_server import mcp
        tools = mcp._tool_manager._tools
        for name in tools:
            assert name.startswith("kernel_"), f"Tool {name} missing kernel_ prefix"

    def test_tool_names(self):
        from ea_kernel.mcp_server import mcp
        tools = mcp._tool_manager._tools
        expected = {
            "kernel_list_entities",
            "kernel_list_relations",
            "kernel_list_rules",
            "kernel_describe_profile",
            "kernel_describe_rule",
            "kernel_judge",
            "kernel_get_entity_names",
        }
        assert set(tools.keys()) == expected
