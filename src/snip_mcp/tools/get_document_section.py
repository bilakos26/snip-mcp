"""get_document_section tool — retrieve specific section content via byte offsets."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_document_section(repo_path: str, section_id: str) -> dict:
    """Retrieve the content of a specific document section.

    Uses byte offsets for efficient retrieval on text-based documents
    (markdown, csv). For binary documents (pdf, docx, etc.), returns
    the stored content preview.

    Args:
        repo_path: Absolute path to the indexed folder.
        section_id: The section ID to retrieve.

    Returns:
        Envelope with section content.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # Find the section across all documents
    target_section = None
    target_doc = None
    for doc in index.documents.values():
        for sec in doc.sections:
            if sec.id == section_id:
                target_section = sec
                target_doc = doc
                break
        if target_section:
            break

    if target_section is None:
        return meta_envelope(
            {"error": f"Section not found: {section_id}"},
            repo_path=repo_path,
        )

    # Try byte-offset retrieval for text-based formats
    content = target_section.content_preview
    if (
        target_doc.format in ("markdown", "csv")
        and target_section.byte_end > target_section.byte_start
    ):
        source_path = Path(index.repo_path) / target_section.file_path
        if source_path.is_file():
            try:
                with source_path.open("rb") as fh:
                    fh.seek(target_section.byte_start)
                    raw = fh.read(target_section.byte_end - target_section.byte_start)
                content = raw.decode("utf-8", errors="replace")
            except OSError:
                pass

    return meta_envelope(
        {
            "section_id": section_id,
            "title": target_section.title,
            "type": target_section.section_type,
            "file_path": target_section.file_path,
            "format": target_doc.format,
            "line_start": target_section.line_start,
            "line_end": target_section.line_end,
            "content": content,
            "metadata": dict(target_section.metadata),
        },
        repo_path=index.repo_path,
    )
