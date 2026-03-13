"""Per-language import extraction using regex patterns."""

from __future__ import annotations

import re

# Python: import X, from X import Y
_PY_IMPORT = re.compile(r"^\s*import\s+(\S+)", re.MULTILINE)
_PY_FROM_IMPORT = re.compile(r"^\s*from\s+(\S+)\s+import", re.MULTILINE)

# JavaScript/TypeScript: import ... from 'X', require('X')
_JS_IMPORT = re.compile(
    r"""(?:import\s+.*?\s+from\s+|require\s*\(\s*)['"]([^'"]+)['"]""",
    re.MULTILINE,
)

# Go: import "X" or import ( "X" )
_GO_IMPORT = re.compile(r"""["\s]([a-zA-Z0-9_./-]+)["\s]""")
_GO_IMPORT_BLOCK = re.compile(r"import\s*\((.*?)\)", re.DOTALL)
_GO_IMPORT_SINGLE = re.compile(r'import\s+"([^"]+)"')

# Rust: use X::Y, extern crate X
_RUST_USE = re.compile(
    r"^\s*use\s+([a-zA-Z_][a-zA-Z0-9_]*(?:::[a-zA-Z_*][a-zA-Z0-9_]*)*)",
    re.MULTILINE,
)
_RUST_EXTERN = re.compile(r"^\s*extern\s+crate\s+(\w+)", re.MULTILINE)

# Java/C#: import X.Y.Z, using X.Y.Z
_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([a-zA-Z_][\w.]*\w)", re.MULTILINE)
_CS_USING = re.compile(r"^\s*using\s+(?:static\s+)?([a-zA-Z_][\w.]*\w)\s*;", re.MULTILINE)

# C/C++: #include <X> or #include "X"
_C_INCLUDE = re.compile(r'^\s*#\s*include\s+[<"]([^>"]+)[>"]', re.MULTILINE)

# SQL: no standard imports, but we can detect referenced tables
_SQL_FROM = re.compile(r"\bFROM\s+(\w+(?:\.\w+)*)", re.IGNORECASE)
_SQL_JOIN = re.compile(r"\bJOIN\s+(\w+(?:\.\w+)*)", re.IGNORECASE)


def extract_imports(source: str, language_id: str) -> list[str]:
    """Extract import/include statements from source code.

    Returns a list of imported module/file paths as strings.
    """
    extractors = _EXTRACTORS.get(language_id)
    if extractors is None:
        return []
    return extractors(source)


def _extract_python(source: str) -> list[str]:
    imports: list[str] = []
    for m in _PY_IMPORT.finditer(source):
        imports.append(m.group(1))
    for m in _PY_FROM_IMPORT.finditer(source):
        imports.append(m.group(1))
    return sorted(set(imports))


def _extract_javascript(source: str) -> list[str]:
    imports: list[str] = []
    for m in _JS_IMPORT.finditer(source):
        imports.append(m.group(1))
    return sorted(set(imports))


def _extract_go(source: str) -> list[str]:
    imports: list[str] = []
    # Single imports
    for m in _GO_IMPORT_SINGLE.finditer(source):
        imports.append(m.group(1))
    # Block imports
    for block_match in _GO_IMPORT_BLOCK.finditer(source):
        block = block_match.group(1)
        for m in re.finditer(r'"([^"]+)"', block):
            imports.append(m.group(1))
    return sorted(set(imports))


def _extract_rust(source: str) -> list[str]:
    imports: list[str] = []
    for m in _RUST_USE.finditer(source):
        imports.append(m.group(1))
    for m in _RUST_EXTERN.finditer(source):
        imports.append(m.group(1))
    return sorted(set(imports))


def _extract_java(source: str) -> list[str]:
    return sorted({m.group(1) for m in _JAVA_IMPORT.finditer(source)})


def _extract_csharp(source: str) -> list[str]:
    return sorted({m.group(1) for m in _CS_USING.finditer(source)})


def _extract_c(source: str) -> list[str]:
    return sorted({m.group(1) for m in _C_INCLUDE.finditer(source)})


def _extract_sql(source: str) -> list[str]:
    tables: set[str] = set()
    for m in _SQL_FROM.finditer(source):
        tables.add(m.group(1))
    for m in _SQL_JOIN.finditer(source):
        tables.add(m.group(1))
    return sorted(tables)


_EXTRACTORS: dict[str, callable] = {
    "python": _extract_python,
    "javascript": _extract_javascript,
    "typescript": _extract_javascript,  # same syntax
    "tsx": _extract_javascript,  # same syntax
    "go": _extract_go,
    "rust": _extract_rust,
    "java": _extract_java,
    "c_sharp": _extract_csharp,
    "c": _extract_c,
    "cpp": _extract_c,  # same #include syntax
    "sql": _extract_sql,
}
