"""search_annotations tool — find symbols by decorator/annotation pattern."""

from __future__ import annotations

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def search_annotations(
    repo_path: str,
    pattern: str,
    *,
    max_results: int = 50,
) -> dict:
    """Find symbols by decorator/annotation pattern.

    Searches the existing ``Symbol.decorators`` tuple for matches.

    Args:
        repo_path: Absolute path to the indexed folder.
        pattern: Decorator/annotation pattern to search for (e.g. "router.get", "pytest.mark").
        max_results: Maximum results to return.

    Returns:
        Envelope with matching symbols.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    pattern_lower = pattern.lower()
    results = []

    for sym in index.symbols.values():
        if not sym.decorators:
            continue

        for dec in sym.decorators:
            if pattern_lower in dec.lower():
                results.append(
                    {
                        "symbol_id": sym.id,
                        "name": sym.name,
                        "kind": sym.kind.value,
                        "file_path": sym.file_path,
                        "line_start": sym.line_start,
                        "signature": sym.signature,
                        "decorator": dec,
                    }
                )
                break

        if len(results) >= max_results:
            break

    return meta_envelope(
        {
            "pattern": pattern,
            "total_matches": len(results),
            "results": results,
        },
        repo_path=index.repo_path,
    )
