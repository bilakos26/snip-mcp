"""Snip MCP server — stdio transport, 29 tool schemas, call dispatch."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger("snip-mcp")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    Tool(
        name="index_folder",
        description=(
            "Index a local folder using tree-sitter AST parsing. Extracts symbols "
            "(functions, classes, methods, etc.) from source files in 23 languages. "
            "Supports incremental indexing — only re-parses changed files."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "folder_path": {
                    "type": "string",
                    "description": "Absolute path to the folder to index.",
                },
                "force": {
                    "type": "boolean",
                    "description": "Force re-index all files, ignoring cache.",
                    "default": False,
                },
                "max_files": {
                    "type": "integer",
                    "description": "Maximum number of files to index.",
                    "default": 50000,
                },
            },
            "required": ["folder_path"],
        },
    ),
    Tool(
        name="list_repos",
        description="List all locally indexed repositories/folders with their stats.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_file_tree",
        description=(
            "Get the directory tree of an indexed folder, annotated with languages "
            "and optionally symbol counts."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth to show.",
                    "default": 5,
                },
                "show_symbols": {
                    "type": "boolean",
                    "description": "Annotate files with symbol counts.",
                    "default": False,
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="get_file_outline",
        description=(
            "Get the symbol hierarchy/outline for a specific file — shows all "
            "functions, classes, methods, etc. with their signatures and nesting."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file within the repo.",
                },
            },
            "required": ["repo_path", "file_path"],
        },
    ),
    Tool(
        name="get_file_content",
        description=(
            "Get the content of a file, optionally limited to a specific line range. "
            "More token-efficient than reading the whole file when you only need a section."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file within the repo.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "1-based start line (inclusive).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "1-based end line (inclusive).",
                },
            },
            "required": ["repo_path", "file_path"],
        },
    ),
    Tool(
        name="get_repo_outline",
        description=(
            "Get a high-level overview of an indexed repository: directory structure, "
            "language breakdown, symbol kind distribution, and top files."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="get_symbol",
        description=(
            "Retrieve a single symbol's full source code using O(1) byte-offset seeking. "
            "Much more token-efficient than reading the entire file."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "symbol_id": {
                    "type": "string",
                    "description": "Symbol ID (format: file::kind::name::line).",
                },
            },
            "required": ["repo_path", "symbol_id"],
        },
    ),
    Tool(
        name="get_symbols",
        description=(
            "Batch retrieve multiple symbols' source code in one call. "
            "Each symbol is fetched via O(1) byte-offset seeking."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "symbol_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of symbol IDs to retrieve.",
                },
            },
            "required": ["repo_path", "symbol_ids"],
        },
    ),
    Tool(
        name="search_symbols",
        description=(
            "Search symbols using weighted scoring: exact name match (+100), "
            "prefix (+20), substring (+10), signature (+8), docstring (+5), "
            "file path (+3). Filter by kind and file pattern."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query string.",
                },
                "kind": {
                    "type": "string",
                    "description": "Filter by symbol kind (function, class, method, etc.).",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Filter by file path substring.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 20,
                },
            },
            "required": ["repo_path", "query"],
        },
    ),
    Tool(
        name="search_text",
        description=(
            "Full-text search across all indexed files with context lines. "
            "Supports regex and case-sensitive modes."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "query": {
                    "type": "string",
                    "description": "Search string or regex pattern.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Filter by file path substring.",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case-sensitive search.",
                    "default": False,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Context lines before/after match.",
                    "default": 2,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 50,
                },
                "regex": {
                    "type": "boolean",
                    "description": "Treat query as regex.",
                    "default": False,
                },
            },
            "required": ["repo_path", "query"],
        },
    ),
    Tool(
        name="search_columns",
        description=(
            "Search column metadata from context providers (e.g., dbt schema.yml). "
            "Find columns by name, description, or table."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "query": {
                    "type": "string",
                    "description": "Column name or description search string.",
                },
                "table": {
                    "type": "string",
                    "description": "Filter by table/model name.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 50,
                },
            },
            "required": ["repo_path", "query"],
        },
    ),
    Tool(
        name="find_importers",
        description=(
            "Find files that import a given module/file. Builds a reverse import "
            "graph from the indexed imports."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "target": {
                    "type": "string",
                    "description": "Module name, file path, or package name to search for.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 50,
                },
            },
            "required": ["repo_path", "target"],
        },
    ),
    Tool(
        name="find_references",
        description=(
            "Find all references to a symbol name across the indexed codebase. "
            "Uses word-boundary matching for precise results."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "name": {
                    "type": "string",
                    "description": "Symbol or module name to search for.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Filter by file path substring.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 50,
                },
            },
            "required": ["repo_path", "name"],
        },
    ),
    Tool(
        name="invalidate_cache",
        description="Delete the cached index for a repository, forcing a full re-index next time.",
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="get_stats",
        description=(
            "Get Snip token savings statistics for the current session and "
            "cumulative totals. Shows how many tokens were saved by using "
            "targeted symbol retrieval instead of reading full files."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_call_graph",
        description=(
            "Get what a symbol calls — returns callees with optional depth "
            "traversal through the call graph."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "symbol_id": {
                    "type": "string",
                    "description": "Symbol ID to get call graph for.",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many levels deep to traverse.",
                    "default": 1,
                },
            },
            "required": ["repo_path", "symbol_id"],
        },
    ),
    Tool(
        name="get_callers",
        description=("Find all symbols that call a given symbol — reverse call graph lookup."),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "symbol_id": {
                    "type": "string",
                    "description": "Symbol ID to find callers for.",
                },
            },
            "required": ["repo_path", "symbol_id"],
        },
    ),
    Tool(
        name="get_change_impact",
        description=(
            "Identify changed symbols by comparing current files to the stored "
            "index, then find their dependents via the call graph."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional relative path to limit analysis to one file.",
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="search_annotations",
        description=(
            "Find symbols by decorator/annotation pattern "
            '(e.g. "router.get", "pytest.mark", "Override").'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "pattern": {
                    "type": "string",
                    "description": "Decorator/annotation pattern to search for.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 50,
                },
            },
            "required": ["repo_path", "pattern"],
        },
    ),
    Tool(
        name="get_changes",
        description=(
            "Show symbols added, modified, or removed since the last index. "
            "Requires at least two index runs to have comparison data."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="get_document_outline",
        description=(
            "Get the section hierarchy/outline of a document (Markdown, Excel, Word, PDF, CSV)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the document within the repo.",
                },
            },
            "required": ["repo_path", "file_path"],
        },
    ),
    Tool(
        name="get_document_section",
        description="Retrieve the content of a specific document section by section ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "section_id": {
                    "type": "string",
                    "description": "Section ID to retrieve.",
                },
            },
            "required": ["repo_path", "section_id"],
        },
    ),
    Tool(
        name="search_documents",
        description="Search document sections by title or content across all indexed documents.",
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "query": {
                    "type": "string",
                    "description": "Search query string.",
                },
                "format": {
                    "type": "string",
                    "description": (
                        "Filter by format (markdown, excel, word, powerpoint, pdf, csv)."
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return.",
                    "default": 20,
                },
            },
            "required": ["repo_path", "query"],
        },
    ),
    Tool(
        name="watch_repo",
        description=(
            "Start or stop watching a repo for file changes. "
            "Auto-reindexes on changes (requires watchfiles)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "action": {
                    "type": "string",
                    "enum": ["start", "stop"],
                    "description": "Start or stop watching.",
                    "default": "start",
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="export_diagram",
        description=("Generate a Mermaid diagram: class_hierarchy, call_graph, or imports."),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "type": {
                    "type": "string",
                    "enum": ["class_hierarchy", "call_graph", "imports"],
                    "description": "Type of diagram to generate.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional file path filter.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional file path to write the diagram to (e.g. 'diagram.mmd').",
                },
            },
            "required": ["repo_path", "type"],
        },
    ),
    Tool(
        name="export_docs",
        description=("Generate markdown documentation from the code index."),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional file path filter.",
                },
                "format": {
                    "type": "string",
                    "description": "Output format.",
                    "default": "markdown",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional file path to write the documentation to (e.g. 'docs.md').",
                },
            },
            "required": ["repo_path"],
        },
    ),
    Tool(
        name="resolve_cross_repo",
        description=("Resolve an import to a symbol in another indexed repo."),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the source repo.",
                },
                "import_string": {
                    "type": "string",
                    "description": "Import string to resolve.",
                },
            },
            "required": ["repo_path", "import_string"],
        },
    ),
    Tool(
        name="get_test_coverage",
        description=(
            "Find test files and functions for a symbol via naming "
            "conventions, imports, and call graph analysis."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "symbol_id": {
                    "type": "string",
                    "description": "Symbol ID to find tests for.",
                },
            },
            "required": ["repo_path", "symbol_id"],
        },
    ),
    Tool(
        name="get_dead_code",
        description=(
            "Detect potentially unused symbols (zero callers, not imported, "
            "not entry points) and circular import chains."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Absolute path to the indexed folder.",
                },
                "include_tests": {
                    "type": "boolean",
                    "description": "Include test files in analysis.",
                    "default": False,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum dead symbols to return.",
                    "default": 100,
                },
            },
            "required": ["repo_path"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------


def _dispatch(tool_name: str, arguments: dict) -> dict:
    """Dispatch a tool call to the appropriate handler function."""
    if tool_name == "index_folder":
        from snip_mcp.tools.index_folder import index_folder

        return index_folder(
            arguments["folder_path"],
            force=arguments.get("force", False),
            max_files=arguments.get("max_files", 50000),
        )

    elif tool_name == "list_repos":
        from snip_mcp.tools.list_repos import list_repos

        return list_repos()

    elif tool_name == "get_file_tree":
        from snip_mcp.tools.get_file_tree import get_file_tree

        return get_file_tree(
            arguments["repo_path"],
            max_depth=arguments.get("max_depth", 5),
            show_symbols=arguments.get("show_symbols", False),
        )

    elif tool_name == "get_file_outline":
        from snip_mcp.tools.get_file_outline import get_file_outline

        return get_file_outline(arguments["repo_path"], arguments["file_path"])

    elif tool_name == "get_file_content":
        from snip_mcp.tools.get_file_content import get_file_content

        return get_file_content(
            arguments["repo_path"],
            arguments["file_path"],
            start_line=arguments.get("start_line"),
            end_line=arguments.get("end_line"),
        )

    elif tool_name == "get_repo_outline":
        from snip_mcp.tools.get_repo_outline import get_repo_outline

        return get_repo_outline(arguments["repo_path"])

    elif tool_name == "get_symbol":
        from snip_mcp.tools.get_symbol import get_symbol

        return get_symbol(arguments["repo_path"], arguments["symbol_id"])

    elif tool_name == "get_symbols":
        from snip_mcp.tools.get_symbol import get_symbols

        return get_symbols(arguments["repo_path"], arguments["symbol_ids"])

    elif tool_name == "search_symbols":
        from snip_mcp.tools.search_symbols import search_symbols

        return search_symbols(
            arguments["repo_path"],
            arguments["query"],
            kind=arguments.get("kind"),
            file_pattern=arguments.get("file_pattern"),
            max_results=arguments.get("max_results", 20),
        )

    elif tool_name == "search_text":
        from snip_mcp.tools.search_text import search_text

        return search_text(
            arguments["repo_path"],
            arguments["query"],
            file_pattern=arguments.get("file_pattern"),
            case_sensitive=arguments.get("case_sensitive", False),
            context_lines=arguments.get("context_lines", 2),
            max_results=arguments.get("max_results", 50),
            regex=arguments.get("regex", False),
        )

    elif tool_name == "search_columns":
        from snip_mcp.tools.search_columns import search_columns

        return search_columns(
            arguments["repo_path"],
            arguments["query"],
            table=arguments.get("table"),
            max_results=arguments.get("max_results", 50),
        )

    elif tool_name == "find_importers":
        from snip_mcp.tools.find_importers import find_importers

        return find_importers(
            arguments["repo_path"],
            arguments["target"],
            max_results=arguments.get("max_results", 50),
        )

    elif tool_name == "find_references":
        from snip_mcp.tools.find_references import find_references

        return find_references(
            arguments["repo_path"],
            arguments["name"],
            file_pattern=arguments.get("file_pattern"),
            max_results=arguments.get("max_results", 50),
        )

    elif tool_name == "invalidate_cache":
        from snip_mcp.tools.invalidate_cache import invalidate_cache

        return invalidate_cache(arguments["repo_path"])

    elif tool_name == "get_stats":
        from snip_mcp.storage.token_tracker import TokenTracker

        return TokenTracker().get_stats()

    elif tool_name == "get_call_graph":
        from snip_mcp.tools.get_call_graph import get_call_graph

        return get_call_graph(
            arguments["repo_path"],
            arguments["symbol_id"],
            depth=arguments.get("depth", 1),
        )

    elif tool_name == "get_callers":
        from snip_mcp.tools.get_callers import get_callers

        return get_callers(arguments["repo_path"], arguments["symbol_id"])

    elif tool_name == "get_change_impact":
        from snip_mcp.tools.get_change_impact import get_change_impact

        return get_change_impact(
            arguments["repo_path"],
            file_path=arguments.get("file_path"),
        )

    elif tool_name == "search_annotations":
        from snip_mcp.tools.search_annotations import search_annotations

        return search_annotations(
            arguments["repo_path"],
            arguments["pattern"],
            max_results=arguments.get("max_results", 50),
        )

    elif tool_name == "get_changes":
        from snip_mcp.tools.get_changes import get_changes

        return get_changes(arguments["repo_path"])

    elif tool_name == "get_document_outline":
        from snip_mcp.tools.get_document_outline import get_document_outline

        return get_document_outline(arguments["repo_path"], arguments["file_path"])

    elif tool_name == "get_document_section":
        from snip_mcp.tools.get_document_section import get_document_section

        return get_document_section(arguments["repo_path"], arguments["section_id"])

    elif tool_name == "search_documents":
        from snip_mcp.tools.search_documents import search_documents

        return search_documents(
            arguments["repo_path"],
            arguments["query"],
            format=arguments.get("format"),
            max_results=arguments.get("max_results", 20),
        )

    elif tool_name == "watch_repo":
        from snip_mcp.watcher import is_watching, start_watching, stop_watching

        action = arguments.get("action", "start")
        rp = arguments["repo_path"]
        if action == "start":
            ok = start_watching(rp)
            if ok:
                return {"status": "watching", "repo_path": rp}
            if is_watching(rp):
                return {"status": "already_watching", "repo_path": rp}
            return {
                "error": "watchfiles not installed. Install with: pip install snip-mcp[watch]"
            }
        else:
            ok = stop_watching(rp)
            return {"status": "stopped" if ok else "not_watching", "repo_path": rp}

    elif tool_name == "export_diagram":
        from snip_mcp.tools.export_diagram import export_diagram

        return export_diagram(
            arguments["repo_path"],
            arguments["type"],
            file_pattern=arguments.get("file_pattern"),
            output_path=arguments.get("output_path"),
        )

    elif tool_name == "export_docs":
        from snip_mcp.tools.export_docs import export_docs

        return export_docs(
            arguments["repo_path"],
            file_pattern=arguments.get("file_pattern"),
            format=arguments.get("format", "markdown"),
            output_path=arguments.get("output_path"),
        )

    elif tool_name == "resolve_cross_repo":
        from snip_mcp.tools.cross_repo import resolve_cross_repo

        return resolve_cross_repo(arguments["repo_path"], arguments["import_string"])

    elif tool_name == "get_test_coverage":
        from snip_mcp.tools.get_test_coverage import get_test_coverage

        return get_test_coverage(arguments["repo_path"], arguments["symbol_id"])

    elif tool_name == "get_dead_code":
        from snip_mcp.tools.get_dead_code import get_dead_code

        return get_dead_code(
            arguments["repo_path"],
            include_tests=arguments.get("include_tests", False),
            max_results=arguments.get("max_results", 100),
        )

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------

server = Server("snip-mcp")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return all available tools."""
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Dispatch a tool call and return the result as JSON text."""
    import asyncio

    arguments = arguments or {}

    try:
        result = await asyncio.to_thread(_dispatch, name, arguments)
    except Exception as e:
        logger.exception("Tool %s failed", name)
        result = {"error": str(e)}

    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _run() -> None:
    """Run the MCP server using stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _format_tokens(n: int) -> str:
    """Format a token count as a human-readable string (e.g., 12.3K, 1.5M)."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _ensure_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8 on Windows (avoids cp1252 encode errors)."""
    import io
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    elif sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _print_stats() -> None:
    """Print a visual token savings summary and exit."""

    from snip_mcp.statusline import _progress_bar
    from snip_mcp.storage.token_tracker import TokenTracker

    _ensure_utf8_stdout()
    stats = TokenTracker().get_stats()
    session = stats["session"]
    cumulative = stats["cumulative"]

    s_saved = session["full_tokens"] - session["returned_tokens"]
    s_pct = session["savings_pct"]
    c_saved = cumulative["total_full_tokens"] - cumulative["total_returned_tokens"]
    c_pct = cumulative["savings_pct"]

    print(
        f"  \u26a1 Session   {_progress_bar(max(0, s_pct))} "
        f"{session['retrievals']} calls  "
        f"{_format_tokens(s_saved)} saved ({s_pct}%)"
    )
    print(
        f"  \u2211 Lifetime  {_progress_bar(max(0, c_pct))} "
        f"{cumulative['total_retrievals']} calls  "
        f"{_format_tokens(c_saved)} saved ({c_pct}%)"
    )


def _setup_statusline() -> None:
    """Copy statusline.py to ~/.claude/ and configure settings.json automatically."""
    import shutil

    _ensure_utf8_stdout()

    # 1. Copy the script
    src = Path(__file__).parent / "statusline.py"
    dest = Path.home() / ".claude" / "snip-statusline.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)

    # 2. Update ~/.claude/settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = {}
    else:
        settings = {}

    settings["statusLine"] = {
        "type": "command",
        "command": f"python {dest.as_posix()}",
    }

    settings_path.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )

    # 3. Confirm
    print(f"\u2705 Copied statusline script to {dest}")
    print(f"\u2705 Updated {settings_path} with statusLine config")
    print()
    print("Restart Claude Code to see Snip savings in your status bar.")


def main() -> None:
    """CLI entry point for snip-mcp.

    Flags:
        --stats             Print session token savings and exit.
        --setup-statusline  Install statusline script and print config.
        (default)           Reset session, start MCP stdio server.
    """
    import sys

    if "--stats" in sys.argv:
        _print_stats()
        return

    if "--setup-statusline" in sys.argv:
        _setup_statusline()
        return

    # Default: reset session and start MCP server
    import asyncio

    from snip_mcp.storage.token_tracker import TokenTracker

    TokenTracker().reset_session()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
