"""Tree-sitter AST walking and symbol extraction for Snip MCP.

Parses source code using tree-sitter-language-pack, walks the AST, and
extracts Symbol instances based on LanguageSpec node type mappings.
"""

from __future__ import annotations

from snip_mcp.parser.languages import LanguageSpec
from snip_mcp.parser.sql_preprocessor import is_dbt_model, strip_jinja
from snip_mcp.parser.symbols import (
    Symbol,
    SymbolKind,
    compute_content_hash,
    make_symbol_id,
)

try:
    import tree_sitter_language_pack as tslp

    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


def _get_parser(language_id: str):
    """Get a tree-sitter parser for the given language."""
    if not HAS_TREE_SITTER:
        raise RuntimeError("tree-sitter-language-pack is not installed")
    return tslp.get_parser(language_id)


def _get_language(language_id: str):
    """Get a tree-sitter Language object for the given language."""
    if not HAS_TREE_SITTER:
        raise RuntimeError("tree-sitter-language-pack is not installed")
    return tslp.get_language(language_id)


def _node_text(node, source_bytes: bytes) -> str:
    """Extract text from a tree-sitter node."""
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _first_line(text: str) -> str:
    """Get the first line of text, stripped."""
    idx = text.find("\n")
    if idx != -1:
        return text[:idx].strip()
    return text.strip()


def _extract_name(node, source_bytes: bytes, language_id: str) -> str:
    """Extract the symbol name from a tree-sitter node.

    Tries common child node types across languages.
    """
    # Common name-bearing child types
    name_types = {"identifier", "name", "type_identifier", "property_identifier"}

    for child in node.children:
        if child.type in name_types:
            return _node_text(child, source_bytes)

    # For Go type declarations: type_declaration -> type_spec -> name
    if node.type == "type_declaration":
        for child in node.children:
            if child.type == "type_spec":
                for grandchild in child.children:
                    if grandchild.type in name_types:
                        return _node_text(grandchild, source_bytes)

    # For variable_declarator (JS arrow functions)
    if node.type == "variable_declarator":
        for child in node.children:
            if child.type in name_types:
                return _node_text(child, source_bytes)

    # For decorated_definition (Python)
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type in ("function_definition", "class_definition"):
                return _extract_name(child, source_bytes, language_id)

    # For lexical_declaration/variable_declaration containing arrow_function
    if node.type in ("lexical_declaration", "variable_declaration"):
        for child in node.children:
            if child.type == "variable_declarator":
                return _extract_name(child, source_bytes, language_id)

    # Fallback: first identifier-like child
    for child in node.children:
        text = _node_text(child, source_bytes)
        if text and text.isidentifier():
            return text

    return ""


def _extract_docstring(node, source_bytes: bytes, spec: LanguageSpec) -> str:
    """Extract docstring from a node if present.

    For Python: looks for a string expression_statement as first body child.
    For Rust/C-like: looks for preceding doc comments.
    """
    if spec.language_id == "python":
        # Find the body/block child
        for child in node.children:
            if child.type == "block":
                for stmt in child.children:
                    # Handle both bare string nodes and expression_statement wrapping
                    doc_node = None
                    if stmt.type in spec.docstring_node_types:
                        doc_node = stmt
                    elif stmt.type == "expression_statement":
                        for expr in stmt.children:
                            if expr.type in spec.docstring_node_types:
                                doc_node = expr
                                break
                    if doc_node is not None:
                        text = _node_text(doc_node, source_bytes)
                        # Strip triple quotes
                        for q in ('"""', "'''", '"', "'"):
                            if text.startswith(q) and text.endswith(q):
                                text = text[len(q) : -len(q)]
                                break
                        return text.strip()
                    # Only check the first statement in the block
                    break
        return ""

    if spec.language_id == "decorated_definition":
        # Find the actual definition inside
        for child in node.children:
            if child.type in ("function_definition", "class_definition"):
                return _extract_docstring(child, source_bytes, spec)

    return ""


def _extract_decorators(node, source_bytes: bytes) -> tuple[str, ...]:
    """Extract decorator names from a decorated_definition or similar node."""
    decorators: list[str] = []

    if node.type == "decorated_definition":
        for child in node.children:
            if child.type == "decorator":
                text = _node_text(child, source_bytes).strip()
                # Remove @ prefix and arguments
                if text.startswith("@"):
                    text = text[1:]
                paren = text.find("(")
                if paren != -1:
                    text = text[:paren]
                decorators.append(text.strip())

    return tuple(decorators)


def _determine_kind(
    node_type: str, kind_value: str, node, source_bytes: bytes, language_id: str
) -> SymbolKind:
    """Determine the precise SymbolKind for a node."""
    try:
        kind = SymbolKind(kind_value)
    except ValueError:
        kind = SymbolKind.UNKNOWN

    # For Go type_declaration, distinguish struct vs interface
    if language_id == "go" and node.type == "type_declaration":
        node_text = _node_text(node, source_bytes)
        if "struct" in node_text:
            kind = SymbolKind.STRUCT
        elif "interface" in node_text:
            kind = SymbolKind.INTERFACE

    # Python: method vs function (inside class = method)
    if language_id == "python" and kind_value == "method":
        # Check if parent is a class body — we do this in hierarchy later
        # For now, keep the extractor's assignment
        pass

    # decorated_definition: use the inner kind
    if node.type == "decorated_definition":
        for child in node.children:
            if child.type == "function_definition":
                return SymbolKind.FUNCTION
            elif child.type == "class_definition":
                return SymbolKind.CLASS
        return SymbolKind.FUNCTION

    return kind


def _walk_and_extract(
    node,
    source_bytes: bytes,
    spec: LanguageSpec,
    file_path: str,
    target_types: dict[str, str],
    symbols: list[Symbol],
) -> None:
    """Recursively walk the AST and extract symbols matching target node types."""
    node_type = node.type

    # Check if this node type is one we're looking for
    matched_kind: str | None = None
    for kind_value, type_names in target_types.items():
        types = [t.strip() for t in type_names.split(",")]
        if node_type in types:
            matched_kind = kind_value
            break

    # Special handling: arrow functions in variable declarations (JS/TS)
    if node_type in ("lexical_declaration", "variable_declaration") and "function" in target_types:
        fn_types = [t.strip() for t in target_types["function"].split(",")]
        if "arrow_function" in fn_types:
            for child in node.children:
                if child.type == "variable_declarator":
                    for grandchild in child.children:
                        if grandchild.type == "arrow_function":
                            name = _extract_name(child, source_bytes, spec.language_id)
                            if name:
                                sig = _first_line(_node_text(node, source_bytes))
                                sym_kind = SymbolKind.FUNCTION
                                line_num = node.start_point[0] + 1
                                sym_id = make_symbol_id(file_path, sym_kind, name, line_num)
                                content = _node_text(node, source_bytes)
                                symbols.append(
                                    Symbol(
                                        id=sym_id,
                                        name=name,
                                        kind=sym_kind,
                                        file_path=file_path,
                                        line_start=node.start_point[0] + 1,
                                        line_end=node.end_point[0] + 1,
                                        byte_start=node.start_byte,
                                        byte_end=node.end_byte,
                                        signature=sig,
                                        docstring="",
                                        content_hash=compute_content_hash(content),
                                        language=spec.language_id,
                                    )
                                )
                            # Don't recurse into this node further for function extraction
                            return

    if matched_kind is not None:
        name = _extract_name(node, source_bytes, spec.language_id)
        if name:
            kind = _determine_kind(node_type, matched_kind, node, source_bytes, spec.language_id)
            sig = _first_line(_node_text(node, source_bytes))
            docstring = _extract_docstring(node, source_bytes, spec)
            decorators = _extract_decorators(node, source_bytes)
            content = _node_text(node, source_bytes)

            sym_id = make_symbol_id(file_path, kind, name, node.start_point[0] + 1)
            symbols.append(
                Symbol(
                    id=sym_id,
                    name=name,
                    kind=kind,
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    byte_start=node.start_byte,
                    byte_end=node.end_byte,
                    signature=sig,
                    docstring=docstring,
                    decorators=decorators,
                    content_hash=compute_content_hash(content),
                    language=spec.language_id,
                )
            )

    # Recurse into children
    for child in node.children:
        _walk_and_extract(child, source_bytes, spec, file_path, target_types, symbols)


def extract_file_symbols(
    source: str,
    spec: LanguageSpec,
    file_path: str,
) -> list[Symbol]:
    """Parse source code and extract symbols using tree-sitter.

    Args:
        source: The source code text.
        spec: Language specification defining which node types to match.
        file_path: Relative file path (used in symbol IDs).

    Returns:
        List of Symbol instances extracted from the source.
    """
    if not HAS_TREE_SITTER:
        return []

    if not spec.symbol_queries:
        return []

    # SQL preprocessing: strip Jinja/dbt templates
    parse_source = source
    if spec.language_id == "sql" and is_dbt_model(source):
        parse_source = strip_jinja(source)

    source_bytes = parse_source.encode("utf-8")

    try:
        parser = _get_parser(spec.language_id)
        tree = parser.parse(source_bytes)
    except Exception:
        return []

    symbols: list[Symbol] = []
    _walk_and_extract(
        tree.root_node,
        source_bytes,
        spec,
        file_path,
        spec.symbol_queries,
        symbols,
    )

    return symbols
