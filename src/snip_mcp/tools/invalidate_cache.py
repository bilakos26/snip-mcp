"""invalidate_cache tool — delete a cached index."""

from __future__ import annotations

from snip_mcp.tools._utils import get_store, meta_envelope


def invalidate_cache(repo_path: str) -> dict:
    """Delete the cached index for a repository.

    Args:
        repo_path: Path to the indexed folder.
    """
    store = get_store()
    deleted = store.delete(repo_path)

    if deleted:
        return meta_envelope({"status": "deleted", "repo_path": repo_path})
    else:
        return meta_envelope({"status": "not_found", "repo_path": repo_path})
