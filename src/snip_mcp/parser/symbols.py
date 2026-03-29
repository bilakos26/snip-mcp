"""Core Symbol data model for Snip MCP.

Defines the canonical representation of code symbols extracted by language
parsers.  Every parsed file produces a ``FileSymbols`` container holding
zero-or-more ``Symbol`` records.  Symbols are immutable (frozen dataclasses)
so they can be stored in sets, used as dict keys, and safely shared across
threads.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple

# ---------------------------------------------------------------------------
# SymbolKind
# ---------------------------------------------------------------------------


class SymbolKind(str, Enum):
    """Enumeration of all symbol kinds recognised by Snip parsers.

    The enum inherits from ``str`` so that ``kind.value`` is always a plain
    string and JSON-serialises without extra work.
    """

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    MODULE = "module"
    VARIABLE = "variable"
    CONSTANT = "constant"
    PROPERTY = "property"
    TYPE_ALIAS = "type_alias"
    TRAIT = "trait"
    IMPL = "impl"
    NAMESPACE = "namespace"
    IMPORT_STMT = "import_stmt"
    DECORATOR = "decorator"

    # SQL-specific kinds
    SQL_TABLE = "sql_table"
    SQL_VIEW = "sql_view"
    SQL_CTE = "sql_cte"
    SQL_COLUMN = "sql_column"
    SQL_PROCEDURE = "sql_procedure"
    SQL_FUNCTION = "sql_function"

    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# ID & hash helpers
# ---------------------------------------------------------------------------


def make_symbol_id(
    file_path: str,
    kind: SymbolKind,
    name: str,
    line: int,
) -> str:
    """Generate a deterministic, human-readable symbol identifier.

    Format::

        {file_path}::{kind.value}::{name}::{line}

    Parameters
    ----------
    file_path:
        Relative path from the repository root (forward-slash separated).
    kind:
        The ``SymbolKind`` of the symbol.
    name:
        The symbol's declared name.
    line:
        1-based starting line number of the symbol in *file_path*.

    Returns
    -------
    str
        A unique identifier string.
    """
    return f"{file_path}::{kind.value}::{name}::{line}"


def compute_content_hash(content: str) -> str:
    """Return a truncated SHA-256 hex digest of *content*.

    The content is encoded as UTF-8 before hashing.  Only the first 16
    hex characters are returned -- enough to detect changes while keeping
    IDs compact.

    Parameters
    ----------
    content:
        Arbitrary text whose hash is needed.

    Returns
    -------
    str
        First 16 characters of the SHA-256 hex digest.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Parameter (for type info extraction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Parameter:
    """A single parameter of a function or method.

    Attributes
    ----------
    name:
        Parameter name.
    type_annotation:
        Type annotation string (empty if absent).
    default_value:
        Default value string (empty if absent).
    """

    name: str
    type_annotation: str = ""
    default_value: str = ""


# ---------------------------------------------------------------------------
# Symbol
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Symbol:
    """Immutable representation of a single code symbol.

    Being *frozen* makes ``Symbol`` instances hashable and safe to use as
    dictionary keys or set members.

    Attributes
    ----------
    id:
        Unique identifier generated via :func:`make_symbol_id`.
    name:
        Declared name of the symbol (e.g. ``"MyClass"``).
    kind:
        Category of the symbol.
    file_path:
        Relative path from the repository root.
    line_start:
        1-based starting line number.
    line_end:
        1-based ending line number (inclusive).
    byte_start:
        Byte offset from the beginning of the file (for O(1) seeking).
    byte_end:
        Byte offset end (exclusive).
    signature:
        First line / declaration signature of the symbol.
    docstring:
        Extracted docstring, if any.
    parent_id:
        ``id`` of the enclosing symbol (empty string for top-level symbols).
    children:
        Tuple of ``id`` strings for symbols nested inside this one.
    content_hash:
        Truncated SHA-256 hash of the symbol's source text.
    language:
        Language identifier (e.g. ``"python"``, ``"sql"``).
    decorators:
        Tuple of decorator names applied to this symbol.
    imports:
        Tuple of import strings this symbol uses (may be populated in a
        later analysis pass).
    """

    id: str
    name: str
    kind: SymbolKind
    file_path: str
    line_start: int
    line_end: int
    byte_start: int
    byte_end: int
    signature: str
    docstring: str = ""
    parent_id: str = ""
    children: Tuple[str, ...] = ()
    content_hash: str = ""
    language: str = ""
    decorators: Tuple[str, ...] = ()
    imports: Tuple[str, ...] = ()
    return_type: str = ""
    parameters: Tuple[Parameter, ...] = ()


# ---------------------------------------------------------------------------
# FileSymbols
# ---------------------------------------------------------------------------


@dataclass
class FileSymbols:
    """Container for all symbols extracted from a single file.

    Attributes
    ----------
    file_path:
        Relative path from the repository root.
    language:
        Language identifier (e.g. ``"python"``).
    symbols:
        List of :class:`Symbol` instances found in the file.
    imports:
        Raw import strings (e.g. ``"import os"``, ``"from pathlib import Path"``).
    content_hash:
        Truncated SHA-256 hash of the *entire* file content.
    file_size:
        Size of the file in bytes.
    line_count:
        Total number of lines in the file.
    """

    file_path: str
    language: str
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    content_hash: str = ""
    file_size: int = 0
    line_count: int = 0
