"""Device-specific REST menus + SPA extends (#438)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pybragerone.api.client import ApiError
from pybragerone.models.api.modules import DeviceMenuRef
from pybragerone.models.catalog import AssetRef, LiveAssetsCatalog, _parse_extends_ref
from pybragerone.models.menu import MenuResult


def _route(path: str, *, name: str | None = None) -> dict[str, Any]:
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
    assert catalog.resolve_extended_menu_asset("not-a-ref") is None


def test_menu_variant_map_cleared_when_device_menu_regex_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regex deviceMenu parse failures reset menu_variant_map (except path)."""
    catalog = LiveAssetsCatalog(AsyncMock())
    real_compile = __import__("re").compile
    state = {"n": 0}

    def _compile(pattern: str, flags: int = 0) -> Any:
        text = str(pattern)
        if "deviceMenu/(\\d+)" in text or "deviceMenu/(\\d+)/" in text:
            state["n"] += 1
            if state["n"] == 1:
                raise RuntimeError("forced deviceMenu parse failure")
        return real_compile(pattern, flags)

    monkeypatch.setattr("pybragerone.models.catalog.re.compile", _compile)
    idx = catalog._build_asset_index_from_index_js(
        "https://one.brager.pl/assets/index-x.js",
        b'{"../config/router/deviceMenu/1/0.ts":()=>d(()=>import("./0-x.js"))}',
    )
    assert idx.menu_variant_map == {}


@pytest.mark.asyncio
async def test_fetch_devices_menu_bad_priority_defaults_to_zero() -> None:
    """Non-int priority values fall back to 0."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": object(),
            "extends": "not-a-list",
            "standalone": False,
            "deviceMenu": [_route("ok"), {"path": None}, {"path": ""}, "skip"],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    routes, meta, _hint = await catalog._fetch_devices_menu_payload(0, 0, "0.0.0")
    assert meta["priority"] == 0
    assert meta["extends"] == []
    # Non-dict rows are dropped; empty/None paths remain until merge.
    assert any(r.get("path") == "ok" for r in routes)
    assert all(isinstance(r, dict) for r in routes)


def test_merge_menu_route_layers_skips_empty_paths_and_keeps_higher_second() -> None:
    """Empty paths drop; a later higher-priority layer wins the display name."""
    low: list[dict[str, Any]] = [_route("shared", name="low"), {"name": "no-path"}, {"path": ""}]
    high: list[dict[str, Any]] = [_route("shared", name="high")]
    merged = LiveAssetsCatalog._merge_menu_route_layers([(low, 1), (high, 9)])
    assert len(merged) == 1
    assert merged[0]["name"] == "high"


def test_merge_menu_route_layers_keeps_higher_when_later_is_lower() -> None:
    """A later lower-priority layer does not overwrite an earlier path name."""
    high: list[dict[str, Any]] = [_route("shared", name="high")]
    low: list[dict[str, Any]] = [_route("shared", name="low")]
    merged = LiveAssetsCatalog._merge_menu_route_layers([(high, 9), (low, 1)])
    assert len(merged) == 1
    assert merged[0]["name"] == "high"


def test_merge_menu_route_layers_unions_complementary_parameters() -> None:
    """Higher-priority write params keep lower-priority read params on the same path."""
    low: list[dict[str, Any]] = [
        {
            "path": "shared",
            "name": "low",
            "meta": {
                "parameters": {
                    "read": [{"token": "PARAM_READ"}],
                    "write": [],
                    "status": [],
                    "special": [],
                }
            },
        }
    ]
    high: list[dict[str, Any]] = [
        {
            "path": "shared",
            "name": "high",
            "meta": {
                "parameters": {
                    "read": [],
                    "write": [{"token": "PARAM_WRITE"}],
                    "status": [],
                    "special": [],
                }
            },
        }
    ]
    merged = LiveAssetsCatalog._merge_menu_route_layers([(low, 10), (high, 50)])
    assert len(merged) == 1
    assert merged[0]["name"] == "high"
    params = merged[0]["meta"]["parameters"]
    assert [e["token"] for e in params["read"]] == ["PARAM_READ"]
    assert [e["token"] for e in params["write"]] == ["PARAM_WRITE"]


def test_merge_helpers_cover_edge_identities_and_children() -> None:
    """Parameter identity helpers + top-level params/children merge branches."""
    assert LiveAssetsCatalog._param_entry_key({"token": "T"}) == "T"
    assert LiveAssetsCatalog._param_entry_key({"parameter": "P"}) == "P"
    assert LiveAssetsCatalog._param_entry_key({"other": 1}) is None
    assert LiveAssetsCatalog._param_entry_key("RAW") == "RAW"
    assert LiveAssetsCatalog._param_entry_key("") is None
    assert LiveAssetsCatalog._param_entry_key(3) is None

    assert LiveAssetsCatalog._merge_parameters_maps(None, None) is None
    assert LiveAssetsCatalog._merge_parameters_maps("x", 1) == "x"

    # Preferred duplicate token drops the fallback copy.
    merged_section = LiveAssetsCatalog._merge_parameter_section_lists(
        [{"token": "A"}, {"no": "key"}],
        [{"token": "A"}, {"token": "B"}, "C"],
    )
    assert [LiveAssetsCatalog._param_entry_key(e) for e in merged_section] == ["A", None, "B", "C"]

    low: list[dict[str, Any]] = [
        {
            "path": "parent",
            "name": "low",
            "parameters": {"read": [{"token": "TOP_READ"}], "write": []},
            "children": [{"path": "child", "name": "low-child", "meta": {"parameters": {"read": [{"token": "CHILD_READ"}]}}}],
        }
    ]
    high: list[dict[str, Any]] = [
        {
            "path": "parent",
            "name": "high",
            "parameters": {"read": [], "write": [{"token": "TOP_WRITE"}]},
            "children": [{"path": "child", "name": "high-child", "meta": {"parameters": {"write": [{"token": "CHILD_WRITE"}]}}}],
        }
    ]
    merged = LiveAssetsCatalog._merge_menu_route_layers([(low, 1), (high, 9)])
    assert merged[0]["name"] == "high"
    assert [e["token"] for e in merged[0]["parameters"]["read"]] == ["TOP_READ"]
    assert [e["token"] for e in merged[0]["parameters"]["write"]] == ["TOP_WRITE"]
    child = merged[0]["children"][0]
    assert child["name"] == "high-child"
    assert [e["token"] for e in child["meta"]["parameters"]["read"]] == ["CHILD_READ"]
    assert [e["token"] for e in child["meta"]["parameters"]["write"]] == ["CHILD_WRITE"]


def test_parse_menu_export_bad_priority_defaults_to_zero() -> None:
    """Non-int export priority falls back to 0."""
    catalog = LiveAssetsCatalog(AsyncMock())
    routes, priority = catalog._parse_menu_export(
        b"""
        export default {
          priority: "nope",
          deviceMenu: [{ path: "x", name: "n", meta: { displayName: "d", displayDropdown: true } }]
        };
        """
    )
    assert priority == 0
    assert [r["path"] for r in routes] == ["x"]


@pytest.mark.asyncio
async def test_fetch_devices_menu_none_priority_defaults_to_zero() -> None:
    """Explicit null priority becomes 0."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": None,
            "extends": [],
            "standalone": False,
            "deviceMenu": [_route("ok")],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    _routes, meta, _hint = await catalog._fetch_devices_menu_payload(0, 0, "0.0.0")
    assert meta["priority"] == 0


@pytest.mark.asyncio
async def test_extends_skips_blank_duplicates_and_fetch_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Blank/duplicate extends refs are ignored; get_bytes failures skip the chunk."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": ["", "  ", "153:1211", "153:1211"],
            "standalone": False,
            "deviceMenu": [_route("base")],
        }
    )
    mock_api.get_bytes = AsyncMock(side_effect=RuntimeError("cdn down"))
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    catalog._idx.menu_variant_map[(153, "1211")] = "1211-AbCdEfGh"
    catalog._idx.assets_by_basename["1211"] = [
        AssetRef(url="https://one.brager.pl/assets/1211-AbCdEfGh.js", base="1211", hash="AbCdEfGh")
    ]
    with caplog.at_level("WARNING"):
        menu = await catalog.get_module_menu(device_menu=0)
    assert [r.path for r in menu.routes] == ["base"]
    assert "cdn down" in caplog.text or "Extended menu fetch failed" in caplog.text
    mock_api.get_bytes.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_symbols_for_permissions_passes_devices() -> None:
    """list_symbols_for_permissions forwards devices into get_module_menu."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": [],
            "standalone": True,
            "deviceMenu": [
                {
                    "path": "dhw",
                    "name": "modules.menu.dhw",
                    "meta": {
                        "permissionModule": "DISPLAY_MENU_DHW",
                        "parameters": {
                            "read": [{"permissionModule": "DISPLAY_PARAMETER_LEVEL_1", "parameter": "PARAM_P30_2"}],
                        },
                    },
                }
            ],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    devices = [DeviceMenuRef(manuf_code=1, dev_code=2, fw="1.0")]
    tokens = await catalog.list_symbols_for_permissions(
        0,
        ["DISPLAY_MENU_DHW", "DISPLAY_PARAMETER_LEVEL_1"],
        devices=devices,
    )
    assert "PARAM_P30_2" in tokens
    mock_api.get_devices_menu.assert_awaited_once_with(1, 2, "1.0")


@pytest.mark.asyncio
async def test_standalone_still_loads_later_devices() -> None:
    """Standalone suppresses default only — subsequent Module.devices keep loading."""
    mock_api = AsyncMock()

    async def _get_menu(manuf: int, dev: int, fw: str = "0.0.0") -> dict[str, object]:
        if (manuf, dev) == (1, 1):
            return {
                "priority": 10,
                "extends": [],
                "standalone": True,
                "deviceMenu": [_route("first")],
            }
        if (manuf, dev) == (2, 2):
            return {
                "priority": 20,
                "extends": [],
                "standalone": False,
                "deviceMenu": [_route("second")],
            }
        raise AssertionError(f"default must not load after standalone: {manuf}/{dev}/{fw}")

    mock_api.get_devices_menu = AsyncMock(side_effect=_get_menu)
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    menu = await catalog.get_module_menu(
        device_menu=0,
        devices=[
            DeviceMenuRef(manuf_code=1, dev_code=1, fw="1.0"),
            DeviceMenuRef(manuf_code=2, dev_code=2, fw="1.0"),
        ],
    )
    paths = {r.path for r in menu.routes}
    assert paths == {"first", "second"}
    assert mock_api.get_devices_menu.await_count == 2


@pytest.mark.asyncio
async def test_devices_prefer_rest_over_mapped_js_chunk() -> None:
    """With devices=, REST wins even when index maps a usable deviceMenu JS chunk."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 50,
            "extends": [],
            "standalone": True,
            "deviceMenu": [_route("from-rest")],
        }
    )
    mock_api.get_bytes = AsyncMock(
        return_value=b"""
        export default [{
          path: "from-js",
          name: "modules.menu.from_js",
          meta: { displayName: "menu.JS", displayDropdown: true }
        }];
        """
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.menu_map[153] = "0-JsJsJsJs"
    catalog._idx.assets_by_basename["0"] = [AssetRef(url="https://one.brager.pl/assets/0-JsJsJsJs.js", base="0", hash="JsJsJsJs")]
    menu = await catalog.get_module_menu(
        device_menu=153,
        devices=[DeviceMenuRef(manuf_code=67, dev_code=7, fw="2.08")],
    )
    assert [r.path for r in menu.routes] == ["from-rest"]
    mock_api.get_bytes.assert_not_called()
    mock_api.get_devices_menu.assert_awaited_once_with(67, 7, "2.08")


@pytest.mark.asyncio
async def test_extends_priority_beats_lower_rest_layer() -> None:
    """Extended chunk export priority participates in path merge."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 10,
            "extends": ["153:1211"],
            "standalone": False,
            "deviceMenu": [_route("shared", name="rest.shared")],
        }
    )
    chunk_js = b"""
    export default {
      priority: 100,
      deviceMenu: [{
        path: "shared",
        name: "ext.shared",
        meta: { displayName: "menu.EXT", displayDropdown: true }
      }]
    };
    """
    mock_api.get_bytes = AsyncMock(return_value=chunk_js)
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    catalog._idx.menu_variant_map[(153, "1211")] = "1211-AbCdEfGh"
    catalog._idx.assets_by_basename["1211"] = [
        AssetRef(url="https://one.brager.pl/assets/1211-AbCdEfGh.js", base="1211", hash="AbCdEfGh")
    ]
    menu = await catalog.get_module_menu(device_menu=0)
    assert [r.name for r in menu.routes if r.path == "shared"] == ["ext.shared"]


@pytest.mark.asyncio
async def test_extends_empty_parse_is_skipped() -> None:
    """Resolved extends chunks that parse to zero routes are ignored."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": ["153:1211"],
            "standalone": False,
            "deviceMenu": [_route("base")],
        }
    )
    mock_api.get_bytes = AsyncMock(return_value=b"export default 1;")
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    catalog._idx.menu_variant_map[(153, "1211")] = "1211-AbCdEfGh"
    catalog._idx.assets_by_basename["1211"] = [
        AssetRef(url="https://one.brager.pl/assets/1211-AbCdEfGh.js", base="1211", hash="AbCdEfGh")
    ]
    menu = await catalog.get_module_menu(device_menu=0)
    assert [r.path for r in menu.routes] == ["base"]
    mock_api.get_bytes.assert_awaited_once()


@pytest.mark.asyncio
async def test_device_meta_without_routes_still_collects_extends() -> None:
    """Empty deviceMenu with meta still contributes extends (branch coverage)."""
    mock_api = AsyncMock()

    async def _get_menu(manuf: int, dev: int, fw: str = "0.0.0") -> dict[str, object]:
        if manuf == 1:
            return {"priority": 0, "extends": ["153:1211"], "standalone": False, "deviceMenu": []}
        return {
            "priority": 0,
            "extends": [],
            "standalone": False,
            "deviceMenu": [_route("default")],
        }

    mock_api.get_devices_menu = AsyncMock(side_effect=_get_menu)
    mock_api.get_bytes = AsyncMock(
        return_value=b"""
        export default [{
          path: "extended",
          name: "modules.menu.extended",
          meta: { displayName: "menu.EXTENDED", displayDropdown: true }
        }];
        """
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/d.js", base="dummy", hash="x")]
    catalog._idx.menu_variant_map[(153, "1211")] = "1211-AbCdEfGh"
    catalog._idx.assets_by_basename["1211"] = [
        AssetRef(url="https://one.brager.pl/assets/1211-AbCdEfGh.js", base="1211", hash="AbCdEfGh")
    ]
    menu = await catalog.get_module_menu(
        device_menu=0,
        devices=[DeviceMenuRef(manuf_code=1, dev_code=1, fw="1.0")],
    )
    paths = {r.path for r in menu.routes}
    assert "default" in paths
    assert "extended" in paths
