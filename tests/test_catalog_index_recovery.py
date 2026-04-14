"""Tests for resilient index discovery in LiveAssetsCatalog."""

from __future__ import annotations

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog


class _FakeApi:
    """Tiny fake API exposing one_base and get_bytes()."""

    def __init__(self, mapping: dict[str, bytes], failures: set[str] | None = None) -> None:
        """Initialize fake API with deterministic URL payloads."""
        self.one_base = "https://one.brager.pl"
        self._mapping = mapping
        self._failures = failures or set()
        self.requests: list[str] = []

    async def get_bytes(self, url: str) -> bytes:
        """Return bytes for URL or raise for configured failures."""
        self.requests.append(url)
        if url in self._failures:
            raise RuntimeError(f"boom:{url}")
        if url in self._mapping:
            return self._mapping[url]
        raise RuntimeError(f"missing:{url}")


@pytest.mark.asyncio
async def test_auto_discover_uses_homepage_index_hint() -> None:
    """Discovery should parse index asset URL from homepage HTML."""
    index_url = "https://one.brager.pl/assets/index-NEW123.js"
    api = _FakeApi(
        {
            "https://one.brager.pl/": b'<script src="/assets/index-NEW123.js"></script>',
            index_url: b'const x=()=>import("./module.menu-ABC.js");',
        }
    )
    catalog = LiveAssetsCatalog(api)  # type: ignore[arg-type]

    await catalog._auto_discover_and_load_index()

    assert index_url in api.requests
    assert catalog._idx.index_bytes != b""


@pytest.mark.asyncio
async def test_refresh_index_recovers_after_hashed_index_failure() -> None:
    """refresh_index should rediscover index when hashed URL fails."""
    stale_index = "https://one.brager.pl/assets/index-OLD999.js"
    fresh_index = "https://one.brager.pl/assets/index-NEW123.js"
    api = _FakeApi(
        {
            "https://one.brager.pl/": b'<script src="/assets/index-NEW123.js"></script>',
            fresh_index: b'const x=()=>import("./module.menu-ABC.js");',
        },
        failures={stale_index},
    )
    catalog = LiveAssetsCatalog(api)  # type: ignore[arg-type]

    await catalog.refresh_index(stale_index)

    assert stale_index in api.requests
    assert fresh_index in api.requests
    assert catalog._idx.index_bytes != b""


@pytest.mark.asyncio
async def test_index_parser_supports_device_menu_numeric_route_chunks() -> None:
    """Index parser should map deviceMenu routes using numeric ts/js chunk names."""
    index_url = "https://one.brager.pl/assets/index-NEW123.js"
    api = _FakeApi(
        {
            index_url: (b'Object.assign({"/src/config/router/deviceMenu/0/0.ts":()=>f(()=>import("./0-r9AwvEAY.js"),[])})'),
        }
    )
    catalog = LiveAssetsCatalog(api)  # type: ignore[arg-type]

    await catalog.refresh_index(index_url, allow_recover=False)

    assert catalog._idx.menu_map.get(0) == "0-r9AwvEAY"
