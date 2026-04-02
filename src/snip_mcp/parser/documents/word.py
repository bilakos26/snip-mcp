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

        # Collect paragraphs with metadata
        parsed_paras: list[tuple[int, int, str, str]] = []  # (line, level, text, sec_id)
        line = 0
        for para in doc.paragraphs:
            line += 1
            style_name = para.style.name if para.style else ""
            text = para.text.strip()
            if not text:
                continue
            level = _HEADING_STYLES.get(style_name, 0)
            parsed_paras.append((line, level, text, ""))

        # Find heading indices
        heading_indices = [i for i, (_, lvl, _, _) in enumerate(parsed_paras) if lvl > 0]

        if heading_indices:
            # Build sections with body text under each heading
            for hi, idx in enumerate(heading_indices):
                h_line, h_level, h_text, _ = parsed_paras[idx]
                sec_id = f"{rel_path}::heading::{h_text}::{h_line}"

                parent_id = ""
                while heading_stack and heading_stack[-1][0] >= h_level:
                    heading_stack.pop()
                if heading_stack:
                    parent_id = heading_stack[-1][1]
                heading_stack.append((h_level, sec_id))

                # Collect body text until next heading of same or higher level
                body_parts = [h_text]
                end_line = h_line
                next_idx = heading_indices[hi + 1] if hi + 1 < len(heading_indices) else len(parsed_paras)
                for bi in range(idx + 1, next_idx):
                    b_line, b_level, b_text, _ = parsed_paras[bi]
                    if b_level > 0:
                        break
                    body_parts.append(b_text)
                    end_line = b_line

                content = "\n".join(body_parts)
                sections.append(
                    DocumentSection(
                        id=sec_id,
                        title=h_text,
                        section_type="heading",
                        file_path=rel_path,
                        line_start=h_line,
                        line_end=end_line,
                        byte_start=0,
                        byte_end=len(file_bytes),
                        content_preview=content[:500],
                        level=h_level,
                        parent_id=parent_id,
                    )
                )
        else:
            # Fallback: no headings — collect all body text into a single section
            body_lines = [text for _, _, text, _ in parsed_paras]
            if body_lines:
                full_body = "\n".join(body_lines)
                sec_id = f"{rel_path}::body::Document Body::1"
                sections.append(
                    DocumentSection(
                        id=sec_id,
                        title="Document Body",
                        section_type="body",
                        file_path=rel_path,
                        line_start=1,
                        line_end=len(body_lines),
                        byte_start=0,
                        byte_end=len(file_bytes),
                        content_preview=full_body[:500],
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
