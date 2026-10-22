"""Tests for LiveAssetsCatalog.fetch_alarm_name_source."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from pybragerone.api import BragerOneApiClient
from pybragerone.models.catalog import AssetIndex, AssetRef, LiveAssetsCatalog

# Minimal ``AlarmName``-like payloads for multi-chunk selection (post-1.04 SPA).
_ENUM_CHUNK = b"obj['ERROR_BRAK_PALIWA']=0x26,obj['ERROR_PELLET_NIEUDANE_ROZPALANIE']=54"
_PAGE_CHUNK = b"import{A as x}from'./Alarms-enum.js';export{default}"


class _FakeApi:
    def __init__(
        self,
        *,
        payload: Any = b"alarms-chunk",
        error: bool = False,
        by_url: dict[str, Any] | None = None,
    ) -> None:
        self._payload = payload
        self._error = error
        self._by_url = by_url or {}
        self.urls: list[str] = []

    async def get_bytes(self, url: str) -> Any:
        self.urls.append(url)
        if self._error:
            raise RuntimeError("fetch failed")
        if url in self._by_url:
            return self._by_url[url]
        return self._payload


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_uses_find_basename() -> None:
    """Primary lookup uses exact ``Alarms`` / ``alarms`` basenames."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=_ENUM_CHUNK)))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "alarms": [AssetRef(url="https://cdn/assets/alarms-abc123.js", base="alarms", hash="abc123")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == _ENUM_CHUNK
    fake_api = cast(_FakeApi, catalog._api)
    assert fake_api.urls == ["https://cdn/assets/alarms-abc123.js"]


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_scans_assets_by_basename() -> None:
    """Fallback scans assets whose basename starts with alarms."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=_ENUM_CHUNK)))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "AlarmsPanel-x": [AssetRef(url="https://cdn/assets/AlarmsPanel-x.js", base="AlarmsPanel", hash="x")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == _ENUM_CHUNK


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
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=bytearray(_ENUM_CHUNK))))
    catalog._idx = AssetIndex(assets_by_basename={"alarms-h": [AssetRef(url="https://cdn/a.js", base="alarms", hash="h")]})
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() == _ENUM_CHUNK


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
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=_ENUM_CHUNK)))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "Alarms": [AssetRef(url="https://cdn/assets/Alarms.js", base="Alarms", hash="h1")],
            "AlarmsPanel-x": [AssetRef(url="https://cdn/assets/panel.js", base="AlarmsPanel", hash="x")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == _ENUM_CHUNK
    fake_api = cast(_FakeApi, catalog._api)
    assert fake_api.urls == ["https://cdn/assets/Alarms.js"]


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_prefers_enum_chunk_over_page() -> None:
    """When two ``Alarms-*`` hashes exist, pick the one that parses to AlarmName pairs."""
    enum_url = "https://cdn/assets/Alarms-enumHash.js"
    page_url = "https://cdn/assets/Alarms-pageHash.js"
    catalog = LiveAssetsCatalog(
        cast(
            BragerOneApiClient,
            _FakeApi(by_url={enum_url: _ENUM_CHUNK, page_url: _PAGE_CHUNK}),
        )
    )
    catalog._idx = AssetIndex(
        assets_by_basename={
            "Alarms": [
                AssetRef(url=enum_url, base="Alarms", hash="enumHash"),
                AssetRef(url=page_url, base="Alarms", hash="pageHash"),
            ],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    source = await catalog.fetch_alarm_name_source()

    assert source == _ENUM_CHUNK
    fake_api = cast(_FakeApi, catalog._api)
    assert fake_api.urls == [enum_url, page_url]


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_returns_none_when_chunks_lack_enum() -> None:
    """Vue-only Alarms chunks (no AlarmName pairs) yield None."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=_PAGE_CHUNK)))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "Alarms": [AssetRef(url="https://cdn/assets/Alarms-page.js", base="Alarms", hash="page")],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() is None


@pytest.mark.asyncio
async def test_fetch_alarm_name_source_scan_skips_invalid_basenames_and_empty_refs() -> None:
    """Basename scan ignores non-alarms keys and empty ref lists."""
    catalog = LiveAssetsCatalog(cast(BragerOneApiClient, _FakeApi(payload=_ENUM_CHUNK)))
    catalog._idx = AssetIndex(
        assets_by_basename={
            "menu.js": [AssetRef(url="https://cdn/menu.js", base="menu", hash="m")],
            "alarmsEmpty": [],
        }
    )
    catalog._ensure_index_loaded = AsyncMock()  # type: ignore[method-assign]

    assert await catalog.fetch_alarm_name_source() is None
