"""export_diagram tool — generates Mermaid diagrams from index data."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.parser.symbols import SymbolKind
from snip_mcp.tools._utils import meta_envelope, resolve_repo


def export_diagram(
    repo_path: str,
    type: str,
    *,
    file_pattern: str | None = None,
    output_path: str | None = None,
) -> dict:
    """Generate a Mermaid markdown diagram from the index.

    Args:
        repo_path: Absolute path to the indexed folder.
        type: Diagram type — "class_hierarchy", "call_graph", or "imports".
        file_pattern: Optional file path filter.
        output_path: If provided, write the diagram to this file path.

    Returns:
        Envelope with Mermaid markdown string and optional saved path.
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

    saved_to: str | None = None
    if output_path:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(mermaid, encoding="utf-8")
        saved_to = str(dest)

    result: dict = {"type": type, "mermaid": mermaid}
    if saved_to:
        result["saved_to"] = saved_to

    return meta_envelope(result, repo_path=index.repo_path)


# Color palette for directory groups (fill, stroke)
_GROUP_COLORS = [
    ("class1", "#4a90d9", "#2c6fad"),  # blue
    ("class2", "#e67e22", "#c0392b"),  # orange-red
    ("class3", "#27ae60", "#1e8449"),  # green
    ("class4", "#8e44ad", "#6c3483"),  # purple
    ("class5", "#16a085", "#117a65"),  # teal
    ("class6", "#d35400", "#a04000"),  # dark orange
    ("class7", "#2980b9", "#1a5276"),  # dark blue
    ("class8", "#c0392b", "#922b21"),  # red
]


def _top_dir(rel_path: str) -> str:
    """Return the top-level directory of a path, or '' for root-level files."""
    parts = rel_path.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else ""


def _build_classdefs(node_groups: dict[str, str]) -> list[str]:
    """Build classDef + class assignment lines for node color groups.

    node_groups: maps node_id -> top-level directory name (the color group).
    """
    # Unique groups in stable sorted order
    unique_groups = sorted(set(node_groups.values()))
    group_to_cls: dict[str, str] = {}
    lines = []
    for i, grp in enumerate(unique_groups):
        cls_name, fill, stroke = _GROUP_COLORS[i % len(_GROUP_COLORS)]
        full_cls = f"{cls_name}_{i}"
        group_to_cls[grp] = full_cls
        lines.append(f"    classDef {full_cls} fill:{fill},stroke:{stroke},color:#fff")

    # One class assignment per group
    for grp, full_cls in group_to_cls.items():
        nids = [nid for nid, g in node_groups.items() if g == grp]
        if nids:
            lines.append(f"    class {','.join(nids)} {full_cls}")
    return lines


def _matches_pattern(file_path: str, pattern: str | None) -> bool:
    if pattern is None:
        return True
    return pattern.lower() in file_path.lower()


def _sanitize_id(name: str) -> str:
    """Make a string safe for Mermaid node IDs."""
    return name.replace(".", "_").replace("/", "_").replace("::", "_").replace("-", "_")


def _class_hierarchy(index, file_pattern: str | None) -> str:
    from collections import defaultdict

    _method_kinds = {SymbolKind.METHOD, SymbolKind.FUNCTION}
    max_classes = 30

    # Collect (sym, public_methods) grouped by top-level directory
    dir_buckets: dict[str, list] = defaultdict(list)
    total_candidates = 0

    for sym in index.symbols.values():
        if not _matches_pattern(sym.file_path, file_pattern):
            continue
        if sym.kind != SymbolKind.CLASS:
            continue
        public_methods = [
            index.symbols[cid]
            for cid in sym.children
            if cid in index.symbols
            and index.symbols[cid].kind in _method_kinds
            and not index.symbols[cid].name.startswith("_")
        ]
        if not public_methods:
            continue
        total_candidates += 1
        dir_buckets[_top_dir(sym.file_path)].append((sym, public_methods))

    if not dir_buckets:
        return "classDiagram\n    %% No classes with public methods found — try a different file_pattern"

    # Flatten and cap at max_classes, preserving directory order
    selected: list[tuple[str, object, list]] = []
    for top_dir in sorted(dir_buckets):
        for sym, methods in dir_buckets[top_dir]:
            if len(selected) >= max_classes:
                break
            selected.append((top_dir, sym, methods))

    # Build using namespace blocks so classes are visually grouped by directory
    lines = ["classDiagram"]
    classes: dict[str, str] = {}  # sym.id -> class name used in diagram
    edges: list[str] = []
    style_lines: list[str] = []

    unique_dirs = sorted({top for top, _, _ in selected})
    dir_to_color = {
        d: _GROUP_COLORS[i % len(_GROUP_COLORS)]
        for i, d in enumerate(unique_dirs)
    }

    for top_dir in unique_dirs:
        ns = _sanitize_id(top_dir) if top_dir else "root"
        lines.append(f"    namespace {ns} {{")
        for td, sym, methods in selected:
            if td != top_dir:
                continue
            # Use plain class name inside namespace (namespace provides scoping)
            # Suffix with line number to disambiguate same-name classes in same namespace
            cname = f"{sym.name}_{sym.line_start}" if any(
                s.name == sym.name and s.id != sym.id
                for s, _ in [(x[1], x[2]) for x in selected if x[0] == top_dir]
            ) else sym.name
            classes[sym.id] = cname
            lines.append(f"        class {cname} {{")
            for child in methods[:6]:
                lines.append(f"            +{child.name}()")
            lines.append("        }")
            _, fill, stroke = dir_to_color[top_dir]
            style_lines.append(f"    style {cname} fill:{fill},stroke:{stroke},color:#fff")
        lines.append("    }")

    # Inheritance edges (outside namespace blocks)
    for sym in index.symbols.values():
        if sym.kind == SymbolKind.CLASS and sym.parent_id:
            p = classes.get(sym.parent_id)
            c = classes.get(sym.id)
            if p and c and p != c:
                edges.append(f"    {p} <|-- {c}")

    lines.extend(edges)

    if len(selected) < total_candidates:
        lines.append(
            f"    %% Showing {len(selected)} of {total_candidates} classes"
            f" — use file_pattern to narrow scope"
        )

    lines.extend(style_lines)
    return "\n".join(lines)


def _call_graph_diagram(index, file_pattern: str | None) -> str:
    lines = ["graph TD"]

    if not index.call_graph:
        lines.append("    %% No call graph data — re-index to build it")
        return "\n".join(lines)

    node_ids: dict[str, str] = {}
    node_groups: dict[str, str] = {}  # node_id -> top-level dir
    edge_count = 0
    max_edges = 100

    for caller_id, callees in index.call_graph.items():
        if edge_count >= max_edges:
            break
        caller = index.symbols.get(caller_id)
        if not caller or not _matches_pattern(caller.file_path, file_pattern):
            continue

        if caller_id not in node_ids:
            nid = _sanitize_id(f"{caller.name}_{caller.line_start}")
            node_ids[caller_id] = nid
            node_groups[nid] = _top_dir(caller.file_path)
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
                node_groups[nid] = _top_dir(callee.file_path)
                lines.append(f"    {nid}[{callee.name}]")

            lines.append(f"    {node_ids[caller_id]} --> {node_ids[callee_id]}")
            edge_count += 1

    if edge_count >= max_edges:
        lines.append(
            f"    %% Truncated at {max_edges} edges — use file_pattern to narrow scope"
        )
    if node_groups:
        lines.extend(_build_classdefs(node_groups))

    return "\n".join(lines)


def _resolve_import_to_file(imp: str, index) -> str | None:
    """Try to resolve a Python module import string to a file path in the index.

    Returns the matching rel_path key from index.files, or None if external/unresolvable.
    """
    if not imp or imp.startswith("."):
        return None
    candidate = imp.replace(".", "/") + ".py"
    if candidate in index.files:
        return candidate
    # Also try the module as a direct path (e.g. already a path-like string)
    if imp in index.files:
        return imp
    return None


def _short_label(rel_path: str) -> str:
    """Return a readable node label: show last two path segments to disambiguate."""
    parts = rel_path.replace("\\", "/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def _imports_diagram(index, file_pattern: str | None) -> str:
    lines = ["graph TD"]
    node_ids: dict[str, str] = {}
    node_groups: dict[str, str] = {}  # node_id -> top-level dir
    edge_count = 0
    max_edges = 100

    for rel_path, fs in index.files.items():
        if edge_count >= max_edges:
            break
        if not _matches_pattern(rel_path, file_pattern):
            continue
        if not fs.imports:
            continue

        for imp in fs.imports:
            if edge_count >= max_edges:
                break

            # Only draw edges between project-internal files
            target_path = _resolve_import_to_file(imp, index)
            if target_path is None:
                continue

            if rel_path not in node_ids:
                nid = _sanitize_id(rel_path)
                node_ids[rel_path] = nid
                node_groups[nid] = _top_dir(rel_path)
                lines.append(f"    {nid}[{_short_label(rel_path)}]")

            if target_path not in node_ids:
                nid = _sanitize_id(target_path)
                node_ids[target_path] = nid
                node_groups[nid] = _top_dir(target_path)
                lines.append(f"    {nid}[{_short_label(target_path)}]")

            lines.append(f"    {node_ids[rel_path]} --> {node_ids[target_path]}")
            edge_count += 1

    if edge_count == 0:
        lines.append("    %% No internal imports found")
    else:
        if edge_count >= max_edges:
            lines.append(
                f"    %% Truncated at {max_edges} edges — use file_pattern to narrow scope"
            )
        lines.extend(_build_classdefs(node_groups))

    return "\n".join(lines)
