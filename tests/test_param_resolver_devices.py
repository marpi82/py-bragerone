"""ParamResolver devices= soft-compat forwarding (#438)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, cast

from pybragerone.models.api.modules import DeviceMenuRef
from pybragerone.models.menu import MenuResult
from pybragerone.models.param import ParamStore
from pybragerone.models.param_resolver import AssetsProtocol, ParamResolver


@dataclass
class _Assets:
    menu: MenuResult = field(default_factory=lambda: MenuResult.model_validate({"routes": []}))
    menu_calls: list[dict[str, Any]] = field(default_factory=list)
    symbols: set[str] = field(default_factory=lambda: {"PARAM_1"})

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
        devices: object | None = None,
    ) -> MenuResult:
        self.menu_calls.append(
            {
                "device_menu": device_menu,
                "permissions": None if permissions is None else set(permissions),
                "debug_mode": debug_mode,
                "devices": devices,
            }
        )
        return self.menu

    async def list_symbols_for_permissions(
        self,
        device_menu: int,
        permissions: Iterable[str],
        *,
        devices: object | None = None,
    ) -> set[str]:
        _ = (device_menu, permissions, devices)
        return set(self.symbols)

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, Any]:
        _ = tokens
        return {}

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        _ = lang, namespace
        return {}

    async def get_unit_descriptor(self, unit_code: Any) -> None:
        _ = unit_code
        return None

    async def list_language_config(self) -> None:
        return None


def _resolver(assets: _Assets) -> ParamResolver:
    return ParamResolver(store=ParamStore(), assets=cast(AssetsProtocol, assets), lang="en")


async def test_get_module_menu_forwards_devices_and_separates_cache() -> None:
    """devices= is forwarded and participates in the menu cache key."""
    assets = _Assets()
    resolver = _resolver(assets)
    devices_a = [DeviceMenuRef(manuf_code=1, dev_code=2, fw="1.0")]
    devices_b = [DeviceMenuRef(manuf_code=9, dev_code=8, fw="2.0")]

    first = await resolver.get_module_menu(0, permissions=["READ"], devices=devices_a)
    second = await resolver.get_module_menu(0, permissions=["READ"], devices=devices_a)
    assert first is second
    assert assets.menu_calls == [
        {
            "device_menu": 0,
            "permissions": {"READ"},
            "debug_mode": False,
            "devices": devices_a,
        }
    ]

    await resolver.get_module_menu(0, permissions=["READ"], devices=devices_b)
    assert len(assets.menu_calls) == 2
    assert assets.menu_calls[1]["devices"] is devices_b

    await resolver.get_module_menu(0, permissions=["READ"], devices=devices_a, debug_mode=True)
    assert assets.menu_calls[-1]["debug_mode"] is True
    assert assets.menu_calls[-1]["devices"] is devices_a


async def test_build_panel_groups_and_diagnostics_forward_devices() -> None:
    """Panel helpers pass devices= through to get_module_menu."""
    assets = _Assets()
    resolver = _resolver(assets)
    devices = [DeviceMenuRef(manuf_code=67, dev_code=7, fw="2.08")]

    await resolver.build_panel_groups(device_menu=4, permissions=["P"], devices=devices)
    await resolver.panel_route_diagnostics(device_menu=4, permissions=["P"], devices=devices)
    assert all(call["devices"] is devices for call in assets.menu_calls)


async def test_merge_assets_with_permissions_forwards_devices() -> None:
    """merge_assets_with_permissions forwards devices= to list_symbols_for_permissions."""
    assets = _Assets(symbols={"PARAM_X"})
    resolver = _resolver(assets)
    devices = [DeviceMenuRef(manuf_code=1, dev_code=1, fw="0.0.0")]
    merged = await resolver.merge_assets_with_permissions(["READ"], device_menu=0, devices=devices)
    assert "PARAM_X" in merged
