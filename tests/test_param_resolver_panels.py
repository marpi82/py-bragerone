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


def test_build_panel_groups_from_menu_all_panels_uses_routes_i18n_titles() -> None:
    """Resolve panel titles via routes i18n when displayName uses routes.* keys."""
    menu = _menu_fixture()
    routes_i18n = {
        "modules": {
            "menu": {
                "boiler": "Ustawienia kotła",
                "dhw": "Ciepła woda",
                "valve1": "Zawór 1",
                "user": "Użytkownik",
                "sensorsCorrections": "Korekty czujników",
            }
        }
    }

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=True, routes_i18n=routes_i18n)

    assert "Ustawienia kotła" in groups
    assert "Ciepła woda" in groups
    assert "Zawór 1" in groups
    assert "Użytkownik" in groups
    assert "Korekty czujników" in groups
    assert groups["Użytkownik"] == ["PARAM_66"]


def test_build_panel_groups_from_menu_all_panels_merges_duplicate_panel_titles() -> None:
    """Merge symbols when multiple routes resolve to the same panel title."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "dhw",
                    "name": "modules.menu.dhw",
                    "meta": {
                        "displayName": "CWU",
                        "parameters": {"read": [{"parameter": "E(A.READ,'PARAM_P4_2')"}]},
                    },
                },
                {
                    "path": "boiler/dhw",
                    "name": "modules.menu.boilerDHW",
                    "meta": {
                        "displayName": "CWU",
                        "parameters": {"write": [{"parameter": "E(A.WRITE,'PARAM_51')"}]},
                    },
                },
            ]
        }
    )

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=True)

    assert "CWU" in groups
    assert groups["CWU"] == ["PARAM_51", "PARAM_P4_2"]


def test_build_panel_groups_from_menu_all_panels_uses_parent_child_titles_for_duplicates() -> None:
    """Disambiguate duplicate child route titles via parent/child panel titles."""
    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "valves",
                    "name": "modules.menu.valves",
                    "meta": {"displayName": "routes.modules.menu.valves", "displayDropdown": "1"},
                    "children": [
                        {
                            "path": "valve/1",
                            "name": "modules.menu.valve1",
                            "meta": {
                                "displayName": "routes.modules.menu.valve1",
                                "parameters": {
                                    "read": [{"parameter": "E(A.READ,'PARAM_531')"}],
                                },
                            },
                        }
                    ],
                },
                {
                    "path": "thermostats",
                    "name": "modules.menu.thermostats",
                    "meta": {"displayName": "routes.modules.menu.thermostats", "displayDropdown": "1"},
                    "children": [
                        {
                            "path": "valve/1",
                            "name": "modules.menu.thermostat.valve1",
                            "meta": {
                                "displayName": "routes.modules.menu.thermostat.valve1",
                                "parameters": {
                                    "read": [{"parameter": "E(A.READ,'PARAM_541')"}],
                                },
                            },
                        }
                    ],
                },
            ]
        }
    )

    routes_i18n = {
        "modules": {
            "menu": {
                "valves": "Zawory",
                "thermostats": "Termostaty",
                "valve1": "Zawór 1",
                "thermostat": {
                    "valve1": "Zawór 1",
                },
            }
        }
    }

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=True, routes_i18n=routes_i18n)

    assert "Zawory/Zawór 1" in groups
    assert "Termostaty/Zawór 1" in groups
    assert all("(" not in key and ")" not in key for key in groups)
    assert groups["Zawory/Zawór 1"] == ["PARAM_531"]
    assert groups["Termostaty/Zawór 1"] == ["PARAM_541"]


async def test_panel_title_i18n_overlays_mainmenu_string_namespaces() -> None:
    """Bare MAINMENU_* tokens resolve from string-default namespaces and menu pack."""
    from typing import Any, cast
    from unittest.mock import AsyncMock

    from pybragerone.models.param import ParamStore
    from pybragerone.models.param_resolver import AssetsProtocol

    menu = MenuResult.model_validate(
        {
            "routes": [
                {
                    "path": "thermostats",
                    "name": "MAINMENU_MENU_TERMOSTATU",
                    "meta": {
                        "displayName": "MAINMENU_MENU_TERMOSTATU",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_1')"}],
                        },
                    },
                    "children": [
                        {
                            "path": "pump",
                            "name": "modules.menu.thermostat.pump",
                            "meta": {
                                "displayName": "routes.modules.menu.thermostat.pump",
                                "parameters": {
                                    "write": [{"parameter": "E(A.WRITE,'PARAM_2')"}],
                                },
                            },
                        }
                    ],
                },
                {
                    "path": "buffer",
                    "name": "MAINMENU_MENU_BUFOR",
                    "meta": {
                        "displayName": "MAINMENU_MENU_BUFOR",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_3')"}],
                        },
                    },
                },
            ]
        }
    )

    namespaces: dict[str, dict[str, Any]] = {
        "routes": {"modules": {"menu": {"thermostat": {"pump": "Pompa CO"}}}},
        "menu": {"MAINMENU_MENU_BUFOR": "Menu bufor"},
        "MAINMENU_MENU_TERMOSTATU": {"MAINMENU_MENU_TERMOSTATU": "Menu termostatów"},
    }

    class _StubI18n:
        async def get_namespace(self, namespace: str, *, lang: str | None = None) -> dict[str, Any]:
            return dict(namespaces.get(namespace, {}))

    assets = AsyncMock()
    resolver = ParamResolver(store=ParamStore(), assets=cast(AssetsProtocol, assets), lang="pl", i18n=_StubI18n())  # type: ignore[arg-type]
    title_i18n = await resolver._panel_title_i18n(menu)
    assert title_i18n["MAINMENU_MENU_TERMOSTATU"] == "Menu termostatów"
    assert title_i18n["MAINMENU_MENU_BUFOR"] == "Menu bufor"

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=True, routes_i18n=title_i18n)
    assert "Menu termostatów/Pompa CO" in groups
    assert "Menu bufor" in groups
    assert ParamResolver._collect_menu_title_tokens(menu) == {
        "MAINMENU_MENU_TERMOSTATU",
        "MAINMENU_MENU_BUFOR",
    }
