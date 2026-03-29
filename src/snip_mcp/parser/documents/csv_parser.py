"""CSV/TSV document parser — stdlib csv, no external deps."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from snip_mcp.parser.documents.base import DocumentFile, DocumentParser, DocumentSection
from snip_mcp.parser.symbols import compute_content_hash


class CsvParser(DocumentParser):
    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return (".csv", ".tsv")

    @property
    def format_name(self) -> str:
        return "csv"

    def parse(self, file_path: Path, rel_path: str) -> DocumentFile:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        content_bytes = content.encode("utf-8")

        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
        reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        rows = list(reader)

        sections: list[DocumentSection] = []

        if not rows:
            return DocumentFile(
                file_path=rel_path,
                format=self.format_name,
                sections=sections,
                content_hash=compute_content_hash(content),
                file_size=len(content_bytes),
            )

        headers = rows[0] if rows else []
        row_count = len(rows) - 1  # exclude header

        # Infer data types from first few data rows
        type_samples: dict[int, set[str]] = {i: set() for i in range(len(headers))}
        for row in rows[1:6]:  # sample first 5 data rows
            for i, val in enumerate(row):
                if i >= len(headers):
                    break
                if not val:
                    type_samples[i].add("empty")
                elif val.replace(".", "", 1).replace("-", "", 1).isdigit():
                    type_samples[i].add("numeric")
                else:
                    type_samples[i].add("text")

        inferred_types = {}
        for i, types in type_samples.items():
            if i < len(headers):
                types.discard("empty")
                if types == {"numeric"}:
                    inferred_types[headers[i]] = "numeric"
                else:
                    inferred_types[headers[i]] = "text"

        # Header section
        header_preview = delimiter.join(headers)
        sec_id = f"{rel_path}::headers::columns::1"
        sections.append(
            DocumentSection(
                id=sec_id,
                title="Column Headers",
                section_type="headers",
                file_path=rel_path,
                line_start=1,
                line_end=1,
                byte_start=0,
                byte_end=len(header_preview.encode("utf-8")),
                content_preview=header_preview[:200],
                metadata={
                    "columns": str(len(headers)),
                    "rows": str(row_count),
                    "types": str(inferred_types),
                },
            )
        )

        # Sample rows section
        if row_count > 0:
            sample_lines = []
            for row in rows[1:6]:
                sample_lines.append(delimiter.join(row))
            sample_text = "\n".join(sample_lines)
            sec_id = f"{rel_path}::sample::data::2"
            sections.append(
                DocumentSection(
                    id=sec_id,
                    title=f"Sample Data ({min(5, row_count)} of {row_count} rows)",
                    section_type="sample",
                    file_path=rel_path,
                    line_start=2,
                    line_end=min(6, len(rows)),
                    byte_start=0,
                    byte_end=len(content_bytes),
                    content_preview=sample_text[:200],
                    metadata={"sample_rows": str(min(5, row_count))},
                )
            )

        return DocumentFile(
            file_path=rel_path,
            format=self.format_name,
            sections=sections,
            content_hash=compute_content_hash(content),
            file_size=len(content_bytes),
        )
