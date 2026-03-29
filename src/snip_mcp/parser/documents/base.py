"""Base dataclasses and ABC for document parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DocumentSection:
    """A single section within a parsed document."""

    id: str
    title: str
    section_type: str  # "heading", "table", "code_block", "slide", "sheet", etc.
    file_path: str
    line_start: int
    line_end: int
    byte_start: int
    byte_end: int
    content_preview: str  # first 200 chars
    level: int = 0
    parent_id: str = ""
    children: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class DocumentFile:
    """Container for a parsed document and its sections."""

    file_path: str
    format: str  # "markdown", "excel", "word", "powerpoint", "pdf", "csv"
    sections: list[DocumentSection] = field(default_factory=list)
    content_hash: str = ""
    file_size: int = 0


class DocumentParser(ABC):
    """Abstract base class for document parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> tuple[str, ...]:
        """File extensions this parser handles (including dot)."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Short format name (e.g. 'markdown', 'excel')."""

    @abstractmethod
    def parse(self, file_path: Path, rel_path: str) -> DocumentFile:
        """Parse a document file and return a DocumentFile with sections."""
