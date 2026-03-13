"""find_importers tool — reverse import graph (who imports this file/module)."""

from __future__ import annotations

from pathlib import PurePosixPath

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def find_importers(
    repo_path: str,
    target: str,
    *,
    max_results: int = 50,
) -> dict:
    """Find files that import a given module/file.

    Args:
        repo_path: Path to the indexed folder.
        target: Module name, file path, or package name to search for.
        max_results: Maximum results to return.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    target_lower = target.lower()

    # Also derive possible module name from file path
    # e.g., "src/utils/helpers.py" -> "utils.helpers", "src.utils.helpers"
    target_variants: set[str] = {target_lower}

    # If it looks like a file path, derive module name
    if "/" in target or "\\" in target or target.endswith(".py"):
        p = PurePosixPath(target.replace("\\", "/"))
        stem = p.stem if p.suffix else p.name
        # Try dotted module path
        parts = list(p.parts)
        if parts and parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        module_name = ".".join(parts)
        target_variants.add(module_name.lower())
        target_variants.add(stem.lower())

    importers: list[dict] = []

    for rel_path, file_syms in index.files.items():
        if len(importers) >= max_results:
            break

        for imp in file_syms.imports:
            imp_lower = imp.lower()
            if any(v in imp_lower or imp_lower in v for v in target_variants):
                importers.append(
                    {
                        "file_path": rel_path,
                        "language": file_syms.language,
                        "import_statement": imp,
                        "symbol_count": len(file_syms.symbols),
                    }
                )
                break  # Only list each file once

    return meta_envelope(
        {
            "target": target,
            "total_importers": len(importers),
            "importers": importers,
        },
        repo_path=index.repo_path,
    )
