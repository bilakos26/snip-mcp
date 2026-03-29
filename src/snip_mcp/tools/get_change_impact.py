"""get_change_impact tool — identifies changed symbols and their dependents."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.parser.call_graph import get_callers
from snip_mcp.parser.extractor import extract_file_symbols
from snip_mcp.parser.languages import get_language_for_file
from snip_mcp.parser.symbols import compute_content_hash
from snip_mcp.security import safe_read
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_change_impact(repo_path: str, file_path: str | None = None) -> dict:
    """Identify changed symbols and their dependents via the call graph.

    Compares current file contents against the stored index to find symbols
    that have been added, modified, or removed, then uses the call graph to
    identify impacted symbols.

    Args:
        repo_path: Absolute path to the indexed folder.
        file_path: Optional relative path to limit analysis to a single file.

    Returns:
        Envelope with changed and impacted symbols.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    root = Path(index.repo_path)
    files_to_check = {}

    if file_path:
        # Normalize path separators
        rel = file_path.replace("\\", "/")
        if rel in index.files:
            files_to_check[rel] = index.file_hashes.get(rel, "")
        else:
            return meta_envelope(
                {"error": f"File not in index: {rel}"},
                repo_path=repo_path,
            )
    else:
        files_to_check = dict(index.file_hashes)

    changed_symbols: list[dict] = []
    added_symbols: list[dict] = []
    removed_symbols: list[dict] = []

    for rel, old_hash in files_to_check.items():
        abs_path = root / rel
        if not abs_path.is_file():
            # File was deleted — all its symbols are removed
            if rel in index.files:
                for sym in index.files[rel].symbols:
                    removed_symbols.append(
                        {
                            "symbol_id": sym.id,
                            "name": sym.name,
                            "kind": sym.kind.value,
                            "file_path": rel,
                            "change": "removed",
                        }
                    )
            continue

        content = safe_read(abs_path)
        if content is None:
            continue

        new_hash = compute_content_hash(content)
        if new_hash == old_hash:
            continue

        # File changed — re-extract symbols and compare
        lang_spec = get_language_for_file(str(abs_path))
        if lang_spec is None:
            continue

        try:
            new_symbols = extract_file_symbols(content, lang_spec, rel)
        except Exception:
            continue

        new_by_name: dict[str, object] = {s.name: s for s in new_symbols}
        old_symbols = index.files.get(rel)
        old_by_name: dict[str, object] = {}
        if old_symbols:
            old_by_name = {s.name: s for s in old_symbols.symbols}

        # Find added and modified
        for name, new_sym in new_by_name.items():
            if name not in old_by_name:
                added_symbols.append(
                    {
                        "symbol_id": new_sym.id,
                        "name": new_sym.name,
                        "kind": new_sym.kind.value,
                        "file_path": rel,
                        "change": "added",
                    }
                )
            else:
                old_sym = old_by_name[name]
                if new_sym.content_hash != old_sym.content_hash:
                    changed_symbols.append(
                        {
                            "symbol_id": old_sym.id,
                            "name": old_sym.name,
                            "kind": old_sym.kind.value,
                            "file_path": rel,
                            "change": "modified",
                        }
                    )

        # Find removed
        for name, old_sym in old_by_name.items():
            if name not in new_by_name:
                removed_symbols.append(
                    {
                        "symbol_id": old_sym.id,
                        "name": old_sym.name,
                        "kind": old_sym.kind.value,
                        "file_path": rel,
                        "change": "removed",
                    }
                )

    # Find impacted symbols via call graph
    all_changed_ids = set()
    for entry in changed_symbols + added_symbols + removed_symbols:
        all_changed_ids.add(entry["symbol_id"])

    impacted: list[dict] = []
    if index.call_graph:
        seen_impacted: set[str] = set()
        for sid in all_changed_ids:
            for caller_id in get_callers(index, sid):
                if caller_id not in all_changed_ids and caller_id not in seen_impacted:
                    seen_impacted.add(caller_id)
                    caller_sym = index.symbols.get(caller_id)
                    if caller_sym:
                        impacted.append(
                            {
                                "symbol_id": caller_id,
                                "name": caller_sym.name,
                                "kind": caller_sym.kind.value,
                                "file_path": caller_sym.file_path,
                                "reason": "calls changed symbol",
                            }
                        )

    return meta_envelope(
        {
            "changed": changed_symbols,
            "added": added_symbols,
            "removed": removed_symbols,
            "impacted": impacted,
            "summary": {
                "total_changed": len(changed_symbols),
                "total_added": len(added_symbols),
                "total_removed": len(removed_symbols),
                "total_impacted": len(impacted),
            },
        },
        repo_path=repo_path,
    )
