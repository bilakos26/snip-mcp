"""Persisted code-index storage for Snip MCP.

Manages saving, loading, and querying of :class:`CodeIndex` instances on disk.
Each indexed repository is stored as a single compact JSON file under
``~/.snip/indexes/``.  File names are derived from a SHA-256 hash of the
repository's absolute path so that the mapping is deterministic and
filesystem-safe.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from snip_mcp.parser.symbols import FileSymbols, Symbol, SymbolKind

# ---------------------------------------------------------------------------
# CodeIndex dataclass
# ---------------------------------------------------------------------------


@dataclass
class CodeIndex:
    """In-memory representation of a fully indexed repository.

    Attributes
    ----------
    repo_path:
        Absolute path to the indexed folder.
    repo_name:
        Short human-readable name (typically the folder basename).
    files:
        Mapping of *relative_path* to :class:`FileSymbols`.
    symbols:
        Mapping of *symbol_id* to :class:`Symbol` for O(1) lookup.
    file_hashes:
        Mapping of *relative_path* to content hash (for incremental re-index).
    indexed_at:
        ISO-8601 timestamp of the last full or incremental index run.
    language_stats:
        Mapping of language identifier to file count.
    total_symbols:
        Total number of symbols across all files.
    total_files:
        Total number of indexed files.
    """

    repo_path: str
    repo_name: str
    files: dict[str, FileSymbols] = field(default_factory=dict)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    file_hashes: dict[str, str] = field(default_factory=dict)
    indexed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    language_stats: dict[str, int] = field(default_factory=dict)
    total_symbols: int = 0
    total_files: int = 0


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialize_symbol(sym: Symbol) -> dict[str, Any]:
    """Convert a :class:`Symbol` to a plain dict suitable for JSON encoding."""
    return {
        "id": sym.id,
        "name": sym.name,
        "kind": sym.kind.value,
        "file_path": sym.file_path,
        "line_start": sym.line_start,
        "line_end": sym.line_end,
        "byte_start": sym.byte_start,
        "byte_end": sym.byte_end,
        "signature": sym.signature,
        "docstring": sym.docstring,
        "parent_id": sym.parent_id,
        "children": list(sym.children),
        "content_hash": sym.content_hash,
        "language": sym.language,
        "decorators": list(sym.decorators),
        "imports": list(sym.imports),
    }


def _deserialize_symbol(data: dict[str, Any]) -> Symbol:
    """Reconstruct a :class:`Symbol` from a plain dict."""
    return Symbol(
        id=data["id"],
        name=data["name"],
        kind=SymbolKind(data["kind"]),
        file_path=data["file_path"],
        line_start=data["line_start"],
        line_end=data["line_end"],
        byte_start=data["byte_start"],
        byte_end=data["byte_end"],
        signature=data["signature"],
        docstring=data.get("docstring", ""),
        parent_id=data.get("parent_id", ""),
        children=tuple(data.get("children", ())),
        content_hash=data.get("content_hash", ""),
        language=data.get("language", ""),
        decorators=tuple(data.get("decorators", ())),
        imports=tuple(data.get("imports", ())),
    )


def _serialize_file_symbols(fs: FileSymbols) -> dict[str, Any]:
    """Convert a :class:`FileSymbols` to a plain dict."""
    return {
        "file_path": fs.file_path,
        "language": fs.language,
        "symbols": [_serialize_symbol(s) for s in fs.symbols],
        "imports": list(fs.imports),
        "content_hash": fs.content_hash,
        "file_size": fs.file_size,
        "line_count": fs.line_count,
    }


def _deserialize_file_symbols(data: dict[str, Any]) -> FileSymbols:
    """Reconstruct a :class:`FileSymbols` from a plain dict."""
    return FileSymbols(
        file_path=data["file_path"],
        language=data["language"],
        symbols=[_deserialize_symbol(s) for s in data.get("symbols", [])],
        imports=list(data.get("imports", [])),
        content_hash=data.get("content_hash", ""),
        file_size=data.get("file_size", 0),
        line_count=data.get("line_count", 0),
    )


def _serialize_index(index: CodeIndex) -> dict[str, Any]:
    """Convert a :class:`CodeIndex` to a JSON-serialisable dict."""
    return {
        "repo_path": index.repo_path,
        "repo_name": index.repo_name,
        "files": {rp: _serialize_file_symbols(fs) for rp, fs in index.files.items()},
        "symbols": {sid: _serialize_symbol(sym) for sid, sym in index.symbols.items()},
        "file_hashes": dict(index.file_hashes),
        "indexed_at": index.indexed_at,
        "language_stats": dict(index.language_stats),
        "total_symbols": index.total_symbols,
        "total_files": index.total_files,
    }


def _deserialize_index(data: dict[str, Any]) -> CodeIndex:
    """Reconstruct a :class:`CodeIndex` from a plain dict."""
    return CodeIndex(
        repo_path=data["repo_path"],
        repo_name=data["repo_name"],
        files={
            rp: _deserialize_file_symbols(fs_data) for rp, fs_data in data.get("files", {}).items()
        },
        symbols={
            sid: _deserialize_symbol(sym_data) for sid, sym_data in data.get("symbols", {}).items()
        },
        file_hashes=dict(data.get("file_hashes", {})),
        indexed_at=data.get("indexed_at", ""),
        language_stats=dict(data.get("language_stats", {})),
        total_symbols=data.get("total_symbols", 0),
        total_files=data.get("total_files", 0),
    )


# ---------------------------------------------------------------------------
# IndexStore
# ---------------------------------------------------------------------------


class IndexStore:
    """On-disk store for :class:`CodeIndex` instances.

    Each index is persisted as a single JSON file whose name is derived from
    the SHA-256 hash of the repository's absolute path.  Writes are atomic
    (write to a temporary file in the same directory, then rename) to avoid
    corruption from interrupted writes.

    Parameters
    ----------
    storage_dir:
        Directory where index JSON files are stored.  Defaults to
        ``~/.snip/indexes/``.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        if storage_dir is None:
            storage_dir = Path.home() / ".snip" / "indexes"
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # -- path helpers -------------------------------------------------------

    def _index_path(self, repo_path: str) -> Path:
        """Return the deterministic file path for *repo_path*'s index.

        The filename is the first 16 hex characters of the SHA-256 hash of
        *repo_path* with a ``.json`` extension.
        """
        digest = hashlib.sha256(repo_path.encode("utf-8")).hexdigest()[:16]
        return self._storage_dir / f"{digest}.json"

    # -- CRUD operations ----------------------------------------------------

    def save(self, index: CodeIndex) -> Path:
        """Persist *index* to disk atomically.

        Writes to a temporary file in the same directory and renames it to
        the target path so that a partial write never leaves a corrupt file.

        Returns
        -------
        Path
            The path the index was saved to.
        """
        target = self._index_path(index.repo_path)
        payload = json.dumps(_serialize_index(index), indent=None)

        # Write to a temp file in the same directory, then atomic rename.
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._storage_dir),
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            # On Windows, os.rename fails if target exists — use os.replace.
            os.replace(tmp_path, str(target))
        except BaseException:
            # Clean up the temp file on any error.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        return target

    def load(self, repo_path: str) -> CodeIndex | None:
        """Load the index for *repo_path* from disk.

        Returns ``None`` if no index file exists for the given path.
        """
        path = self._index_path(repo_path)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return _deserialize_index(data)

    def delete(self, repo_path: str) -> bool:
        """Delete the persisted index for *repo_path*.

        Returns ``True`` if the file was deleted, ``False`` if it did not
        exist.
        """
        path = self._index_path(repo_path)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_repos(self) -> list[CodeIndex]:
        """Load and return all persisted indexes.

        Returns a list of :class:`CodeIndex` instances.  Corrupt or
        unreadable files are silently skipped.
        """
        indexes: list[CodeIndex] = []
        for json_file in sorted(self._storage_dir.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                indexes.append(_deserialize_index(data))
            except (json.JSONDecodeError, KeyError, TypeError):
                # Skip corrupt / incompatible index files.
                continue
        return indexes

    # -- symbol source retrieval --------------------------------------------

    def get_symbol_source(
        self,
        index: CodeIndex,
        symbol_id: str,
    ) -> str | None:
        """Retrieve the source text of a symbol using byte-offset seeking.

        Performs an O(1) seek+read on the original source file using the
        ``byte_start`` and ``byte_end`` stored in the :class:`Symbol`.

        Parameters
        ----------
        index:
            The :class:`CodeIndex` containing the symbol.
        symbol_id:
            The unique identifier of the symbol to retrieve.

        Returns
        -------
        str | None
            The source text of the symbol, or ``None`` if the symbol is not
            found in the index or the source file is inaccessible.
        """
        sym = index.symbols.get(symbol_id)
        if sym is None:
            return None

        source_path = Path(index.repo_path) / sym.file_path
        if not source_path.is_file():
            return None

        byte_length = sym.byte_end - sym.byte_start
        if byte_length <= 0:
            return None

        try:
            with source_path.open("rb") as fh:
                fh.seek(sym.byte_start)
                raw = fh.read(byte_length)
            return raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return None
