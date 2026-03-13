"""search_symbols tool — weighted scoring search across symbol index."""

from __future__ import annotations

from snip_mcp.summarizer import summarize_symbol
from snip_mcp.tools._utils import meta_envelope, resolve_repo

# Scoring weights
_WEIGHT_NAME_EXACT = 100
_WEIGHT_NAME_PREFIX = 20
_WEIGHT_NAME_SUBSTRING = 10
_WEIGHT_SIGNATURE = 8
_WEIGHT_DOCSTRING = 5
_WEIGHT_FILE_PATH = 3


def search_symbols(
    repo_path: str,
    query: str,
    *,
    kind: str | None = None,
    file_pattern: str | None = None,
    max_results: int = 20,
) -> dict:
    """Search symbols using weighted scoring.

    Scoring weights:
    - Exact name match: +100
    - Name prefix match: +20
    - Name substring match: +10
    - Signature match: +8
    - Docstring match: +5
    - File path match: +3

    Args:
        repo_path: Path to the indexed folder.
        query: Search query string.
        kind: Optional filter by symbol kind (e.g., "function", "class").
        file_pattern: Optional filter by file path substring.
        max_results: Maximum results to return.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    query_lower = query.lower()
    scored: list[tuple[float, object]] = []

    for sym in index.symbols.values():
        # Filter by kind
        kind_val = sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind)
        if kind and kind_val != kind:
            continue

        # Filter by file pattern
        if file_pattern and file_pattern.lower() not in sym.file_path.lower():
            continue

        # Score
        score = 0.0
        name_lower = sym.name.lower()

        if name_lower == query_lower:
            score += _WEIGHT_NAME_EXACT
        elif name_lower.startswith(query_lower):
            score += _WEIGHT_NAME_PREFIX
        elif query_lower in name_lower:
            score += _WEIGHT_NAME_SUBSTRING

        if query_lower in sym.signature.lower():
            score += _WEIGHT_SIGNATURE

        if sym.docstring and query_lower in sym.docstring.lower():
            score += _WEIGHT_DOCSTRING

        if query_lower in sym.file_path.lower():
            score += _WEIGHT_FILE_PATH

        if score > 0:
            scored.append((score, sym))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    results = []
    for score, sym in top:
        results.append(
            {
                "symbol_id": sym.id,
                "name": sym.name,
                "kind": sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind),
                "file_path": sym.file_path,
                "line_start": sym.line_start,
                "signature": sym.signature,
                "summary": summarize_symbol(sym),
                "score": score,
            }
        )

    return meta_envelope(
        {
            "query": query,
            "total_matches": len(scored),
            "results": results,
        },
        repo_path=index.repo_path,
    )
