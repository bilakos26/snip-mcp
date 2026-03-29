"""Tests for the language specification registry."""

from __future__ import annotations

import pytest

from snip_mcp.parser.languages import (
    LANGUAGE_SPECS,
    get_language_by_id,
    get_language_for_file,
)


class TestLanguageRegistry:
    def test_has_23_languages(self) -> None:
        assert len(LANGUAGE_SPECS) == 23

    @pytest.mark.parametrize(
        "lang_id",
        [
            "python",
            "javascript",
            "typescript",
            "tsx",
            "go",
            "rust",
            "java",
            "c_sharp",
            "c",
            "cpp",
            "sql",
        ],
    )
    def test_language_exists(self, lang_id: str) -> None:
        spec = get_language_by_id(lang_id)
        assert spec is not None
        assert spec.language_id == lang_id

    def test_unknown_language(self) -> None:
        assert get_language_by_id("haskell") is None


class TestFileExtensionLookup:
    @pytest.mark.parametrize(
        "filepath,expected_lang",
        [
            ("main.py", "python"),
            ("app.js", "javascript"),
            ("app.mjs", "javascript"),
            ("types.ts", "typescript"),
            ("Component.tsx", "tsx"),
            ("main.go", "go"),
            ("lib.rs", "rust"),
            ("App.java", "java"),
            ("Program.cs", "c_sharp"),
            ("main.c", "c"),
            ("main.h", "c"),
            ("main.cpp", "cpp"),
            ("main.cc", "cpp"),
            ("main.hpp", "cpp"),
            ("query.sql", "sql"),
        ],
    )
    def test_extension_mapping(self, filepath: str, expected_lang: str) -> None:
        spec = get_language_for_file(filepath)
        assert spec is not None
        assert spec.language_id == expected_lang

    def test_unknown_extension(self) -> None:
        assert get_language_for_file("readme.md") is None

    def test_no_extension(self) -> None:
        assert get_language_for_file("Makefile") is None

    def test_case_insensitive(self) -> None:
        spec = get_language_for_file("Main.PY")
        assert spec is not None
        assert spec.language_id == "python"


class TestLanguageSpecFields:
    def test_python_spec(self) -> None:
        spec = get_language_by_id("python")
        assert spec.name == "Python"
        assert ".py" in spec.extensions
        assert "function" in spec.symbol_queries
        assert "class" in spec.symbol_queries
        assert spec.comment_prefix == "#"

    def test_sql_spec(self) -> None:
        spec = get_language_by_id("sql")
        assert spec.name == "SQL"
        assert "sql_table" in spec.symbol_queries
        assert "sql_view" in spec.symbol_queries
        assert spec.comment_prefix == "--"
