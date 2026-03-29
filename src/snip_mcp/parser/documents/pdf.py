"""PDF document parser — requires pymupdf (fitz)."""

from __future__ import annotations

from pathlib import Path

import fitz  # pymupdf

from snip_mcp.parser.documents.base import DocumentFile, DocumentParser, DocumentSection
from snip_mcp.parser.symbols import compute_content_hash


class PdfParser(DocumentParser):
    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".pdf",)

    @property
    def format_name(self) -> str:
        return "pdf"

    def parse(self, file_path: Path, rel_path: str) -> DocumentFile:
        file_bytes = file_path.read_bytes()
        doc = fitz.open(file_path)
        sections: list[DocumentSection] = []

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            text = page.get_text()
            page_num = page_idx + 1

            if not text.strip():
                continue

            sec_id = f"{rel_path}::page::Page {page_num}::{page_num}"
            sections.append(
                DocumentSection(
                    id=sec_id,
                    title=f"Page {page_num}",
                    section_type="page",
                    file_path=rel_path,
                    line_start=page_num,
                    line_end=page_num,
                    byte_start=0,
                    byte_end=len(file_bytes),
                    content_preview=text.strip()[:200],
                    level=0,
                    metadata={"page_number": str(page_num)},
                )
            )

            # Try to detect headings via font size heuristic
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:  # text block
                    continue
                for line_data in block.get("lines", []):
                    for span in line_data.get("spans", []):
                        font_size = span.get("size", 12)
                        span_text = span.get("text", "").strip()
                        if font_size >= 16 and span_text and len(span_text) < 200:
                            heading_id = f"{rel_path}::heading::{span_text}::{page_num}"
                            # Avoid duplicating the page section
                            if heading_id not in {s.id for s in sections}:
                                sections.append(
                                    DocumentSection(
                                        id=heading_id,
                                        title=span_text,
                                        section_type="heading",
                                        file_path=rel_path,
                                        line_start=page_num,
                                        line_end=page_num,
                                        byte_start=0,
                                        byte_end=len(file_bytes),
                                        content_preview=span_text[:200],
                                        level=1 if font_size >= 24 else 2,
                                        parent_id=sec_id,
                                    )
                                )

        doc.close()

        return DocumentFile(
            file_path=rel_path,
            format=self.format_name,
            sections=sections,
            content_hash=compute_content_hash(file_bytes.hex()),
            file_size=len(file_bytes),
        )
