"""Tests for AssetIndex lookup helpers and catalog miss paths."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import AssetIndex, AssetRef, LiveAssetsCatalog
from pybragerone.models.menu import MenuResult


def test_find_asset_for_basename_returns_last_and_none() -> None:
    """Basename lookup returns the last registered asset, or None when missing."""
    idx = AssetIndex()
    assert idx.find_asset_for_basename("PARAM_66") is None

    older = AssetRef(url="https://one.brager.pl/a.js", base="PARAM_66", hash="OLD")
    newer = AssetRef(url="https://one.brager.pl/b.js", base="PARAM_66", hash="NEW")
    idx.assets_by_basename["PARAM_66"] = [older, newer]
    found = idx.find_asset_for_basename("PARAM_66")
    assert found is newer


def test_find_asset_for_full_name_matches_hash_and_misses() -> None:
    """Full-name lookup matches ``base-hash`` and returns None otherwise."""
    idx = AssetIndex()
    asset = AssetRef(url="https://one.brager.pl/module.menu-Ab12.js", base="module.menu", hash="Ab12")
    idx.assets_by_basename["module.menu"] = [asset]
    assert idx.find_asset_for_full_name("module.menu-Ab12") is asset
    assert idx.find_asset_for_full_name("module.menu-Ab12.js") is asset
    assert idx.find_asset_for_full_name("module.menu-NOPE") is None
    trailing = AssetRef(url="https://one.brager.pl/tariff-Db9Vj8s-.js", base="tariff", hash="Db9Vj8s-")
    idx.assets_by_basename["tariff"] = [trailing]
    assert idx.find_asset_for_full_name("tariff-Db9Vj8s-") is trailing
    url_only = AssetRef(url="https://cdn.example/units-Ab12.js", base="other", hash="zzzz")
    idx.assets_by_basename["other"] = [url_only]
    assert idx.find_asset_for_full_name("units-Ab12.js") is url_only


@pytest.mark.asyncio
async def test_get_param_mapping_omits_empty_missing_and_failed_assets() -> None:
    """Empty tokens, unknown tokens, and failed fetches are omitted from the mapping."""
    mock_api = AsyncMock()

    async def get_bytes(_url: str) -> bytes:
        raise RuntimeError("network")

    mock_api.get_bytes.side_effect = get_bytes
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/dummy.js", base="dummy", hash="x")]
    catalog._idx.assets_by_basename["PARAM_FAIL"] = [
        AssetRef(url="https://example.com/PARAM_FAIL-zzz.js", base="PARAM_FAIL", hash="zzz")
    ]

    assert await catalog.get_param_mapping([]) == {}
    assert await catalog.get_param_mapping(["", "NO_SUCH"]) == {}

    failed = await catalog.get_param_mapping(["PARAM_FAIL"])
    assert "PARAM_FAIL" not in failed


@pytest.mark.asyncio
async def test_list_language_config_returns_none_without_index() -> None:
    """Language config is None when the index has not been loaded."""
    mock_api = AsyncMock()
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/dummy.js", base="dummy", hash="x")]
    assert await catalog.list_language_config() is None


@pytest.mark.asyncio
async def test_get_module_menu_without_asset_returns_empty_menu() -> None:
    """Missing menu mappings yield an empty cached menu instead of raising."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(side_effect=RuntimeError("offline"))
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/dummy.js", base="dummy", hash="x")]

    menu = await catalog.get_module_menu(device_menu=99)
    assert isinstance(menu, MenuResult)
    assert menu.routes == []
    mock_api.get_bytes.assert_not_called()
    mock_api.get_devices_menu.assert_awaited_once_with(0, 0, "0.0.0")


def test_generic_menu_asset_skips_menu_0_i18n_chunk() -> None:
    """Post-1.04 ``menu-0-*.js`` is locale MAINMENU text, not a route menu."""
    catalog = LiveAssetsCatalog(AsyncMock())
    bare_zero = AssetRef(url="https://one.brager.pl/assets/0-AAAA.js", base="0", hash="AAAA")
    menu_zero = AssetRef(url="https://one.brager.pl/assets/menu-0-BBBB.js", base="menu-0", hash="BBBB")
    catalog._idx.assets_by_basename["0"] = [bare_zero]
    catalog._idx.assets_by_basename["menu-0"] = [menu_zero]
    assert catalog._generic_menu_asset() is bare_zero


async def test_get_module_menu_falls_back_to_server_default_menu() -> None:
    """Unmapped device_menu loads SPA REST default menu when assets are gone."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": [],
            "standalone": False,
            "deviceMenu": [
                {
                    "path": "dhw",
                    "name": "modules.menu.dhw",
                    "meta": {
                        "displayName": "menu.MAINMENU_USTAWIENIA_CWU",
                        "permissionModule": "DISPLAY_MENU_DHW",
                        "displayDropdown": True,
                        "parameters": {
                            "read": [{"permissionModule": "DISPLAY_PARAMETER_LEVEL_1", "parameter": "PARAM_P30_2"}],
                        },
                    },
                }
            ],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    # Index has only non-menu basenames (post-1.04: no module.menu / deviceMenu/0).
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://one.brager.pl/assets/dummy-x.js", base="dummy", hash="x")]

    menu = await catalog.get_module_menu(device_menu=0, permissions=["DISPLAY_MENU_DHW", "DISPLAY_PARAMETER_LEVEL_1"])
    assert isinstance(menu, MenuResult)
    assert len(menu.routes) == 1
    assert menu.routes[0].path == "dhw"
    assert menu.routes[0].meta is not None
    assert menu.routes[0].meta.display_dropdown is True
    mock_api.get_bytes.assert_not_called()
    mock_api.get_devices_menu.assert_awaited_once_with(0, 0, "0.0.0")


async def test_fetch_server_default_menu_guards_invalid_payloads() -> None:
    """Server menu fallback skips when the API method/payload is unusable."""
    mock_api = AsyncMock()
    mock_api.get_devices_menu = "not-callable"
    empty_routes, empty_url = await LiveAssetsCatalog(mock_api)._fetch_server_default_menu_routes()
    assert empty_routes == []
    assert empty_url is None

    mock_api.get_devices_menu = AsyncMock(return_value=["not", "an", "object"])
    catalog = LiveAssetsCatalog(mock_api)
    bad_type, _ = await catalog._fetch_server_default_menu_routes()
    assert bad_type == []

    mock_api.get_devices_menu = AsyncMock(return_value={"priority": 0, "deviceMenu": "oops"})
    missing_list, _ = await catalog._fetch_server_default_menu_routes()
    assert missing_list == []


async def test_get_module_menu_uses_rest_when_asset_parses_to_zero_routes() -> None:
    """Empty/malformed menu JS still falls through to the SPA default REST menu."""
    mock_api = AsyncMock()
    mock_api.get_bytes = AsyncMock(return_value=b"export default [];")
    mock_api.get_devices_menu = AsyncMock(
        return_value={
            "priority": 0,
            "extends": [],
            "standalone": False,
            "deviceMenu": [
                {
                    "path": "dhw",
                    "name": "modules.menu.dhw",
                    "meta": {
                        "displayName": "menu.MAINMENU_USTAWIENIA_CWU",
                        "permissionModule": "DISPLAY_MENU_DHW",
                    },
                }
            ],
        }
    )
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.menu_map[0] = "0-AAAA"
    catalog._idx.assets_by_basename["0"] = [AssetRef(url="https://one.brager.pl/assets/0-AAAA.js", base="0", hash="AAAA")]

    menu = await catalog.get_module_menu(device_menu=0, permissions=["DISPLAY_MENU_DHW"])
    assert len(menu.routes) == 1
    assert menu.routes[0].path == "dhw"
    mock_api.get_bytes.assert_awaited_once_with("https://one.brager.pl/assets/0-AAAA.js")
    mock_api.get_devices_menu.assert_awaited_once_with(0, 0, "0.0.0")
