"""Test new menu models with validation and prefix cleanup."""

from pybragerone.models.menu import MenuMeta, MenuParameter, MenuParameters, MenuResult, MenuRoute


def test_menu_parameter_extraction() -> None:
    """Test parameter token extraction from various formats."""
    # Test lowercase format
    param_data = {"permissionModule": "A.DISPLAY_PARAMETER_LEVEL_1", "parameter": 'e(E.READ,"AKTUALNA_TEMP_CWU_READ")'}

    param = MenuParameter.model_validate(param_data)

    assert param.token == "AKTUALNA_TEMP_CWU_READ"
    assert param.permission is not None
    assert param.permission is not None
    assert param.permission.name == "DISPLAY_PARAMETER_LEVEL_1"
    assert param.raw_parameter == 'e(E.READ,"AKTUALNA_TEMP_CWU_READ")'
    assert param.raw_permission == "A.DISPLAY_PARAMETER_LEVEL_1"


def test_menu_parameter_uppercase_format() -> None:
    """Test parameter extraction from uppercase format."""
    param_data = {"permissionModule": "e.HeaterManagement", "parameter": "E(A.WRITE,'URUCHOMIENIE_KOTLA')"}

    param = MenuParameter.model_validate(param_data)

    assert param.token == "URUCHOMIENIE_KOTLA"
    assert param.permission is not None
    assert param.permission is not None
    assert param.permission.name == "HeaterManagement"
    assert param.raw_parameter == "E(A.WRITE,'URUCHOMIENIE_KOTLA')"


def test_menu_parameters_collection() -> None:
    """Test parameters collection with multiple sections."""
    params_data = {
        "read": [{"permissionModule": "A.DISPLAY_PARAMETER_LEVEL_1", "parameter": 'e(E.READ,"TEMP_1")'}],
        "write": [{"permissionModule": "e.HeaterControl", "parameter": "E(A.WRITE,'SET_TEMP')"}],
    }

    params = MenuParameters.model_validate(params_data)

    assert len(params.read) == 1
    assert len(params.write) == 1
    assert params.read[0].token == "TEMP_1"
    assert params.write[0].token == "SET_TEMP"

    all_tokens = params.all_tokens()
    assert "TEMP_1" in all_tokens
    assert "SET_TEMP" in all_tokens
    assert len(all_tokens) == 2


def test_menu_meta_icon_cleanup() -> None:
    """Test meta with icon prefix cleanup."""
    meta_data = {"displayName": "Heating Control", "icon": "a.heating", "permissionModule": "A.HEATING_MODULE", "parameters": {}}

    meta = MenuMeta.model_validate(meta_data)

    assert meta.display_name == "Heating Control"
    assert meta.icon == "heating"  # 'a.' prefix removed
    assert meta.permission is not None
    assert meta.permission.name == "HEATING_MODULE"  # 'A.' prefix removed
    assert meta.raw_permission == "A.HEATING_MODULE"


def test_menu_route_full() -> None:
    """Test complete menu route with nested children."""
    route_data = {
        "path": "/heating",
        "name": "heating-control",
        "meta": {
            "displayName": "Heating Control",
            "icon": "a.heating",
            "permissionModule": "A.HEATING_MODULE",
            "parameters": {"read": [{"permissionModule": "A.READ_TEMP", "parameter": 'e(E.READ,"CURRENT_TEMP")'}]},
        },
        "component": "HeatingView",
        "children": [
            {
                "path": "/settings",
                "name": "heating-settings",
                "meta": {
                    "displayName": "Settings",
                    "icon": "a.settings",
                    "permissionModule": "e.SettingsAccess",
                    "parameters": {"write": [{"permissionModule": "e.WriteSettings", "parameter": "E(A.WRITE,'TARGET_TEMP')"}]},
                },
                "component": "SettingsView",
                "children": [],
            }
        ],
    }

    route = MenuRoute.model_validate(route_data)

    assert route.path == "/heating"
    assert route.name == "heating-control"
    assert route.meta is not None
    assert route.meta.display_name == "Heating Control"
    assert route.meta is not None
    assert route.meta.icon == "heating"  # prefix cleaned
    assert route.component == "HeatingView"

    # Check nested child
    assert len(route.children) == 1
    child = route.children[0]
    assert child.path == "/settings"
    assert child.meta is not None
    assert child.meta.icon == "settings"  # prefix cleaned

    # Check token collection
    all_tokens = route.all_tokens()
    assert "CURRENT_TEMP" in all_tokens
    assert "TARGET_TEMP" in all_tokens
    assert len(all_tokens) == 2


def test_menu_result_full() -> None:
    """Test complete menu result with statistics."""
    menu_data = {
        "routes": [
            {
                "path": "/home",
                "name": "home",
                "meta": {
                    "displayName": "Home",
                    "icon": "a.home",
                    "permissionModule": "A.HOME_ACCESS",
                    "parameters": {"read": [{"permissionModule": "A.READ_STATUS", "parameter": 'e(E.READ,"SYSTEM_STATUS")'}]},
                },
                "component": "HomeView",
                "children": [],
            }
        ],
        "asset_url": "https://example.com/menu.js",
    }

    result = MenuResult.model_validate(menu_data)

    assert len(result.routes) == 1
    assert result.asset_url == "https://example.com/menu.js"
    assert result.token_count() == 1
    assert result.route_count() == 1

    # Check routes by path
    routes_by_path = result.routes_by_path()
    assert "home" in routes_by_path
    assert routes_by_path["home"].meta is not None
    assert routes_by_path["home"].meta.display_name == "Home"


def test_permission_prefix_variations() -> None:
    """Test different permission prefix patterns."""
    test_cases = [
        ("A.DISPLAY_PARAMETER", "DISPLAY_PARAMETER"),
        ("a.DISPLAY_MENU_DHW", "DISPLAY_MENU_DHW"),
        ("X.DISPLAY_MENU_PUMPS", "DISPLAY_MENU_PUMPS"),
        ("e.HeaterManagement", "HeaterManagement"),
        ("E.WRITE_ACCESS", "WRITE_ACCESS"),
        ("NO_PREFIX", "NO_PREFIX"),
        ("", ""),
    ]

    for input_perm, expected_clean in test_cases:
        param_data = {"permissionModule": input_perm, "parameter": 'e(E.READ,"TEST_TOKEN")'}

        param = MenuParameter.model_validate(param_data)

        if expected_clean:
            assert param.permission is not None
            assert param.permission.name == expected_clean
        else:
            assert param.permission is None


def test_parameter_regex_edge_cases() -> None:
    """Test parameter extraction with edge cases."""
    test_cases = [
        # Standard formats
        ('e(E.READ,"TOKEN1")', "TOKEN1"),
        ("E(A.WRITE,'TOKEN2')", "TOKEN2"),
        # Multi-character helper identifiers (minifier/build changes)
        ('helper(E.READ,"TOKEN7")', "TOKEN7"),
        ("doThing(A.WRITE,'TOKEN8')", "TOKEN8"),
        # With spaces
        ('e(E.READ, "TOKEN3")', "TOKEN3"),
        ("E(A.WRITE, 'TOKEN4')", "TOKEN4"),
        # Mixed case letters
        ('a(E.READ,"TOKEN5")', "TOKEN5"),
        ("z(A.WRITE,'TOKEN6')", "TOKEN6"),
    ]

    for param_expr, expected_token in test_cases:
        param_data = {"permissionModule": "A.TEST", "parameter": param_expr}

        param = MenuParameter.model_validate(param_data)
        assert param.token == expected_token, f"Failed for {param_expr}"
