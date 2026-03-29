"""Word document parser — requires python-docx."""

from __future__ import annotations

from pathlib import Path

import docx

from snip_mcp.parser.documents.base import DocumentFile, DocumentParser, DocumentSection
from snip_mcp.parser.symbols import compute_content_hash

_HEADING_STYLES = {
    "Heading 1": 1,
    "Heading 2": 2,
    "Heading 3": 3,
    "Heading 4": 4,
    "Heading 5": 5,
    "Heading 6": 6,
}


class WordParser(DocumentParser):
    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".docx",)

    @property
    def format_name(self) -> str:
        return "word"

    def parse(self, file_path: Path, rel_path: str) -> DocumentFile:
        file_bytes = file_path.read_bytes()
        doc = docx.Document(file_path)
        sections: list[DocumentSection] = []
        heading_stack: list[tuple[int, str]] = []

        line = 0
        for para in doc.paragraphs:
            line += 1
            style_name = para.style.name if para.style else ""
            text = para.text.strip()

            if not text:
                continue

            level = _HEADING_STYLES.get(style_name, 0)
            if level > 0:
                sec_id = f"{rel_path}::heading::{text}::{line}"

                parent_id = ""
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                if heading_stack:
                    parent_id = heading_stack[-1][1]
                heading_stack.append((level, sec_id))

                sections.append(
                    DocumentSection(
                        id=sec_id,
                        title=text,
                        section_type="heading",
                        file_path=rel_path,
                        line_start=line,
                        line_end=line,
                        byte_start=0,
                        byte_end=len(file_bytes),
                        content_preview=text[:200],
                        level=level,
                        parent_id=parent_id,
                    )
                )

        # Tables
        for table_idx, table in enumerate(doc.tables):
            headers = []
            if table.rows:
                headers = [cell.text.strip() for cell in table.rows[0].cells]

            preview_rows = []
            for row in table.rows[:5]:
                preview_rows.append(" | ".join(cell.text.strip() for cell in row.cells))
            preview = "\n".join(preview_rows)

            sec_id = f"{rel_path}::table::table_{table_idx + 1}::{table_idx + 1}"
            sections.append(
                DocumentSection(
                    id=sec_id,
                    title=f"Table {table_idx + 1}",
                    section_type="table",
                    file_path=rel_path,
                    line_start=0,
                    line_end=0,
                    byte_start=0,
                    byte_end=len(file_bytes),
                    content_preview=preview[:200],
                    metadata={
                        "rows": str(len(table.rows)),
                        "columns": str(len(headers)),
                        "headers": ", ".join(headers[:10]),
                    },
                )
            )

        return DocumentFile(
            file_path=rel_path,
            format=self.format_name,
            sections=sections,
            content_hash=compute_content_hash(file_bytes.hex()),
            file_size=len(file_bytes),
        )
