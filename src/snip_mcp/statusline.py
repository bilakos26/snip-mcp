#!/usr/bin/env python3
"""Snip statusline script for Claude Code.

Reads Claude Code JSON context from stdin and combines it with Snip
session stats from ~/.snip/session.json. Outputs a visual 2-line status
with Unicode block progress bars:

    Opus  ▐████████░░░░░░░░░░▌ 42% ctx  84.0K/200.0K  $0.15
      ⚡ Snip  ▐████████████████░░▌ 5 calls  12.3K saved (87%)

Install via: snip-mcp --setup-statusline

No external dependencies — stdlib only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Bar characters
_FILLED = "\u2588"  # █
_EMPTY = "\u2591"  # ░
_LEFT = "\u2590"  # ▐
_RIGHT = "\u258c"  # ▌


def _format_tokens(n: int | float) -> str:
    """Format a token count as a human-readable string."""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _progress_bar(pct: float, width: int = 18) -> str:
    """Render a Unicode block progress bar.

    Parameters
    ----------
    pct:
        Percentage (0-100).
    width:
        Number of bar segments (excluding left/right caps).

    Returns
    -------
    str
        e.g. ``▐████████░░░░░░░░░░▌``
    """
    pct = max(0.0, min(100.0, pct))
    filled = round(pct / 100.0 * width)
    empty = width - filled
    return f"{_LEFT}{_FILLED * filled}{_EMPTY * empty}{_RIGHT}"


def _load_session() -> dict:
    """Load Snip session stats from disk."""
    path = Path.home() / ".snip" / "session.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _format_claude_line(ctx: dict) -> str:
    """Format line 1 from Claude Code's stdin JSON with a context progress bar."""
    model = ctx.get("model", {}).get("display_name", "Claude")
    cw = ctx.get("context_window", {})
    used_pct = cw.get("used_percentage", 0)
    total_input = cw.get("total_input_tokens", 0)
    window_size = cw.get("context_window_size", 0)
    cost = ctx.get("cost", {}).get("total_cost_usd", 0)

    bar = _progress_bar(used_pct)
    return (
        f"{model}  {bar} {used_pct}% ctx  "
        f"{_format_tokens(total_input)}/{_format_tokens(window_size)}  "
        f"${cost:.2f}"
    )


def _format_snip_line(session: dict) -> str:
    """Format line 2 from Snip session stats with a savings progress bar."""
    retrievals = session.get("retrievals", 0)
    full = session.get("full_tokens", 0)
    returned = session.get("returned_tokens", 0)
    saved = full - returned
    pct = round((1.0 - returned / full) * 100.0, 1) if full > 0 else 0.0

    bar = _progress_bar(max(0.0, pct))
    return f"  \u26a1 Snip  {bar} {retrievals} calls  {_format_tokens(saved)} saved ({pct}%)"


def _ensure_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8 on Windows (avoids cp1252 encode errors)."""
    import io

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    elif sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def main() -> None:
    """Entry point -- read stdin JSON, combine with session stats, print 2 lines."""
    _ensure_utf8_stdout()
    raw = sys.stdin.read().strip()
    if not raw:
        return

    try:
        ctx = json.loads(raw)
    except json.JSONDecodeError:
        return

    session = _load_session()

    print(_format_claude_line(ctx))
    if session and session.get("retrievals", 0) > 0:
        print(_format_snip_line(session))


if __name__ == "__main__":
    main()
