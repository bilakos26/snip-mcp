"""Cross-file symbol resolution for Snip MCP.

Resolves import strings to actual symbol IDs within the same repository
by converting module paths to file paths and matching symbol names.
"""

from __future__ import annotations

from snip_mcp.storage.index_store import CodeIndex


def resolve_imports(index: CodeIndex) -> dict[str, dict[str, str]]:
    """Resolve imports across all files in the index.

    For each file, attempts to resolve its import strings to symbol IDs
    in other indexed files.

    Returns
    -------
    dict[str, dict[str, str]]
        Mapping of file_path -> {import_string -> symbol_id}.
    """
    # Build file stem -> relative path lookup
    # e.g. "app/services/orders" -> "app/services/orders.py"
    stem_to_path: dict[str, str] = {}
    for rel_path in index.files:
        # Strip extension for matching
        if "." in rel_path:
            stem = rel_path.rsplit(".", 1)[0]
        else:
            stem = rel_path
        stem_to_path[stem] = rel_path
        # Also store with dots as separators (for Python-style imports)
        dotted = stem.replace("/", ".")
        stem_to_path[dotted] = rel_path

    # Build name -> symbol_id lookup per file
    file_symbol_names: dict[str, dict[str, str]] = {}
    for rel_path, fs in index.files.items():
        names: dict[str, str] = {}
        for sym in fs.symbols:
            names[sym.name] = sym.id
        file_symbol_names[rel_path] = names

    resolved: dict[str, dict[str, str]] = {}

    for rel_path, fs in index.files.items():
        file_resolved: dict[str, str] = {}
        for imp in fs.imports:
            symbol_id = _resolve_single_import(
                imp, rel_path, stem_to_path, file_symbol_names, index
            )
            if symbol_id:
                file_resolved[imp] = symbol_id
        if file_resolved:
            resolved[rel_path] = file_resolved

    return resolved


def _resolve_single_import(
    import_string: str,
    current_file: str,
    stem_to_path: dict[str, str],
    file_symbol_names: dict[str, dict[str, str]],
    index: CodeIndex,
) -> str:
    """Try to resolve a single import string to a symbol ID.

    Strategies:
    1. Python-style: "from app.services.orders import OrderService"
       -> find file "app/services/orders.py", look for symbol "OrderService"
    2. Module path: "app.services.orders" -> file "app/services/orders.py"
    3. Direct name match: search all files for a symbol with the imported name
    """
    parts = import_string.replace("\\", "/").replace(".", "/").split("/")

    # Strategy 1: last part might be a symbol name, rest is the module path
    if len(parts) >= 2:
        module_path = "/".join(parts[:-1])
        symbol_name = parts[-1]
        target_file = stem_to_path.get(module_path)
        if target_file and target_file in file_symbol_names:
            sym_id = file_symbol_names[target_file].get(symbol_name)
            if sym_id:
                return sym_id

    # Strategy 2: entire import is a module path
    full_path = "/".join(parts)
    target_file = stem_to_path.get(full_path)
    if target_file and target_file in file_symbol_names:
        # Return the first symbol in that file as a "module" reference
        syms = file_symbol_names[target_file]
        if syms:
            return next(iter(syms.values()))

    # Strategy 3: direct name match (last component)
    target_name = parts[-1] if parts else import_string
    for file_path, names in file_symbol_names.items():
        if file_path == current_file:
            continue
        if target_name in names:
            return names[target_name]

    return ""
