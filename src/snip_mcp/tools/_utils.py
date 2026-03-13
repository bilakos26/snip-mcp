"""Shared utility functions for Snip MCP tools."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.storage.index_store import CodeIndex, IndexStore

_store = IndexStore()


def get_store() -> IndexStore:
    """Return the global IndexStore instance."""
    return _store


def resolve_repo(repo_path: str) -> tuple[CodeIndex | None, str]:
    """Resolve a repo path to its CodeIndex.

    Returns (index, error_message). If index is None, error_message explains why.
    """
    path = Path(repo_path).resolve()
    if not path.exists():
        return None, f"Path does not exist: {path}"
    if not path.is_dir():
        return None, f"Path is not a directory: {path}"

    index = _store.load(str(path))
    if index is None:
        return None, f"No index found for {path}. Run index_folder first."
    return index, ""


def meta_envelope(
    data: dict | list | str,
    *,
    repo_path: str = "",
    tokens_saved: int = 0,
) -> dict:
    """Wrap tool output in a standard envelope with metadata."""
    envelope: dict = {"data": data}
    if repo_path:
        envelope["repo_path"] = repo_path
    if tokens_saved > 0:
        envelope["tokens_saved"] = tokens_saved
    return envelope


def truncate(text: str, max_chars: int = 50000) -> str:
    """Truncate text to max_chars, adding a note if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated at {max_chars} chars]"


def relative_to_repo(file_path: str, repo_path: str) -> str:
    """Convert an absolute or relative file path to be relative to repo root."""
    try:
        return str(Path(file_path).relative_to(repo_path))
    except ValueError:
        return file_path
