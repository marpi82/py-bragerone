"""Tests for route visibility and static menu route shells (#192)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import AssetIndex, AssetRef, LiveAssetsCatalog, ParamMap
from pybragerone.models.menu import MenuResult, MenuRoute
from pybragerone.models.param_resolver import AssetsProtocol, ParamResolver

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


def test_normalize_route_path_key_rejects_non_paths() -> None:
    """Static-route lookup keys ignore unsafe or non-string paths."""
    assert ParamResolver._normalize_route_path_key(None) == ""
    assert ParamResolver._normalize_route_path_key(42) == ""
    assert ParamResolver._normalize_route_path_key(".") == ""
    assert ParamResolver._normalize_route_path_key("..") == ""
    assert ParamResolver._normalize_route_path_key("  /timezones/  ") == "timezones"


def test_route_visibility_dependency_keys_skips_ancestor_without_meta() -> None:
    """Ancestor routes without meta do not contribute dropdown hints."""
    route = SimpleNamespace(name="modules.menu.leaf", path="leaf", meta=None)
    keys = ParamResolver.route_visibility_dependency_keys(route, ancestors=(SimpleNamespace(meta=None),))
    assert keys == set()


@pytest.mark.asyncio
async def test_assets_protocol_discover_static_route_default_raises() -> None:
    """Protocol default bodies remain explicit until a catalog implements them."""

    class StubAssets(AssetsProtocol):
        async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
            return {}

        async def get_module_menu(
            self,
            device_menu: int,
            permissions: Iterable[str] | None = None,
            *,
            debug_mode: bool = False,
        ) -> MenuResult:
            return MenuResult.model_validate({"routes": []})

        async def list_symbols_for_permissions(self, device_menu: int, permissions: Iterable[str]) -> set[str]:
            return set()

        async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
            return {}

        async def get_unit_descriptor(self, unit_code: Any) -> Mapping[str, Any] | None:
            return None

        async def list_language_config(self) -> Any:
            return None

    stub = StubAssets()  # type: ignore[abstract]
    with pytest.raises(NotImplementedError):
        await stub.discover_static_route_tokens("timezones")


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
async def test_discover_static_route_tokens_unknown_path_returns_empty() -> None:
    """Paths absent from both the static map and basename index yield no tokens."""
    catalog = LiveAssetsCatalog(AsyncMock())
    catalog._idx = AssetIndex(static_route_map={}, assets_by_basename={}, index_bytes=b"loaded")
    assert await catalog.discover_static_route_tokens("missing-route") == set()


@pytest.mark.asyncio
async def test_discover_static_route_tokens_missing_asset_ref() -> None:
    """Missing asset refs for a basename yield an empty token set."""
    catalog = LiveAssetsCatalog(AsyncMock())
    catalog._idx = SimpleNamespace(  # type: ignore[assignment]
        static_route_map={"timezones": "timezones"},
        assets_by_basename={"timezones": [AssetRef(url="https://example/tz.js", base="timezones", hash="x")]},
        index_bytes=b"loaded",
        find_asset_for_basename=lambda _base: None,
    )
    assert await catalog.discover_static_route_tokens("timezones") == set()


@pytest.mark.asyncio
async def test_discover_static_route_tokens_falls_back_to_assets_basename() -> None:
    """When static-route map misses, basename keys can still resolve the chunk."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=b"PARAM_99")
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        static_route_map={},
        assets_by_basename={"timezones": [AssetRef(url="https://example/tz.js", base="timezones", hash="x")]},
    )
    assert await catalog.discover_static_route_tokens("timezones") == {"PARAM_99"}


@pytest.mark.asyncio
async def test_discover_static_route_tokens_fetch_failure_is_non_fatal() -> None:
    """Asset fetch failures yield empty tokens and do not poison the cache."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(side_effect=OSError("offline"))
    catalog = LiveAssetsCatalog(api)
    catalog._idx = AssetIndex(
        static_route_map={"timezones": "timezones"},
        assets_by_basename={"timezones": [AssetRef(url="https://example/tz.js", base="timezones", hash="x")]},
    )
    assert await catalog.discover_static_route_tokens("timezones") == set()
    assert "timezones" not in catalog._static_route_tokens_cache

    api.get_bytes = AsyncMock(return_value=b"PARAM_177")
    assert await catalog.discover_static_route_tokens("timezones") == {"PARAM_177"}
    assert api.get_bytes.await_count == 1


@pytest.mark.asyncio
async def test_refresh_index_clears_static_route_tokens_cache() -> None:
    """Index refresh invalidates cached static-route token lookups."""
    api = AsyncMock()
    api.get_bytes = AsyncMock(return_value=b'const x=()=>import("./module.menu-ABC.js");')
    catalog = LiveAssetsCatalog(api)
    catalog._static_route_tokens_cache["timezones"] = {"PARAM_OLD"}
    await catalog.refresh_index("https://example/assets/index-NEW.js", allow_recover=False)
    assert catalog._static_route_tokens_cache == {}


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


def test_route_visibility_dependency_keys_ignores_invalid_status_fields() -> None:
    """Malformed status items do not produce dependency keys."""
    route = SimpleNamespace(
        name="modules.menu.test",
        path="test",
        meta=SimpleNamespace(
            parameters=SimpleNamespace(status=[{"group": "P6", "use": "s", "number": "219"}]),
            display_dropdown=None,
        ),
    )
    assert ParamResolver.route_visibility_dependency_keys(route) == set()


def test_route_visibility_dependency_keys_skips_non_list_status() -> None:
    """Non-list ``status`` containers contribute no dependency keys."""
    route = SimpleNamespace(
        name="modules.menu.test",
        path="test",
        meta=SimpleNamespace(parameters=SimpleNamespace(status={"group": "P6"}), display_dropdown=None),
    )
    assert ParamResolver.route_visibility_dependency_keys(route) == set()


def test_route_visibility_dependency_keys_includes_ancestor_param_key_dropdown() -> None:
    """Ancestor ``displayDropdown`` ParamStore keys are included as flat deps."""
    parent = SimpleNamespace(meta=SimpleNamespace(display_dropdown="P6.v219"))
    route = SimpleNamespace(name="leaf", path="leaf", meta=None)
    assert ParamResolver.route_visibility_dependency_keys(route, ancestors=(parent,)) == {"P6.v219"}


def test_route_visibility_dependency_keys_includes_own_param_key_dropdown() -> None:
    """Route-own ``displayDropdown`` ParamStore keys are visibility deps."""
    route = SimpleNamespace(
        name="modules.menu.circulation",
        path="circulation",
        meta=SimpleNamespace(parameters=None, display_dropdown="P6.v219"),
    )
    assert ParamResolver.route_visibility_dependency_keys(route) == {"P6.v219"}


def test_resolve_route_symbols_ignores_empty_static_overlay() -> None:
    """Empty static overlays leave the route symbol set empty."""
    route = SimpleNamespace(path="timezones", name="MAINMENU_STREFY_CZASOWE", meta=None, parameters=None)
    symbols = ParamResolver._resolve_route_symbols(route, static_route_symbols={"timezones": set()})
    assert symbols == set()


def test_route_visibility_dependency_keys_accepts_dict_status_items() -> None:
    """Status dependency extraction supports plain dict items."""
    route = SimpleNamespace(
        name="modules.menu.test",
        path="test",
        meta=SimpleNamespace(
            parameters=SimpleNamespace(status=[{"group": "P6", "number": 219, "use": "s"}]),
            display_dropdown=None,
        ),
    )
    assert ParamResolver.route_visibility_dependency_keys(route) == {"P6.s219"}


def test_route_visibility_dependency_keys_collects_ancestor_dropdown_marker() -> None:
    """Ancestor numeric ``displayDropdown`` values become soft route deps."""
    parent = SimpleNamespace(meta=SimpleNamespace(display_dropdown=" 42 "))
    route = SimpleNamespace(name="leaf", path="leaf", meta=SimpleNamespace(parameters=None))
    deps = ParamResolver.route_visibility_dependency_keys(route, ancestors=(parent,))
    assert deps == {"route_dropdown:42"}


def test_route_visibility_dependency_keys_ignores_own_non_param_dropdown() -> None:
    """Own ``displayDropdown`` strings that are not ParamStore keys add no deps."""
    route = SimpleNamespace(
        name="modules.menu.shell",
        path="shell",
        meta=SimpleNamespace(parameters=None, display_dropdown="!![]"),
    )
    assert ParamResolver.route_visibility_dependency_keys(route) == set()

    maybe_route = SimpleNamespace(
        name="modules.menu.maybe",
        path="maybe",
        meta=SimpleNamespace(parameters=None, display_dropdown="maybe"),
    )
    assert ParamResolver.route_visibility_dependency_keys(maybe_route) == set()


def test_route_visibility_dependency_keys_skips_ancestor_non_str_dropdown() -> None:
    """Ancestor ``displayDropdown`` values that are not strings are ignored."""
    parent = SimpleNamespace(meta=SimpleNamespace(display_dropdown=True))
    route = SimpleNamespace(name="leaf", path="leaf", meta=None)
    assert ParamResolver.route_visibility_dependency_keys(route, ancestors=(parent,)) == set()

    numeric_parent = SimpleNamespace(meta=SimpleNamespace(display_dropdown=42))
    assert ParamResolver.route_visibility_dependency_keys(route, ancestors=(numeric_parent,)) == set()


def test_route_visibility_dependency_keys_ignores_ancestor_non_key_non_digit() -> None:
    """Ancestor dropdown strings that are neither ParamStore keys nor digits add nothing."""
    parent = SimpleNamespace(meta=SimpleNamespace(display_dropdown="!![]"))
    route = SimpleNamespace(name="leaf", path="leaf", meta=None)
    assert ParamResolver.route_visibility_dependency_keys(route, ancestors=(parent,)) == set()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (True, True),
        (False, False),
        (1.5, True),
        (0.0, False),
        ("yes", True),
        ("0", False),
        ("false", False),
    ],
)
def test_dropdown_param_truthy(raw: object, expected: bool) -> None:
    """Dropdown gating mirrors SPA truthiness for common runtime shapes."""
    assert ParamResolver._dropdown_param_truthy(raw) is expected


def test_route_display_dropdown_visibility_extra_shapes() -> None:
    """Cover bool/unknown/always-on dropdown leftovers on raw route objects."""
    bool_route = SimpleNamespace(meta=SimpleNamespace(display_dropdown=True))
    visible, reason = ParamResolver._route_display_dropdown_visibility(bool_route, {})
    assert visible is True
    assert reason == "visible:dropdown-true"

    false_route = SimpleNamespace(meta=SimpleNamespace(display_dropdown=False))
    visible, reason = ParamResolver._route_display_dropdown_visibility(false_route, {})
    assert visible is False
    assert reason == "hidden:dropdown-false"

    unknown_route = SimpleNamespace(meta=SimpleNamespace(display_dropdown=123))
    visible, reason = ParamResolver._route_display_dropdown_visibility(unknown_route, {})
    assert visible is True
    assert reason == "visible:dropdown-unknown"

    empty_route = SimpleNamespace(meta=SimpleNamespace(display_dropdown=""))
    visible, reason = ParamResolver._route_display_dropdown_visibility(empty_route, {})
    assert visible is True
    assert reason == "visible:no-dropdown"

    unknown_route = SimpleNamespace(meta=SimpleNamespace(display_dropdown="maybe-later"))
    visible, reason = ParamResolver._route_display_dropdown_visibility(unknown_route, {})
    assert visible is True
    assert reason == "visible:dropdown-unknown"


def test_dropdown_param_truthy_falls_back_to_bool_cast() -> None:
    """Non-scalar leftovers still participate in dropdown gating."""
    assert ParamResolver._dropdown_param_truthy(["active"]) is True
    assert ParamResolver._dropdown_param_truthy([]) is False


def test_route_component_is_panel_shell_matches_marker_substring() -> None:
    """Component markers match case-insensitively when embedded in the view name."""
    route = SimpleNamespace(component="pages/scheduleview/index")
    assert ParamResolver._route_component_is_panel_shell(route) is True


def test_route_is_panel_shell_accepts_component_marker() -> None:
    """Known SPA shell components qualify even without static overlays."""
    route = SimpleNamespace(
        name="modules.menu.schedules",
        path="schedules",
        component="ScheduleView",
        meta=SimpleNamespace(display_dropdown=None),
        children=[],
    )
    assert ParamResolver._route_is_panel_shell(route)


def test_route_has_child_routes() -> None:
    """Child routes are not treated as parameter-less shells."""
    route = SimpleNamespace(children=[SimpleNamespace()])
    assert ParamResolver._route_has_child_routes(route) is True
    assert ParamResolver._route_has_child_routes(SimpleNamespace(children=[])) is False


def test_resolve_route_symbols_uses_static_overlay() -> None:
    """Shell routes without inline tokens inherit static-route overlays."""
    route = _route(path="timezones", name="MAINMENU_STREFY_CZASOWE")
    symbols = ParamResolver._resolve_route_symbols(route, static_route_symbols={"timezones": {"PARAM_177"}})
    assert symbols == {"PARAM_177"}


def test_route_visibility_diagnostics_hides_non_module_item_when_all_panels() -> None:
    """``all_panels`` still rejects routes outside module-item classification."""
    route = SimpleNamespace(name="installer.only", path="installer", meta=None, component=None, children=[])
    visible, reason = ParamResolver.route_visibility_diagnostics(route, all_panels=True)
    assert visible is False
    assert reason == "hidden:not-module-item"


def test_panel_route_diagnostics_rejection_branches() -> None:
    """Diagnostics enumerate why routes fail everyday panel inclusion."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "empty",
                    "name": "modules.menu.empty",
                    "meta": {"displayName": "Empty", "displayDropdown": "!![]"},
                },
                {
                    "path": "hidden",
                    "name": "modules.menu.hidden",
                    "meta": {"displayName": "Hidden", "displayDropdown": "![]"},
                },
            ]
        }
    )
    rows = ParamResolver.panel_route_diagnostics_from_menu(menu, all_panels=True, web_ui_only=True)
    by_path = {row["path"]: row for row in rows}
    assert by_path["empty"]["accepted"] is False
    assert by_path["empty"]["reason"] == "rejected:no-symbols"
    assert by_path["hidden"]["accepted"] is False
    assert by_path["hidden"]["reason"].startswith("rejected:route-hidden:")


def test_empty_mainmenu_shell_without_symbols_is_rejected() -> None:
    """Empty MAINMENU shells must not emit panels or be accepted without tokens."""
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
    routes_i18n = {"MAINMENU_STREFY_CZASOWE": "Strefy czasowe"}
    groups = ParamResolver.build_panel_groups_from_menu(
        menu,
        all_panels=True,
        web_ui_only=True,
        routes_i18n=routes_i18n,
    )
    assert "Strefy czasowe" not in groups
    assert groups == {}

    diagnostics = ParamResolver.panel_route_diagnostics_from_menu(
        menu,
        all_panels=True,
        web_ui_only=True,
        routes_i18n=routes_i18n,
    )
    assert len(diagnostics) == 1
    row = diagnostics[0]
    assert row["accepted"] is False
    assert row["reason"] == "rejected:no-symbols"
    assert row["panel_shell"] is True


def test_panel_route_diagnostics_non_all_panels_rejects_hidden_route() -> None:
    """Legacy boiler/DHW grouping still honors route visibility diagnostics."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "hidden",
                    "name": "modules.menu.hidden",
                    "meta": {"displayName": "Hidden", "displayDropdown": "![]"},
                }
            ]
        }
    )
    rows = ParamResolver.panel_route_diagnostics_from_menu(menu, all_panels=False, web_ui_only=True)
    assert rows[0]["accepted"] is False
    assert rows[0]["reason"].startswith("rejected:route-hidden:")


def test_panel_route_diagnostics_non_all_panels_rejects_no_symbols() -> None:
    """Legacy grouping rejects empty panel shells with ``rejected:no-symbols``."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "empty",
                    "name": "modules.menu.empty",
                    "meta": {"displayName": "Empty", "displayDropdown": "!![]"},
                }
            ]
        }
    )
    rows = ParamResolver.panel_route_diagnostics_from_menu(menu, all_panels=False, web_ui_only=True)
    assert len(rows) == 1
    assert rows[0]["accepted"] is False
    assert rows[0]["reason"] == "rejected:no-symbols"
    assert rows[0]["symbol_count"] == 0


def test_route_visibility_dependency_keys_accepts_object_status_items() -> None:
    """Status dependency extraction supports object-shaped meta items."""
    status_item = SimpleNamespace(group="P6", number=219, use="s")
    route = SimpleNamespace(
        name="modules.menu.test",
        path="test",
        meta=SimpleNamespace(parameters=SimpleNamespace(status=[status_item]), display_dropdown=None),
    )
    assert ParamResolver.route_visibility_dependency_keys(route) == {"P6.s219"}


@pytest.mark.asyncio
async def test_static_route_symbols_for_menu_skips_non_shell_and_dedupes() -> None:
    """Only shell routes are fetched; duplicate paths and failures are tolerated."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "timezones",
                    "name": "MAINMENU_STREFY_CZASOWE",
                    "meta": {"displayName": "TZ", "displayDropdown": "!![]"},
                },
                {
                    "path": "timezones",
                    "name": "MAINMENU_STREFY_CZASOWE_DUP",
                    "meta": {"displayName": "TZ dup", "displayDropdown": "!![]"},
                },
                {
                    "path": "regular",
                    "name": "modules.menu.regular",
                    "meta": {
                        "displayName": "Regular",
                        "parameters": {"read": [{"parameter": "E(A.READ,'PARAM_1')"}]},
                    },
                },
            ]
        }
    )
    assets = AsyncMock()
    assets.discover_static_route_tokens = AsyncMock(return_value={"PARAM_177"})
    store = SimpleNamespace(flatten=lambda: {})
    resolver = ParamResolver(store=store, assets=assets)  # type: ignore[arg-type]
    overlays = await resolver._static_route_symbols_for_menu(menu)
    assert overlays == {"timezones": {"PARAM_177"}}
    assets.discover_static_route_tokens.assert_awaited_once_with("timezones")


@pytest.mark.asyncio
async def test_static_route_symbols_for_menu_swallows_fetch_errors(caplog: pytest.LogCaptureFixture) -> None:
    """Asset fetch failures leave the overlay empty and log the discovery failure."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "timezones",
                    "name": "MAINMENU_STREFY_CZASOWE",
                    "meta": {"displayName": "TZ", "displayDropdown": "!![]"},
                },
            ]
        }
    )
    assets = AsyncMock()
    assets.discover_static_route_tokens = AsyncMock(side_effect=RuntimeError("offline"))
    store = SimpleNamespace(flatten=lambda: {})
    resolver = ParamResolver(store=store, assets=assets)  # type: ignore[arg-type]
    with caplog.at_level("ERROR", logger="pybragerone.models.param_resolver"):
        assert await resolver._static_route_symbols_for_menu(menu) == {}
    assert "Static route token discovery failed for timezones" in caplog.text


@pytest.mark.asyncio
async def test_static_route_symbols_for_menu_without_discover_helper() -> None:
    """Assets without ``discover_static_route_tokens`` yield no overlays."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {"path": "timezones", "name": "MAINMENU_STREFY_CZASOWE", "meta": {"displayName": "TZ", "displayDropdown": "!![]"}}
            ]
        }
    )
    store = SimpleNamespace(flatten=lambda: {})
    resolver = ParamResolver(store=store, assets=SimpleNamespace())  # type: ignore[arg-type]
    assert await resolver._static_route_symbols_for_menu(menu) == {}
