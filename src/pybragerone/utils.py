"""Library utilities.

This module provides utility functions for the pybragerone library, organized into categories:

**Task Management:**
    - :func:`spawn` - Background task spawning with error handling

**JSON Utilities:**
    - :func:`json_preview` - Single-line JSON preview with length limits
    - :func:`log_json_payload` - Debug logging for JSON payloads
    - :func:`save_json_payload` - Save JSON to UTF-8 files
    - :func:`summarize_top_level` - Quick structural summary of JSON objects
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from contextlib import suppress
from logging import Logger
from pathlib import Path
from typing import Any

# EventBus consumer (ParamStore)
bg_tasks: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], name: str, log: Logger) -> None:
    """Spawn a background task and track it in bg_tasks set.

    Args:
        coro: The coroutine to execute as a background task.
        name: Descriptive name for the task (used in logging).
        log: Logger instance for error reporting.

    Note:
        Tasks are automatically cleaned up on completion or cancellation.
        Exceptions are logged but don't crash the application.
    """
    t = asyncio.create_task(coro, name=name)
    bg_tasks.add(t)

    def _done(task: asyncio.Task[Any]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Background task %s failed", name)
        finally:
            bg_tasks.discard(task)

    t.add_done_callback(_done)


def json_preview(obj: Any, *, maxlen: int = 2000) -> str:
    """Return a single-line JSON preview trimmed to maxlen with no indent.

    Converts any Python object to a compact JSON string representation,
    truncating if necessary. Safe for any input type.

    Args:
        obj: Any Python object to preview.
        maxlen: Maximum length of the returned string (default: 2000).

    Returns:
        A single-line JSON string, possibly truncated with "…".

    Example:
        >>> json_preview({"key": "value", "numbers": [1, 2, 3]})
        '{"key":"value","numbers":[1,2,3]}'
    """
    try:
        s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        s = str(obj)
    if len(s) > maxlen:
        s = s[:maxlen] + "…"
    return s


def log_json_payload(logger: Logger, tag: str, payload: Any, *, maxlen: int = 2000) -> None:
    """Log a one-line JSON payload preview at the DEBUG level."""
    with suppress(Exception):
        logger.debug("%s → %s", tag, json_preview(payload, maxlen=maxlen))


def save_json_payload(payload: Any, path: str | Path) -> Path:
    """Write the JSON payload to a UTF-8 file and return the path."""
    p = Path(path)
    p.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return p


def summarize_top_level(obj: Any) -> dict[str, Any]:
    """Return a quick summary of a top-level JSON-like object.

    This function inspects the provided object and produces a simple overview.

    - For dictionaries: lists the first ten top-level keys and counts elements.
    - For lists: reports the number of elements and the type of the first item.
    - For scalar values: records the concrete type name.

    Args:
        obj: The JSON-like object to summarize. Typically a dict, list,
            or scalar (str, int, float, bool).

    Returns:
        A dictionary describing the top-level structure.

    Example:
        >>> summarize_top_level({"a": 1, "b": 2})
        {'type': 'dict', 'keys': ['a', 'b'], 'len': 2}
        >>> summarize_top_level([1, 2, 3])
        {'type': 'list', 'len': 3, 'first_type': 'int'}
        >>> summarize_top_level("hello")
        {'type': 'str'}
    """
    if isinstance(obj, dict):
        return {
            "type": "dict",
            "keys": list(obj.keys())[:10],
            "len": len(obj),
        }
    if isinstance(obj, list):
        return {
            "type": "list",
            "len": len(obj),
            "first_type": type(obj[0]).__name__ if obj else None,
        }
    return {"type": type(obj).__name__}
