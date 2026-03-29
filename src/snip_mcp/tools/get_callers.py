"""get_callers tool — returns who calls a given symbol."""

from __future__ import annotations

from snip_mcp.parser.call_graph import get_callers as _get_callers
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_callers(repo_path: str, symbol_id: str) -> dict:
    """Find all symbols that call the given symbol.

    Args:
        repo_path: Absolute path to the indexed folder.
        symbol_id: The symbol to find callers for.

    Returns:
        Envelope with caller data.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    if not index.call_graph:
        return meta_envelope(
            {"error": "No call graph available. Re-index the folder to build it."},
            repo_path=repo_path,
        )

    sym = index.symbols.get(symbol_id)
    if sym is None:
        return meta_envelope(
            {"error": f"Symbol not found: {symbol_id}"},
            repo_path=repo_path,
        )

    caller_ids = _get_callers(index, symbol_id)
    callers = []
    for cid in caller_ids:
        caller_sym = index.symbols.get(cid)
        if caller_sym:
            callers.append(
                {
                    "symbol_id": cid,
                    "name": caller_sym.name,
                    "kind": caller_sym.kind.value,
                    "file_path": caller_sym.file_path,
                    "line": caller_sym.line_start,
                    "signature": caller_sym.signature,
                }
            )

    return meta_envelope(
        {
            "symbol_id": symbol_id,
            "symbol_name": sym.name,
            "callers": callers,
            "total_callers": len(callers),
        },
        repo_path=repo_path,
    )
