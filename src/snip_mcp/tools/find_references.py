"""find_references tool — find usage of a symbol/module name across the codebase."""

from __future__ import annotations

import re
from pathlib import Path

from snip_mcp.security import safe_read
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def find_references(
    repo_path: str,
    name: str,
    *,
    file_pattern: str | None = None,
    max_results: int = 50,
) -> dict:
    """Find references to a symbol name across the indexed codebase.

    Searches for word-boundary matches of the name in all indexed files.

    Args:
        repo_path: Path to the indexed folder.
        name: Symbol or module name to search for.
        file_pattern: Optional file path substring filter.
        max_results: Maximum results to return.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # Use word boundary matching
    try:
        pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    except re.error:
        pattern = re.compile(re.escape(name))

    root = Path(index.repo_path)
    references: list[dict] = []

    for rel_path, file_syms in sorted(index.files.items()):
        if len(references) >= max_results:
            break

        if file_pattern and file_pattern.lower() not in rel_path.lower():
            continue

        full_path = root / rel_path
        content = safe_read(full_path)
        if content is None:
            continue

        lines = content.split("\n")
        file_refs: list[dict] = []

        for i, line in enumerate(lines):
            if pattern.search(line):
                file_refs.append(
                    {
                        "line": i + 1,
                        "text": line.strip(),
                    }
                )

        if file_refs:
            references.append(
                {
                    "file_path": rel_path,
                    "language": file_syms.language,
                    "matches": file_refs[:10],  # Cap per-file matches
                    "total_in_file": len(file_refs),
                }
            )

    return meta_envelope(
        {
            "name": name,
            "total_files": len(references),
            "total_matches": sum(r["total_in_file"] for r in references),
            "references": references,
        },
        repo_path=index.repo_path,
    )
