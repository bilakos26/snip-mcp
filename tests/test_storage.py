"""Tests for the storage layer — IndexStore and TokenTracker."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.parser.symbols import FileSymbols, Symbol, SymbolKind, make_symbol_id
from snip_mcp.storage.index_store import CodeIndex, IndexStore
from snip_mcp.storage.token_tracker import TokenTracker, estimate_tokens


class TestIndexStore:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        store = IndexStore(storage_dir=tmp_path / "indexes")

        sym = Symbol(
            id=make_symbol_id("main.py", SymbolKind.FUNCTION, "hello", 1),
            name="hello",
            kind=SymbolKind.FUNCTION,
            file_path="main.py",
            line_start=1,
            line_end=3,
            byte_start=0,
            byte_end=50,
            signature="def hello():",
            docstring="Say hello.",
            language="python",
        )

        fs = FileSymbols(
            file_path="main.py",
            language="python",
            symbols=[sym],
            imports=["os"],
            content_hash="abcd1234abcd1234",
            file_size=100,
            line_count=5,
        )

        index = CodeIndex(
            repo_path=str(tmp_path / "myrepo"),
            repo_name="myrepo",
            files={"main.py": fs},
            symbols={sym.id: sym},
            file_hashes={"main.py": "abcd1234abcd1234"},
            language_stats={"python": 1},
            total_symbols=1,
            total_files=1,
        )

        store.save(index)
        loaded = store.load(str(tmp_path / "myrepo"))

        assert loaded is not None
        assert loaded.repo_name == "myrepo"
        assert loaded.total_files == 1
        assert loaded.total_symbols == 1
        assert "main.py" in loaded.files
        assert sym.id in loaded.symbols
        assert loaded.symbols[sym.id].name == "hello"
        assert loaded.symbols[sym.id].kind == SymbolKind.FUNCTION

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        store = IndexStore(storage_dir=tmp_path / "indexes")
        assert store.load("/nonexistent/path") is None

    def test_delete(self, tmp_path: Path) -> None:
        store = IndexStore(storage_dir=tmp_path / "indexes")
        index = CodeIndex(
            repo_path=str(tmp_path / "repo"),
            repo_name="repo",
        )
        store.save(index)
        assert store.delete(str(tmp_path / "repo")) is True
        assert store.load(str(tmp_path / "repo")) is None
        assert store.delete(str(tmp_path / "repo")) is False

    def test_list_repos(self, tmp_path: Path) -> None:
        store = IndexStore(storage_dir=tmp_path / "indexes")

        for name in ["repo1", "repo2"]:
            index = CodeIndex(
                repo_path=str(tmp_path / name),
                repo_name=name,
            )
            store.save(index)

        repos = store.list_repos()
        assert len(repos) == 2
        names = {r.repo_name for r in repos}
        assert "repo1" in names
        assert "repo2" in names

    def test_byte_offset_retrieval(self, tmp_path: Path) -> None:
        # Create a real file
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        source = "line 1\ndef hello():\n    pass\nline 4\n"
        (repo_dir / "main.py").write_text(source, encoding="utf-8")

        # "def hello():\n    pass\n" starts at byte 7
        func_start = source.index("def hello()")
        func_end = source.index("line 4")

        sym = Symbol(
            id=make_symbol_id("main.py", SymbolKind.FUNCTION, "hello", 2),
            name="hello",
            kind=SymbolKind.FUNCTION,
            file_path="main.py",
            line_start=2,
            line_end=3,
            byte_start=func_start,
            byte_end=func_end,
            signature="def hello():",
            language="python",
        )

        index = CodeIndex(
            repo_path=str(repo_dir),
            repo_name="repo",
            symbols={sym.id: sym},
        )

        store = IndexStore(storage_dir=tmp_path / "indexes")
        result = store.get_symbol_source(index, sym.id)
        assert result is not None
        assert "def hello():" in result


class TestTokenTracker:
    def test_record_and_get_stats(self, tmp_path: Path) -> None:
        tracker = TokenTracker(storage_dir=tmp_path)
        tracker.record_retrieval(full_tokens=1000, returned_tokens=100)
        tracker.record_retrieval(full_tokens=2000, returned_tokens=200)

        stats = tracker.get_stats()
        assert stats["total_retrievals"] == 2
        assert stats["total_full_tokens"] == 3000
        assert stats["total_returned_tokens"] == 300
        assert stats["savings_pct"] == 90.0

    def test_empty_stats(self, tmp_path: Path) -> None:
        tracker = TokenTracker(storage_dir=tmp_path)
        stats = tracker.get_stats()
        assert stats["total_retrievals"] == 0
        assert stats["savings_pct"] == 0.0


class TestTokenTrackerSession:
    def test_reset_session(self, tmp_path: Path) -> None:
        tracker = TokenTracker(storage_dir=tmp_path)
        tracker.reset_session()
        stats = tracker.get_session_stats()
        assert stats["retrievals"] == 0
        assert stats["full_tokens"] == 0
        assert stats["returned_tokens"] == 0
        assert stats["tokens_saved"] == 0
        assert stats["savings_pct"] == 0.0
        assert stats["session_started"] is not None

    def test_session_accumulate(self, tmp_path: Path) -> None:
        tracker = TokenTracker(storage_dir=tmp_path)
        tracker.reset_session()
        tracker.record_retrieval(full_tokens=1000, returned_tokens=100)
        tracker.record_retrieval(full_tokens=2000, returned_tokens=200)

        stats = tracker.get_session_stats()
        assert stats["retrievals"] == 2
        assert stats["full_tokens"] == 3000
        assert stats["returned_tokens"] == 300
        assert stats["tokens_saved"] == 2700
        assert stats["savings_pct"] == 90.0

    def test_session_independent_from_cumulative(self, tmp_path: Path) -> None:
        tracker = TokenTracker(storage_dir=tmp_path)
        # Record before session reset — goes to cumulative only
        tracker.record_retrieval(full_tokens=5000, returned_tokens=500)
        tracker.reset_session()
        tracker.record_retrieval(full_tokens=1000, returned_tokens=100)

        session = tracker.get_session_stats()
        assert session["retrievals"] == 1
        assert session["full_tokens"] == 1000

        cumulative = tracker.get_stats()["cumulative"]
        assert cumulative["total_retrievals"] == 2
        assert cumulative["total_full_tokens"] == 6000

    def test_session_persists_across_instances(self, tmp_path: Path) -> None:
        t1 = TokenTracker(storage_dir=tmp_path)
        t1.reset_session()
        t1.record_retrieval(full_tokens=1000, returned_tokens=100)

        t2 = TokenTracker(storage_dir=tmp_path)
        t2.record_retrieval(full_tokens=2000, returned_tokens=200)

        stats = t2.get_session_stats()
        assert stats["retrievals"] == 2
        assert stats["full_tokens"] == 3000

    def test_get_stats_backward_compat(self, tmp_path: Path) -> None:
        tracker = TokenTracker(storage_dir=tmp_path)
        tracker.reset_session()
        tracker.record_retrieval(full_tokens=1000, returned_tokens=100)

        stats = tracker.get_stats()
        # Legacy top-level keys still present
        assert stats["total_retrievals"] == 1
        assert stats["total_full_tokens"] == 1000
        assert stats["total_returned_tokens"] == 100
        assert stats["savings_pct"] == 90.0
        # New structured keys also present
        assert "session" in stats
        assert "cumulative" in stats


class TestEstimateTokens:
    def test_basic_estimate(self) -> None:
        assert estimate_tokens("hello world!") == 3  # 12 chars / 4

    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0
