"""Tests for CLI helpers that consume ``get_modules``."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from pybragerone.api.client import ApiError
from pybragerone.cli import _build_watch_groups, _prompt_select_modules


class _FakeApi:
    """API stub that can raise ``ApiError`` from ``get_modules``."""

    def __init__(self, *, error: ApiError | None = None, rows: list[Any] | None = None) -> None:
        """Store the configured response or error."""
        self._error = error
        self._rows = list(rows or [])

    async def get_modules(self, object_id: int) -> list[Any]:
        """Return configured rows or raise the configured error."""
        _ = object_id
        if self._error is not None:
            raise self._error
        return list(self._rows)


@pytest.mark.asyncio
async def test_prompt_select_modules_handles_api_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Non-200 ``get_modules`` must not crash interactive module selection."""
    api = _FakeApi(error=ApiError(401, {"message": "unauthorized"}, {}))
    selected = await _prompt_select_modules(cast(Any, api), object_id=9)
    assert selected == []
    out = capsys.readouterr().out
    assert "Failed to list modules for object 9" in out
    assert "HTTP 401" in out


@pytest.mark.asyncio
async def test_build_watch_groups_handles_api_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Watch-group bootstrap degrades to empty panels when modules cannot be listed."""

    class _Resolver:
        async def build_panel_groups(self, **kwargs: object) -> dict[str, list[str]]:
            _ = kwargs
            raise AssertionError("resolver must not be called after get_modules failure")

    api = _FakeApi(error=ApiError(500, {"message": "boom"}, {}))
    groups = await _build_watch_groups(
        api=cast(Any, api),
        resolver=cast(Any, _Resolver()),
        object_id=3,
        module_ids=["M1"],
        all_panels=False,
    )
    assert groups == {"Boiler": [], "DHW": [], "Valve 1": []}
    out = capsys.readouterr().out
    assert "Failed to load modules for watch groups" in out
    assert "HTTP 500" in out


@pytest.mark.asyncio
async def test_prompt_select_modules_empty_listing(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty listing prints a clear message and returns no selection."""
    api = _FakeApi(rows=[])
    assert await _prompt_select_modules(cast(Any, api), object_id=1) == []
    assert "No modules" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_build_watch_groups_missing_selected_module() -> None:
    """Unknown module ids fall back to empty default panels."""

    class _Resolver:
        async def build_panel_groups(self, **kwargs: object) -> dict[str, list[str]]:
            _ = kwargs
            raise AssertionError("resolver must not be called for missing module")

    api = _FakeApi(rows=[SimpleNamespace(devid="OTHER", deviceMenu=1, permissions=[])])
    groups = await _build_watch_groups(
        api=cast(Any, api),
        resolver=cast(Any, _Resolver()),
        object_id=1,
        module_ids=["M1"],
        all_panels=False,
    )
    assert groups == {"Boiler": [], "DHW": [], "Valve 1": []}
