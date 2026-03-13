"""Integration tests for Snip MCP tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from snip_mcp.tools._utils import get_store
from snip_mcp.tools.find_references import find_references
from snip_mcp.tools.get_file_content import get_file_content
from snip_mcp.tools.get_file_outline import get_file_outline
from snip_mcp.tools.get_file_tree import get_file_tree
from snip_mcp.tools.get_repo_outline import get_repo_outline
from snip_mcp.tools.get_symbol import get_symbol, get_symbols
from snip_mcp.tools.index_folder import index_folder
from snip_mcp.tools.invalidate_cache import invalidate_cache
from snip_mcp.tools.search_symbols import search_symbols
from snip_mcp.tools.search_text import search_text


@pytest.fixture
def indexed_repo(tmp_path: Path) -> str:
    """Create and index a small test repo."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    (repo / "main.py").write_text(
        "import os\n\n"
        "def greet(name: str) -> str:\n"
        '    """Say hello."""\n'
        '    return f"Hello, {name}!"\n\n\n'
        "class Greeter:\n"
        "    def __init__(self, name: str):\n"
        "        self.name = name\n\n"
        "    def greet(self) -> str:\n"
        "        return greet(self.name)\n"
    )
    (repo / "utils.py").write_text(
        "from main import greet\n\n"
        "def double_greet(name: str) -> str:\n"
        "    return greet(name) + greet(name)\n"
    )

    # Use a temporary store to avoid polluting ~/.snip
    store = get_store()
    store._storage_dir = tmp_path / ".snip" / "indexes"
    store._storage_dir.mkdir(parents=True, exist_ok=True)

    result = index_folder(str(repo))
    assert result["data"]["status"] == "indexed"
    return str(repo)


class TestIndexFolder:
    def test_index_nonexistent(self) -> None:
        result = index_folder("/nonexistent/path")
        assert "error" in result["data"]

    def test_index_success(self, indexed_repo: str) -> None:
        # Already indexed via fixture, just verify we can load it
        store = get_store()
        index = store.load(indexed_repo)
        assert index is not None
        assert index.total_files >= 2


class TestGetFileTree:
    def test_basic_tree(self, indexed_repo: str) -> None:
        result = get_file_tree(indexed_repo)
        assert "tree" in result["data"]

    def test_with_symbols(self, indexed_repo: str) -> None:
        result = get_file_tree(indexed_repo, show_symbols=True)
        tree = result["data"]["tree"]
        # Should have symbol count annotations
        assert any("symbols" in str(v) for v in tree.values())


class TestGetFileOutline:
    def test_python_outline(self, indexed_repo: str) -> None:
        result = get_file_outline(indexed_repo, "main.py")
        assert "outline" in result["data"]
        outline = result["data"]["outline"]
        assert len(outline) >= 1
        names = [s["name"] for s in outline]
        assert "greet" in names or "Greeter" in names

    def test_nonexistent_file(self, indexed_repo: str) -> None:
        result = get_file_outline(indexed_repo, "nope.py")
        assert "error" in result["data"]


class TestGetFileContent:
    def test_full_content(self, indexed_repo: str) -> None:
        result = get_file_content(indexed_repo, "main.py")
        assert "content" in result["data"]
        assert "def greet" in result["data"]["content"]

    def test_line_range(self, indexed_repo: str) -> None:
        result = get_file_content(indexed_repo, "main.py", start_line=3, end_line=5)
        assert result["data"]["start_line"] == 3


class TestGetRepoOutline:
    def test_basic_outline(self, indexed_repo: str) -> None:
        result = get_repo_outline(indexed_repo)
        assert result["data"]["total_files"] >= 2
        assert "python" in result["data"]["languages"]


class TestSearchSymbols:
    def test_search_by_name(self, indexed_repo: str) -> None:
        result = search_symbols(indexed_repo, "greet")
        assert result["data"]["total_matches"] >= 1

    def test_search_by_kind(self, indexed_repo: str) -> None:
        result = search_symbols(indexed_repo, "Greeter", kind="class")
        results = result["data"]["results"]
        assert any(r["kind"] == "class" for r in results)


class TestSearchText:
    def test_basic_search(self, indexed_repo: str) -> None:
        result = search_text(indexed_repo, "Hello")
        assert result["data"]["total_matches"] >= 1

    def test_regex_search(self, indexed_repo: str) -> None:
        result = search_text(indexed_repo, r"def \w+\(", regex=True)
        assert result["data"]["total_matches"] >= 1


class TestGetSymbol:
    def test_get_existing_symbol(self, indexed_repo: str) -> None:
        # First search for a symbol
        search = search_symbols(indexed_repo, "greet")
        results = search["data"]["results"]
        assert len(results) >= 1
        sid = results[0]["symbol_id"]

        result = get_symbol(indexed_repo, sid)
        assert "source" in result["data"]
        assert "greet" in result["data"]["source"]

    def test_get_nonexistent_symbol(self, indexed_repo: str) -> None:
        result = get_symbol(indexed_repo, "nonexistent::symbol::id::1")
        assert "error" in result["data"]


class TestGetSymbols:
    def test_batch_retrieval(self, indexed_repo: str) -> None:
        search = search_symbols(indexed_repo, "greet", max_results=3)
        sids = [r["symbol_id"] for r in search["data"]["results"]]
        if len(sids) >= 2:
            result = get_symbols(indexed_repo, sids[:2])
            assert result["data"]["total_found"] >= 1


class TestFindReferences:
    def test_find_function_refs(self, indexed_repo: str) -> None:
        result = find_references(indexed_repo, "greet")
        assert result["data"]["total_files"] >= 1


class TestInvalidateCache:
    def test_invalidate(self, indexed_repo: str) -> None:
        result = invalidate_cache(indexed_repo)
        assert result["data"]["status"] == "deleted"

        # Should be gone now
        result2 = invalidate_cache(indexed_repo)
        assert result2["data"]["status"] == "not_found"
