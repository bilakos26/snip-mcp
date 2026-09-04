"""Call graph builder for Snip MCP.

Builds a caller-to-callees mapping by scanning function/method bodies for
references to known symbol names.
"""

from __future__ import annotations

import keyword
import re

from snip_mcp.parser.symbols import SymbolKind
from snip_mcp.storage.index_store import CodeIndex

# Names excluded from call-graph candidate matching.
# Includes Python keywords, built-ins, and ubiquitous local variable names
# that appear in virtually every function body but never represent a
# meaningful call target (e.g. `self`, `data`, `result`).
_EXCLUDED_NAMES: frozenset[str] = (
    frozenset(keyword.kwlist)
    | frozenset(dir(__builtins__) if not isinstance(__builtins__, dict) else __builtins__)
    | frozenset({
        "self", "cls", "args", "kwargs", "data", "result", "error",
        "value", "key", "name", "path", "index", "item", "items",
        "text", "line", "lines", "content", "output", "response",
        "config", "options", "params", "info", "msg", "obj", "ctx",
        "row", "col", "val", "buf", "ret", "tmp", "src", "dst",
        "e", "ex", "err", "ok", "yes", "no",
    })
)


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

    # Filter to names worth matching: skip single-char names and excluded noise
    candidate_names = {
        name for name in name_to_ids
        if len(name) >= 2 and name not in _EXCLUDED_NAMES
    }

    # Pre-compile a single regex to extract all word-boundary identifiers
    _WORD_RE = re.compile(r"\b[A-Za-z_]\w*\b")

    call_graph: dict[str, list[str]] = {}
    repo_root = Path(index.repo_path)

    # Cache file contents to avoid re-reading the same file for every symbol
    _file_cache: dict[str, bytes] = {}

    for sym in index.symbols.values():
        if sym.kind not in callable_kinds:
            continue

        byte_length = sym.byte_end - sym.byte_start
        if byte_length <= 0:
            continue

        # Read file from cache or disk
        file_key = sym.file_path
        if file_key not in _file_cache:
            source_path = repo_root / sym.file_path
            if not source_path.is_file():
                _file_cache[file_key] = b""
                continue
            try:
                _file_cache[file_key] = source_path.read_bytes()
            except OSError:
                _file_cache[file_key] = b""
                continue

        raw = _file_cache[file_key]
        if not raw:
            continue

        try:
            body = raw[sym.byte_start : sym.byte_end].decode("utf-8", errors="replace")
        except (IndexError, OSError):
            continue

        # Extract all identifiers in the body and intersect with known names
        body_words = set(_WORD_RE.findall(body))
        matched_names = body_words & candidate_names

        callees: list[str] = []
        for name in matched_names:
            for callee_id in name_to_ids[name]:
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
