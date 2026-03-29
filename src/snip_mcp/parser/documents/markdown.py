"""Markdown document parser — pure Python, no external deps."""

from __future__ import annotations

import re
from pathlib import Path

from snip_mcp.parser.documents.base import DocumentFile, DocumentParser, DocumentSection
from snip_mcp.parser.symbols import compute_content_hash

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"^```(\w*)", re.MULTILINE)
_TABLE_RE = re.compile(r"^\|(.+)\|$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class MarkdownParser(DocumentParser):
    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".md", ".markdown", ".mdx")

    @property
    def format_name(self) -> str:
        return "markdown"

    def parse(self, file_path: Path, rel_path: str) -> DocumentFile:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        content_bytes = content.encode("utf-8")
        sections: list[DocumentSection] = []
        lines = content.split("\n")

        # Track heading stack for parent-child
        heading_stack: list[tuple[int, str]] = []  # (level, section_id)

        # Frontmatter
        fm_match = _FRONTMATTER_RE.match(content)
        if fm_match:
            fm_text = fm_match.group(1)
            end_pos = fm_match.end()
            line_end = content[:end_pos].count("\n") + 1
            sec_id = f"{rel_path}::frontmatter::yaml::1"
            sections.append(
                DocumentSection(
                    id=sec_id,
                    title="Frontmatter",
                    section_type="frontmatter",
                    file_path=rel_path,
                    line_start=1,
                    line_end=line_end,
                    byte_start=0,
                    byte_end=end_pos,
                    content_preview=fm_text[:200],
                    level=0,
                    metadata={"format": "yaml"},
                )
            )

        # Headings
        for m in _HEADING_RE.finditer(content):
            level = len(m.group(1))
            title = m.group(2).strip()
            byte_start = len(content[: m.start()].encode("utf-8"))
            line_start = content[: m.start()].count("\n") + 1

            # Find section end (next heading of same or higher level, or EOF)
            byte_end = len(content_bytes)
            line_end = len(lines)
            for m2 in _HEADING_RE.finditer(content, m.end()):
                next_level = len(m2.group(1))
                if next_level <= level:
                    byte_end = len(content[: m2.start()].encode("utf-8"))
                    line_end = content[: m2.start()].count("\n")
                    break

            section_content = content[m.start() : m.start() + (byte_end - byte_start)]
            sec_id = f"{rel_path}::heading::{title}::{line_start}"

            # Determine parent
            parent_id = ""
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            if heading_stack:
                parent_id = heading_stack[-1][1]
            heading_stack.append((level, sec_id))

            sections.append(
                DocumentSection(
                    id=sec_id,
                    title=title,
                    section_type="heading",
                    file_path=rel_path,
                    line_start=line_start,
                    line_end=line_end,
                    byte_start=byte_start,
                    byte_end=byte_end,
                    content_preview=section_content[:200],
                    level=level,
                    parent_id=parent_id,
                )
            )

        # Code blocks
        in_code = False
        code_start_line = 0
        code_start_byte = 0
        code_lang = ""
        byte_offset = 0
        for i, line in enumerate(lines, 1):
            line_bytes = len(line.encode("utf-8")) + 1  # +1 for newline
            if line.startswith("```"):
                if not in_code:
                    in_code = True
                    code_start_line = i
                    code_start_byte = byte_offset
                    lang_match = re.match(r"```(\w+)", line)
                    code_lang = lang_match.group(1) if lang_match else ""
                else:
                    in_code = False
                    sec_id = f"{rel_path}::code_block::{code_lang or 'code'}::{code_start_line}"
                    block_end_byte = byte_offset + line_bytes
                    block_text = content_bytes[code_start_byte:block_end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    sections.append(
                        DocumentSection(
                            id=sec_id,
                            title=f"Code block ({code_lang})" if code_lang else "Code block",
                            section_type="code_block",
                            file_path=rel_path,
                            line_start=code_start_line,
                            line_end=i,
                            byte_start=code_start_byte,
                            byte_end=block_end_byte,
                            content_preview=block_text[:200],
                            metadata={"language": code_lang} if code_lang else {},
                        )
                    )
            byte_offset += line_bytes

        return DocumentFile(
            file_path=rel_path,
            format=self.format_name,
            sections=sections,
            content_hash=compute_content_hash(content),
            file_size=len(content_bytes),
        )
