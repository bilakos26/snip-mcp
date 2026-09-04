"""export_docs tool — generates markdown documentation from index."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.tools._utils import meta_envelope, resolve_repo


def export_docs(
    repo_path: str,
    *,
    file_pattern: str | None = None,
    format: str = "markdown",
    output_path: str | None = None,
) -> dict:
    """Generate markdown documentation from the code index.

    Args:
        repo_path: Absolute path to the indexed folder.
        file_pattern: Optional file path filter.
        format: Output format (currently only "markdown").
        output_path: If provided, write the documentation to this file path.

    Returns:
        Envelope with generated documentation string and optional saved path.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    if format != "markdown":
        return meta_envelope(
            {"error": f"Unsupported format: {format}. Only 'markdown' is supported."},
            repo_path=repo_path,
        )

    lines: list[str] = []
    lines.append(f"# {index.repo_name}")
    lines.append("")
    lines.append(f"**{index.total_files}** files, **{index.total_symbols}** symbols")
    lines.append("")

    # Group symbols by file
    files_to_show = sorted(index.files.keys())
    if file_pattern:
        pattern_lower = file_pattern.lower()
        files_to_show = [f for f in files_to_show if pattern_lower in f.lower()]

    for rel_path in files_to_show:
        fs = index.files[rel_path]
        if not fs.symbols:
            continue

        lines.append(f"## `{rel_path}`")
        lines.append("")

        for sym in fs.symbols:
            # Only top-level symbols
            if sym.parent_id:
                continue

            kind_label = sym.kind.value.replace("_", " ").title()
            lines.append(f"### {kind_label}: `{sym.name}`")
            lines.append("")
            lines.append("```")
            lines.append(sym.signature)
            lines.append("```")
            lines.append("")

            if sym.parameters:
                lines.append("**Parameters:**")
                lines.append("")
                for param in sym.parameters:
                    type_str = f": `{param.type_annotation}`" if param.type_annotation else ""
                    default_str = f" = `{param.default_value}`" if param.default_value else ""
                    lines.append(f"- `{param.name}`{type_str}{default_str}")
                lines.append("")

            if sym.return_type:
                lines.append(f"**Returns:** `{sym.return_type}`")
                lines.append("")

            if sym.docstring:
                lines.append(f"> {sym.docstring[:300]}")
                lines.append("")

            # Show children (methods)
            if sym.children:
                for child_id in sym.children:
                    child = index.symbols.get(child_id)
                    if child:
                        lines.append(f"- **{child.kind.value}** `{child.name}` — {child.signature}")
                lines.append("")

        lines.append("---")
        lines.append("")

    content = "\n".join(lines)

    saved_to: str | None = None
    if output_path:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        saved_to = str(dest)

    result: dict = {
        "format": format,
        "files_documented": len(files_to_show),
        "content": content,
    }
    if saved_to:
        result["saved_to"] = saved_to

    return meta_envelope(result, repo_path=index.repo_path)
