"""Filesystem watcher for auto-reindexing — requires watchfiles."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger("snip-mcp.watcher")

try:
    import watchfiles

    HAS_WATCHFILES = True
except ImportError:
    HAS_WATCHFILES = False

# Active watchers keyed by repo_path
_watchers: dict[str, asyncio.Task] = {}

# Debounce delay in seconds
_DEBOUNCE_SECONDS = 2.0


async def _watch_loop(repo_path: str) -> None:
    """Watch a repository for file changes and trigger incremental re-index."""
    if not HAS_WATCHFILES:
        return

    root = Path(repo_path)
    logger.info("Starting watcher for %s", repo_path)

    try:
        async for changes in watchfiles.awatch(root):
            # Debounce: wait a bit for more changes to accumulate
            await asyncio.sleep(_DEBOUNCE_SECONDS)

            changed_files = {str(Path(path)) for _change_type, path in changes}
            logger.info(
                "Detected %d changed files in %s, re-indexing...",
                len(changed_files),
                repo_path,
            )

            # Trigger incremental re-index
            try:
                from snip_mcp.tools.index_folder import index_folder

                index_folder(repo_path, force=False)
                logger.info("Re-index complete for %s", repo_path)
            except Exception:
                logger.exception("Re-index failed for %s", repo_path)
    except asyncio.CancelledError:
        logger.info("Watcher stopped for %s", repo_path)
        raise


def start_watching(repo_path: str) -> bool:
    """Start watching a repository for changes.

    Returns True if watcher was started, False if already watching or
    watchfiles is not installed.
    """
    if not HAS_WATCHFILES:
        return False

    if repo_path in _watchers and not _watchers[repo_path].done():
        return False  # Already watching

    loop = asyncio.get_event_loop()
    task = loop.create_task(_watch_loop(repo_path))
    _watchers[repo_path] = task
    return True


def stop_watching(repo_path: str) -> bool:
    """Stop watching a repository.

    Returns True if watcher was stopped, False if not watching.
    """
    task = _watchers.pop(repo_path, None)
    if task is None or task.done():
        return False
    task.cancel()
    return True


def is_watching(repo_path: str) -> bool:
    """Check if a repository is being watched."""
    task = _watchers.get(repo_path)
    return task is not None and not task.done()


def list_watched() -> list[str]:
    """Return list of currently watched repo paths."""
    return [rp for rp, task in _watchers.items() if not task.done()]
