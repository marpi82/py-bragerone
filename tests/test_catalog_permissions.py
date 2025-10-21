"""Tests for permission-based filtering in catalog module.

This module tests the permission filtering functionality in LiveAssetsCatalog,
ensuring that menu routes and parameters are properly filtered based on user permissions.
"""

from typing import Any
from unittest.mock import Mock

import pytest

from pybragerone.models.catalog import LiveAssetsCatalog


class TestCatalogPermissions:
    """Test suite for permission filtering in LiveAssetsCatalog."""

    @pytest.fixture
    def catalog(self) -> LiveAssetsCatalog:
        """Create a LiveAssetsCatalog instance for testing."""
        # Create a mock API client since we're only testing the permission filtering logic
        mock_api = Mock()
        return LiveAssetsCatalog(api=mock_api)

    @pytest.fixture
    def sample_routes_with_permissions(self) -> list[dict[str, Any]]:
        """Sample route data with various permission scenarios."""
        return [
            {
                "name": "DHW",
                "path": "/dhw",
                "meta": {
                    "permissionModule": "DISPLAY_MENU_DHW",
                    "parameters": {
                        "read": [
                            {"name": "temp", "permissionModule": "DISPLAY_PARAMETER_LEVEL_1"},
                            {"name": "mode", "permissionModule": "DISPLAY_PARAMETER_ADMIN"},
                        ]
                    },
                },
                "parameters": {
                    "status": [
                        {"name": "status", "permissionModule": "DISPLAY_PARAMETER_LEVEL_1"},
                    ]
                },
            },
            {
                "name": "Heating",
                "path": "/heating",
                "meta": {
                    "permissionModule": "A.DISPLAY_MENU_HEATING",
                    "parameters": {
                        "write": [
                            {"name": "setpoint", "permissionModule": "A.DISPLAY_PARAMETER_LEVEL_1"},
                        ]
                    },
                },
                "parameters": {
                    "read": [
                        {"name": "current_temp", "permissionModule": "DISPLAY_PARAMETER_LEVEL_1"},
                    ]
                },
            },
            {
                "name": "Admin",
                "path": "/admin",
                "meta": {
                    "permissionModule": "DISPLAY_MENU_ADMIN",
                    "parameters": {
                        "special": [
                            {"name": "debug_mode", "permissionModule": "DISPLAY_PARAMETER_ADMIN"},
                        ]
                    },
                },
            },
            {
                "name": "Public",
                "path": "/public",
                "meta": {
                    # No permissionModule means no permissions required
                },
            },
        ]

    @pytest.fixture
    def level1_permissions(self) -> list[str]:
        """User permissions for level 1 access."""
        return ["DISPLAY_MENU_DHW", "DISPLAY_MENU_HEATING", "DISPLAY_PARAMETER_LEVEL_1"]

    @pytest.fixture
    def admin_permissions(self) -> list[str]:
        """User permissions for admin access."""
        return [
            "DISPLAY_MENU_DHW",
            "DISPLAY_MENU_HEATING",
            "DISPLAY_MENU_ADMIN",
            "DISPLAY_PARAMETER_LEVEL_1",
            "DISPLAY_PARAMETER_ADMIN",
        ]

    def test_filter_with_level1_permissions(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]], level1_permissions: list[str]
    ) -> None:
        """Test filtering with level 1 permissions - should see DHW and Heating but not Admin."""
        gated_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set(level1_permissions))

        # Check visibility flags
        routes_by_name = {route["name"]: route for route in gated_routes}
        assert routes_by_name["DHW"]["_visible"] is True
        assert routes_by_name["Heating"]["_visible"] is True
        assert routes_by_name["Admin"]["_visible"] is False
        assert routes_by_name["Public"]["_visible"] is True  # No permissions required

        # Filter to only visible routes (as the application would)
        visible_routes = [route for route in gated_routes if route.get("_visible", False)]
        visible_names = [route["name"] for route in visible_routes]
        assert "DHW" in visible_names
        assert "Heating" in visible_names
        assert "Admin" not in visible_names
        assert "Public" in visible_names
        assert len(visible_routes) == 3

    def test_filter_with_admin_permissions(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]], admin_permissions: list[str]
    ) -> None:
        """Test filtering with admin permissions - should see all routes."""
        gated_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set(admin_permissions))

        # Check that all routes are visible for admin
        routes_by_name = {route["name"]: route for route in gated_routes}
        assert routes_by_name["DHW"]["_visible"] is True
        assert routes_by_name["Heating"]["_visible"] is True
        assert routes_by_name["Admin"]["_visible"] is True
        assert routes_by_name["Public"]["_visible"] is True

        # All routes should be visible
        visible_routes = [route for route in gated_routes if route.get("_visible", False)]
        assert len(visible_routes) == 4

    def test_filter_with_empty_permissions(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]]
    ) -> None:
        """Test filtering with no permissions - should only see public routes."""
        gated_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set())

        # Check visibility flags
        routes_by_name = {route["name"]: route for route in gated_routes}
        assert routes_by_name["DHW"]["_visible"] is False
        assert routes_by_name["Heating"]["_visible"] is False
        assert routes_by_name["Admin"]["_visible"] is False
        assert routes_by_name["Public"]["_visible"] is True  # No permissions required

        # Filter to only visible routes (as the application would)
        visible_routes = [route for route in gated_routes if route.get("_visible", False)]
        visible_names = [route["name"] for route in visible_routes]
        assert "DHW" not in visible_names
        assert "Heating" not in visible_names
        assert "Admin" not in visible_names
        assert "Public" in visible_names
        assert len(visible_routes) == 1

    def test_a_prefix_permission_matching(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]], level1_permissions: list[str]
    ) -> None:
        """Test that A. prefixed permissions are properly matched."""
        # level1_permissions contains "DISPLAY_MENU_HEATING" which should match "A.DISPLAY_MENU_HEATING"
        gated_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set(level1_permissions))

        heating_route = next((r for r in gated_routes if r["name"] == "Heating"), None)
        assert heating_route is not None, "Route with A. prefixed permission should exist"
        assert heating_route["_visible"] is True, "Route with A. prefixed permission should be accessible"

    def test_parameter_filtering_level1(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]], level1_permissions: list[str]
    ) -> None:
        """Test that parameters are filtered based on user permissions."""
        filtered_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set(level1_permissions))

        dhw_route = next((r for r in filtered_routes if r["name"] == "DHW"), None)
        assert dhw_route is not None

        # Check meta parameters filtering
        meta_read_params = [p["name"] for p in dhw_route["meta"]["parameters"]["read"]]
        assert "temp" in meta_read_params  # DISPLAY_PARAMETER_LEVEL_1 allowed
        assert "mode" not in meta_read_params  # DISPLAY_PARAMETER_ADMIN not allowed

        # Check node parameters filtering
        node_status_params = [p["name"] for p in dhw_route["parameters"]["status"]]
        assert "status" in node_status_params  # DISPLAY_PARAMETER_LEVEL_1 allowed

    def test_parameter_filtering_admin(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]], admin_permissions: list[str]
    ) -> None:
        """Test that admin users see all parameters."""
        filtered_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set(admin_permissions))

        dhw_route = next((r for r in filtered_routes if r["name"] == "DHW"), None)
        assert dhw_route is not None

        # Check meta parameters - admin should see all
        meta_read_params = [p["name"] for p in dhw_route["meta"]["parameters"]["read"]]
        assert "temp" in meta_read_params
        assert "mode" in meta_read_params

        # Check admin route parameters
        admin_route = next((r for r in filtered_routes if r["name"] == "Admin"), None)
        assert admin_route is not None
        admin_special_params = [p["name"] for p in admin_route["meta"]["parameters"]["special"]]
        assert "debug_mode" in admin_special_params

    def test_a_prefix_parameter_filtering(
        self, catalog: LiveAssetsCatalog, sample_routes_with_permissions: list[dict[str, Any]], level1_permissions: list[str]
    ) -> None:
        """Test that A. prefixed parameter permissions are properly handled."""
        filtered_routes = catalog._gate_routes_independent(sample_routes_with_permissions, set(level1_permissions))

        heating_route = next((r for r in filtered_routes if r["name"] == "Heating"), None)
        assert heating_route is not None

        # Check that A. prefixed parameter permission is matched
        meta_write_params = [p["name"] for p in heating_route["meta"]["parameters"]["write"]]
        assert "setpoint" in meta_write_params  # A.DISPLAY_PARAMETER_LEVEL_1 should match DISPLAY_PARAMETER_LEVEL_1

    def test_missing_parameters_field(self, catalog: LiveAssetsCatalog, level1_permissions: list[str]) -> None:
        """Test handling of routes without parameters field."""
        routes_without_params = [
            {
                "name": "SimpleRoute",
                "path": "/simple",
                "meta": {"permissionModule": "DISPLAY_MENU_DHW"},
                # No "parameters" field
            }
        ]

        # Should not crash and should include the route
        filtered_routes = catalog._gate_routes_independent(routes_without_params, set(level1_permissions))
        assert len(filtered_routes) == 1
        assert filtered_routes[0]["name"] == "SimpleRoute"

    def test_missing_meta_parameters_field(self, catalog: LiveAssetsCatalog, level1_permissions: list[str]) -> None:
        """Test handling of routes without meta.parameters field."""
        routes_without_meta_params = [
            {
                "name": "RouteWithoutMetaParams",
                "path": "/no-meta-params",
                "meta": {
                    "permissionModule": "DISPLAY_MENU_DHW"
                    # No "parameters" field in meta
                },
                "parameters": {"read": [{"name": "param1", "permissionModule": "DISPLAY_PARAMETER_LEVEL_1"}]},
            }
        ]

        # Should not crash and should filter node parameters
        filtered_routes = catalog._gate_routes_independent(routes_without_meta_params, set(level1_permissions))
        assert len(filtered_routes) == 1
        assert len(filtered_routes[0]["parameters"]["read"]) == 1
        assert filtered_routes[0]["parameters"]["read"][0]["name"] == "param1"
