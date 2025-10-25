"""Integration test for clean menu models with real data."""

import json
from pathlib import Path

import pytest

from pybragerone.models.menu import MenuResult


def test_clean_menu_models_with_real_data() -> None:
    """Test that clean menu models work with real menu data."""
    # Load real test results
    test_file = (
        Path(__file__).parent.parent / "scripts" / "live_test_results" / "live_test_results_module_0_HT  DasPell GL 37kW.json"
    )

    if not test_file.exists():
        pytest.skip("Real test data file not available")

    with open(test_file) as f:
        test_data = json.load(f)

    # Extract route data
    sample_route = test_data["menu_filtered"]["sample_route"]

    # Test single route validation and cleanup
    from pybragerone.models.menu import MenuRoute

    clean_route = MenuRoute.model_validate(sample_route)

    # Verify cleanup happened
    assert clean_route.meta is not None
    assert clean_route.meta.icon is not None
    assert not clean_route.meta.icon.startswith("a.")  # Icon prefix removed

    # Check permission cleanup
    if clean_route.meta.permission:
        # Should not have A./e./E. prefix
        perm_name = clean_route.meta.permission.name
        assert not perm_name.startswith("A.")
        assert not perm_name.startswith("e.")
        assert not perm_name.startswith("E.")

    # Check parameter token extraction
    if clean_route.meta.parameters.read:
        read_param = clean_route.meta.parameters.read[0]
        assert read_param.token  # Should have extracted token
        assert not read_param.token.startswith("e(")  # Should not be raw expression
        assert not read_param.token.startswith("E(")  # Should not be raw expression

        # Permission should be cleaned
        if read_param.permission:
            perm_name = read_param.permission.name
            assert not perm_name.startswith("A.")
            assert not perm_name.startswith("e.")
            assert not perm_name.startswith("E.")

    print(f"✓ Route path: {clean_route.path}")
    print(f"✓ Display name: {clean_route.meta.display_name}")
    print(f"✓ Clean icon: {clean_route.meta.icon}")
    print(f"✓ Tokens found: {len(clean_route.all_tokens())}")
    print(f"✓ Permissions found: {len(clean_route.all_permissions())}")


def test_menu_result_statistics() -> None:
    """Test MenuResult statistics with real data."""
    # Create a sample menu result with multiple routes
    menu_data = {
        "routes": [
            {
                "path": "/heating",
                "name": "heating",
                "meta": {
                    "displayName": "Heating Control",
                    "icon": "a.heating",
                    "permissionModule": "A.HEATING_ACCESS",
                    "parameters": {
                        "read": [{"permissionModule": "A.READ_TEMP", "parameter": 'e(E.READ,"CURRENT_TEMP")'}],
                        "write": [{"permissionModule": "e.WriteTemp", "parameter": "E(A.WRITE,'TARGET_TEMP')"}],
                    },
                },
                "component": "HeatingView",
                "children": [
                    {
                        "path": "/schedule",
                        "name": "schedule",
                        "meta": {
                            "displayName": "Schedule",
                            "icon": "a.schedule",
                            "permissionModule": "e.ScheduleAccess",
                            "parameters": {
                                "special": [{"permissionModule": "A.SCHEDULE_EDIT", "parameter": 'e(E.SPECIAL,"SCHEDULE_DATA")'}]
                            },
                        },
                        "component": "ScheduleView",
                        "children": [],
                    }
                ],
            }
        ],
        "asset_url": "https://example.com/test-menu.js",
    }

    result = MenuResult.model_validate(menu_data)

    # Check statistics
    assert result.token_count() == 3  # CURRENT_TEMP, TARGET_TEMP, SCHEDULE_DATA
    assert result.route_count() == 2  # heating + schedule child

    # Check token collection works recursively
    all_tokens = result.all_tokens()
    assert "CURRENT_TEMP" in all_tokens
    assert "TARGET_TEMP" in all_tokens
    assert "SCHEDULE_DATA" in all_tokens

    # Check permission collection
    all_permissions = result.all_permissions()
    permission_names = {p.name for p in all_permissions}

    # Should have cleaned permissions (no prefixes)
    assert "HEATING_ACCESS" in permission_names  # from A.HEATING_ACCESS
    assert "READ_TEMP" in permission_names  # from A.READ_TEMP
    assert "WriteTemp" in permission_names  # from e.WriteTemp
    assert "ScheduleAccess" in permission_names  # from e.ScheduleAccess
    assert "SCHEDULE_EDIT" in permission_names  # from A.SCHEDULE_EDIT

    # Check routes by path
    routes_by_path = result.routes_by_path()
    assert "heating" in routes_by_path
    assert "heating/schedule" in routes_by_path

    heating_route = routes_by_path["heating"]
    assert heating_route.meta is not None
    assert heating_route.meta.icon == "heating"  # prefix cleaned

    schedule_route = routes_by_path["heating/schedule"]
    assert schedule_route.meta is not None
    assert schedule_route.meta.icon == "schedule"  # prefix cleaned

    print(f"✓ Total tokens: {result.token_count()}")
    print(f"✓ Total routes: {result.route_count()}")
    print(f"✓ Unique permissions: {len(all_permissions)}")
    print(f"✓ Routes accessible by path: {len(routes_by_path)}")


if __name__ == "__main__":
    test_clean_menu_models_with_real_data()
    test_menu_result_statistics()
    print("All integration tests passed!")
