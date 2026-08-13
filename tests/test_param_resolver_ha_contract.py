"""Regression tests for the ParamResolver surface used by ha-bragerone.

These lock the config-flow / describe_symbol contract from
``docs/reference/ha_integration.rst`` and ``docs/reference/param_store_metadata.rst``.
They are not a coverage sweep of private helpers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast
from unittest.mock import AsyncMock

from pybragerone.api.client import BragerOneApiClient
from pybragerone.models import ParamResolver, ParamStore
from pybragerone.models.catalog import LiveAssetsCatalog, ParamMap, TranslationConfig
from pybragerone.models.menu import MenuResult
from pybragerone.models.param_resolver import AssetsProtocol

_DESCRIBE_TOP_LEVEL = frozenset(
    {
        "symbol",
        "pool",
        "idx",
        "chan",
        "computed_primary",
        "label",
        "unit",
        "value",
        "computed_value",
        "computed_value_label",
        "unit_code",
        "min",
        "max",
        "status",
        "mapping_origin",
        "mapping",
    }
)

_MAPPING_KEYS = frozenset(
    {
        "component_type",
        "channels",
        "paths",
        "status_conditions",
        "limits",
        "status_flags",
        "command_rules",
        "inputs",
        "values",
        "units_source",
        "origin",
        "raw",
    }
)


def _param_map(
    key: str,
    *,
    group: str | None = "P4",
    paths: dict[str, list[dict[str, Any]]] | None = None,
    raw: dict[str, Any] | None = None,
    units: Any = None,
    component_type: str | None = "u.SWITCH",
    command_rules: list[dict[str, Any]] | None = None,
    status_conditions: dict[str, list[dict[str, Any]]] | None = None,
    origin: str = "inline:test",
) -> ParamMap:
    # Upstream assets emit string flags; ParamMap's field is typed more narrowly.
    status_flags: list[Any] = ["t.INVISIBLE"]
    return ParamMap(
        key=key,
        group=group,
        paths=paths or {},
        component_type=component_type,
        units=units,
        limits={"min": 0, "max": 100},
        status_flags=cast(list[dict[str, Any]], status_flags),
        status_conditions=status_conditions,
        command_rules=command_rules or [],
        origin=origin,
        raw=raw or {},
    )


@dataclass
class _HaAssets:
    mappings: dict[str, ParamMap]
    i18n_by_namespace: dict[str, dict[str, Any]] = field(default_factory=dict)
    symbols_for_permissions: set[str] = field(default_factory=set)
    menu: MenuResult = field(default_factory=lambda: MenuResult.model_validate({"routes": []}))
    language: TranslationConfig | None = None
    mapping_calls: list[list[str]] = field(default_factory=list)
    menu_calls: int = 0

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        requested = [str(token) for token in tokens]
        self.mapping_calls.append(requested)
        return {token: self.mappings[token] for token in requested if token in self.mappings}

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
    ) -> MenuResult:
        self.menu_calls += 1
        _ = (device_menu, permissions, debug_mode)
        return self.menu

    async def list_symbols_for_permissions(self, device_menu: int, permissions: Iterable[str]) -> set[str]:
        _ = (device_menu, permissions)
        return set(self.symbols_for_permissions)

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        _ = lang
        return self.i18n_by_namespace.get(namespace, {})

    async def get_unit_descriptor(self, unit_code: Any) -> Mapping[str, Any] | None:
        _ = unit_code
        return None

    async def list_language_config(self) -> TranslationConfig | None:
        return self.language


def _resolver(assets: _HaAssets, store: ParamStore | None = None, *, lang: str | None = "en") -> ParamResolver:
    return ParamResolver(store=store or ParamStore(), assets=cast(AssetsProtocol, assets), lang=lang)


async def test_describe_symbol_keeps_documented_ha_payload_keys() -> None:
    """describe_symbol must keep the keys HA adapters and the metadata docs consume."""
    mapping = _param_map(
        "PARAM_66",
        paths={"value": [{"group": "P4", "number": 1, "use": "v"}]},
        raw={"name": "parameters.PARAM_66", "group": "P4", "value": [{"group": "P4", "number": 1, "use": "v"}]},
        command_rules=[
            {
                "logic": "any",
                "kind": "if",
                "command": "a.WRITE",
                "value": "e.ON",
                "conditions": [
                    {
                        "operation": "e.equalTo",
                        "expected": 1,
                        "targets": [{"group": "P4", "number": 2, "use": "v"}],
                    }
                ],
            }
        ],
    )
    assets = _HaAssets(
        mappings={"PARAM_66": mapping},
        i18n_by_namespace={"parameters": {"PARAM_66": "Boiler setpoint"}},
    )
    store = ParamStore()
    store.upsert("P4.v1", 42)
    store.upsert("P4.u1", 2)
    store.upsert("P4.n1", 10)
    store.upsert("P4.x1", 90)
    store.upsert("P4.s1", 8)

    desc = await _resolver(assets, store).describe_symbol("PARAM_66")

    assert set(desc) >= _DESCRIBE_TOP_LEVEL
    assert desc["symbol"] == "PARAM_66"
    assert desc["pool"] == "P4"
    assert desc["chan"] == "v"
    assert desc["idx"] == 1
    assert desc["label"] == "Boiler setpoint"
    assert desc["value"] == 42
    assert desc["unit_code"] == 2
    assert desc["min"] == 10
    assert desc["max"] == 90
    assert desc["status"] == 8
    assert desc["mapping_origin"] == "inline:test"
    assert desc["computed_primary"] is None

    mapping_out = desc["mapping"]
    assert isinstance(mapping_out, dict)
    assert set(mapping_out) >= _MAPPING_KEYS
    assert mapping_out["component_type"] == "SWITCH"
    assert mapping_out["channels"]["value"][0]["channel"] == "P4.v1"
    assert mapping_out["channels"]["value"][0]["address"] == "P4.v1"
    assert mapping_out["command_rules"][0]["command"] == "WRITE"
    assert mapping_out["command_rules"][0]["value"] == "ON"
    assert mapping_out["command_rules"][0]["conditions"][0]["targets"][0]["channel"] == "P4.v2"
    assert mapping_out["status_flags"] == ["INVISIBLE"]
    assert mapping_out["origin"] == "inline:test"


async def test_describe_symbol_status_token_overrides_mapping_address() -> None:
    """STATUS_P* tokens must describe the status channel, not a mismatched mapping address."""
    mapping = _param_map(
        "STATUS_P5_7",
        group="P4",
        paths={"value": [{"group": "P4", "number": 2, "use": "v"}]},
        raw={"name": "parameters.STATUS_P5_7", "group": "P4", "value": [{"group": "P4", "number": 2, "use": "v"}]},
    )
    assets = _HaAssets(
        mappings={"STATUS_P5_7": mapping},
        i18n_by_namespace={"parameters": {"STATUS_P5_7": "Pump status"}},
    )
    store = ParamStore()
    store.upsert("P5.s7", 3)
    store.upsert("P4.v2", 99)

    desc = await _resolver(assets, store).describe_symbol("STATUS_P5_7")
    assert desc["pool"] == "P5"
    assert desc["chan"] == "s"
    assert desc["idx"] == 7
    assert desc["value"] is None
    assert desc["status"] == 3
    assert desc["computed_primary"] == {"pool": "P4", "chan": "v", "idx": 2}
    assert desc["label"] == "Pump status"


async def test_describe_symbols_prefetches_once_and_skips_blank_duplicates() -> None:
    """Config-flow bulk describe must prefetch unique symbols in one catalog round-trip."""
    mappings = {
        "PARAM_1": _param_map("PARAM_1", raw={"name": "parameters.PARAM_1"}),
        "PARAM_2": _param_map("PARAM_2", raw={"name": "parameters.PARAM_2"}),
    }
    assets = _HaAssets(
        mappings=mappings,
        i18n_by_namespace={"parameters": {"PARAM_1": "One", "PARAM_2": "Two"}},
    )
    resolver = _resolver(assets)

    out = await resolver.describe_symbols(["PARAM_1", "", "PARAM_2", "PARAM_1"])
    assert list(out) == ["PARAM_1", "PARAM_2"]
    assert out["PARAM_1"]["label"] == "One"
    assert out["PARAM_2"]["label"] == "Two"
    assert assets.mapping_calls == [["PARAM_1", "PARAM_2"]]

    await resolver.describe_symbols(["PARAM_1", "PARAM_2"])
    assert assets.mapping_calls == [["PARAM_1", "PARAM_2"]]


async def test_merge_assets_with_permissions_matches_ha_config_flow_shape() -> None:
    """HA config flow reads symbol/label/unit from merge_assets_with_permissions()."""
    mappings = {
        "PARAM_1": _param_map("PARAM_1", raw={"name": "parameters.PARAM_1"}, units=2),
        "PARAM_2": _param_map("PARAM_2", raw={"name": "parameters.PARAM_2"}),
    }
    assets = _HaAssets(
        mappings=mappings,
        symbols_for_permissions={"PARAM_2", "PARAM_1"},
        i18n_by_namespace={
            "parameters": {"PARAM_1": "Setpoint", "PARAM_2": "Mode"},
            "units": {"2": "°C"},
        },
    )

    merged = await _resolver(assets).merge_assets_with_permissions(permissions=["READ"], device_menu=4)
    assert list(merged) == ["PARAM_1", "PARAM_2"]

    descriptors = [{"symbol": symbol, "label": desc.get("label"), "unit": desc.get("unit")} for symbol, desc in merged.items()]
    assert descriptors == [
        {"symbol": "PARAM_1", "label": "Setpoint", "unit": "°C"},
        {"symbol": "PARAM_2", "label": "Mode", "unit": None},
    ]


async def test_visibility_diagnostics_cover_ha_hide_reasons() -> None:
    """HA entity filtering depends on the documented visibility reason strings."""
    store = ParamStore()
    resolver = _resolver(_HaAssets(mappings={}), store)

    visible, reason = resolver.parameter_visibility_diagnostics(desc={}, resolved=None)
    assert visible is True
    assert reason == "visible:no-mapping"

    visible, reason = resolver.parameter_visibility_diagnostics(
        desc={"mapping": {"raw": {"value2": [{"group": "P1", "number": 0}]}}},
        resolved=None,
    )
    assert visible is False
    assert reason == "hidden:composite-component"

    store.upsert("P5.s0", 1 << 3)
    invisible_desc = {
        "mapping": {
            "paths": {
                "status": [{"group": "P5", "number": 0, "use": "s", "bit": 3, "condition": "[u.INVISIBLE]"}],
            }
        }
    }
    visible, reason = resolver.parameter_visibility_diagnostics(desc=invisible_desc, resolved=None)
    assert visible is False
    assert reason == "hidden:invisible"

    store.upsert("P5.s0", 0)
    visible, reason = resolver.parameter_visibility_diagnostics(desc=invisible_desc, resolved=None)
    assert visible is True
    assert reason == "visible:default"


async def test_resolve_value_falls_back_to_direct_when_computed_rules_miss() -> None:
    """Unmatched computed rules must still show the live register, not an empty computed value."""
    mapping = _param_map(
        "PARAM_14",
        paths={"value": [{"group": "P4", "number": 14, "use": "v"}]},
        raw={
            "any": [
                {
                    "if": [
                        {
                            "expected": 9,
                            "operation": "equalTo",
                            "value": [{"group": "P4", "number": 14, "use": "v"}],
                        }
                    ],
                    "then": {"value": "e.SPECIAL"},
                }
            ]
        },
    )
    store = ParamStore()
    store.upsert("P4.v14", 53)
    resolved = await _resolver(_HaAssets(mappings={"PARAM_14": mapping}), store).resolve_value("PARAM_14")

    assert resolved.kind == "direct"
    assert resolved.address == "P4.v14"
    assert resolved.value == 53
    assert await _resolver(_HaAssets(mappings={"PARAM_14": mapping}), store).get_value("PARAM_14") == 53


async def test_describe_by_address_uses_live_family_and_mapping_unit_fallback() -> None:
    """Address describe is what runtime HA uses when it already knows pool/idx."""
    mapping = _param_map("PARAM_66", raw={"name": "parameters.PARAM_66"}, units=2)
    assets = _HaAssets(
        mappings={"PARAM_66": mapping},
        i18n_by_namespace={"parameters": {"PARAM_66": "Setpoint"}, "units": {"2": "°C"}},
    )
    store = ParamStore()
    resolver = _resolver(assets, store)

    assert await resolver.describe("P4", 1) == (None, None, None)

    store.upsert("P4.v1", 21.5)
    label, unit, value = await resolver.describe("P4", 1, param_symbol="PARAM_66")
    assert label == "Setpoint"
    assert unit == "°C"
    assert value == 21.5


async def test_module_menu_is_cached_except_debug_mode() -> None:
    """Config-time menu fetches must be cached; debug_mode bypasses the cache."""
    assets = _HaAssets(mappings={})
    resolver = _resolver(assets)

    first = await resolver.get_module_menu(4, permissions=["READ"])
    second = await resolver.get_module_menu(4, permissions=["READ"])
    assert first is second
    assert assets.menu_calls == 1

    await resolver.get_module_menu(4, permissions=["WRITE"])
    assert assets.menu_calls == 2

    await resolver.get_module_menu(4, permissions=["READ"], debug_mode=True)
    assert assets.menu_calls == 3


async def test_from_api_and_ensure_lang_follow_documented_config_flow() -> None:
    """from_api() must wrap LiveAssetsCatalog; unset lang follows asset defaultTranslation."""
    api = cast(BragerOneApiClient, AsyncMock(spec=BragerOneApiClient))
    wired = ParamResolver.from_api(api=api, store=ParamStore(), lang="en")
    assert isinstance(wired._assets, LiveAssetsCatalog)

    assets = _HaAssets(
        mappings={},
        language=TranslationConfig(translations=[{"id": "pl", "flag": "PL"}], default_translation="pl"),
    )
    assert await _resolver(assets, lang=None).ensure_lang() == "pl"
    assert await _resolver(assets, lang="en").ensure_lang() == "en"
