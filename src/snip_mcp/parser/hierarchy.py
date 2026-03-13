"""Parent-child symbol tree builder — organizes flat symbol lists into hierarchies."""

from __future__ import annotations

from snip_mcp.parser.symbols import Symbol


def build_hierarchy(symbols: list[Symbol]) -> list[Symbol]:
    """Build parent-child relationships between symbols based on line ranges.

    A symbol B is a child of symbol A if:
    - B.line_start >= A.line_start
    - B.line_end <= A.line_end
    - B is not A
    - A is the tightest enclosing symbol (smallest range)

    Returns a new list of Symbol instances with parent_id and children populated.
    """
    if not symbols:
        return []

    # Sort by line_start ascending, then by range size descending (larger ranges first)
    sorted_syms = sorted(symbols, key=lambda s: (s.line_start, -(s.line_end - s.line_start)))

    # For each symbol, find its parent (tightest enclosing symbol)
    parent_map: dict[str, str] = {}  # child_id -> parent_id
    children_map: dict[str, list[str]] = {s.id: [] for s in sorted_syms}

    for i, sym in enumerate(sorted_syms):
        best_parent: Symbol | None = None
        best_range = float("inf")

        for j in range(i):
            candidate = sorted_syms[j]
            if candidate.id == sym.id:
                continue
            # Check if candidate encloses sym
            if candidate.line_start <= sym.line_start and candidate.line_end >= sym.line_end:
                candidate_range = candidate.line_end - candidate.line_start
                if candidate_range < best_range:
                    best_range = candidate_range
                    best_parent = candidate

        if best_parent is not None:
            parent_map[sym.id] = best_parent.id
            children_map[best_parent.id].append(sym.id)

    # Rebuild symbols with parent/children info
    result: list[Symbol] = []
    for sym in sorted_syms:
        new_sym = Symbol(
            id=sym.id,
            name=sym.name,
            kind=sym.kind,
            file_path=sym.file_path,
            line_start=sym.line_start,
            line_end=sym.line_end,
            byte_start=sym.byte_start,
            byte_end=sym.byte_end,
            signature=sym.signature,
            docstring=sym.docstring,
            parent_id=parent_map.get(sym.id, ""),
            children=tuple(children_map.get(sym.id, [])),
            content_hash=sym.content_hash,
            language=sym.language,
            decorators=sym.decorators,
            imports=sym.imports,
        )
        result.append(new_sym)

    return result


def get_top_level_symbols(symbols: list[Symbol]) -> list[Symbol]:
    """Return only symbols that have no parent (top-level declarations)."""
    return [s for s in symbols if not s.parent_id]


def get_children(symbols: list[Symbol], parent_id: str) -> list[Symbol]:
    """Return direct children of a given symbol."""
    sym_map = {s.id: s for s in symbols}
    parent = sym_map.get(parent_id)
    if parent is None:
        return []
    return [sym_map[cid] for cid in parent.children if cid in sym_map]
