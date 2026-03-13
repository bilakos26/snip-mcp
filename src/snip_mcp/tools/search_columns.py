"""search_columns tool — column metadata search (dbt-aware)."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.parser.context.base import registry
from snip_mcp.parser.context.dbt import DbtContextProvider  # noqa: F401 — triggers registration
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def search_columns(
    repo_path: str,
    query: str,
    *,
    table: str | None = None,
    max_results: int = 50,
) -> dict:
    """Search column metadata across context providers (e.g., dbt schema.yml).

    Args:
        repo_path: Path to the indexed folder.
        query: Column name or description search string.
        table: Optional table/model name filter.
        max_results: Maximum results to return.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # Ensure providers are loaded for this repo
    repo_path_obj = Path(index.repo_path)
    if not registry.get_active():
        registry.discover(repo_path_obj)

    if table:
        columns = registry.get_all_columns(table)
        # Also filter by query within those columns
        if query:
            query_lower = query.lower()
            columns = [
                c
                for c in columns
                if query_lower in c.name.lower() or query_lower in c.description.lower()
            ]
    else:
        columns = registry.search_all_columns(query)

    results = [
        {
            "name": col.name,
            "description": col.description,
            "data_type": col.data_type,
            "table": col.table,
            "source_file": col.source_file,
            "tags": list(col.tags),
        }
        for col in columns[:max_results]
    ]

    return meta_envelope(
        {
            "query": query,
            "table_filter": table,
            "total_matches": len(results),
            "results": results,
        },
        repo_path=index.repo_path,
    )
