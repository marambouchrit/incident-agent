"""Shared safety guards for every agent tool.

- safe_path: keeps every file access inside the current scenario folder.
- cap_output: keeps every observation under ~100 lines.
- run_with_timeout: keeps one slow tool from hanging the whole loop.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path, PurePath
from typing import Any, Callable, TypeVar

T = TypeVar("T")

DEFAULT_MAX_LINES = 100
DEFAULT_TIMEOUT_S = 10.0


class ToolError(Exception):
    """A problem the model can recover from. The loop turns it into a tool result."""


class ToolTimeout(ToolError):
    """The tool took longer than its time budget."""


def safe_path(scenario_dir: str | Path, rel: str) -> Path:
    """Resolve `rel` inside `scenario_dir`, or raise ToolError.

    Rejects absolute paths, any `..` part, and anything that ends up outside the
    scenario folder after resolving symlinks.
    """
    root = Path(scenario_dir).resolve()
    if not rel or not rel.strip():
        raise ToolError("Empty path.")

    candidate = PurePath(rel)
    # Path("C:/x").is_absolute() is False on POSIX, so also check drive/anchor.
    if candidate.is_absolute() or candidate.anchor or rel.startswith(("/", "\\")):
        raise ToolError(f"Absolute paths are not allowed: {rel!r}. Use a path relative to the scenario folder.")
    if ".." in candidate.parts:
        raise ToolError(f"'..' is not allowed in paths: {rel!r}.")

    # resolve() follows symlinks, so a link pointing outside is caught here.
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise ToolError(f"Path is outside the scenario folder: {rel!r}.")
    return resolved


def cap_output(text: str, max_lines: int = DEFAULT_MAX_LINES) -> str:
    """Return `text` unchanged if it fits; otherwise the first `max_lines` lines plus a footer."""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    omitted = len(lines) - max_lines
    return "\n".join(lines[:max_lines] + [truncation_footer(omitted, len(lines))])


def truncation_footer(omitted: int, total: int) -> str:
    shown = total - omitted
    return (
        f"[… output truncated: showing {shown} of {total} lines, {omitted} lines NOT shown. "
        f"Narrow your query (filter by level, keyword, or a shorter time window) "
        f"or use log_stats for an overview.]"
    )


def run_with_timeout(fn: Callable[..., T], *args: Any, timeout_s: float = DEFAULT_TIMEOUT_S, **kwargs: Any) -> T:
    """Run `fn` in a worker thread; raise ToolTimeout if it doesn't finish in time.

    Python can't kill a thread, so a timed-out call keeps running in the
    background. That's fine for read-only file tools; the loop just moves on.
    """
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout_s)
    except concurrent.futures.TimeoutError:
        raise ToolTimeout(f"Tool timed out after {timeout_s:g}s.") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
