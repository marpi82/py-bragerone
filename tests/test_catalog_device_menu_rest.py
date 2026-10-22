"""Device-specific REST menus + SPA extends (#438)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pybragerone.api.client import ApiError
from pybragerone.models.api.modules import DeviceMenuRef
from pybragerone.models.catalog import AssetRef, LiveAssetsCatalog, _parse_extends_ref
from pybragerone.models.menu import MenuResult


def _route(path: str, *, name: str | None = None) -> dict[str, object]:
    return {
        "path": path,
        "name": name or f"modules.menu.{path}",
        "meta": {"displayName": f"menu.{path.upper()}", "displayDropdown": True},
    }


def test_parse_extends_ref() -> None:
    """SPA extends tokens accept colon or slash separators."""
    assert _parse_extends_ref("153:1211") == (153, "1211")
    assert _parse_extends_ref("153/1211") == (153, "1211")
    assert _parse_extends_ref("bad") is None


@pytest.mark.asyncio
async def test_device_specific_404_falls_back_to_default() -> None:
    """Device menu 404 then default 200 — both URLs tried (#438 / #437)."""
    mock_api = AsyncMock()

    async def _get_menu(manuf: int, dev: int, fw: str = "0.0.0") -> dict[str, object]:
        if (manuf, dev, fw) == (67, 7, "2.08"):
            raise ApiError(404, {"message": "missing"})
        if (manuf, dev, fw) == (0, 0, "0.0.0"):
            return {
                "priority": 0,
                "extends": [],
                "standalone": False,
                "deviceMenu": [_route("dhw")],
            }
        raise AssertionError(f"unexpected menu fetch {manuf}/{dev}/{fw}")

    mock_api.get_devices_menu = AsyncMock(side_effect=_get_menu)
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]

    devices = [DeviceMenuRef(manuf_code=67, dev_code=7, fw="2.08")]
    menu = await catalog.get_module_menu(device_menu=0, devices=devices)
    assert isinstance(menu, MenuResult)
    assert [r.path for r in menu.routes] == ["dhw"]
    assert mock_api.get_devices_menu.await_count == 2
    mock_api.get_devices_menu.assert_any_await(67, 7, "2.08")
    mock_api.get_devices_menu.assert_any_await(0, 0, "0.0.0")


@pytest.mark.asyncio
async def test_standalone_device_menu_skips_default() -> None:
    """Standalone device menu wins — default 0/0/0.0.0 is not fetched."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 10,
            "extends": [],
            "standalone": True,
            "deviceMenu": [_route("boiler")],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]

    menu = await catalog.get_module_menu(
        device_menu=0,
        devices=[DeviceMenuRef(manuf_code=1, dev_code=2, fw="1.0")],
    )
    assert [r.path for r in menu.routes] == ["boiler"]
    mock_api.get_devices_menu.assert_awaited_once_with(1, 2, "1.0")


@pytest.mark.asyncio
async def test_path_merge_prefers_higher_priority() -> None:
    """Overlapping paths keep the higher-priority REST layer."""
    mock_api = AsyncMock()

    async def _get_menu(manuf: int, dev: int, fw: str = "0.0.0") -> dict[str, object]:
        if manuf == 1:
            return {
                "priority": 50,
                "extends": [],
                "standalone": False,
                "deviceMenu": [_route("shared", name="device.shared"), _route("only-device")],
            }
        return {
            "priority": 10,
            "extends": [],
            "standalone": False,
            "deviceMenu": [_route("shared", name="default.shared"), _route("only-default")],
        }

    mock_api.get_devices_menu = AsyncMock(side_effect=_get_menu)
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]

    menu = await catalog.get_module_menu(
        device_menu=0,
        devices=[DeviceMenuRef(manuf_code=1, dev_code=1, fw="0.0.0")],
    )
    by_path = {r.path: r.name for r in menu.routes}
    assert by_path["shared"] == "device.shared"
    assert "only-device" in by_path
    assert "only-default" in by_path


@pytest.mark.asyncio
async def test_extends_loads_vite_chunk_routes() -> None:
    """REST extends refs pull matching index Vite menu chunks."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": ["153:1211"],
            "standalone": False,
            "deviceMenu": [_route("base")],
        }
    )
    # Minimal export that _parse_menu_routes can read as a route list.
    chunk_js = b"""
    export default [{
      path: "extended",
      name: "modules.menu.extended",
      meta: { displayName: "menu.EXTENDED", displayDropdown: true }
    }];
    """
    mock_api.get_bytes = AsyncMock(return_value=chunk_js)

    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    catalog._idx.menu_variant_map[(153, "1211")] = "1211-AbCdEfGh"
    catalog._idx.assets_by_basename["1211"] = [
        AssetRef(url="https://one.brager.pl/assets/1211-AbCdEfGh.js", base="1211", hash="AbCdEfGh")
    ]

    menu = await catalog.get_module_menu(device_menu=0)
    paths = {r.path for r in menu.routes}
    assert "base" in paths
    assert "extended" in paths
    mock_api.get_bytes.assert_awaited_once_with("https://one.brager.pl/assets/1211-AbCdEfGh.js")


@pytest.mark.asyncio
async def test_extends_miss_does_not_fail_menu(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown extends refs are skipped; REST routes still load."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": ["999:missing"],
            "standalone": False,
            "deviceMenu": [_route("ok")],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]

    with caplog.at_level("WARNING"):
        menu = await catalog.get_module_menu(device_menu=0)
    assert [r.path for r in menu.routes] == ["ok"]
    assert "999:missing" in caplog.text
    mock_api.get_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_no_devices_still_uses_default_only() -> None:
    """Without devices refs, behaviour matches #437 (default REST only)."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": [],
            "standalone": False,
            "deviceMenu": [_route("dhw")],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]

    menu = await catalog.get_module_menu(device_menu=0)
    assert [r.path for r in menu.routes] == ["dhw"]
    mock_api.get_devices_menu.assert_awaited_once_with(0, 0, "0.0.0")


def test_menu_variant_map_populated_from_index() -> None:
    """Index parsing keeps every deviceMenu/N/variant candidate for extends."""
    catalog = LiveAssetsCatalog(AsyncMock())
    index_code = b"""
    {"../config/router/deviceMenu/153/0.ts":()=>d(()=>import("./0-AaaAaaAa.js"),__vite__mapDeps([0])),
     "../config/router/deviceMenu/153/1211.ts":()=>d(()=>import("./1211-BbBbBbBb.js"),__vite__mapDeps([1]))}
    """
    idx = catalog._build_asset_index_from_index_js("https://one.brager.pl/assets/index-x.js", index_code)
    assert idx.menu_map[153] == "0-AaaAaaAa"
    assert idx.menu_variant_map[(153, "0")] == "0-AaaAaaAa"
    assert idx.menu_variant_map[(153, "1211")] == "1211-BbBbBbBb"
    catalog._idx = idx
    resolved = catalog.resolve_extended_menu_asset("153:1211")
    assert resolved is not None
    assert resolved.hash == "BbBbBbBb"
    assert catalog.resolve_extended_menu_asset("999:nope") is None
