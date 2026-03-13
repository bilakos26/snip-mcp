"""index_folder tool — indexes a local folder with tree-sitter + security filtering."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from snip_mcp.parser.extractor import extract_file_symbols
from snip_mcp.parser.hierarchy import build_hierarchy
from snip_mcp.parser.imports import extract_imports
from snip_mcp.parser.languages import get_language_for_file
from snip_mcp.parser.symbols import FileSymbols, compute_content_hash
from snip_mcp.security import is_ignored, load_ignore_patterns, safe_read, should_index
from snip_mcp.storage.index_store import CodeIndex
from snip_mcp.tools._utils import get_store, meta_envelope


def index_folder(
    folder_path: str,
    *,
    force: bool = False,
    max_files: int = 50000,
) -> dict:
    """Index a local folder, building a symbol index with tree-sitter.

    Args:
        folder_path: Absolute path to the folder to index.
        force: If True, re-index all files even if unchanged.
        max_files: Maximum number of files to index.

    Returns:
        Envelope with indexing stats.
    """
    root = Path(folder_path).resolve()
    if not root.exists():
        return meta_envelope({"error": f"Path does not exist: {root}"})
    if not root.is_dir():
        return meta_envelope({"error": f"Path is not a directory: {root}"})

    store = get_store()
    repo_path_str = str(root)

    # Load existing index for incremental support
    existing_index = None if force else store.load(repo_path_str)
    existing_hashes = existing_index.file_hashes if existing_index else {}

    # Load gitignore patterns
    ignore_spec = load_ignore_patterns(root)

    # Discover files
    start = time.monotonic()
    all_files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if len(all_files) >= max_files:
            break

        rel = str(path.relative_to(root)).replace("\\", "/")

        # Check gitignore
        if is_ignored(path, root, ignore_spec):
            continue

        # Security checks
        ok, _reason = should_index(path, root)
        if not ok:
            continue

        # Only index files we have a language spec for
        if get_language_for_file(str(path)) is not None:
            all_files.append(path)

    # Parse files
    files_map: dict[str, FileSymbols] = {}
    symbols_map: dict[str, object] = {}
    file_hashes: dict[str, str] = {}
    language_stats: dict[str, int] = {}
    total_symbols = 0
    files_parsed = 0
    files_skipped = 0

    for path in all_files:
        rel = str(path.relative_to(root)).replace("\\", "/")
        lang_spec = get_language_for_file(str(path))
        if lang_spec is None:
            continue

        # Read file content
        content = safe_read(path)
        if content is None:
            continue

        content_hash = compute_content_hash(content)

        # Incremental: skip unchanged files
        if not force and rel in existing_hashes and existing_hashes[rel] == content_hash:
            # Reuse existing data
            if existing_index and rel in existing_index.files:
                old_fs = existing_index.files[rel]
                files_map[rel] = old_fs
                file_hashes[rel] = content_hash
                for sym in old_fs.symbols:
                    symbols_map[sym.id] = sym
                total_symbols += len(old_fs.symbols)
                lid = lang_spec.language_id
                language_stats[lid] = language_stats.get(lid, 0) + 1
                files_skipped += 1
                continue

        # Extract symbols
        try:
            raw_symbols = extract_file_symbols(content, lang_spec, rel)
        except Exception:
            continue

        # Build hierarchy
        hierarchical_symbols = build_hierarchy(raw_symbols)

        # Extract imports
        imports = extract_imports(content, lang_spec.language_id)

        lines = content.split("\n")
        file_symbols = FileSymbols(
            file_path=rel,
            language=lang_spec.language_id,
            symbols=hierarchical_symbols,
            imports=imports,
            content_hash=content_hash,
            file_size=len(content.encode("utf-8")),
            line_count=len(lines),
        )

        files_map[rel] = file_symbols
        file_hashes[rel] = content_hash
        for sym in hierarchical_symbols:
            symbols_map[sym.id] = sym
        total_symbols += len(hierarchical_symbols)
        language_stats[lang_spec.language_id] = language_stats.get(lang_spec.language_id, 0) + 1
        files_parsed += 1

    # Build index
    index = CodeIndex(
        repo_path=repo_path_str,
        repo_name=root.name,
        files=files_map,
        symbols=symbols_map,
        file_hashes=file_hashes,
        indexed_at=datetime.now(timezone.utc).isoformat(),
        language_stats=language_stats,
        total_symbols=total_symbols,
        total_files=len(files_map),
    )

    # Save
    store.save(index)

    elapsed = time.monotonic() - start

    # Note: indexing builds the index but doesn't retrieve content, so no
    # token savings are recorded here.  Savings come from get_symbol/get_symbols
    # calls that use the index to avoid reading full files.

    return meta_envelope(
        {
            "status": "indexed",
            "repo_path": repo_path_str,
            "repo_name": root.name,
            "total_files": len(files_map),
            "total_symbols": total_symbols,
            "files_parsed": files_parsed,
            "files_skipped_unchanged": files_skipped,
            "languages": language_stats,
            "elapsed_seconds": round(elapsed, 2),
        },
        repo_path=repo_path_str,
    )
