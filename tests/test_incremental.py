"""Tests for incremental indexing behavior."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.tools.index_folder import index_folder


class TestIncrementalIndexing:
    def test_index_then_reindex_skips_unchanged(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello():\n    pass\n")

        # First index
        result1 = index_folder(str(repo))
        assert result1["data"]["status"] == "indexed"
        assert result1["data"]["files_parsed"] >= 1

        # Second index — should skip unchanged files
        result2 = index_folder(str(repo))
        assert result2["data"]["status"] == "indexed"
        assert result2["data"]["files_skipped_unchanged"] >= 1

    def test_force_reindexes_all(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "main.py").write_text("def hello():\n    pass\n")

        index_folder(str(repo))
        result = index_folder(str(repo), force=True)
        assert result["data"]["files_parsed"] >= 1
        assert result["data"]["files_skipped_unchanged"] == 0
