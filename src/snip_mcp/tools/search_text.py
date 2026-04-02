"""search_text tool — full-text search with context lines."""

from __future__ import annotations

import re
from pathlib import Path

from snip_mcp.security import safe_read
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def search_text(
    repo_path: str,
    query: str,
    *,
    file_pattern: str | None = None,
    case_sensitive: bool = False,
    context_lines: int = 2,
    max_results: int = 50,
    regex: bool = False,
) -> dict:
    """Full-text search across indexed files.

    Args:
        repo_path: Path to the indexed folder.
        query: Search string or regex pattern.
        file_pattern: Optional file path substring filter.
        case_sensitive: Case-sensitive search.
        context_lines: Number of context lines before/after match.
        max_results: Maximum results to return.
        regex: Treat query as regex pattern.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    if regex:
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query, flags)
        except re.error as e:
            return meta_envelope({"error": f"Invalid regex: {e}"})
    else:
        pattern = None
        if not case_sensitive:
            query_match = query.lower()
        else:
            query_match = query

    results = []
    root = Path(index.repo_path)

    # Search code files
    for rel_path, file_syms in sorted(index.files.items()):
        if file_pattern and file_pattern.lower() not in rel_path.lower():
            continue

        if len(results) >= max_results:
            break

        full_path = root / rel_path
        content = safe_read(full_path)
        if content is None:
            continue

        lines = content.split("\n")

        for i, line in enumerate(lines):
            if len(results) >= max_results:
                break

            matched = False
            if pattern is not None:
                matched = bool(pattern.search(line))
            elif case_sensitive:
                matched = query_match in line
            else:
                matched = query_match in line.lower()

            if matched:
                # Gather context
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(lines), i + context_lines + 1)
                context = []
                for j in range(ctx_start, ctx_end):
                    prefix = ">" if j == i else " "
                    context.append(f"{prefix} {j + 1}: {lines[j]}")

                results.append(
                    {
                        "file_path": rel_path,
                        "line": i + 1,
                        "match": line.strip(),
                        "context": "\n".join(context),
                        "language": file_syms.language,
                    }
                )

    # Search document files (markdown, docx, xlsx, pptx, pdf, csv)
    for rel_path, doc_file in sorted(index.documents.items()):
        if rel_path in index.files:
            continue  # already searched as code

        if file_pattern and file_pattern.lower() not in rel_path.lower():
            continue

        if len(results) >= max_results:
            break

        full_path = root / rel_path
        content = safe_read(full_path)
        if content is None:
            continue

        lines = content.split("\n")

        for i, line in enumerate(lines):
            if len(results) >= max_results:
                break

            matched = False
            if pattern is not None:
                matched = bool(pattern.search(line))
            elif case_sensitive:
                matched = query_match in line
            else:
                matched = query_match in line.lower()

            if matched:
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(lines), i + context_lines + 1)
                context = []
                for j in range(ctx_start, ctx_end):
                    prefix = ">" if j == i else " "
                    context.append(f"{prefix} {j + 1}: {lines[j]}")

                results.append(
                    {
                        "file_path": rel_path,
                        "line": i + 1,
                        "match": line.strip(),
                        "context": "\n".join(context),
                        "language": doc_file.format,
                    }
                )

    return meta_envelope(
        {
            "query": query,
            "total_matches": len(results),
            "results": results,
        },
        repo_path=index.repo_path,
    )
