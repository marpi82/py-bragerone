"""Tests for library task-spawn and JSON helper utilities."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from pybragerone.utils import bg_tasks, json_preview, log_json_payload, save_json_payload, spawn, summarize_top_level


class _NotJson:
    """Object that cannot be serialized by json.dumps."""

    def __str__(self) -> str:
        """Return a stable fallback string."""
        return "not-json"


async def _drain_bg_tasks() -> None:
    """Yield until spawn() callbacks have removed finished tasks."""
    for _ in range(50):
        if not bg_tasks:
            return
        await asyncio.sleep(0)
    remaining = list(bg_tasks)
    for task in remaining:
        task.cancel()
    raise AssertionError(f"background tasks did not finish: {remaining!r}")


def test_json_preview_compacts_truncates_and_falls_back() -> None:
    """Preview is compact JSON, truncates long output, and stringifies bad values."""
    assert json_preview({"key": "value", "n": 1}) == '{"key":"value","n":1}'
    truncated = json_preview({"x": "a" * 50}, maxlen=10)
    assert truncated.endswith("…")
    assert truncated.startswith("{")
    assert json_preview(_NotJson()) == "not-json"


def test_log_and_save_json_payload(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Debug logger and file writer accept ordinary JSON-like payloads."""
    logger = logging.getLogger("test.utils.json")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        log_json_payload(logger, "prime", {"ok": True})
    assert "prime" in caplog.text
    assert "ok" in caplog.text

    path = save_json_payload({"a": 1}, tmp_path / "payload.json")
    assert path.read_text(encoding="utf-8") == '{\n  "a": 1\n}'


def test_summarize_top_level_dict_list_and_scalar() -> None:
    """Summary reports type, truncated keys, list length, and scalar type name."""
    wide = {f"k{i}": i for i in range(12)}
    summary = summarize_top_level(wide)
    assert summary["type"] == "dict"
    assert summary["len"] == 12
    assert summary["keys"] == [f"k{i}" for i in range(10)]

    assert summarize_top_level([1, 2]) == {"type": "list", "len": 2, "first_type": "int"}
    assert summarize_top_level([]) == {"type": "list", "len": 0, "first_type": None}
    assert summarize_top_level("hello") == {"type": "str"}


async def test_spawn_success_failure_and_cancel(caplog: pytest.LogCaptureFixture) -> None:
    """spawn() tracks tasks, logs unexpected errors, and forgets cancelled work."""
    log = logging.getLogger("test.utils.spawn")

    async def ok() -> None:
        return None

    spawn(ok(), "ok", log)
    await _drain_bg_tasks()

    async def boom() -> None:
        raise RuntimeError("spawn-boom")

    with caplog.at_level(logging.ERROR, logger=log.name):
        spawn(boom(), "boom", log)
        await _drain_bg_tasks()
    assert "Background task boom failed" in caplog.text

    async def parked() -> None:
        await asyncio.Event().wait()

    spawn(parked(), "parked", log)
    assert bg_tasks
    next(iter(bg_tasks)).cancel()
    await _drain_bg_tasks()
