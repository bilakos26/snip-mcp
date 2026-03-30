"""get_dead_code tool — detect unused symbols and circular imports."""

from __future__ import annotations

from snip_mcp.parser.symbols import SymbolKind
from snip_mcp.tools._utils import meta_envelope, resolve_repo

# Symbols that are typically entry points or framework-invoked, not "dead"
_ENTRY_POINT_NAMES = {
    "main",
    "__init__",
    "__main__",
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",
    "setup",
    "teardown",
}

_ENTRY_POINT_PREFIXES = ("test_", "Test")

# Kinds that are commonly used implicitly (decorators, type aliases, etc.)
_IMPLICIT_KINDS = {
    SymbolKind.DECORATOR,
    SymbolKind.IMPORT_STMT,
    SymbolKind.NAMESPACE,
    SymbolKind.MODULE,
    SymbolKind.IMPL,
}


def get_dead_code(
    repo_path: str,
    *,
    include_tests: bool = False,
    max_results: int = 100,
) -> dict:
    """Detect potentially unused symbols and circular imports.

    A symbol is considered potentially dead if:
    - It has zero callers in the call graph
    - It is not a child of another symbol (method of a class)
    - It is not a test function, entry point, or framework hook
    - It is not referenced in any import statement

    Args:
        repo_path: Absolute path to the indexed folder.
        include_tests: Include test files in analysis (default False).
        max_results: Maximum dead symbols to return.

    Returns:
        Envelope with dead symbols and circular imports.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    # --- Dead code detection ---

    # Build set of all symbols that are called by something
    called_symbols: set[str] = set()
    for callees in index.call_graph.values():
        called_symbols.update(callees)

    # Build set of imported names (symbols referenced via imports)
    imported_names: set[str] = set()
    for fs in index.files.values():
        for imp in fs.imports:
            # Extract the last component as the imported name
            parts = imp.replace("\\", "/").replace("/", ".").split(".")
            imported_names.add(parts[-1])

    dead_symbols: list[dict] = []

    for sym in index.symbols.values():
        # Skip implicit kinds
        if sym.kind in _IMPLICIT_KINDS:
            continue

        # Skip test files unless requested
        if not include_tests and "test" in sym.file_path.lower():
            continue

        # Skip child symbols (methods belong to their class)
        if sym.parent_id:
            continue

        # Skip entry points and test functions
        if sym.name in _ENTRY_POINT_NAMES:
            continue
        if any(sym.name.startswith(p) for p in _ENTRY_POINT_PREFIXES):
            continue

        # Skip if this symbol is called
        if sym.id in called_symbols:
            continue

        # Skip if the name appears in imports (exported/used elsewhere)
        if sym.name in imported_names:
            continue

        # Skip __dunder__ methods
        if sym.name.startswith("__") and sym.name.endswith("__"):
            continue

        dead_symbols.append(
            {
                "symbol_id": sym.id,
                "name": sym.name,
                "kind": sym.kind.value,
                "file_path": sym.file_path,
                "line_start": sym.line_start,
                "signature": sym.signature,
            }
        )

        if len(dead_symbols) >= max_results:
            break

    # --- Circular import detection ---
    circular_imports = _detect_circular_imports(index)

    return meta_envelope(
        {
            "dead_symbols": dead_symbols,
            "circular_imports": circular_imports,
            "summary": {
                "total_dead_symbols": len(dead_symbols),
                "total_circular_imports": len(circular_imports),
                "total_symbols_analyzed": len(index.symbols),
            },
        },
        repo_path=index.repo_path,
    )


def _detect_circular_imports(index) -> list[dict]:
    """Detect circular import chains in the codebase.

    Uses DFS on the file-level import graph to find cycles.
    """
    # Build file-level import graph: file -> [files it imports]
    # Map import strings to actual files in the index
    file_stems: dict[str, str] = {}
    for rel_path in index.files:
        stem = rel_path.rsplit(".", 1)[0]
        file_stems[stem] = rel_path
        # Also map dotted version
        file_stems[stem.replace("/", ".")] = rel_path
        # And just the filename stem
        filename = rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        file_stems.setdefault(filename, rel_path)

    import_graph: dict[str, set[str]] = {}
    for rel_path, fs in index.files.items():
        targets: set[str] = set()
        for imp in fs.imports:
            # Try to resolve import to an indexed file
            parts = imp.replace("\\", "/").replace("/", ".").split(".")
            # Try full path, then progressively shorter
            for i in range(len(parts)):
                candidate = ".".join(parts[i:])
                if candidate in file_stems:
                    target = file_stems[candidate]
                    if target != rel_path:
                        targets.add(target)
                    break
        if targets:
            import_graph[rel_path] = targets

    # DFS cycle detection
    cycles: list[list[str]] = []
    visited: set[str] = set()
    in_stack: set[str] = set()
    path: list[str] = []

    def dfs(node: str) -> None:
        if node in in_stack:
            # Found a cycle — extract it
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            # Normalize: start from the lexicographically smallest
            min_idx = cycle.index(min(cycle[:-1]))
            normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
            # Deduplicate
            key = " -> ".join(normalized)
            if not any(c["chain_str"] == key for c in cycles):
                cycles.append(
                    {
                        "files": normalized,
                        "chain_str": key,
                        "length": len(normalized) - 1,
                    }
                )
            return

        if node in visited:
            return

        visited.add(node)
        in_stack.add(node)
        path.append(node)

        for neighbor in import_graph.get(node, set()):
            if len(cycles) >= 20:  # cap results
                break
            dfs(neighbor)

        path.pop()
        in_stack.discard(node)

    for file in import_graph:
        if len(cycles) >= 20:
            break
        if file not in visited:
            dfs(file)

    return cycles
