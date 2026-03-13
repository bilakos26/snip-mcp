"""Tests for find_importers tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from snip_mcp.tools._utils import get_store
from snip_mcp.tools.find_importers import find_importers
from snip_mcp.tools.index_folder import index_folder


@pytest.fixture
def import_repo(tmp_path: Path) -> str:
    """Create a repo with import relationships."""
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "utils.py").write_text("def helper():\n    pass\n")
    (repo / "main.py").write_text("from utils import helper\n\ndef run():\n    helper()\n")
    (repo / "cli.py").write_text("import main\nimport os\n\ndef start():\n    main.run()\n")

    store = get_store()
    store._storage_dir = tmp_path / ".snip" / "indexes"
    store._storage_dir.mkdir(parents=True, exist_ok=True)

    index_folder(str(repo))
    return str(repo)


class TestFindImporters:
    def test_find_who_imports_utils(self, import_repo: str) -> None:
        result = find_importers(import_repo, "utils")
        assert result["data"]["total_importers"] >= 1
        files = [i["file_path"] for i in result["data"]["importers"]]
        assert "main.py" in files

    def test_find_who_imports_main(self, import_repo: str) -> None:
        result = find_importers(import_repo, "main")
        assert result["data"]["total_importers"] >= 1
        files = [i["file_path"] for i in result["data"]["importers"]]
        assert "cli.py" in files

    def test_no_importers(self, import_repo: str) -> None:
        result = find_importers(import_repo, "nonexistent_module")
        assert result["data"]["total_importers"] == 0
