"""Tests for the parser modules — symbol extraction across languages."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.parser.extractor import extract_file_symbols
from snip_mcp.parser.languages import LANGUAGE_SPECS
from snip_mcp.parser.symbols import SymbolKind

FIXTURES = Path(__file__).parent / "fixtures"


class TestPythonExtraction:
    def setup_method(self) -> None:
        self.spec = LANGUAGE_SPECS["python"]
        self.source = (FIXTURES / "sample.py").read_text(encoding="utf-8")
        self.symbols = extract_file_symbols(self.source, self.spec, "sample.py")

    def test_extracts_class(self) -> None:
        classes = [s for s in self.symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) >= 1
        assert any(s.name == "MyClass" for s in classes)

    def test_extracts_functions(self) -> None:
        funcs = [s for s in self.symbols if s.kind == SymbolKind.FUNCTION]
        assert any(s.name == "top_level_function" for s in funcs)

    def test_has_docstrings(self) -> None:
        cls = next((s for s in self.symbols if s.name == "MyClass"), None)
        assert cls is not None
        assert "sample class" in cls.docstring.lower()

    def test_byte_offsets_valid(self) -> None:
        for sym in self.symbols:
            assert sym.byte_start >= 0
            assert sym.byte_end > sym.byte_start
            # Verify we can extract the source with byte offsets
            source_bytes = self.source.encode("utf-8")
            extracted = source_bytes[sym.byte_start : sym.byte_end].decode("utf-8")
            assert sym.name in extracted


class TestJavaScriptExtraction:
    def setup_method(self) -> None:
        self.spec = LANGUAGE_SPECS["javascript"]
        self.source = (FIXTURES / "sample.js").read_text(encoding="utf-8")
        self.symbols = extract_file_symbols(self.source, self.spec, "sample.js")

    def test_extracts_function(self) -> None:
        funcs = [s for s in self.symbols if s.kind == SymbolKind.FUNCTION]
        assert any(s.name == "regularFunction" for s in funcs)

    def test_extracts_class(self) -> None:
        classes = [s for s in self.symbols if s.kind == SymbolKind.CLASS]
        assert any(s.name == "Animal" for s in classes)


class TestTypeScriptExtraction:
    def setup_method(self) -> None:
        self.spec = LANGUAGE_SPECS["typescript"]
        self.source = (FIXTURES / "sample.ts").read_text(encoding="utf-8")
        self.symbols = extract_file_symbols(self.source, self.spec, "sample.ts")

    def test_extracts_interface(self) -> None:
        interfaces = [s for s in self.symbols if s.kind == SymbolKind.INTERFACE]
        assert any(s.name == "User" for s in interfaces)

    def test_extracts_enum(self) -> None:
        enums = [s for s in self.symbols if s.kind == SymbolKind.ENUM]
        assert any(s.name == "Color" for s in enums)

    def test_extracts_type_alias(self) -> None:
        aliases = [s for s in self.symbols if s.kind == SymbolKind.TYPE_ALIAS]
        assert any(s.name == "Status" for s in aliases)


class TestGoExtraction:
    def setup_method(self) -> None:
        self.spec = LANGUAGE_SPECS["go"]
        self.source = (FIXTURES / "sample.go").read_text(encoding="utf-8")
        self.symbols = extract_file_symbols(self.source, self.spec, "sample.go")

    def test_extracts_struct(self) -> None:
        structs = [s for s in self.symbols if s.kind == SymbolKind.STRUCT]
        assert any(s.name == "Animal" for s in structs)

    def test_extracts_interface(self) -> None:
        interfaces = [s for s in self.symbols if s.kind == SymbolKind.INTERFACE]
        assert any(s.name == "Speaker" for s in interfaces)

    def test_extracts_function(self) -> None:
        funcs = [s for s in self.symbols if s.kind == SymbolKind.FUNCTION]
        assert any(s.name == "NewAnimal" for s in funcs)


class TestRustExtraction:
    def setup_method(self) -> None:
        self.spec = LANGUAGE_SPECS["rust"]
        self.source = (FIXTURES / "sample.rs").read_text(encoding="utf-8")
        self.symbols = extract_file_symbols(self.source, self.spec, "sample.rs")

    def test_extracts_struct(self) -> None:
        structs = [s for s in self.symbols if s.kind == SymbolKind.STRUCT]
        assert any(s.name == "Point" for s in structs)

    def test_extracts_enum(self) -> None:
        enums = [s for s in self.symbols if s.kind == SymbolKind.ENUM]
        assert any(s.name == "Shape" for s in enums)

    def test_extracts_trait(self) -> None:
        traits = [s for s in self.symbols if s.kind == SymbolKind.TRAIT]
        assert any(s.name == "Drawable" for s in traits)

    def test_extracts_function(self) -> None:
        funcs = [s for s in self.symbols if s.kind == SymbolKind.FUNCTION]
        assert any(s.name == "distance" for s in funcs)
