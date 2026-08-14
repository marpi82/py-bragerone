"""Tests for the menu manager and permission filtering."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog
from pybragerone.models.menu_manager import MenuManager, RawMenuData


@pytest.fixture()
def sample_routes() -> list[dict[str, Any]]:
    """Return a single route with prefixed permissions and parameters."""
    return [
        {
            "path": "/test",
            "name": "test-route",
            "meta": {
                "displayName": "Test Route",
                "icon": "a.test_icon",
                "permissionModule": "A.TEST_PERMISSION",
                "parameters": {"read": [{"permissionModule": "A.READ_TEST", "parameter": 'e(E.READ,"TEST_TOKEN")'}]},
            },
            "component": "TestView",
            "children": [],
        }
    ]


@pytest.fixture()
def base_manager(sample_routes: list[dict[str, Any]]) -> tuple[MenuManager, int]:
    """Store sample routes in a fresh MenuManager."""
    manager = MenuManager()
    device_menu = 0
    manager.store_raw_menu(device_menu=device_menu, routes=sample_routes, asset_url="https://test.com/menu.js")
    return manager, device_menu


@pytest.fixture()
def nested_manager() -> tuple[MenuManager, int]:
    """Return a manager with nested routes requiring different permissions."""
    manager = MenuManager()
    device_menu = 1
    manager.store_raw_menu(
        device_menu=device_menu,
        routes=[
            {
                "path": "/parent",
                "name": "parent",
                "meta": {"permissionModule": "DISPLAY_MENU_PARENT", "displayName": "Parent"},
                "children": [
                    {
                        "path": "/parent/hidden-child",
                        "name": "child",
                        "meta": {"permissionModule": "DISPLAY_MENU_CHILD", "displayName": "Child"},
                        "children": [],
                    }
                ],
            }
        ],
    )
    return manager, device_menu


def test_menu_manager_basic_processing(base_manager: tuple[MenuManager, int]) -> None:
    """Ensure storing raw menus yields processed output when permissions match."""
    manager, device_menu = base_manager

    debug_info = manager.get_debug_info(device_menu)
    assert debug_info["raw_routes_count"] == 1
    assert debug_info["asset_url"] == "https://test.com/menu.js"

    raw_menu = manager.get_raw_menu(device_menu)
    assert len(raw_menu.routes) == 1

    filtered_menu = manager.get_menu(device_menu, permissions={"TEST_PERMISSION", "READ_TEST"})
    assert len(filtered_menu.routes) == 1
    route = filtered_menu.routes[0]
    assert route.path == "/test"
    assert route.meta is not None
    assert route.meta.icon == "test_icon"
    assert route.meta.permission is not None and route.meta.permission.name == "TEST_PERMISSION"
    assert route.meta.parameters.read[0].token == "TEST_TOKEN"


def test_permission_filter_hides_routes(base_manager: tuple[MenuManager, int]) -> None:
    """Routes without matching permissions should be hidden by default."""
    manager, device_menu = base_manager

    menu = manager.get_menu(device_menu, permissions=set())
    assert menu.routes == []


def test_debug_mode_includes_hidden_routes(base_manager: tuple[MenuManager, int]) -> None:
    """Debug mode should retain routes even when permissions are missing."""
    manager, device_menu = base_manager

    menu = manager.get_menu(device_menu, permissions=set(), debug_mode=True)
    assert [route.name for route in menu.routes] == ["test-route"]
    assert menu.routes[0].meta is not None
    assert menu.routes[0].meta.permission is not None
    assert menu.routes[0].meta.permission.name == "TEST_PERMISSION"


def test_hidden_children_removed_without_permission(nested_manager: tuple[MenuManager, int]) -> None:
    """Children requiring missing permissions should be pruned."""
    manager, device_menu = nested_manager

    menu = manager.get_menu(device_menu, permissions={"DISPLAY_MENU_PARENT"})
    assert len(menu.routes) == 1
    assert menu.routes[0].children == []


def test_route_kept_when_parameter_permission_allows_access() -> None:
    """Keep route visible when parameter-level permission grants access."""
    manager = MenuManager()
    device_menu = 2
    manager.store_raw_menu(
        device_menu=device_menu,
        routes=[
            {
                "path": "/internet",
                "name": "internet",
                "meta": {"permissionModule": "DISPLAY_MENU_ADMIN", "displayName": "Internet"},
                "parameters": {
                    "write": [
                        {
                            "permissionModule": "DISPLAY_PARAMETER_LEVEL_1",
                            "parameter": 'e(E.WRITE,"COMMAND_MODULE_RESTART")',
                        }
                    ]
                },
                "children": [],
            }
        ],
    )

    menu = manager.get_menu(device_menu, permissions={"DISPLAY_PARAMETER_LEVEL_1"})
    assert len(menu.routes) == 1
    assert menu.routes[0].name == "internet"
    assert menu.routes[0].parameters.write[0].token == "COMMAND_MODULE_RESTART"


def test_debug_mode_keeps_hidden_children(nested_manager: tuple[MenuManager, int]) -> None:
    """Debug mode should keep children even when inaccessible."""
    manager, device_menu = nested_manager

    menu = manager.get_menu(device_menu, permissions={"DISPLAY_MENU_PARENT"}, debug_mode=True)
    assert len(menu.routes) == 1
    assert [child.name for child in menu.routes[0].children] == ["child"]


def test_raw_menu_data_route_count() -> None:
    """Ensure RawMenuData counts nested routes correctly."""
    routes = [{"path": "/test", "name": "test"}]
    raw = RawMenuData(routes=routes, asset_url="test.js")

    assert raw.route_count() == 1
    assert raw.asset_url == "test.js"

    nested_routes = [
        {
            "path": "/parent",
            "name": "parent",
            "children": [
                {"path": "/child1", "name": "child1", "children": []},
                {
                    "path": "/child2",
                    "name": "child2",
                    "children": [{"path": "/grandchild", "name": "grandchild", "children": []}],
                },
            ],
        }
    ]

    raw_nested = RawMenuData(routes=nested_routes)
    assert raw_nested.route_count() == 4


@pytest.mark.asyncio()
async def test_catalog_integration() -> None:
    """Validate catalog wiring into the menu manager end to end."""
    mock_api = AsyncMock()
    mock_api.get_bytes.return_value = b"""
    export default [
        {
            path: \"/test\",
            name: \"test-route\",
            meta: {
                displayName: \"Test Route\",
                icon: \"a.test\",
                permissionModule: \"A.TEST_PERM\"
            },
            component: \"TestView\",
            children: []
        }
    ];
    """

    catalog = LiveAssetsCatalog(mock_api)

    from pybragerone.models.catalog import AssetRef

    test_asset = AssetRef(url="https://test.com/menu.js", base="module.menu", hash="test123")
    catalog._idx.menu_map[0] = "module.menu-test123.js"
    catalog._idx.assets_by_basename["module.menu"] = [test_asset]

    menu = await catalog.get_module_menu(0, permissions=["TEST_PERM"])

    assert len(menu.routes) == 1
    assert menu.routes[0].path == "/test"
    assert menu.asset_url == "https://test.com/menu.js"

    raw_menu = catalog.get_raw_menu(0)
    assert len(raw_menu.routes) == 1

    debug_info = catalog.get_menu_debug_info(0)
    assert debug_info["raw_routes_count"] == 1


@pytest.mark.asyncio()
async def test_redirect_only_nodes_are_pruned() -> None:
    """Redirect-only nodes lacking name/path should not break menu parsing."""
    mock_api = AsyncMock()
    mock_api.get_bytes.return_value = b"""
    export default [
        {
            path: "/root",
            name: "root",
            meta: {
                displayName: "Root",
                icon: "a.root",
                permissionModule: "A.ROOT_PERM"
            },
            children: [
                { redirect: { name: "moved" }, children: [] },
                { path: "/child", name: "child", children: [] }
            ]
        }
    ];
    """

    catalog = LiveAssetsCatalog(mock_api)

    from pybragerone.models.catalog import AssetRef

    test_asset = AssetRef(url="https://test.com/menu.js", base="module.menu", hash="test123")
    catalog._idx.menu_map[0] = "module.menu-test123.js"
    catalog._idx.assets_by_basename["module.menu"] = [test_asset]

    menu = await catalog.get_module_menu(0, permissions=["ROOT_PERM"])

    assert len(menu.routes) == 1
    assert menu.routes[0].name == "root"
    assert len(menu.routes[0].children) == 1
    assert menu.routes[0].children[0].name == "child"


@pytest.mark.asyncio()
async def test_catalog_integration_fallback_when_no_device_menu_mapping() -> None:
    """Use generic module.menu when deviceMenu mapping is missing (e.g. device_menu=0)."""
    mock_api = AsyncMock()
    mock_api.get_bytes.return_value = b"""
    export default [
        {
            path: \"/test\",
            name: \"test-route\",
            meta: {
                displayName: \"Test Route\",
                icon: \"a.test\",
                permissionModule: \"A.TEST_PERM\"
            },
            component: \"TestView\",
            children: []
        }
    ];
    """

    catalog = LiveAssetsCatalog(mock_api)

    from pybragerone.models.catalog import AssetRef

    test_asset = AssetRef(url="https://test.com/menu.js", base="module.menu", hash="test123")
    catalog._idx.assets_by_basename["module.menu"] = [test_asset]
    # Intentionally do NOT provide catalog._idx.menu_map[0]

    menu = await catalog.get_module_menu(0, permissions=["TEST_PERM"])

    assert len(menu.routes) == 1
    assert menu.routes[0].path == "/test"
    assert menu.asset_url == "https://test.com/menu.js"


def test_device_menu_mapping_parsed_from_router_paths() -> None:
    """Parse deviceMenu to module.menu mapping from index router path entries."""
    mock_api = AsyncMock()
    catalog = LiveAssetsCatalog(mock_api)

    index_code = b"""
    {"../config/router/deviceMenu/0/module.menu.ts":()=>d(()=>import("./module.menu-B60xPU0K.js"),__vite__mapDeps([0]))
    ,"../config/router/deviceMenu/1/module.menu.ts":()=>d(()=>import("./module.menu-lSoMfgab.js"),__vite__mapDeps([1]))}
    """

    idx = catalog._build_asset_index_from_index_js("https://one.brager.pl/assets/index-main.js", index_code)

    assert idx.menu_map[0] == "module.menu-B60xPU0K"
    assert idx.menu_map[1] == "module.menu-lSoMfgab"


def test_device_menu_mapping_parsed_from_src_router_paths() -> None:
    """Parse deviceMenu mapping from /src router paths with arbitrary helper name."""
    mock_api = AsyncMock()
    catalog = LiveAssetsCatalog(mock_api)

    index_code = b"""
    {"/src/config/router/deviceMenu/0/module.menu.ts":()=>_(()=>import("./module.menu-DmY2Kb59.js"),__vite__mapDeps([0]))
    ,"/src/config/router/deviceMenu/1/module.menu.ts":()=>_(()=>import("./module.menu-DCbbkfeq.js"),__vite__mapDeps([1]))}
    """

    idx = catalog._build_asset_index_from_index_js("https://one.brager.pl/assets/index-main.js", index_code)

    assert idx.menu_map[0] == "module.menu-DmY2Kb59"
    assert idx.menu_map[1] == "module.menu-DCbbkfeq"


_LIVE_MENU_ZERO = """
export default [{
  path:'dhw',
  name:'modules.menu.dhw',
  meta:{
    displayName:'MAINMENU_USTAWIENIA_CWU',
    permissionModule:_0x521864['DISPLAY_MENU_DHW'],
    parameters:{
      read:[{permissionModule:_0x521864['DISPLAY_PARAMETER_LEVEL_1'], parameter:_0x3e8c51(_0x1cc358['READ'],'PARAM_P30_2')}],
      write:[{
        permissionModule:_0x521864['DISPLAY_PARAMETER_LEVEL_MAX'],
        parameter:_0x3e8c51(_0x1cc358['WRITE'],'PARAM_P32_184')
      }],
      status:[],
      special:[]
    }
  },
  children:[]
}];
"""


def test_menu_manager_gates_leftover_subscript_permission_strings() -> None:
    """Gating still matches when permissionModule was left as raw subscript text."""
    manager = MenuManager()
    manager.store_raw_menu(
        0,
        [
            {
                "path": "dhw",
                "name": "dhw",
                "meta": {
                    "displayName": "DHW",
                    "permissionModule": "_0x521864['DISPLAY_MENU_DHW']",
                    "parameters": {
                        "read": [
                            {
                                "permissionModule": "_0x521864['DISPLAY_PARAMETER_LEVEL_1']",
                                "parameter": "_0x3e8c51(_0x1cc358['READ'],'PARAM_P30_2')",
                            }
                        ]
                    },
                },
                "children": [],
            }
        ],
    )
    gated = manager.get_menu(0, permissions={"DISPLAY_MENU_DHW", "DISPLAY_PARAMETER_LEVEL_1"})
    assert gated.all_tokens() == {"PARAM_P30_2"}


@pytest.mark.asyncio()
async def test_get_module_menu_gates_obfuscated_permission_subscripts() -> None:
    """API DISPLAY_* strings must match live ``_0x…['DISPLAY_*']`` menu fields."""
    mock_api = AsyncMock()
    mock_api.get_bytes.return_value = _LIVE_MENU_ZERO.encode()
    catalog = LiveAssetsCatalog(mock_api)
    from pybragerone.models.catalog import AssetRef

    catalog._idx.menu_map[0] = "0-DRINFhbV"
    catalog._idx.assets_by_basename["0"] = [AssetRef(url="https://one.brager.pl/assets/0-DRINFhbV.js", base="0", hash="DRINFhbV")]

    gated = await catalog.get_module_menu(
        0,
        permissions=["DISPLAY_MENU_DHW", "DISPLAY_PARAMETER_LEVEL_1"],
    )
    assert gated.all_tokens() == {"PARAM_P30_2"}
    assert gated.routes[0].meta is not None
    assert gated.routes[0].meta.permission is not None
    assert gated.routes[0].meta.permission.name == "DISPLAY_MENU_DHW"

    ungated = await catalog.get_module_menu(0, permissions=None)
    assert ungated.all_tokens() == {"PARAM_P30_2", "PARAM_P32_184"}


def test_resolve_tokens_normalizes_leftover_permission_on_fast_path() -> None:
    """Pre-extracted token+parameter entries still strip ``_0x…['DISPLAY_*']`` permissions."""
    manager = MenuManager()
    manager.store_raw_menu(
        0,
        [
            {
                "path": "dhw",
                "name": "dhw",
                "meta": {
                    "displayName": "DHW",
                    "permissionModule": "DISPLAY_MENU_DHW",
                    "parameters": {
                        "read": [
                            {
                                "permissionModule": "_0x521864['DISPLAY_PARAMETER_LEVEL_1']",
                                "parameter": "E(A.READ,'PARAM_P30_2')",
                                "token": "PARAM_P30_2",
                            },
                            {
                                "permissionModule": "DISPLAY_PLAIN",
                                "parameter": "E(A.READ,'PARAM_P30_3')",
                                "token": "PARAM_P30_3",
                            },
                        ]
                    },
                },
                "children": [],
            }
        ],
    )
    menu = manager.get_menu(0, permissions=None)
    read = menu.routes[0].meta.parameters.read if menu.routes[0].meta is not None else []
    assert read[0].permission is not None
    assert read[0].permission.name == "DISPLAY_PARAMETER_LEVEL_1"
    assert read[1].permission is not None
    assert read[1].permission.name == "DISPLAY_PLAIN"


_LIVE_MENU_MAP = """
const _201={'priority':0x64,'deviceMenu':[{
  path:'userMenu',
  name:'MAINMENU_MENU_UZYTKOWNIKA',
  meta:{
    displayName:'MAINMENU_MENU_UZYTKOWNIKA',
    permissionModule:_0x58838d['DISPLAY_PARAMETER_LEVEL_1'],
    parameters:{
      read:[],
      write:['PARAM_45','PARAM_34']['map'](_0x46820c=>({
        permissionModule:_0x58838d['DISPLAY_PARAMETER_LEVEL_1'],
        parameter:_0x2d2290(_0x870f31['WRITE'],_0x46820c)
      })),
      status:[],
      special:[]
    }
  },
  children:[]
}]};
export default _201;
"""


@pytest.mark.asyncio()
async def test_get_module_menu_unwraps_array_map_write_lists() -> None:
    """DeviceMenu 153/2190 write lists must become PARAM_* tokens, not ValidationError."""
    mock_api = AsyncMock()
    mock_api.get_bytes.return_value = _LIVE_MENU_MAP.encode()
    catalog = LiveAssetsCatalog(mock_api)
    from pybragerone.models.catalog import AssetRef

    catalog._idx.menu_map[2190] = "201-DKEZsk-M"
    catalog._idx.assets_by_basename["201"] = [
        AssetRef(url="https://one.brager.pl/assets/201-DKEZsk-M.js", base="201", hash="DKEZsk-M")
    ]

    menu = await catalog.get_module_menu(2190, permissions=None)
    assert menu.all_tokens() == {"PARAM_45", "PARAM_34"}
    gated = await catalog.get_module_menu(2190, permissions=["DISPLAY_PARAMETER_LEVEL_1"])
    assert gated.all_tokens() == {"PARAM_45", "PARAM_34"}


def test_menu_manager_does_not_iterate_map_leftover_strings() -> None:
    """A leftover map call must not explode MenuResult into per-character errors."""
    leftover = (
        "['PARAM_45','PARAM_34']['map'](_0x46820c=>"
        "({'permissionModule':_0x58838d['DISPLAY_PARAMETER_LEVEL_1'],"
        "'parameter':_0x2d2290(_0x870f31['WRITE'],_0x46820c)}))"
    )
    manager = MenuManager()
    manager.store_raw_menu(
        2190,
        [
            {
                "path": "userMenu",
                "name": "userMenu",
                "meta": {
                    "displayName": "User",
                    "permissionModule": "DISPLAY_PARAMETER_LEVEL_1",
                    "parameters": {"write": leftover, "read": {"not": "a-list"}},
                },
                "children": [],
            }
        ],
    )
    unfiltered = manager.get_menu(2190, permissions=None, debug_mode=True)
    assert unfiltered.routes[0].meta is not None
    assert unfiltered.routes[0].meta.parameters.write == []
    menu = manager.get_menu(2190, permissions={"DISPLAY_PARAMETER_LEVEL_1"}, debug_mode=True)
    assert menu.routes[0].meta is not None
    assert menu.routes[0].meta.parameters.write == []
    assert menu.routes[0].meta.parameters.read == []
