"""get_file_outline tool — symbol hierarchy for a single file."""

from __future__ import annotations

from snip_mcp.parser.hierarchy import get_children, get_top_level_symbols
from snip_mcp.summarizer import summarize_symbol
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_file_outline(repo_path: str, file_path: str) -> dict:
    """Get the symbol outline/hierarchy for a specific file.

    Args:
        repo_path: Path to the indexed folder.
        file_path: Relative path to the file within the repo.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # Normalize path separators
    file_path = file_path.replace("\\", "/")
    file_syms = index.files.get(file_path)
    if file_syms is None:
        return meta_envelope({"error": f"File not found in index: {file_path}"})

    symbols = file_syms.symbols
    top_level = get_top_level_symbols(symbols)

    def _build_outline(sym) -> dict:
        children = get_children(symbols, sym.id)
        entry = {
            "id": sym.id,
            "name": sym.name,
            "kind": sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind),
            "line_start": sym.line_start,
            "line_end": sym.line_end,
            "signature": sym.signature,
            "summary": summarize_symbol(sym),
        }
        if sym.decorators:
            entry["decorators"] = list(sym.decorators)
        if children:
            entry["children"] = [_build_outline(c) for c in children]
        return entry

    outline = [_build_outline(s) for s in top_level]

    return meta_envelope(
        {
            "file_path": file_path,
            "language": file_syms.language,
            "line_count": file_syms.line_count,
            "symbol_count": len(symbols),
            "imports": file_syms.imports,
            "outline": outline,
        },
        repo_path=index.repo_path,
    )
