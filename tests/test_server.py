"""Smoke tests for the MCP server."""

from __future__ import annotations

from snip_mcp.server import TOOLS, _dispatch


class TestToolDefinitions:
    def test_has_18_tools(self) -> None:
        assert len(TOOLS) == 18

    def test_tool_names(self) -> None:
        expected = {
            "index_folder",
            "list_repos",
            "get_file_tree",
            "get_file_outline",
            "get_file_content",
            "get_repo_outline",
            "get_symbol",
            "get_symbols",
            "search_symbols",
            "search_text",
            "search_columns",
            "find_importers",
            "find_references",
            "invalidate_cache",
            "get_stats",
            "get_call_graph",
            "get_callers",
            "get_change_impact",
        }
        actual = {t.name for t in TOOLS}
        assert actual == expected

    def test_all_tools_have_schemas(self) -> None:
        for tool in TOOLS:
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema
            assert tool.inputSchema["type"] == "object"

    def test_all_tools_have_descriptions(self) -> None:
        for tool in TOOLS:
            assert tool.description
            assert len(tool.description) > 10


class TestDispatch:
    def test_unknown_tool(self) -> None:
        result = _dispatch("nonexistent_tool", {})
        assert "error" in result

    def test_list_repos_dispatch(self) -> None:
        result = _dispatch("list_repos", {})
        assert "data" in result

    def test_index_folder_bad_path(self) -> None:
        result = _dispatch("index_folder", {"folder_path": "/nonexistent/path"})
        assert "error" in result["data"]

    def test_get_stats_dispatch(self) -> None:
        result = _dispatch("get_stats", {})
        assert "session" in result
        assert "cumulative" in result
        # Legacy keys
        assert "total_retrievals" in result
        assert "savings_pct" in result
