"""Language specification registry for Snip MCP.

Defines supported languages, their file extensions, tree-sitter node types
for symbol extraction, and comment/docstring conventions. The extractor
walks the AST and matches against the node type names stored here —
no S-expression query strings are used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    """Specification for a single programming language.

    Parameters
    ----------
    name:
        Human-readable name (e.g. "Python").
    language_id:
        Identifier used by *tree-sitter-language-pack* (e.g. "python").
    extensions:
        File extensions **including** the leading dot (e.g. ``(".py",)``).
    symbol_queries:
        Mapping of ``SymbolKind`` value to a comma-separated string of
        tree-sitter node type names the extractor should match.
    comment_prefix:
        Single-line comment prefix (default ``"#"``).
    docstring_node_types:
        AST node types that represent docstrings (e.g. ``("string",)``
        for Python's triple-quoted strings that appear as expression
        statements).
    """

    name: str
    language_id: str
    extensions: tuple[str, ...]
    symbol_queries: dict[str, str] = field(default_factory=dict)
    comment_prefix: str = "#"
    docstring_node_types: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Tier 1 language specifications
# ---------------------------------------------------------------------------

_PYTHON = LanguageSpec(
    name="Python",
    language_id="python",
    extensions=(".py",),
    symbol_queries={
        "function": "function_definition",
        "class": "class_definition",
        "method": "function_definition",
        "decorator": "decorated_definition",
    },
    comment_prefix="#",
    docstring_node_types=("string", "concatenated_string"),
)

_JAVASCRIPT = LanguageSpec(
    name="JavaScript",
    language_id="javascript",
    extensions=(".js", ".mjs", ".cjs"),
    symbol_queries={
        "function": "function_declaration,arrow_function",
        "class": "class_declaration",
        "method": "method_definition",
    },
    comment_prefix="//",
)

_TYPESCRIPT = LanguageSpec(
    name="TypeScript",
    language_id="typescript",
    extensions=(".ts",),
    symbol_queries={
        "function": "function_declaration,arrow_function",
        "class": "class_declaration",
        "method": "method_definition",
        "interface": "interface_declaration",
        "type_alias": "type_alias_declaration",
        "enum": "enum_declaration",
    },
    comment_prefix="//",
)

_TSX = LanguageSpec(
    name="TSX",
    language_id="tsx",
    extensions=(".tsx",),
    symbol_queries={
        "function": "function_declaration,arrow_function",
        "class": "class_declaration",
        "method": "method_definition",
        "interface": "interface_declaration",
        "type_alias": "type_alias_declaration",
        "enum": "enum_declaration",
    },
    comment_prefix="//",
)

_GO = LanguageSpec(
    name="Go",
    language_id="go",
    extensions=(".go",),
    symbol_queries={
        "function": "function_declaration",
        "method": "method_declaration",
        "struct": "type_declaration",
        "interface": "type_declaration",
    },
    comment_prefix="//",
)

_RUST = LanguageSpec(
    name="Rust",
    language_id="rust",
    extensions=(".rs",),
    symbol_queries={
        "function": "function_item",
        "struct": "struct_item",
        "enum": "enum_item",
        "trait": "trait_item",
        "impl": "impl_item",
    },
    comment_prefix="//",
    docstring_node_types=("line_comment", "block_comment"),
)

_JAVA = LanguageSpec(
    name="Java",
    language_id="java",
    extensions=(".java",),
    symbol_queries={
        "class": "class_declaration",
        "method": "method_declaration",
        "interface": "interface_declaration",
        "enum": "enum_declaration",
    },
    comment_prefix="//",
)

_CSHARP = LanguageSpec(
    name="C#",
    language_id="c_sharp",
    extensions=(".cs",),
    symbol_queries={
        "class": "class_declaration",
        "method": "method_declaration",
        "interface": "interface_declaration",
        "enum": "enum_declaration",
        "struct": "struct_declaration",
        "namespace": "namespace_declaration",
    },
    comment_prefix="//",
)

_C = LanguageSpec(
    name="C",
    language_id="c",
    extensions=(".c", ".h"),
    symbol_queries={
        "function": "function_definition",
        "struct": "struct_specifier",
        "enum": "enum_specifier",
    },
    comment_prefix="//",
)

_CPP = LanguageSpec(
    name="C++",
    language_id="cpp",
    extensions=(".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh"),
    symbol_queries={
        "function": "function_definition",
        "struct": "struct_specifier",
        "enum": "enum_specifier",
        "class": "class_specifier",
        "namespace": "namespace_definition",
    },
    comment_prefix="//",
)

_SQL = LanguageSpec(
    name="SQL",
    language_id="sql",
    extensions=(".sql",),
    symbol_queries={
        "sql_cte": "cte",
        "sql_table": "create_table_statement",
        "sql_view": "create_view_statement",
        "sql_procedure": "create_procedure_statement",
        "sql_function": "create_function_statement",
    },
    comment_prefix="--",
)

# ---------------------------------------------------------------------------
# Tier 2 language specifications (12 new languages)
# ---------------------------------------------------------------------------

_RUBY = LanguageSpec(
    name="Ruby",
    language_id="ruby",
    extensions=(".rb", ".rake", ".gemspec"),
    symbol_queries={
        "method": "method",
        "class": "class",
        "module": "module",
    },
    comment_prefix="#",
)

_KOTLIN = LanguageSpec(
    name="Kotlin",
    language_id="kotlin",
    extensions=(".kt", ".kts"),
    symbol_queries={
        "function": "function_declaration",
        "class": "class_declaration",
        "interface": "interface_declaration",
    },
    comment_prefix="//",
)

_SWIFT = LanguageSpec(
    name="Swift",
    language_id="swift",
    extensions=(".swift",),
    symbol_queries={
        "function": "function_declaration",
        "class": "class_declaration",
        "struct": "struct_declaration",
        "enum": "enum_declaration",
        "protocol": "protocol_declaration",
    },
    comment_prefix="//",
)

_PHP = LanguageSpec(
    name="PHP",
    language_id="php",
    extensions=(".php",),
    symbol_queries={
        "function": "function_definition",
        "class": "class_declaration",
        "method": "method_declaration",
        "interface": "interface_declaration",
    },
    comment_prefix="//",
)

_SCALA = LanguageSpec(
    name="Scala",
    language_id="scala",
    extensions=(".scala", ".sc"),
    symbol_queries={
        "function": "function_definition",
        "class": "class_definition",
        "trait": "trait_definition",
        "object": "object_definition",
    },
    comment_prefix="//",
)

_LUA = LanguageSpec(
    name="Lua",
    language_id="lua",
    extensions=(".lua",),
    symbol_queries={
        "function": "function_declaration",
        "variable": "variable_declaration",
    },
    comment_prefix="--",
)

_BASH = LanguageSpec(
    name="Bash",
    language_id="bash",
    extensions=(".sh", ".bash"),
    symbol_queries={
        "function": "function_definition",
    },
    comment_prefix="#",
)

_HTML = LanguageSpec(
    name="HTML",
    language_id="html",
    extensions=(".html", ".htm"),
    symbol_queries={},
    comment_prefix="<!--",
)

_CSS = LanguageSpec(
    name="CSS",
    language_id="css",
    extensions=(".css",),
    symbol_queries={},
    comment_prefix="/*",
)

_YAML = LanguageSpec(
    name="YAML",
    language_id="yaml",
    extensions=(".yml", ".yaml"),
    symbol_queries={},
    comment_prefix="#",
)

_JSON = LanguageSpec(
    name="JSON",
    language_id="json",
    extensions=(".json",),
    symbol_queries={},
    comment_prefix="",
)

_TOML = LanguageSpec(
    name="TOML",
    language_id="toml",
    extensions=(".toml",),
    symbol_queries={},
    comment_prefix="#",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

LANGUAGE_SPECS: dict[str, LanguageSpec] = {
    spec.language_id: spec
    for spec in (
        _PYTHON,
        _JAVASCRIPT,
        _TYPESCRIPT,
        _TSX,
        _GO,
        _RUST,
        _JAVA,
        _CSHARP,
        _C,
        _CPP,
        _SQL,
        _RUBY,
        _KOTLIN,
        _SWIFT,
        _PHP,
        _SCALA,
        _LUA,
        _BASH,
        _HTML,
        _CSS,
        _YAML,
        _JSON,
        _TOML,
    )
}
"""Registry of all supported languages, keyed by ``language_id``."""


# Build a flat map from every registered file extension to its language_id
# for O(1) lookups in :func:`get_language_for_file`.
_EXTENSION_MAP: dict[str, str] = {}
for _spec in LANGUAGE_SPECS.values():
    for _ext in _spec.extensions:
        _ext_lower = _ext.lower()
        if _ext_lower in _EXTENSION_MAP:
            # First registration wins — order in LANGUAGE_SPECS matters.
            continue
        _EXTENSION_MAP[_ext_lower] = _spec.language_id


# ---------------------------------------------------------------------------
# Public lookup helpers
# ---------------------------------------------------------------------------


def get_language_for_file(filepath: str) -> LanguageSpec | None:
    """Return the :class:`LanguageSpec` for *filepath* based on its extension.

    The match is case-insensitive. Returns ``None`` when the extension is not
    recognised.
    """
    # Support both POSIX and Windows paths without importing ``os``.
    # PurePosixPath handles forward-slash paths; PureWindowsPath handles
    # backslash paths.  We try PureWindowsPath first so that paths like
    # ``C:\\code\\main.py`` are handled correctly, then fall back to
    # PurePosixPath for everything else.
    try:
        suffix = PureWindowsPath(filepath).suffix.lower()
    except (TypeError, ValueError):
        return None

    if not suffix:
        try:
            suffix = PurePosixPath(filepath).suffix.lower()
        except (TypeError, ValueError):
            return None

    language_id = _EXTENSION_MAP.get(suffix)
    if language_id is None:
        return None
    return LANGUAGE_SPECS[language_id]


def get_language_by_id(language_id: str) -> LanguageSpec | None:
    """Return the :class:`LanguageSpec` registered under *language_id*.

    Returns ``None`` when no language with that identifier is registered.
    """
    return LANGUAGE_SPECS.get(language_id)
