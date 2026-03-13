"""get_repo_outline tool — high-level overview of an indexed repo."""

from __future__ import annotations

from collections import Counter

from snip_mcp.summarizer import summarize_repo
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_repo_outline(repo_path: str) -> dict:
    """Get a high-level overview of an indexed repository.

    Includes: directory structure summary, language breakdown, symbol kind distribution.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # Directory stats: count files per top-level directory
    dir_stats: Counter[str] = Counter()
    for rel_path in index.files:
        parts = rel_path.replace("\\", "/").split("/")
        top_dir = parts[0] if len(parts) > 1 else "(root)"
        dir_stats[top_dir] += 1

    # Symbol kind distribution
    kind_stats: Counter[str] = Counter()
    for sym in index.symbols.values():
        kind_val = sym.kind.value if hasattr(sym.kind, "value") else str(sym.kind)
        kind_stats[kind_val] += 1

    # Top files by symbol count
    top_files = sorted(
        [
            {"file": fp, "symbols": len(fs.symbols), "language": fs.language}
            for fp, fs in index.files.items()
        ],
        key=lambda x: x["symbols"],
        reverse=True,
    )[:20]

    return meta_envelope(
        {
            "repo_name": index.repo_name,
            "repo_path": index.repo_path,
            "summary": summarize_repo(index.total_files, index.total_symbols, index.language_stats),
            "total_files": index.total_files,
            "total_symbols": index.total_symbols,
            "indexed_at": index.indexed_at,
            "languages": dict(index.language_stats),
            "directories": dict(dir_stats.most_common(30)),
            "symbol_kinds": dict(kind_stats.most_common()),
            "top_files_by_symbols": top_files,
        },
        repo_path=index.repo_path,
    )
