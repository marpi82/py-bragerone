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

    from pybragerone.models.i18n import I18nResolver
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
                {
                    "path": "preset",
                    "name": "MAINMENU_PRESET",
                    "meta": {
                        "displayName": "MAINMENU_PRESET",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_4')"}],
                        },
                    },
                },
                {
                    "path": "empty",
                    "name": "MAINMENU_EMPTY",
                    "meta": {
                        "displayName": "MAINMENU_EMPTY",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_5')"}],
                        },
                    },
                },
                {
                    "path": "spaces",
                    "name": "MAINMENU_SPACES",
                    "meta": {
                        "displayName": "MAINMENU_SPACES",
                        "parameters": {
                            "read": [{"parameter": "E(A.READ,'PARAM_6')"}],
                        },
                    },
                },
            ]
        }
    )

    namespaces: dict[str, dict[str, Any]] = {
        "routes": {
            "modules": {"menu": {"thermostat": {"pump": "Pompa CO"}}},
            # Already-resolved overlay entry must not be replaced by a later fetch
            # or by a competing menu-namespace title.
            "MAINMENU_PRESET": "Preset title",
            # Whitespace-only overlay must be treated as missing and re-fetched.
            "MAINMENU_SPACES": "   ",
            # Blank routes placeholder must be replaced by the menu namespace title.
            "MAINMENU_MENU_BUFOR": "  ",
            # Non-string routes placeholder must also be replaced by menu.
            "MAINMENU_ODD": {"ignored": True},
        },
        "menu": {
            "MAINMENU_MENU_BUFOR": "Menu bufor",
            "MAINMENU_PRESET": "Menu should not win",
            "MAINMENU_ODD": "Odd title",
            "nested": {"ignored": True},
            "bad-key": 12,
        },
        "MAINMENU_MENU_TERMOSTATU": {"MAINMENU_MENU_TERMOSTATU": "Menu termostatów"},
        "MAINMENU_PRESET": {"MAINMENU_PRESET": "Should not win"},
        "MAINMENU_EMPTY": {},
        "MAINMENU_SPACES": {"MAINMENU_SPACES": "Spaces title"},
    }

    class _StubI18n:
        async def get_namespace(self, namespace: str, *, lang: str | None = None) -> dict[str, Any]:
            return dict(namespaces.get(namespace, {}))

    assets = AsyncMock()
    assets.get_module_menu = AsyncMock(return_value=menu)
    resolver = ParamResolver(
        store=ParamStore(),
        assets=cast(AssetsProtocol, assets),
        lang="pl",
        i18n=cast(I18nResolver, _StubI18n()),
    )
    title_i18n = await resolver._panel_title_i18n(menu)
    assert title_i18n["MAINMENU_MENU_TERMOSTATU"] == "Menu termostatów"
    assert title_i18n["MAINMENU_MENU_BUFOR"] == "Menu bufor"
    assert title_i18n["MAINMENU_PRESET"] == "Preset title"
    assert title_i18n["MAINMENU_ODD"] == "Odd title"
    assert title_i18n["MAINMENU_SPACES"] == "Spaces title"
    assert "MAINMENU_EMPTY" not in title_i18n or title_i18n.get("MAINMENU_EMPTY") != ""

    groups = ParamResolver.build_panel_groups_from_menu(menu, all_panels=True, routes_i18n=title_i18n)
    assert "Menu termostatów/Pompa CO" in groups
    assert groups["Menu termostatów/Pompa CO"] == ["PARAM_2"]
    # Bare MAINMENU routes are not module-item panels themselves, but their
    # translated titles still prefix children under modules.menu.*.
    assert "Menu bufor" not in groups
    assert ParamResolver._collect_menu_title_tokens(menu) == {
        "MAINMENU_MENU_TERMOSTATU",
        "MAINMENU_MENU_BUFOR",
        "MAINMENU_PRESET",
        "MAINMENU_EMPTY",
        "MAINMENU_SPACES",
    }

    groups_async = await resolver.build_panel_groups(device_menu=0, all_panels=True)
    assert "Menu termostatów/Pompa CO" in groups_async
    diagnostics = await resolver.panel_route_diagnostics(device_menu=0, all_panels=True)
    assert any(row.get("panel_title") == "Menu termostatów/Pompa CO" for row in diagnostics)
