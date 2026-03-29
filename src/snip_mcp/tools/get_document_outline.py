"""get_document_outline tool — section hierarchy of a document."""

from __future__ import annotations

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_document_outline(repo_path: str, file_path: str) -> dict:
    """Get the section hierarchy of a document.

    Args:
        repo_path: Absolute path to the indexed folder.
        file_path: Relative path to the document within the repo.

    Returns:
        Envelope with document outline.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    rel = file_path.replace("\\", "/")
    doc = index.documents.get(rel)
    if doc is None:
        return meta_envelope(
            {"error": f"Document not found in index: {rel}"},
            repo_path=repo_path,
        )

    outline = []
    for sec in doc.sections:
        indent = "  " * sec.level
        outline.append(
            {
                "section_id": sec.id,
                "title": sec.title,
                "type": sec.section_type,
                "level": sec.level,
                "line_start": sec.line_start,
                "line_end": sec.line_end,
                "parent_id": sec.parent_id,
                "display": f"{indent}{sec.section_type}: {sec.title}",
            }
        )

    return meta_envelope(
        {
            "file_path": rel,
            "format": doc.format,
            "total_sections": len(doc.sections),
            "outline": outline,
        },
        repo_path=index.repo_path,
    )
