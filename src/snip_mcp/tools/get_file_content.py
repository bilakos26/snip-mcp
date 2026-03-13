"""get_file_content tool — file content with optional line range."""

from __future__ import annotations

from pathlib import Path

from snip_mcp.security import safe_read
from snip_mcp.storage.token_tracker import TokenTracker, estimate_tokens
from snip_mcp.tools._utils import meta_envelope, resolve_repo, truncate


def get_file_content(
    repo_path: str,
    file_path: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict:
    """Get the content of a file, optionally limited to a line range.

    Args:
        repo_path: Path to the indexed folder.
        file_path: Relative path to the file within the repo.
        start_line: 1-based start line (inclusive). None = beginning.
        end_line: 1-based end line (inclusive). None = end of file.
    """
    index, err = resolve_repo(repo_path)
    if index is None:
        return meta_envelope({"error": err})

    file_path = file_path.replace("\\", "/")

    # Read the actual file from disk
    full_path = Path(index.repo_path) / file_path
    content = safe_read(full_path)
    if content is None:
        return meta_envelope({"error": f"Cannot read file: {file_path}"})

    lines = content.split("\n")
    total_lines = len(lines)

    # Apply line range
    if start_line is not None or end_line is not None:
        s = (start_line or 1) - 1  # convert to 0-based
        e = end_line or total_lines
        selected_lines = lines[s:e]
        content_out = "\n".join(selected_lines)
        line_info = {"start_line": s + 1, "end_line": min(e, total_lines)}
    else:
        content_out = content
        line_info = {"start_line": 1, "end_line": total_lines}

    # Token tracking
    full_tokens = estimate_tokens(content)
    returned_tokens = estimate_tokens(content_out)
    tracker = TokenTracker()
    tracker.record_retrieval(full_tokens, returned_tokens)

    return meta_envelope(
        {
            "file_path": file_path,
            "total_lines": total_lines,
            **line_info,
            "content": truncate(content_out),
            "language": index.files.get(file_path, None) and index.files[file_path].language or "",
        },
        repo_path=index.repo_path,
        tokens_saved=max(0, full_tokens - returned_tokens),
    )
