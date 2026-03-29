"""get_call_graph tool — returns what a symbol calls (with depth traversal)."""

from __future__ import annotations

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_call_graph(
    repo_path: str,
    symbol_id: str,
    depth: int = 1,
) -> dict:
    """Get the call graph for a symbol — what does it call?

    Args:
        repo_path: Absolute path to the indexed folder.
        symbol_id: The symbol to get callees for.
        depth: How many levels deep to traverse (default 1).

    Returns:
        Envelope with call graph data.
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

    # BFS traversal up to `depth` levels
    result: dict[str, list[dict]] = {}
    visited: set[str] = set()
    current_level = [symbol_id]

    for d in range(depth):
        next_level: list[str] = []
        for sid in current_level:
            if sid in visited:
                continue
            visited.add(sid)
            callees = index.call_graph.get(sid, [])
            callee_infos = []
            for cid in callees:
                callee_sym = index.symbols.get(cid)
                if callee_sym:
                    callee_infos.append(
                        {
                            "symbol_id": cid,
                            "name": callee_sym.name,
                            "kind": callee_sym.kind.value,
                            "file_path": callee_sym.file_path,
                            "line": callee_sym.line_start,
                        }
                    )
                    next_level.append(cid)
            if callee_infos:
                result[sid] = callee_infos
        current_level = next_level

    return meta_envelope(
        {
            "symbol_id": symbol_id,
            "symbol_name": sym.name,
            "depth": depth,
            "call_graph": result,
            "total_callees": sum(len(v) for v in result.values()),
        },
        repo_path=repo_path,
    )
