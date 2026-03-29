"""Document parser registry and dispatch."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.parser.documents.base import DocumentFile, DocumentParser

_PARSERS: list[DocumentParser] = []
_EXT_MAP: dict[str, DocumentParser] = {}


def _ensure_registered() -> None:
    """Lazily register all built-in parsers."""
    if _PARSERS:
        return

    from snip_mcp.parser.documents.csv_parser import CsvParser
    from snip_mcp.parser.documents.markdown import MarkdownParser

    builtin = [MarkdownParser(), CsvParser()]

    # Optional parsers that require extra dependencies
    try:
        from snip_mcp.parser.documents.excel import ExcelParser

        builtin.append(ExcelParser())
    except ImportError:
        pass

    try:
        from snip_mcp.parser.documents.word import WordParser

        builtin.append(WordParser())
    except ImportError:
        pass

    try:
        from snip_mcp.parser.documents.powerpoint import PowerPointParser

        builtin.append(PowerPointParser())
    except ImportError:
        pass

    try:
        from snip_mcp.parser.documents.pdf import PdfParser

        builtin.append(PdfParser())
    except ImportError:
        pass

    for parser in builtin:
        _PARSERS.append(parser)
        for ext in parser.supported_extensions:
            _EXT_MAP.setdefault(ext.lower(), parser)


def get_parser(file_path: str) -> DocumentParser | None:
    """Return the appropriate parser for a file, or None."""
    _ensure_registered()
    suffix = Path(file_path).suffix.lower()
    return _EXT_MAP.get(suffix)


def parse_document(file_path: Path, rel_path: str) -> DocumentFile | None:
    """Parse a document file if a suitable parser is available."""
    parser = get_parser(str(file_path))
    if parser is None:
        return None
    try:
        return parser.parse(file_path, rel_path)
    except Exception:
        return None
