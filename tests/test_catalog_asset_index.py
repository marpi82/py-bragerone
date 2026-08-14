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
    catalog = LiveAssetsCatalog(mock_api)
    catalog._idx.assets_by_basename["dummy"] = [AssetRef(url="https://example.com/dummy.js", base="dummy", hash="x")]

    menu = await catalog.get_module_menu(device_menu=99)
    assert isinstance(menu, MenuResult)
    assert menu.routes == []
    mock_api.get_bytes.assert_not_called()
