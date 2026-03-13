"""get_file_tree tool — directory tree with language and symbol annotations."""

from __future__ import annotations

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_file_tree(repo_path: str, *, max_depth: int = 5, show_symbols: bool = False) -> dict:
    """Get the directory tree of an indexed repo.

    Args:
        repo_path: Path to the indexed folder.
        max_depth: Maximum directory depth to show.
        show_symbols: If True, annotate files with symbol counts.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # Build tree structure from file paths
    tree: dict = {}
    for rel_path, file_syms in sorted(index.files.items()):
        parts = rel_path.replace("\\", "/").split("/")
        node = tree
        for i, part in enumerate(parts[:-1]):
            if i >= max_depth:
                break
            if part not in node:
                node[part] = {}
            node = node[part]

        if len(parts) - 1 < max_depth:
            filename = parts[-1]
            annotation = f"[{file_syms.language}]"
            if show_symbols:
                annotation += f" ({len(file_syms.symbols)} symbols)"
            node[filename] = annotation

    return meta_envelope(
        {
            "repo_name": index.repo_name,
            "total_files": index.total_files,
            "tree": tree,
        },
        repo_path=index.repo_path,
    )
