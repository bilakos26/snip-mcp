"""list_repos tool — lists all indexed folders."""

from __future__ import annotations

from snip_mcp.tools._utils import get_store, meta_envelope


def list_repos() -> dict:
    """List all indexed repositories/folders."""
    store = get_store()
    indexes = store.list_repos()

    repos = []
    for idx in indexes:
        repos.append(
            {
                "repo_path": idx.repo_path,
                "repo_name": idx.repo_name,
                "total_files": idx.total_files,
                "total_symbols": idx.total_symbols,
                "languages": idx.language_stats,
                "indexed_at": idx.indexed_at,
            }
        )

    return meta_envelope(repos)
