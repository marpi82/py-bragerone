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
