"""export_diagram tool — generates Mermaid diagrams from index data."""

from __future__ import annotations

from snip_mcp.parser.symbols import SymbolKind
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def export_diagram(
    repo_path: str,
    type: str,
    *,
    file_pattern: str | None = None,
) -> dict:
    """Generate a Mermaid markdown diagram from the index.

    Args:
        repo_path: Absolute path to the indexed folder.
        type: Diagram type — "class_hierarchy", "call_graph", or "imports".
        file_pattern: Optional file path filter.

    Returns:
        Envelope with Mermaid markdown string.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    if type == "class_hierarchy":
        mermaid = _class_hierarchy(index, file_pattern)
    elif type == "call_graph":
        mermaid = _call_graph_diagram(index, file_pattern)
    elif type == "imports":
        mermaid = _imports_diagram(index, file_pattern)
    else:
        return meta_envelope(
            {"error": f"Unknown diagram type: {type}. Use: class_hierarchy, call_graph, imports"},
            repo_path=repo_path,
        )

    return meta_envelope(
        {"type": type, "mermaid": mermaid},
        repo_path=index.repo_path,
    )


def _matches_pattern(file_path: str, pattern: str | None) -> bool:
    if pattern is None:
        return True
    return pattern.lower() in file_path.lower()


def _sanitize_id(name: str) -> str:
    """Make a string safe for Mermaid node IDs."""
    return name.replace(".", "_").replace("/", "_").replace("::", "_").replace("-", "_")


def _class_hierarchy(index, file_pattern: str | None) -> str:
    lines = ["classDiagram"]
    classes = {}

    for sym in index.symbols.values():
        if not _matches_pattern(sym.file_path, file_pattern):
            continue
        if sym.kind == SymbolKind.CLASS:
            cid = _sanitize_id(sym.name)
            classes[sym.id] = cid
            lines.append(f"    class {cid}")

            # Add methods as class members
            for child_id in sym.children:
                child = index.symbols.get(child_id)
                if child and child.kind == SymbolKind.METHOD:
                    lines.append(f"    {cid} : {child.signature}")

    # Parent-child relationships (nested classes)
    for sym in index.symbols.values():
        if sym.kind == SymbolKind.CLASS and sym.parent_id:
            parent_cid = classes.get(sym.parent_id)
            child_cid = classes.get(sym.id)
            if parent_cid and child_cid:
                lines.append(f"    {parent_cid} <|-- {child_cid}")

    if len(lines) == 1:
        lines.append("    %% No classes found")

    return "\n".join(lines)


def _call_graph_diagram(index, file_pattern: str | None) -> str:
    lines = ["graph LR"]

    if not index.call_graph:
        lines.append("    %% No call graph data — re-index to build it")
        return "\n".join(lines)

    node_ids: dict[str, str] = {}
    edge_count = 0
    max_edges = 100

    for caller_id, callees in index.call_graph.items():
        caller = index.symbols.get(caller_id)
        if not caller or not _matches_pattern(caller.file_path, file_pattern):
            continue

        if caller_id not in node_ids:
            nid = _sanitize_id(f"{caller.name}_{caller.line_start}")
            node_ids[caller_id] = nid
            lines.append(f"    {nid}[{caller.name}]")

        for callee_id in callees:
            if edge_count >= max_edges:
                break
            callee = index.symbols.get(callee_id)
            if not callee:
                continue

            if callee_id not in node_ids:
                nid = _sanitize_id(f"{callee.name}_{callee.line_start}")
                node_ids[callee_id] = nid
                lines.append(f"    {nid}[{callee.name}]")

            lines.append(f"    {node_ids[caller_id]} --> {node_ids[callee_id]}")
            edge_count += 1

    return "\n".join(lines)


def _imports_diagram(index, file_pattern: str | None) -> str:
    lines = ["graph LR"]
    node_ids: dict[str, str] = {}
    edge_count = 0
    max_edges = 100

    for rel_path, fs in index.files.items():
        if not _matches_pattern(rel_path, file_pattern):
            continue
        if not fs.imports:
            continue

        if rel_path not in node_ids:
            nid = _sanitize_id(rel_path)
            node_ids[rel_path] = nid
            # Use just the filename for readability
            short = rel_path.rsplit("/", 1)[-1]
            lines.append(f"    {nid}[{short}]")

        for imp in fs.imports:
            if edge_count >= max_edges:
                break
            imp_id = _sanitize_id(imp)
            if imp not in node_ids:
                node_ids[imp] = imp_id
                short_imp = imp.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
                lines.append(f"    {imp_id}[{short_imp}]")
            lines.append(f"    {node_ids[rel_path]} --> {node_ids[imp]}")
            edge_count += 1

    return "\n".join(lines)
