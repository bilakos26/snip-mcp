"""get_test_coverage tool — find tests for a symbol via naming + imports + call graph."""

from __future__ import annotations

import re

from snip_mcp.parser.symbols import SymbolKind
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def get_test_coverage(repo_path: str, symbol_id: str) -> dict:
    """Find test files and functions that cover a given symbol.

    Uses multiple strategies:
    1. Naming conventions (test_{name}.py, {name}_test.py, {name}.test.ts, etc.)
    2. Import analysis (test files that import the symbol's module)
    3. Call graph (test functions that call the target symbol)

    Args:
        repo_path: Absolute path to the indexed folder.
        symbol_id: The symbol to find tests for.

    Returns:
        Envelope with matched test files and functions.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    sym = index.symbols.get(symbol_id)
    if sym is None:
        return meta_envelope(
            {"error": f"Symbol not found: {symbol_id}"},
            repo_path=repo_path,
        )

    # Extract the module name from the symbol's file path
    file_stem = sym.file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    module_path = sym.file_path.rsplit(".", 1)[0].replace("/", ".")

    # Strategy 1: Find test files by naming convention
    test_patterns = [
        re.compile(rf"test_{re.escape(file_stem)}\.", re.IGNORECASE),
        re.compile(rf"{re.escape(file_stem)}_test\.", re.IGNORECASE),
        re.compile(rf"{re.escape(file_stem)}\.test\.", re.IGNORECASE),
        re.compile(rf"{re.escape(file_stem)}\.spec\.", re.IGNORECASE),
        re.compile(rf"test_{re.escape(file_stem)}_", re.IGNORECASE),
    ]

    test_files: dict[str, dict] = {}

    for rel_path, fs in index.files.items():
        filename = rel_path.rsplit("/", 1)[-1]
        matched = False

        for pattern in test_patterns:
            if pattern.search(filename):
                matched = True
                break

        # Also check if it's in a tests/ directory and mentions the symbol
        if not matched and ("test" in rel_path.lower()):
            # Check if this test file imports the target module
            for imp in fs.imports:
                if file_stem in imp or module_path in imp:
                    matched = True
                    break

        if matched:
            test_files[rel_path] = {
                "file_path": rel_path,
                "language": fs.language,
                "symbol_count": len(fs.symbols),
                "match_reason": "naming_convention",
            }

    # Strategy 2: Check imports more broadly
    for rel_path, fs in index.files.items():
        if rel_path in test_files:
            continue
        if "test" not in rel_path.lower():
            continue
        for imp in fs.imports:
            if file_stem in imp:
                test_files[rel_path] = {
                    "file_path": rel_path,
                    "language": fs.language,
                    "symbol_count": len(fs.symbols),
                    "match_reason": "imports_module",
                }
                break

    # Strategy 3: Find test functions via call graph
    test_functions: list[dict] = []
    if index.call_graph:
        for caller_id, callees in index.call_graph.items():
            if symbol_id in callees:
                caller = index.symbols.get(caller_id)
                if caller and (
                    caller.name.startswith("test_")
                    or caller.name.startswith("Test")
                    or caller.name.endswith("_test")
                ):
                    test_functions.append(
                        {
                            "symbol_id": caller_id,
                            "name": caller.name,
                            "kind": caller.kind.value,
                            "file_path": caller.file_path,
                            "signature": caller.signature,
                            "match_reason": "calls_symbol",
                        }
                    )

    # Also find test functions by name pattern in test files
    name_pattern = re.compile(rf"test.*{re.escape(sym.name)}", re.IGNORECASE)
    for rel_path in test_files:
        fs = index.files.get(rel_path)
        if not fs:
            continue
        for test_sym in fs.symbols:
            if test_sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
                if name_pattern.search(test_sym.name):
                    # Avoid duplicates
                    if not any(tf["symbol_id"] == test_sym.id for tf in test_functions):
                        test_functions.append(
                            {
                                "symbol_id": test_sym.id,
                                "name": test_sym.name,
                                "kind": test_sym.kind.value,
                                "file_path": test_sym.file_path,
                                "signature": test_sym.signature,
                                "match_reason": "name_pattern",
                            }
                        )

    return meta_envelope(
        {
            "symbol_id": symbol_id,
            "symbol_name": sym.name,
            "test_files": list(test_files.values()),
            "test_functions": test_functions,
            "summary": {
                "total_test_files": len(test_files),
                "total_test_functions": len(test_functions),
            },
        },
        repo_path=index.repo_path,
    )
