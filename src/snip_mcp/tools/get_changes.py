"""get_changes tool — shows symbols added/modified/removed since last index."""

from __future__ import annotations

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_changes(repo_path: str) -> dict:
    """Show symbols added, modified, or removed since the last index.

    Compares current symbol hashes against ``previous_symbol_hashes``
    stored during the last re-index.

    Args:
        repo_path: Absolute path to the indexed folder.

    Returns:
        Envelope with added, modified, and removed symbol lists.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    previous = index.previous_symbol_hashes
    if not previous:
        return meta_envelope(
            {"message": "No previous index data. Re-index to track changes."},
            repo_path=index.repo_path,
        )

    current_hashes: dict[str, str] = {sid: sym.content_hash for sid, sym in index.symbols.items()}

    added = []
    modified = []
    removed = []

    # Symbols in current but not in previous -> added
    # Symbols in both but hash differs -> modified
    for sid, current_hash in current_hashes.items():
        sym = index.symbols[sid]
        info = {
            "symbol_id": sid,
            "name": sym.name,
            "kind": sym.kind.value,
            "file_path": sym.file_path,
            "line_start": sym.line_start,
        }
        if sid not in previous:
            added.append(info)
        elif previous[sid] != current_hash:
            modified.append(info)

    # Symbols in previous but not in current -> removed
    for sid, old_hash in previous.items():
        if sid not in current_hashes:
            # We don't have the symbol object anymore, extract info from ID
            parts = sid.split("::")
            removed.append(
                {
                    "symbol_id": sid,
                    "name": parts[2] if len(parts) > 2 else sid,
                    "kind": parts[1] if len(parts) > 1 else "unknown",
                    "file_path": parts[0] if parts else "",
                }
            )

    return meta_envelope(
        {
            "added": added,
            "modified": modified,
            "removed": removed,
            "summary": {
                "total_added": len(added),
                "total_modified": len(modified),
                "total_removed": len(removed),
            },
        },
        repo_path=index.repo_path,
    )
