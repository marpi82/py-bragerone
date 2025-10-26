"""Tests for permission-based filtering in the new menu system."""

from __future__ import annotations

from typing import Any

import pytest

from pybragerone.models.menu_manager import MenuProcessor, RawMenuData


@pytest.fixture
def sample_routes_with_permissions() -> list[dict[str, Any]]:
    """Sample route data with various permission scenarios."""
    return [
        {
            "name": "DHW",
            "path": "/dhw",
            "meta": {
                "displayName": "modules.menu.dhw",
                "permissionModule": "DISPLAY_MENU_DHW",
                "parameters": {
                    "read": [
                        {
                            "name": "temp",
                            "permissionModule": "DISPLAY_PARAMETER_LEVEL_1",
                            "parameter": 'E(A.READ,"temp")',
                        },
                        {
                            "name": "mode",
                            "permissionModule": "DISPLAY_PARAMETER_ADMIN",
                            "parameter": 'E(A.READ,"mode")',
                        },
                    ]
                },
            },
            "parameters": {
                "status": [
                    {
                        "name": "status",
                        "permissionModule": "DISPLAY_PARAMETER_LEVEL_1",
                        "parameter": 'E(A.STATUS,"status")',
                    },
                ]
            },
        },
        {
            "name": "Heating",
            "path": "/heating",
            "meta": {
                "displayName": "modules.menu.heating",
                "permissionModule": "A.DISPLAY_MENU_HEATING",
                "parameters": {
                    "write": [
                        {
                            "name": "setpoint",
                            "permissionModule": "A.DISPLAY_PARAMETER_LEVEL_1",
                            "parameter": 'E(A.WRITE,"setpoint")',
                        },
                    ]
                },
            },
            "parameters": {
                "read": [
                    {
                        "name": "current_temp",
                        "permissionModule": "DISPLAY_PARAMETER_LEVEL_1",
                        "parameter": 'E(A.READ,"current_temp")',
                    },
                ]
            },
        },
        {
            "name": "Admin",
            "path": "/admin",
            "meta": {
                "displayName": "modules.menu.admin",
                "permissionModule": "DISPLAY_MENU_ADMIN",
                "parameters": {
                    "special": [
                        {
                            "name": "debug_mode",
                            "permissionModule": "DISPLAY_PARAMETER_ADMIN",
                            "parameter": 'E(A.SPECIAL,"debug_mode")',
                        },
                    ]
                },
            },
        },
        {
            "name": "Public",
            "path": "/public",
            "meta": {"displayName": "modules.menu.public"},
        },
    ]


@pytest.fixture
def menu_processor(sample_routes_with_permissions: list[dict[str, Any]]) -> MenuProcessor:
    """Create a MenuProcessor wired with sample routes."""
    raw = RawMenuData(routes=sample_routes_with_permissions)
    return MenuProcessor(raw)


@pytest.fixture
def level1_permissions() -> set[str]:
    """Permissions representing a level 1 operator."""
    return {
        "DISPLAY_MENU_DHW",
        "DISPLAY_MENU_HEATING",
        "DISPLAY_PARAMETER_LEVEL_1",
    }


@pytest.fixture
def admin_permissions() -> set[str]:
    """Permissions representing an administrator."""
    return {
        "DISPLAY_MENU_DHW",
        "DISPLAY_MENU_HEATING",
        "DISPLAY_MENU_ADMIN",
        "DISPLAY_PARAMETER_LEVEL_1",
        "DISPLAY_PARAMETER_ADMIN",
    }


def test_filter_with_level1_permissions(menu_processor: MenuProcessor, level1_permissions: set[str]) -> None:
    """Operators should see DHW, Heating, and Public routes."""
    menu = menu_processor.get_clean_menu(filter_permissions=level1_permissions)

    names = {route.name for route in menu.routes}
    assert names == {"DHW", "Heating", "Public"}


def test_filter_with_admin_permissions(menu_processor: MenuProcessor, admin_permissions: set[str]) -> None:
    """Admins should see every route."""
    menu = menu_processor.get_clean_menu(filter_permissions=admin_permissions)

    names = {route.name for route in menu.routes}
    assert names == {"DHW", "Heating", "Admin", "Public"}


def test_filter_with_empty_permissions(menu_processor: MenuProcessor) -> None:
    """No permissions should yield only the public route."""
    menu = menu_processor.get_clean_menu(filter_permissions=set())

    names = [route.name for route in menu.routes]
    assert names == ["Public"]


def test_a_prefix_permission_matching(menu_processor: MenuProcessor, level1_permissions: set[str]) -> None:
    """Prefix detection should treat A.DISPLAY_MENU_HEATING as DISPLAY_MENU_HEATING."""
    menu = menu_processor.get_clean_menu(filter_permissions=level1_permissions)

    heating = next(route for route in menu.routes if route.name == "Heating")
    assert heating.meta is not None
    assert heating.meta.permission is None or heating.meta.permission.name == "DISPLAY_MENU_HEATING"


def test_parameter_filtering_level1(menu_processor: MenuProcessor, level1_permissions: set[str]) -> None:
    """Operators should only see parameters they are allowed to access."""
    menu = menu_processor.get_clean_menu(filter_permissions=level1_permissions)

    dhw = next(route for route in menu.routes if route.name == "DHW")
    assert dhw.meta is not None

    meta_tokens = {param.token for param in dhw.meta.parameters.read}
    assert meta_tokens == {"temp"}

    status_tokens = {param.token for param in dhw.parameters.status}
    assert status_tokens == {"status"}


def test_parameter_filtering_admin(menu_processor: MenuProcessor, admin_permissions: set[str]) -> None:
    """Admins should see every parameter token."""
    menu = menu_processor.get_clean_menu(filter_permissions=admin_permissions)

    dhw = next(route for route in menu.routes if route.name == "DHW")
    assert dhw.meta is not None

    meta_tokens = {param.token for param in dhw.meta.parameters.read}
    assert meta_tokens == {"temp", "mode"}

    admin_route = next(route for route in menu.routes if route.name == "Admin")
    assert admin_route.meta is not None
    special_tokens = {param.token for param in admin_route.meta.parameters.special}
    assert special_tokens == {"debug_mode"}


def test_a_prefix_parameter_filtering(menu_processor: MenuProcessor, level1_permissions: set[str]) -> None:
    """Prefix detection should work for parameter permissions as well."""
    menu = menu_processor.get_clean_menu(filter_permissions=level1_permissions)

    heating = next(route for route in menu.routes if route.name == "Heating")
    assert heating.meta is not None

    write_tokens = {param.token for param in heating.meta.parameters.write}
    assert write_tokens == {"setpoint"}


def test_missing_parameters_field(level1_permissions: set[str]) -> None:
    """Routes without the parameters key should still be processed."""
    routes = [
        {
            "name": "SimpleRoute",
            "path": "/simple",
            "meta": {
                "displayName": "routes.simple",
                "permissionModule": "DISPLAY_MENU_DHW",
            },
        }
    ]
    processor = MenuProcessor(RawMenuData(routes=routes))

    menu = processor.get_clean_menu(filter_permissions=level1_permissions)

    assert [route.name for route in menu.routes] == ["SimpleRoute"]


def test_missing_meta_parameters_field(level1_permissions: set[str]) -> None:
    """Routes without meta.parameters should keep node parameters."""
    routes = [
        {
            "name": "RouteWithoutMetaParams",
            "path": "/no-meta-params",
            "meta": {
                "displayName": "routes.no_meta_params",
                "permissionModule": "DISPLAY_MENU_DHW",
            },
            "parameters": {
                "read": [
                    {
                        "name": "param1",
                        "permissionModule": "DISPLAY_PARAMETER_LEVEL_1",
                        "parameter": 'E(A.READ,"param1")',
                    },
                ]
            },
        }
    ]
    processor = MenuProcessor(RawMenuData(routes=routes))

    menu = processor.get_clean_menu(filter_permissions=level1_permissions)
    assert len(menu.routes) == 1
    assert {param.token for param in menu.routes[0].parameters.read} == {"param1"}


def test_debug_mode_includes_hidden_routes(menu_processor: MenuProcessor, level1_permissions: set[str]) -> None:
    """Debug mode should keep inaccessible routes for inspection."""
    menu = menu_processor.get_clean_menu(filter_permissions=level1_permissions, include_invisible=True)

    names = {route.name for route in menu.routes}
    assert names == {"DHW", "Heating", "Admin", "Public"}
