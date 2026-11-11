"""SPA home ``deviceTile`` parameter discovery (#478)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.api.modules import DeviceMenuRef
from pybragerone.models.catalog import AssetIndex, AssetRef, LiveAssetsCatalog
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import AssetsProtocol, ParamResolver

_TILE_CHUNK = b"""
import{l as _0x1f8d48}from'./index-1TABHy-0.js';
const PUMP_STATUS={'parameters':{
  a:{'parameter':_0x1f8d48('STATUS_POMPY_CIEPLA_STATUS')},
  b:{'parameter':_0x1f8d48('URUCHOMIENIE_POMPY_CIEPLA')},
  c:{'parameter':_0x1f8d48('PARAM_P30_4')}
}};
const CIRCUIT_CO0_TILE={'parameters':{
  r:{'parameter':_0x1f8d48('PARAM_P30_5')},
  w:{'parameter':_0x1f8d48('ZADANA_TEMP_CO0_WRITE')}
}};
const CIRCUIT_CO1_TILE={'parameters':{
  r:{'parameter':_0x1f8d48('PARAM_P30_8')},
  w:{'parameter':loadParameter('ZADANA_TEMP_CO1_WRITE')}
}};
const NOISE=_0x1f8d48('DISPLAY_PARAMETER_LEVEL_MAX');
export{tilesGroup};
"""

_CAPTURED_TILE = Path(__file__).resolve().parent / "assets" / "tiles" / "0-C-o8CJ8v.js"


def test_extract_tile_parameter_tokens_keeps_catalog_like_names() -> None:
    """Tile helper calls yield PARAM/STATUS/URUCHOMIENIE/ZADANA tokens, not DISPLAY_*."""
    tokens = LiveAssetsCatalog._extract_tile_parameter_tokens_from_js(_TILE_CHUNK)
    assert "PARAM_P30_5" in tokens
    assert "PARAM_P30_8" in tokens
    assert "URUCHOMIENIE_POMPY_CIEPLA" in tokens
    assert "ZADANA_TEMP_CO0_WRITE" in tokens
    assert "ZADANA_TEMP_CO1_WRITE" in tokens
    assert "STATUS_POMPY_CIEPLA_STATUS" in tokens
    assert "DISPLAY_PARAMETER_LEVEL_MAX" not in tokens


def test_tile_map_populated_from_index() -> None:
    """Index parsing maps deviceTile/manuf/dev.ts import stems."""
    catalog = LiveAssetsCatalog(AsyncMock())
    index_code = b"""
    {"../../config/router/deviceTile/0/0.ts":()=>d(()=>import("./0-C-o8CJ8v.js"),true),
     "../../config/router/deviceTile/153/1211.ts":()=>d(()=>import("./1211-CrKFnoNa.js"),true)}
    """
    idx = catalog._build_asset_index_from_index_js("https://one.brager.pl/assets/index-x.js", index_code)
    assert idx.tile_map[(0, 0)] == "0-C-o8CJ8v"
    assert idx.tile_map[(153, 1211)] == "1211-CrKFnoNa"


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_default_chunk() -> None:
    """Missing/empty devices load the default deviceTile/0/0 chunk."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=_TILE_CHUNK)
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "0-C-o8CJ8v", (153, 1211): "1211-CrKFnoNa"},
        assets_by_basename={
            "0": [AssetRef(url="https://cdn/0-C-o8CJ8v.js", base="0", hash="C-o8CJ8v")],
        },
        index_bytes=b"loaded",
    )
    tokens = await catalog.discover_device_tile_parameter_tokens(devices=None)
    assert "PARAM_P30_5" in tokens
    assert "URUCHOMIENIE_POMPY_CIEPLA" in tokens
    api.get_bytes.assert_awaited_once_with("https://cdn/0-C-o8CJ8v.js")


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_prefers_device_specific() -> None:
    """When a device has its own tile chunk, that stem is fetched instead of 0/0."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=_TILE_CHUNK)
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "0-C-o8CJ8v", (153, 1211): "1211-CrKFnoNa"},
        assets_by_basename={
            "0": [AssetRef(url="https://cdn/0-C-o8CJ8v.js", base="0", hash="C-o8CJ8v")],
            "1211": [AssetRef(url="https://cdn/1211-CrKFnoNa.js", base="1211", hash="CrKFnoNa")],
        },
        index_bytes=b"loaded",
    )
    tokens = await catalog.discover_device_tile_parameter_tokens(
        devices=[DeviceMenuRef(manuf_code=153, dev_code=1211, fw="1.0.0")]
    )
    assert "PARAM_P30_5" in tokens
    api.get_bytes.assert_awaited_once_with("https://cdn/1211-CrKFnoNa.js")


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_empty_index() -> None:
    """Loaded index without tile_map yields an empty set without fetching."""
    api = AsyncMock()
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(index_bytes=b"loaded", assets_by_basename={"dummy": []})
    assert await catalog.discover_device_tile_parameter_tokens() == set()
    api.get_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_via_resolver() -> None:
    """Resolver forwards catalog discovery and tolerates missing/non-set results."""
    assert await AssetsProtocol.discover_device_tile_parameter_tokens(cast(AssetsProtocol, object())) == set()

    store = ParamStore()
    bare = ParamResolver(store=store, assets=SimpleNamespace())
    assert await bare.discover_device_tile_parameter_tokens() == set()

    bad = ParamResolver(
        store=store,
        assets=SimpleNamespace(discover_device_tile_parameter_tokens=AsyncMock(return_value=["PARAM_P30_5"])),
    )
    assert await bad.discover_device_tile_parameter_tokens() == set()

    async def _with_devices(*, devices: object = None) -> set[object]:
        assert devices is not None
        return {"PARAM_P30_5", 12, "URUCHOMIENIE_POMPY_CIEPLA"}

    good = ParamResolver(
        store=store,
        assets=SimpleNamespace(discover_device_tile_parameter_tokens=_with_devices),
    )
    assert await good.discover_device_tile_parameter_tokens(devices=[DeviceMenuRef(manuf_code=0, dev_code=0, fw="0.0.0")]) == {
        "PARAM_P30_5",
        "URUCHOMIENIE_POMPY_CIEPLA",
    }


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_captured_asset() -> None:
    """Optional local dump under tests/assets/tiles must include HP dashboard symbols."""
    if not _CAPTURED_TILE.is_file():
        pytest.skip("captured deviceTile dump not present")
    tokens = LiveAssetsCatalog._extract_tile_parameter_tokens_from_js(_CAPTURED_TILE.read_bytes())
    assert "PARAM_P30_5" in tokens
    assert "PARAM_P30_8" in tokens
    assert "URUCHOMIENIE_POMPY_CIEPLA" in tokens


def test_tile_map_cleared_when_device_tile_regex_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regex deviceTile parse failures reset tile_map."""
    catalog = LiveAssetsCatalog(AsyncMock())
    real_compile = __import__("re").compile
    state = {"n": 0}

    def _compile(pattern: str, flags: int = 0) -> object:
        text = str(pattern)
        if "deviceTile/" in text:
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("forced deviceTile parse failure")
        return real_compile(pattern, flags)

    monkeypatch.setattr("pybragerone.models.catalog.re.compile", _compile)
    idx = catalog._build_asset_index_from_index_js(
        "https://one.brager.pl/assets/index-x.js",
        b'{"../../config/router/deviceTile/0/0.ts":()=>d(()=>import("./0-x.js"))}',
    )
    assert idx.tile_map == {}


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_unloaded_index() -> None:
    """Completely empty index returns empty without network after ensure no-op."""
    api = AsyncMock()
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex()

    async def _noop() -> None:
        return None

    catalog._ensure_index_loaded = _noop  # type: ignore[method-assign]
    assert await catalog.discover_device_tile_parameter_tokens() == set()
    api.get_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_unknown_device_falls_back() -> None:
    """Devices without a tile mapping still use the default 0/0 chunk."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=_TILE_CHUNK)
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "0-C-o8CJ8v"},
        assets_by_basename={
            "0": [AssetRef(url="https://cdn/0-C-o8CJ8v.js", base="0", hash="C-o8CJ8v")],
        },
        index_bytes=b"loaded",
    )
    tokens = await catalog.discover_device_tile_parameter_tokens(
        devices=[DeviceMenuRef(manuf_code=999, dev_code=999, fw="0.0.0")]
    )
    assert "PARAM_P30_5" in tokens
    api.get_bytes.assert_awaited_once_with("https://cdn/0-C-o8CJ8v.js")


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_dedupes_stems() -> None:
    """Duplicate device refs sharing one tile stem fetch once."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=_TILE_CHUNK)
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(153, 1211): "1211-CrKFnoNa"},
        assets_by_basename={
            "1211": [AssetRef(url="https://cdn/1211-CrKFnoNa.js", base="1211", hash="CrKFnoNa")],
        },
        index_bytes=b"loaded",
    )
    refs = [
        DeviceMenuRef(manuf_code=153, dev_code=1211, fw="1.0.0"),
        DeviceMenuRef(manuf_code=153, dev_code=1211, fw="2.0.0"),
    ]
    tokens = await catalog.discover_device_tile_parameter_tokens(devices=refs)
    assert "URUCHOMIENIE_POMPY_CIEPLA" in tokens
    api.get_bytes.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_basename_fallback() -> None:
    """When full-name lookup misses, basename key still resolves the asset."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=_TILE_CHUNK)
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "tile-stem"},
        assets_by_basename={
            "tile-stem": [AssetRef(url="https://cdn/tile-stem.js", base="tile-stem", hash="x")],
        },
        index_bytes=b"loaded",
    )
    tokens = await catalog.discover_device_tile_parameter_tokens()
    assert "PARAM_P30_5" in tokens
    api.get_bytes.assert_awaited_once_with("https://cdn/tile-stem.js")


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_missing_asset() -> None:
    """Mapped stem with no asset entry is skipped."""
    api = AsyncMock()
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "missing-stem"},
        assets_by_basename={"other": []},
        index_bytes=b"loaded",
    )
    assert await catalog.discover_device_tile_parameter_tokens() == set()
    api.get_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_fetch_failure() -> None:
    """Transient tile fetch failures skip that stem."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(side_effect=RuntimeError("cdn down"))
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "0-C-o8CJ8v"},
        assets_by_basename={
            "0": [AssetRef(url="https://cdn/0-C-o8CJ8v.js", base="0", hash="C-o8CJ8v")],
        },
        index_bytes=b"loaded",
    )
    assert await catalog.discover_device_tile_parameter_tokens() == set()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_generation_mismatch() -> None:
    """Index refresh mid-fetch abandons partial tile tokens."""
    api = AsyncMock()
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "0-C-o8CJ8v"},
        assets_by_basename={
            "0": [AssetRef(url="https://cdn/0-C-o8CJ8v.js", base="0", hash="C-o8CJ8v")],
        },
        index_bytes=b"loaded",
    )
    catalog._index_generation = 1

    async def _bump(_url: str) -> bytes:
        catalog._index_generation = 2
        return _TILE_CHUNK

    api.get_bytes = AsyncMock(side_effect=_bump)
    assert await catalog.discover_device_tile_parameter_tokens() == set()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_generation_mismatch_after_extract() -> None:
    """Generation bump after extract also returns empty."""
    api = AsyncMock()
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        tile_map={(0, 0): "0-C-o8CJ8v"},
        assets_by_basename={
            "0": [AssetRef(url="https://cdn/0-C-o8CJ8v.js", base="0", hash="C-o8CJ8v")],
        },
        index_bytes=b"loaded",
    )
    catalog._index_generation = 1
    real_extract = LiveAssetsCatalog._extract_tile_parameter_tokens_from_js

    def _extract(code: bytes) -> set[str]:
        catalog._index_generation = 2
        return real_extract(code)

    api.get_bytes = AsyncMock(return_value=_TILE_CHUNK)
    catalog._extract_tile_parameter_tokens_from_js = _extract  # type: ignore[method-assign]
    assert await catalog.discover_device_tile_parameter_tokens() == set()


@pytest.mark.asyncio
async def test_discover_device_tile_parameter_tokens_resolver_signature_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolver tolerates no-devices callables and broken signatures."""
    store = ParamStore()

    async def _no_devices() -> set[str]:
        return {"PARAM_P30_5"}

    no_devices = ParamResolver(
        store=store,
        assets=SimpleNamespace(discover_device_tile_parameter_tokens=_no_devices),
    )
    assert await no_devices.discover_device_tile_parameter_tokens() == {"PARAM_P30_5"}

    async def _accepts_devices(*, devices: object = None) -> set[str]:
        _ = devices
        return {"PARAM_P30_8"}

    real_signature = __import__("inspect").signature

    def _signature(obj: object) -> object:
        if obj is _accepts_devices:
            raise ValueError("forced signature failure")
        return real_signature(obj)

    monkeypatch.setattr("pybragerone.models.param_resolver.inspect.signature", _signature)
    broken = ParamResolver(
        store=store,
        assets=SimpleNamespace(discover_device_tile_parameter_tokens=_accepts_devices),
    )
    # Signature failure falls back to calling without devices=.
    assert await broken.discover_device_tile_parameter_tokens(devices=[DeviceMenuRef(manuf_code=0, dev_code=0, fw="0.0.0")]) == {
        "PARAM_P30_8"
    }
