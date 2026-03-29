"""resolve_cross_repo tool — resolve imports across indexed repos."""

from __future__ import annotations

from snip_mcp.tools._utils import get_store, meta_envelope, resolve_repo


def resolve_cross_repo(repo_path: str, import_string: str) -> dict:
    """Resolve an import string to a symbol in another indexed repo.

    Iterates all indexed repos (except the source repo) and searches
    for a matching symbol by name.

    Args:
        repo_path: Absolute path to the source repo.
        import_string: The import string to resolve.

    Returns:
        Envelope with resolved symbol info or empty result.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    store = get_store()
    all_repos = store.list_repos()

    # Extract the target name from the import string
    # e.g. "from app.utils import helper" -> "helper"
    # e.g. "app.utils.helper" -> "helper"
    parts = import_string.replace("\\", "/").replace("/", ".").split(".")
    target_name = parts[-1] if parts else import_string

    results = []
    for other_index in all_repos:
        if other_index.repo_path == index.repo_path:
            continue

        for sym in other_index.symbols.values():
            if sym.name == target_name:
                results.append(
                    {
                        "symbol_id": sym.id,
                        "name": sym.name,
                        "kind": sym.kind.value,
                        "file_path": sym.file_path,
                        "repo_path": other_index.repo_path,
                        "repo_name": other_index.repo_name,
                        "signature": sym.signature,
                    }
                )

        if results:
            break  # Found in first matching repo

    return meta_envelope(
        {
            "import_string": import_string,
            "target_name": target_name,
            "resolved": results,
            "total_matches": len(results),
        },
        repo_path=index.repo_path,
    )
