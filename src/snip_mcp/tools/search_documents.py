"""search_documents tool — search document sections by title/content."""

from __future__ import annotations

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def search_documents(
    repo_path: str,
    query: str,
    *,
    format: str | None = None,
    max_results: int = 20,
) -> dict:
    """Search document sections by title or content preview.

    Args:
        repo_path: Absolute path to the indexed folder.
        query: Search query string.
        format: Optional filter by document format (markdown, excel, etc.).
        max_results: Maximum results to return.

    Returns:
        Envelope with matching sections.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    query_lower = query.lower()
    results = []

    for doc in index.documents.values():
        if format and doc.format != format:
            continue

        for sec in doc.sections:
            score = 0.0

            title_lower = sec.title.lower()
            if query_lower == title_lower:
                score = 100
            elif query_lower in title_lower:
                score = 50
            elif query_lower in sec.content_preview.lower():
                score = 20

            # Check metadata values too
            if score == 0:
                for val in sec.metadata.values():
                    if query_lower in val.lower():
                        score = 10
                        break

            if score > 0:
                results.append((score, sec, doc))

            if len(results) >= max_results * 3:  # collect extras for sorting
                break

    results.sort(key=lambda x: x[0], reverse=True)
    top = results[:max_results]

    output = []
    for score, sec, doc in top:
        output.append(
            {
                "section_id": sec.id,
                "title": sec.title,
                "type": sec.section_type,
                "file_path": sec.file_path,
                "format": doc.format,
                "line_start": sec.line_start,
                "content_preview": sec.content_preview[:150],
                "score": score,
            }
        )

    return meta_envelope(
        {
            "query": query,
            "total_matches": len(results),
            "results": output,
        },
        repo_path=index.repo_path,
    )
