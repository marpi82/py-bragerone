"""Tests for route visibility and static menu route shells (#192)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import AssetIndex, AssetRef, LiveAssetsCatalog
from pybragerone.models.menu import MenuResult, MenuRoute
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


def _route(*, path: str, name: str, meta: dict[str, Any] | None = None, children: list[Any] | None = None) -> MenuRoute:
    meta_payload = {"displayName": name, **(meta or {})}
    return MenuRoute.model_validate(
        {
            "path": path,
            "name": name,
            "meta": meta_payload,
            "children": children or [],
        }
    )


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
    assert reason == "visible:dropdown-always"

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


@pytest.mark.parametrize(
    ("flat_value", "expected_visible", "expected_reason"),
    [
        (0, False, "hidden:dropdown-value"),
        (1, True, "visible:dropdown-value"),
        (None, False, "hidden:dropdown-missing-value"),
    ],
)
def test_route_visibility_diagnostics_evaluates_dropdown_param_key(
    flat_value: int | None,
    expected_visible: bool,
    expected_reason: str,
) -> None:
    """ParamStore-backed ``displayDropdown`` keys gate route visibility at runtime."""
    route = _route(path="circulation", name="modules.menu.circulation", meta={"displayDropdown": "P6.v219"})
    flat_values: dict[str, Any] = {}
    if flat_value is not None:
        flat_values["P6.v219"] = flat_value
    visible, reason = ParamResolver.route_visibility_diagnostics(
        route,
        flat_values=flat_values,
        all_panels=True,
        web_ui_only=True,
    )
    assert visible is expected_visible
    assert reason == expected_reason


def test_route_visibility_diagnostics_hides_literal_dropdown_false() -> None:
    """Literal ``![]`` dropdown leftovers hide the route."""
    route = _route(path="hidden", name="modules.menu.hidden", meta={"displayDropdown": "![]"})
    visible, reason = ParamResolver.route_visibility_diagnostics(route, all_panels=True)
    assert visible is False
    assert reason == "hidden:dropdown-false"


def test_build_panel_groups_excludes_route_hidden_by_dropdown_param() -> None:
    """Runtime-aware ``flat_values`` can drop a route from everyday UI panel groups."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "circulation",
                    "name": "modules.menu.circulation",
                    "meta": {
                        "displayName": "Cyrkulacja",
                        "displayDropdown": "P6.v219",
                        "parameters": {"read": [{"parameter": "E(A.READ,'PARAM_219')"}]},
                    },
                }
            ]
        }
    )
    groups = ParamResolver.build_panel_groups_from_menu(
        menu,
        all_panels=True,
        web_ui_only=True,
        flat_values={"P6.v219": 0},
    )
    assert groups == {}


def test_route_visibility_dependency_keys_collects_status_paths() -> None:
    """Route visibility deps include status channel keys from route meta."""
    status_item = SimpleNamespace(group="P6", number=219, use="s")
    params = SimpleNamespace(status=[status_item])
    meta = SimpleNamespace(parameters=params)
    route = SimpleNamespace(name="MAINMENU_STREFY_CZASOWE", path="timezones", meta=meta)
    deps = ParamResolver.route_visibility_dependency_keys(route)
    assert deps == {"P6.s219"}


def test_route_is_panel_shell_requires_static_tokens_or_mainmenu_name() -> None:
    """Shell detection accepts static overlays and ``MAINMENU_*`` route names."""
    shell_route = _route(path="timezones", name="MAINMENU_STREFY_CZASOWE")
    assert ParamResolver._route_is_panel_shell(
        shell_route,
        static_route_symbols={"timezones": {"PARAM_177"}},
    )
    non_shell = _route(
        path="other",
        name="modules.menu.other",
        meta={"parameters": {"read": [{"parameter": "E(A.READ,'PARAM_1')"}]}},
    )
    assert not ParamResolver._route_is_panel_shell(non_shell)
    parent_with_children = SimpleNamespace(
        name="modules.menu.parent",
        path="parent",
        component=None,
        meta=SimpleNamespace(display_dropdown=None),
        children=[SimpleNamespace()],
    )
    assert not ParamResolver._route_is_panel_shell(parent_with_children)


@pytest.mark.asyncio
async def test_discover_static_route_tokens_from_index_map() -> None:
    """LiveAssetsCatalog loads tokens from static deviceMenu route chunks."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=b"e(E.READ,'PARAM_177'); e(E.WRITE,'PARAM_178'); STATUS_P9_4;")
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        static_route_map={"timezones": "timezones"},
        assets_by_basename={
            "timezones": [
                AssetRef(
                    url="https://example/assets/timezones-abc.js",
                    base="timezones",
                    hash="abc",
                )
            ]
        },
    )
    tokens = await catalog.discover_static_route_tokens("timezones")
    assert tokens == {"PARAM_177", "PARAM_178", "STATUS_P9_4"}


@pytest.mark.asyncio
async def test_discover_static_route_tokens_uses_cache() -> None:
    """Repeated lookups reuse the in-memory static-route token cache."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=b"PARAM_1")
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        static_route_map={"timezones": "timezones"},
        assets_by_basename={"timezones": [AssetRef(url="https://example/tz.js", base="timezones", hash="x")]},
    )
    first = await catalog.discover_static_route_tokens("timezones")
    second = await catalog.discover_static_route_tokens("timezones")
    assert first == {"PARAM_1"}
    assert second == first
    api.get_bytes.assert_awaited_once()


@pytest.mark.asyncio
async def test_discover_static_route_tokens_empty_path() -> None:
    """Empty or unsafe route paths return no tokens."""
    catalog = LiveAssetsCatalog(AsyncMock())
    assert await catalog.discover_static_route_tokens("") == set()
    assert await catalog.discover_static_route_tokens(".") == set()


@pytest.mark.asyncio
async def test_discover_static_route_tokens_fetch_failure_is_non_fatal() -> None:
    """Asset fetch failures yield an empty token set without raising."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(side_effect=OSError("offline"))
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        static_route_map={"timezones": "timezones"},
        assets_by_basename={"timezones": [AssetRef(url="https://example/tz.js", base="timezones", hash="x")]},
    )
    assert await catalog.discover_static_route_tokens("timezones") == set()


@pytest.mark.asyncio
async def test_static_route_symbols_for_menu_overlays_shell_routes() -> None:
    """ParamResolver overlays shell routes with tokens from LiveAssetsCatalog."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "timezones",
                    "name": "MAINMENU_STREFY_CZASOWE",
                    "meta": {"displayName": "MAINMENU_STREFY_CZASOWE", "displayDropdown": "!![]"},
                }
            ]
        }
    )
    assets = AsyncMock()
    assets.discover_static_route_tokens = AsyncMock(return_value={"PARAM_177", "PARAM_178"})
    store = SimpleNamespace(flatten=lambda: {})
    resolver = ParamResolver(store=store, assets=assets)  # type: ignore[arg-type]
    overlays = await resolver._static_route_symbols_for_menu(menu)
    assert overlays == {"timezones": {"PARAM_177", "PARAM_178"}}
