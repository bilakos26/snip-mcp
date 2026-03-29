"""Call graph builder for Snip MCP.

Builds a caller-to-callees mapping by scanning function/method bodies for
references to known symbol names.
"""

from __future__ import annotations

import re

from snip_mcp.parser.symbols import SymbolKind
from snip_mcp.storage.index_store import CodeIndex


def build_call_graph(index: CodeIndex) -> dict[str, list[str]]:
    """Build a call graph from the indexed symbols.

    For each function/method symbol, reads its source text via byte offsets
    and finds identifiers matching other known symbol names.

    Parameters
    ----------
    index:
        A fully populated :class:`CodeIndex`.

    Returns
    -------
    dict[str, list[str]]
        Mapping of caller symbol_id to list of callee symbol_ids.
    """
    from pathlib import Path

    callable_kinds = {
        SymbolKind.FUNCTION,
        SymbolKind.METHOD,
        SymbolKind.CLASS,
    }

    # Build name -> [symbol_id, ...] lookup for all symbols
    name_to_ids: dict[str, list[str]] = {}
    for sym in index.symbols.values():
        name_to_ids.setdefault(sym.name, []).append(sym.id)

    # Pre-compile word boundary patterns for each name
    name_patterns: dict[str, re.Pattern] = {}
    for name in name_to_ids:
        if len(name) < 2:
            continue
        try:
            name_patterns[name] = re.compile(rf"\b{re.escape(name)}\b")
        except re.error:
            continue

    call_graph: dict[str, list[str]] = {}
    repo_root = Path(index.repo_path)

    for sym in index.symbols.values():
        if sym.kind not in callable_kinds:
            continue

        # Read source text via byte offsets
        source_path = repo_root / sym.file_path
        if not source_path.is_file():
            continue

        byte_length = sym.byte_end - sym.byte_start
        if byte_length <= 0:
            continue

        try:
            with source_path.open("rb") as fh:
                fh.seek(sym.byte_start)
                raw = fh.read(byte_length)
            body = raw.decode("utf-8", errors="replace")
        except OSError:
            continue

        callees: list[str] = []
        for name, pattern in name_patterns.items():
            if pattern.search(body):
                for callee_id in name_to_ids[name]:
                    # Exclude self-references
                    if callee_id != sym.id:
                        callees.append(callee_id)

        if callees:
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for cid in callees:
                if cid not in seen:
                    seen.add(cid)
                    unique.append(cid)
            call_graph[sym.id] = unique

    return call_graph


def get_callers(index: CodeIndex, symbol_id: str) -> list[str]:
    """Compute the reverse of the call graph for a specific symbol.

    Returns a list of symbol_ids that call the given symbol.
    """
    callers: list[str] = []
    for caller_id, callees in index.call_graph.items():
        if symbol_id in callees:
            callers.append(caller_id)
    return callers
