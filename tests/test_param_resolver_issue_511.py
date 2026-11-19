"""Regressions for multi-module storeGetter context and panel flatten defaults (#511)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from pybragerone.models import ParamResolver, ParamStore
from pybragerone.models.catalog import ParamMap
from pybragerone.models.menu import MenuResult
from pybragerone.models.param_resolver import AssetsProtocol


class _EmptyAssets:
    """Minimal assets stub (no mappings; dropdown-gated menu route)."""

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        _ = tokens
        return {}

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
        devices: object | None = None,
    ) -> MenuResult:
        _ = (device_menu, permissions, debug_mode, devices)
        return MenuResult.model_validate(
            {
                "routes": [
                    {
                        "name": "modules.menu.main",
                        "path": "main",
                        "meta": {
                            "displayName": "Main",
                            "displayDropdown": "P6.v219",
                            "parameters": {
                                "read": [{"parameter": "E(A.READ,'PARAM_DROP')"}],
                            },
                        },
                    }
                ]
            }
        )

    async def discover_static_route_tokens(self, route_path: str) -> set[str]:
        _ = route_path
        return set()

    async def list_symbols_for_permissions(
        self,
        device_menu: int,
        permissions: Iterable[str],
        *,
        devices: object | None = None,
    ) -> set[str]:
        _ = (device_menu, permissions, devices)
        return set()

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        _ = (lang, namespace)
        return {}

    async def get_unit_descriptor(self, unit_code: Any) -> None:
        _ = unit_code
        return None


def _restart_desc() -> dict[str, Any]:
    """COMMAND_MODULE_RESTART-like ENABLED via modulesMap.{devid}.connectedAt."""
    return {
        "mapping": {
            "paths": {
                "status": [
                    {
                        "condition": "ENABLED",
                        "if": [
                            {
                                "expected": None,
                                "operation": "notEqualTo",
                                "value": {"storeGetter": "modulesMap.{devid}.connectedAt"},
                            }
                        ],
                        "then": "!![]",
                    },
                    {"condition": "ENABLED", "else": "![]"},
                ]
            }
        }
    }


def test_store_scoped_devids_helpers() -> None:
    """ParamStore exposes scoped module ids for multi-module overlay guards."""
    store = ParamStore()
    assert store.scoped_devids() == frozenset()
    assert store.has_multiple_scoped_modules() is False
    store.upsert("P4.v1", 1, devid="M1")
    store.upsert("P4.v1", 2, devid="M2")
    assert store.scoped_devids() == frozenset({"M1", "M2"})
    assert store.has_multiple_scoped_modules() is True


def test_storegetter_enabled_independent_per_devid_without_mutating_context() -> None:
    """Two modules in modulesMap; devid= selects which connectedAt is read (#511)."""
    store = ParamStore()
    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EmptyAssets()), lang="en")
    resolver.set_runtime_context(
        {
            "modulesMap": {
                "M1": {"connectedAt": 1_794_459_623},
                "M2": {"connectedAt": None},
            }
        }
    )
    desc = _restart_desc()

    visible_m1, reason_m1 = resolver.parameter_visibility_diagnostics(desc=desc, resolved=1, devid="M1")
    visible_m2, reason_m2 = resolver.parameter_visibility_diagnostics(desc=desc, resolved=1, devid="M2")

    assert visible_m1 is True
    assert reason_m1 == "visible:default"
    assert visible_m2 is False
    assert reason_m2 == "hidden:enabled"
    # Shared context must not have been mutated by devid= overrides.
    assert "devid" not in resolver._evaluator._context


def test_storegetter_eval_condition_injects_devid_per_call() -> None:
    """Evaluator injects devid into storeGetter templates without shared mutation."""
    store = ParamStore()
    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EmptyAssets()), lang="en")
    resolver.set_runtime_context(
        {
            "modulesMap": {
                "M1": {"connectedAt": 10},
                "M2": {"connectedAt": 0},
            }
        }
    )
    rule = {
        "operation": "notEqualTo",
        "expected": None,
        "value": {"storeGetter": "modulesMap.{devid}.connectedAt"},
    }
    assert resolver._evaluator._eval_condition_any(rule, devid="M1") is True
    # connectedAt 0 maps to None → notEqualTo null is False.
    assert resolver._evaluator._eval_condition_any(rule, devid="M2") is False


async def test_panel_groups_refuse_merged_flatten_when_multi_module() -> None:
    """Without flat_values/devid, multi-module store must not use LWW flatten (#511)."""
    store = ParamStore()
    store.upsert("P6.v219", 1, devid="M1")
    store.upsert("P6.v219", 0, devid="M2")

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EmptyAssets()), lang="en")
    resolver._panel_title_i18n = AsyncMock(return_value={})  # type: ignore[method-assign]
    resolver._static_route_symbols_for_menu = AsyncMock(return_value={})  # type: ignore[method-assign]

    flatten_calls = {"n": 0}
    original = ParamStore.flatten

    def _counting_flatten(self: ParamStore) -> dict[str, Any]:
        flatten_calls["n"] += 1
        return original(self)

    with patch.object(ParamStore, "flatten", _counting_flatten):
        # Merged flatten would see M2's 0 last and hide the dropdown route; refusing merge
        # treats overlay as unprimed so the structural route stays discoverable.
        groups_unscoped = await resolver.build_panel_groups(device_menu=0, all_panels=True, web_ui_only=True)
        assert flatten_calls["n"] == 0
        assert "PARAM_DROP" in {sym for syms in groups_unscoped.values() for sym in syms}

        groups_m1 = await resolver.build_panel_groups(device_menu=0, all_panels=True, web_ui_only=True, devid="M1")
        assert "PARAM_DROP" in {sym for syms in groups_m1.values() for sym in syms}

        groups_m2 = await resolver.build_panel_groups(device_menu=0, all_panels=True, web_ui_only=True, devid="M2")
        # M2 gate value 0 → dropdown hide when primed for that module.
        assert "PARAM_DROP" not in {sym for syms in groups_m2.values() for sym in syms}


async def test_panel_route_diagnostics_accepts_devid_snapshot() -> None:
    """panel_route_diagnostics with devid= primes dropdown gates per module."""
    store = ParamStore()
    store.upsert("P6.v219", 1, devid="M1")
    store.upsert("P6.v219", 0, devid="M2")
    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EmptyAssets()), lang="en")
    resolver._panel_title_i18n = AsyncMock(return_value={})  # type: ignore[method-assign]
    resolver._static_route_symbols_for_menu = AsyncMock(return_value={})  # type: ignore[method-assign]

    diag_m1 = await resolver.panel_route_diagnostics(device_menu=0, all_panels=True, web_ui_only=True, devid="M1")
    diag_m2 = await resolver.panel_route_diagnostics(device_menu=0, all_panels=True, web_ui_only=True, devid="M2")
    assert any(row.get("accepted") for row in diag_m1)
    assert any(not row.get("accepted") for row in diag_m2)


def test_visibility_without_devid_refuses_multi_module_flatten() -> None:
    """Visibility without devid refuses merged flatten in multi-module stores."""
    store = ParamStore()
    store.upsert("P5.s0", 1, devid="M1")
    store.upsert("P5.s0", 0, devid="M2")
    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EmptyAssets()), lang="en")

    flatten_calls = {"n": 0}
    original = ParamStore.flatten

    def _counting_flatten(self: ParamStore) -> dict[str, Any]:
        flatten_calls["n"] += 1
        return original(self)

    desc = {
        "mapping": {
            "raw": {
                "status": {
                    "INVISIBLE": [
                        {
                            "group": "P5",
                            "use": "s",
                            "number": 0,
                            "bit": 0,
                        }
                    ]
                }
            }
        }
    }
    with patch.object(ParamStore, "flatten", _counting_flatten):
        # Without devid, empty overlay → bit missing → not hidden (unknown).
        visible, reason = resolver.parameter_visibility_diagnostics(desc=desc, resolved=1)
        assert flatten_calls["n"] == 0
        assert visible is True
        assert reason == "visible:default"

        # With devid=M1, bit0 of 1 → invisible.
        visible_m1, reason_m1 = resolver.parameter_visibility_diagnostics(desc=desc, resolved=1, devid="M1")
        assert visible_m1 is False
        assert reason_m1 == "hidden:invisible"
