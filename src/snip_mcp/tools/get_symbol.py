"""get_symbol and get_symbols tools — single + batch symbol retrieval via byte-offset."""

from __future__ import annotations

from snip_mcp.storage.token_tracker import TokenTracker, estimate_tokens
from snip_mcp.tools._utils import get_store, meta_envelope, resolve_repo


def get_symbol(repo_path: str, symbol_id: str) -> dict:
    """Get a single symbol's source code via O(1) byte-offset seeking.

    Args:
        repo_path: Path to the indexed folder.
        symbol_id: The symbol ID (format: file::kind::name::line).
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    sym = index.symbols.get(symbol_id)
    if sym is None:
        return meta_envelope({"error": f"Symbol not found: {symbol_id}"})

    store = get_store()
    source = store.get_symbol_source(index, symbol_id)
    if source is None:
        return meta_envelope({"error": f"Could not read source for: {symbol_id}"})

    # Track tokens
    tracker = TokenTracker()
    file_syms = index.files.get(sym.file_path)
    full_tokens = file_syms.file_size // 4 if file_syms else len(source) * 2
    returned_tokens = estimate_tokens(source)
    tracker.record_retrieval(full_tokens, returned_tokens)

    return meta_envelope(
        {
            "symbol_id": sym.id,
            "name": sym.name,
            "kind": sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind),
            "file_path": sym.file_path,
            "line_start": sym.line_start,
            "line_end": sym.line_end,
            "signature": sym.signature,
            "docstring": sym.docstring,
            "decorators": list(sym.decorators),
            "source": source,
        },
        repo_path=index.repo_path,
        tokens_saved=max(0, full_tokens - returned_tokens),
    )


def get_symbols(repo_path: str, symbol_ids: list[str]) -> dict:
    """Batch retrieve multiple symbols' source code.

    Args:
        repo_path: Path to the indexed folder.
        symbol_ids: List of symbol IDs to retrieve.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    store = get_store()
    tracker = TokenTracker()
    results = []
    total_saved = 0

    for sid in symbol_ids:
        sym = index.symbols.get(sid)
        if sym is None:
            results.append({"symbol_id": sid, "error": "not found"})
            continue

        source = store.get_symbol_source(index, sid)
        if source is None:
            results.append({"symbol_id": sid, "error": "could not read source"})
            continue

        file_syms = index.files.get(sym.file_path)
        full_tokens = file_syms.file_size // 4 if file_syms else len(source) * 2
        returned_tokens = estimate_tokens(source)
        tracker.record_retrieval(full_tokens, returned_tokens)
        total_saved += max(0, full_tokens - returned_tokens)

        results.append(
            {
                "symbol_id": sym.id,
                "name": sym.name,
                "kind": sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind),
                "file_path": sym.file_path,
                "line_start": sym.line_start,
                "line_end": sym.line_end,
                "signature": sym.signature,
                "source": source,
            }
        )

    found_count = sum(1 for r in results if "error" not in r)
    return meta_envelope(
        {
            "symbols": results,
            "total_requested": len(symbol_ids),
            "total_found": found_count,
        },
        repo_path=index.repo_path,
        tokens_saved=total_saved,
    )
