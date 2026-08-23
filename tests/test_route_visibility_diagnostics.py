"""Tests for route visibility and static menu route shells (#192)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pybragerone.models.menu import MenuResult
from pybragerone.models.param_resolver import ParamResolver

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "menu_strefy_czasowe.json"


def _load_fixture() -> tuple[MenuResult, dict[str, set[str]], dict[str, str]]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    menu = MenuResult.model_validate(payload)
    static_raw = payload.get("static_route_symbols", {})
    static: dict[str, set[str]] = {str(key): set(value) for key, value in static_raw.items() if isinstance(value, list)}
    routes_i18n = payload.get("routes_i18n", {})
    i18n = {str(k): str(v) for k, v in routes_i18n.items() if isinstance(k, str) and isinstance(v, str)}
    return menu, static, i18n


def test_build_panel_groups_includes_strefy_czasowe_from_static_tokens() -> None:
    """Shell route without menu tokens still becomes a panel when static tokens exist."""
    menu, static, routes_i18n = _load_fixture()
    groups = ParamResolver.build_panel_groups_from_menu(
        menu,
        all_panels=True,
        web_ui_only=True,
        routes_i18n=routes_i18n,
        static_route_symbols=static,
    )
    assert "Strefy czasowe" in groups
    assert groups["Strefy czasowe"] == ["PARAM_177", "PARAM_178", "PARAM_390"]


def test_route_visibility_diagnostics_accepts_display_dropdown_always() -> None:
    """``!![]`` dropdown leftovers mean the route stays on the everyday UI."""
    menu, _, routes_i18n = _load_fixture()
    route = menu.routes[0]
    visible, reason = ParamResolver.route_visibility_diagnostics(
        route,
        all_panels=True,
        web_ui_only=True,
    )
    assert visible is True
    assert reason == "visible:default"

    diagnostics = ParamResolver.panel_route_diagnostics_from_menu(
        menu,
        all_panels=True,
        web_ui_only=True,
        routes_i18n=routes_i18n,
        static_route_symbols={"timezones": {"PARAM_177"}},
    )
    row = diagnostics[0]
    assert row["accepted"] is True
    assert row["panel_shell"] is True
    assert row["symbol_count"] == 1


@pytest.mark.asyncio
async def test_discover_static_route_tokens_from_index_map() -> None:
    """LiveAssetsCatalog loads tokens from static deviceMenu route chunks."""
    from unittest.mock import AsyncMock

    from pybragerone.models.catalog import AssetIndex, LiveAssetsCatalog

    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=b"e(E.READ,'PARAM_177'); e(E.WRITE,'PARAM_178'); STATUS_P9_4;")
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        static_route_map={"timezones": "timezones"},
        assets_by_basename={
            "timezones": [
                type("Ref", (), {"url": "https://example/assets/timezones-abc.js", "hash": "abc", "base": "timezones"})()
            ]
        },
    )
    tokens = await catalog.discover_static_route_tokens("timezones")
    assert "PARAM_177" in tokens
    assert "PARAM_178" in tokens
    assert "STATUS_P9_4" in tokens
