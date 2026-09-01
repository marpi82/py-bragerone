"""Tests for LiveAssetsCatalog.fetch_alarm_name_source."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from pybragerone.api import BragerOneApiClient
from pybragerone.models.catalog import AssetIndex, AssetRef, LiveAssetsCatalog


class _FakeApi:
    def __init__(self, *, payload: Any = b"alarms-chunk", error: bool = False) -> None:
        self._payload = payload
        self._error = error
        self.urls: list[str] = []

    async def get_bytes(self, url: str) -> Any:
        self.urls.append(url)
        if self._error:
            raise RuntimeError("fetch failed")
        return self._payload


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_uses_find_basename() -> None:
    """Primary lookup uses exact Alarms/alarms basenames."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=b"enum-source")))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "alarms-abc123": [AssetRef(url="https://cdn/assets/alarms-abc123.js", base="alarms", hash="abc123")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == b"enum-source"
    fake_api = cast(_FakeApi, catalog._api)
    assert fake_api.urls == ["https://cdn/assets/alarms-abc123.js"]


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_scans_assets_by_basename() -> None:
    """Fallback scans assets whose basename starts with alarms."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload="text-source")))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "AlarmsPanel-x": [AssetRef(url="https://cdn/assets/AlarmsPanel-x.js", base="AlarmsPanel", hash="x")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == "text-source"


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_returns_none_without_index() -> None:
    """Missing index yields None without calling get_bytes."""
    api = _FakeApi()
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, api))
    catalog._idx = AssetIndex()
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() is None
    assert api.urls == []


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_returns_none_on_fetch_failure() -> None:
    """Network failures are swallowed and return None."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(error=True)))
    catalog._idx = AssetIndex(assets_by_basename={"alarms-h": [AssetRef(url="https://cdn/a.js", base="alarms", hash="h")]})
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() is None


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_accepts_bytearray_payload() -> None:
    """Bytearray payloads are normalized to bytes."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=bytearray(b"buf"))))
    catalog._idx = AssetIndex(assets_by_basename={"alarms-h": [AssetRef(url="https://cdn/a.js", base="alarms", hash="h")]})
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() == b"buf"


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_rejects_unsupported_payload_type() -> None:
    """Unsupported payload types return None."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload={"not": "bytes"})))
    catalog._idx = AssetIndex(assets_by_basename={"alarms-h": [AssetRef(url="https://cdn/a.js", base="alarms", hash="h")]})
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() is None


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_prefers_exact_alarms_basename() -> None:
    """Exact ``Alarms`` / ``alarms`` index keys win before the scan fallback."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=b"exact")))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "Alarms": [AssetRef(url="https://cdn/assets/Alarms.js", base="Alarms", hash="h1")],
            "AlarmsPanel-x": [AssetRef(url="https://cdn/assets/panel.js", base="AlarmsPanel", hash="x")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == b"exact"
    fake_api = cast(_FakeApi, catalog._api)
    assert fake_api.urls == ["https://cdn/assets/Alarms.js"]


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_scan_skips_invalid_basenames_and_empty_refs() -> None:
    """Basename scan ignores non-alarms keys and empty ref lists."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=b"chunk")))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "menu.js": [AssetRef(url="https://cdn/menu.js", base="menu", hash="m")],
            "alarmsEmpty": [],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() is None
