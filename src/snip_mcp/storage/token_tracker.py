"""Local-only token-savings tracker for Snip MCP.

Records how many tokens each retrieval would have cost (full file) versus how
many were actually returned (targeted symbols).  All data stays on disk in
``~/.snip/stats.json`` and ``~/.snip/session.json`` -- no telemetry,
no network calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate the token count for *text* using a simple heuristic.

    Uses the common approximation of ~4 characters per token.

    Parameters
    ----------
    text:
        Arbitrary text to estimate tokens for.

    Returns
    -------
    int
        Estimated token count (always >= 0).
    """
    return len(text) // 4


class TokenTracker:
    """Tracks cumulative and per-session token savings.

    Persists two JSON files with running totals so users can see how much
    context-window budget Snip has saved them — both for the current
    MCP session and cumulatively over time.

    Parameters
    ----------
    storage_dir:
        Directory where ``stats.json`` and ``session.json`` are stored.
        Defaults to ``~/.snip/``.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        if storage_dir is None:
            storage_dir = Path.home() / ".snip"
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    # -- Path helpers -------------------------------------------------------

    @property
    def _stats_path(self) -> Path:
        """Path to the cumulative stats JSON file."""
        return self._storage_dir / "stats.json"

    @property
    def _session_path(self) -> Path:
        """Path to the per-session stats JSON file."""
        return self._storage_dir / "session.json"

    # -- Cumulative persistence ---------------------------------------------

    def _load_raw(self) -> dict[str, Any]:
        """Load the stats file, returning empty counters if absent or corrupt."""
        if not self._stats_path.exists():
            return {
                "total_retrievals": 0,
                "total_full_tokens": 0,
                "total_returned_tokens": 0,
            }
        try:
            data = json.loads(self._stats_path.read_text(encoding="utf-8"))
            return {
                "total_retrievals": int(data.get("total_retrievals", 0)),
                "total_full_tokens": int(data.get("total_full_tokens", 0)),
                "total_returned_tokens": int(data.get("total_returned_tokens", 0)),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            return {
                "total_retrievals": 0,
                "total_full_tokens": 0,
                "total_returned_tokens": 0,
            }

    def _save_raw(self, data: dict[str, Any]) -> None:
        """Write cumulative stats to disk."""
        self._stats_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    # -- Session persistence ------------------------------------------------

    def _load_session(self) -> dict[str, Any]:
        """Load session file, returning empty counters if absent or corrupt."""
        if not self._session_path.exists():
            return {
                "session_started": None,
                "retrievals": 0,
                "full_tokens": 0,
                "returned_tokens": 0,
            }
        try:
            data = json.loads(self._session_path.read_text(encoding="utf-8"))
            return {
                "session_started": data.get("session_started"),
                "retrievals": int(data.get("retrievals", 0)),
                "full_tokens": int(data.get("full_tokens", 0)),
                "returned_tokens": int(data.get("returned_tokens", 0)),
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            return {
                "session_started": None,
                "retrievals": 0,
                "full_tokens": 0,
                "returned_tokens": 0,
            }

    def _save_session(self, data: dict[str, Any]) -> None:
        """Write session stats to disk."""
        self._session_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    def reset_session(self) -> None:
        """Reset session counters to zero with a fresh timestamp."""
        self._save_session(
            {
                "session_started": datetime.now(timezone.utc).isoformat(),
                "retrievals": 0,
                "full_tokens": 0,
                "returned_tokens": 0,
            }
        )

    def get_session_stats(self) -> dict[str, Any]:
        """Return per-session usage statistics.

        Returns
        -------
        dict
            Keys: ``session_started``, ``retrievals``, ``full_tokens``,
            ``returned_tokens``, ``tokens_saved``, ``savings_pct``.
        """
        raw = self._load_session()
        full = raw["full_tokens"]
        returned = raw["returned_tokens"]
        saved = full - returned
        pct = round((1.0 - returned / full) * 100.0, 2) if full > 0 else 0.0

        return {
            "session_started": raw["session_started"],
            "retrievals": raw["retrievals"],
            "full_tokens": full,
            "returned_tokens": returned,
            "tokens_saved": saved,
            "savings_pct": pct,
        }

    # -- Recording ----------------------------------------------------------

    def record_retrieval(self, full_tokens: int, returned_tokens: int) -> None:
        """Record a single retrieval event (updates both cumulative and session).

        Parameters
        ----------
        full_tokens:
            Estimated token count if the entire file(s) had been sent.
        returned_tokens:
            Estimated token count of the symbols actually returned.
            Clamped to ``full_tokens`` so savings never go negative.
        """
        # Clamp: returning more than the full file is nonsensical
        returned_tokens = min(returned_tokens, full_tokens)

        # Update cumulative stats
        stats = self._load_raw()
        stats["total_retrievals"] += 1
        stats["total_full_tokens"] += full_tokens
        stats["total_returned_tokens"] += returned_tokens
        self._save_raw(stats)

        # Update session stats
        session = self._load_session()
        session["retrievals"] += 1
        session["full_tokens"] += full_tokens
        session["returned_tokens"] += returned_tokens
        self._save_session(session)

    # -- Public stats -------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return both session and cumulative usage statistics.

        Returns
        -------
        dict
            Top-level keys: ``session``, ``cumulative``, plus legacy
            top-level keys (``total_retrievals``, ``total_full_tokens``,
            ``total_returned_tokens``, ``savings_pct``) for backward
            compatibility.
        """
        raw = self._load_raw()
        total_full = raw["total_full_tokens"]
        total_returned = raw["total_returned_tokens"]

        if total_full > 0:
            savings_pct = round(
                (1.0 - total_returned / total_full) * 100.0,
                2,
            )
        else:
            savings_pct = 0.0

        cumulative = {
            "total_retrievals": raw["total_retrievals"],
            "total_full_tokens": total_full,
            "total_returned_tokens": total_returned,
            "savings_pct": savings_pct,
        }

        return {
            # New structured keys
            "session": self.get_session_stats(),
            "cumulative": cumulative,
            # Legacy top-level keys (backward compat)
            **cumulative,
        }
