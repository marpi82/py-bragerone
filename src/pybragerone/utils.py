"""Library utilities."""

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
    """Spawn a background task and track it in bg_tasks set."""
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
    """Jednolinijkowy podgląd JSON (ucięty do maxlen, bez wcięć).

    Nie wybucha na prymitywach.
    """
    try:
        s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        s = str(obj)
    if len(s) > maxlen:
        s = s[:maxlen] + "…"
    return s


def log_json_payload(logger: Logger, tag: str, payload: Any, *, maxlen: int = 2000) -> None:
    """Log a single-line preview of JSON payload."""
    with suppress(Exception):
        logger.debug("%s → %s", tag, json_preview(payload, maxlen=maxlen))


def save_json_payload(payload: Any, path: str | Path) -> Path:
    """Save JSON to file (UTF-8), return path."""
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
