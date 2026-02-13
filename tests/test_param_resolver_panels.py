"""Tests for route-to-panel grouping helpers in ParamResolver."""

from __future__ import annotations

from pybragerone.models.menu import MenuResult
from pybragerone.models.param_resolver import ParamResolver


def _menu_fixture() -> MenuResult:
    return MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "boiler",
                    "name": "modules.menu.boiler",
                    "meta": {
                        "displayName": "Boiler",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_1')"}],
                            "write": [{"parameter": "E(A.WRITE,'PARAM_2')"}],
                        },
                    },
                },
                {
                    "path": "dhw",
                    "name": "modules.menu.dhw",
                    "meta": {
                        "displayName": "DHW",
                        "parameters": {
                            "status": [{"parameter": "E(A.STATUS,'STATUS_P5_19')"}],
                        },
                    },
                },
                {
                    "path": "valve1",
                    "name": "modules.menu.valve1",
                    "meta": {
                        "displayName": "Valve 1",
                        "parameters": {
                            "write": [{"parameter": "E(A.WRITE,'PARAM_53')"}],
                        },
                    },
                },
                {
                    "path": "user",
                    "name": "modules.menu.user",
                    "meta": {
                        "displayName": "User",
                        "parameters": {
                            "write": [{"parameter": "E(A.WRITE,'PARAM_66')"}],
                        },
                    },
                },
                {
                    "path": "modules",
                    "name": "routes.modules.menu.modules",
                    "meta": {
                        "displayName": "Modules",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_999')"}],
                        },
                    },
                },
                {
                    "path": "sensors-corrections",
                    "name": "modules.menu.sensorsCorrections",
                    "meta": {
                        "displayName": "Sensors corrections",
                        "isVisibleOnSideMenu": False,
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_888')"}],
                        },
                    },
                },
            ]
        }
    )


def test_build_panel_groups_from_menu_core_only() -> None:
    """Return canonical three groups when all-panels mode is disabled."""
    menu = _menu_fixture()

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=False)

    assert set(groups.keys()) == {"Boiler", "DHW", "Valve 1"}
    assert groups["Boiler"] == ["PARAM_1", "PARAM_2"]
    assert groups["DHW"] == ["STATUS_P5_19"]
    assert groups["Valve 1"] == ["PARAM_53"]


def test_build_panel_groups_from_menu_all_panels() -> None:
    """Include module-item routes and exclude non-module-item routes in all-panels mode."""
    menu = _menu_fixture()

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=True)

    assert "Boiler" in groups
    assert "DHW" in groups
    assert "Valve 1" in groups
    assert "User" in groups
    assert "Modules" not in groups
    assert "Sensors corrections" in groups
    assert groups["User"] == ["PARAM_66"]
