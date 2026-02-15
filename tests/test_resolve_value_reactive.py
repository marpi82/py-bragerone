"""Tests for unified value resolution and reactive computed-value caching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from pybragerone.models import ParamResolver, ParamStore
from pybragerone.models.catalog import ParamMap
from pybragerone.models.param_resolver import AssetsProtocol


@dataclass(slots=True)
class _StubAssets:
    mapping: ParamMap
    i18n_by_namespace: dict[str, dict[str, Any]] | None = None
    unit_descriptors: dict[str, dict[str, Any]] | None = None

    async def get_param_mapping(self, symbols: list[str]) -> dict[str, ParamMap | None]:
        return {s: (self.mapping if s == self.mapping.key else None) for s in symbols}

    async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
        return None

    async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
        return None

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        if not isinstance(self.i18n_by_namespace, dict):
            return {}
        return self.i18n_by_namespace.get(namespace, {})

    async def get_unit_descriptor(self, unit_code: Any) -> dict[str, Any] | None:
        if not isinstance(self.unit_descriptors, dict):
            return None
        key = str(unit_code).strip()
        entry = self.unit_descriptors.get(key)
        return dict(entry) if isinstance(entry, dict) else None


@pytest.mark.asyncio
async def test_resolve_value_computed_reactive_any_rules() -> None:
    """Computed values reflect current inputs on subsequent upserts."""
    store = ParamStore()

    raw = {
        "name": "app.one.devicePumpStatus",
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": "e.ON"},
            },
            {
                "elseif": [
                    {
                        "expected": 0,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": "e.OFF"},
            },
        ],
    }

    mapping = ParamMap(
        key="STATUS_P5_0",
        group=None,
        paths={},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw=raw,
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                unit_descriptors={
                    "9996": {
                        "options": {
                            "[kn.ON]": "app.one.diodeState.on",
                            "[kn.OFF]": "app.one.diodeState.off",
                        }
                    }
                },
                i18n_by_namespace={
                    "app": {
                        "one": {
                            "diodeState": {
                                "on": "Włączone",
                                "off": "Wyłączone",
                            }
                        }
                    }
                },
            ),
        ),
        lang="en",
    )

    await store.upsert_async("P5.u0", 9996)
    await store.upsert_async("P5.s0", 1)
    first = await resolver.resolve_value("STATUS_P5_0")
    assert first.kind == "computed"
    assert first.value == "e.ON"
    assert first.value_label == "Włączone"

    await store.upsert_async("P5.s0", 0)
    second = await resolver.resolve_value("STATUS_P5_0")
    assert second.kind == "computed"
    assert second.value == "e.OFF"
    assert second.value_label == "Wyłączone"


@pytest.mark.asyncio
async def test_resolve_value_computed_reactive_paths_value_rules() -> None:
    """Computed rules stored under paths.value are evaluated correctly."""
    store = ParamStore()

    raw = {"name": "app.one.devicePumpStatus"}
    paths = {
        "value": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "t.equalTo",
                        "value": [{"group": "P5", "number": 13, "use": "s", "bit": 1}],
                    }
                ],
                "then": "e.ON",
            },
            {
                "elseif": [
                    {
                        "expected": 0,
                        "operation": "t.equalTo",
                        "value": [{"group": "P5", "number": 13, "use": "s", "bit": 1}],
                    }
                ],
                "then": "e.OFF",
            },
        ]
    }

    mapping = ParamMap(
        key="STATUS_P5_13",
        group=None,
        paths=paths,
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw=raw,
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P5.s13", 1 << 1)
    first = await resolver.resolve_value("STATUS_P5_13")
    assert first.kind == "computed"
    assert first.value == "e.ON"

    await store.upsert_async("P5.s13", 0)
    second = await resolver.resolve_value("STATUS_P5_13")
    assert second.kind == "computed"
    assert second.value == "e.OFF"


@pytest.mark.asyncio
async def test_resolve_value_direct_from_param_map_pool_chan_idx_shape() -> None:
    """Direct values resolve when ParamMap uses pool/chan/idx fields.

    This matches the ParamMap shapes produced by LiveAssetsCatalog ParamMap parsing.
    """
    store = ParamStore()

    raw = {
        "group": "P4",
        "use": {
            "v": {"pool": "P4", "chan": "v", "idx": 1},
        },
    }

    mapping = ParamMap(
        key="PARAM_66",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 1}]},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw=raw,
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P4.v1", 42)
    value = await resolver.resolve_value("PARAM_66")
    assert value.kind == "direct"
    assert value.address == "P4.v1"
    assert value.value == 42


@pytest.mark.asyncio
async def test_resolve_value_direct_uses_unit_dict_for_value_label() -> None:
    """Direct values map to labels when unit metadata is an enum dictionary."""
    store = ParamStore()

    raw = {
        "group": "P4",
        "use": {
            "v": {"pool": "P4", "chan": "v", "idx": 1},
        },
    }

    mapping = ParamMap(
        key="PARAM_66",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 1}]},
        component_type=None,
        units={"0": "Off", "1": "On"},
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw=raw,
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P4.v1", 1)
    value = await resolver.resolve_value("PARAM_66")

    assert value.kind == "direct"
    assert value.value == 1
    assert value.value_label == "On"
    assert value.unit == {"0": "Off", "1": "On"}


@pytest.mark.asyncio
async def test_resolve_value_computed_falls_back_to_unit_dict_for_label() -> None:
    """Computed values use unit dict mapping when assets do not provide labels."""
    store = ParamStore()

    raw = {
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": 1},
            }
        ],
    }

    mapping = ParamMap(
        key="STATUS_P5_0",
        group=None,
        paths={},
        component_type=None,
        units={"0": "Stopped", "1": "Running"},
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw=raw,
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P5.s0", 1)
    value = await resolver.resolve_value("STATUS_P5_0")

    assert value.kind == "computed"
    assert value.value == "1"
    assert value.value_label == "Running"
    assert value.unit == {"0": "Stopped", "1": "Running"}


@pytest.mark.asyncio
async def test_is_parameter_visible_like_app_hides_t_invisible() -> None:
    """Visibility helper hides params when [t.INVISIBLE] resolves to true."""
    store = ParamStore()

    mapping = ParamMap(
        key="PARAM_66",
        group="P6",
        paths={
            "value": [{"group": "P6", "number": 66, "use": "v"}],
            "status": [
                {
                    "if": [
                        {
                            "expected": 1,
                            "operation": "e.equalTo",
                            "value": [{"group": "P6", "number": 34, "use": "v"}],
                        }
                    ],
                    "then": "!1",
                    "condition": "[t.INVISIBLE]",
                },
                {"else": "!0", "condition": "[t.INVISIBLE]"},
            ],
        },
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "group": "P6",
            "use": {
                "v": {"group": "P6", "number": 66, "use": "v"},
            },
        },
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P6.v66", 12)
    await store.upsert_async("P6.v34", 1)

    desc = await resolver.describe_symbol("PARAM_66")
    resolved = await resolver.resolve_value("PARAM_66")
    assert resolver.is_parameter_visible_like_app(desc=desc, resolved=resolved, flat_values=store.flatten()) is True

    await store.upsert_async("P6.v34", 0)
    assert resolver.is_parameter_visible_like_app(desc=desc, resolved=resolved, flat_values=store.flatten()) is False


@pytest.mark.asyncio
async def test_is_parameter_visible_like_app_hides_device_unavailable_status() -> None:
    """Visibility helper hides status params when [o.DEVICE_AVAILABLE] bit is false."""
    store = ParamStore()

    mapping = ParamMap(
        key="STATUS_P5_19",
        group="P5",
        paths={
            "value": [{"group": "P5", "number": 19, "use": "s"}],
            "status": [{"group": "P5", "number": 19, "use": "s", "bit": 0, "condition": "[o.DEVICE_AVAILABLE]"}],
        },
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={},
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P5.s19", 1)
    desc = await resolver.describe_symbol("STATUS_P5_19")
    resolved = await resolver.resolve_value("STATUS_P5_19")
    assert resolver.is_parameter_visible_like_app(desc=desc, resolved=resolved, flat_values=store.flatten()) is True

    await store.upsert_async("P5.s19", 0)
    assert resolver.is_parameter_visible_like_app(desc=desc, resolved=resolved, flat_values=store.flatten()) is False

    visible, reason = resolver.parameter_visibility_diagnostics(desc=desc, resolved=resolved, flat_values=store.flatten())
    assert visible is False
    assert reason == "hidden:device-unavailable"


@pytest.mark.asyncio
async def test_is_parameter_visible_like_app_keeps_write_like_without_value() -> None:
    """Visibility helper keeps command-like params visible even without current value."""
    store = ParamStore()

    mapping = ParamMap(
        key="URUCHOMIENIE_KOTLA",
        group=None,
        paths={},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={},
    )

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    desc = await resolver.describe_symbol("URUCHOMIENIE_KOTLA")
    resolved = await resolver.resolve_value("URUCHOMIENIE_KOTLA")
    assert resolved.value is None
    assert resolver.is_parameter_visible_like_app(desc=desc, resolved=resolved, flat_values=store.flatten()) is True
    visible, reason = resolver.parameter_visibility_diagnostics(desc=desc, resolved=resolved, flat_values=store.flatten())
    assert visible is True
    assert reason.startswith("visible:")


@pytest.mark.asyncio
async def test_resolve_value_applies_unit_descriptor_transform_and_alias_text() -> None:
    """Direct values apply units descriptor transform and use descriptor text target as unit label."""
    store = ParamStore()

    mapping = ParamMap(
        key="PARAM_14",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 14}]},
        component_type=None,
        units=49,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "group": "P4",
            "use": {
                "v": {"pool": "P4", "chan": "v", "idx": 14},
            },
        },
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                unit_descriptors={
                    "49": {
                        "text": "units.31",
                        "value": "e => Number((e * .1).toFixed(1))",
                        "valuePrepare": "e => e / .1",
                    }
                },
                i18n_by_namespace={
                    "units": {
                        "31": "kW",
                        "49": "WRONG_DIRECT_MAPPING",
                    }
                },
            ),
        ),
        lang="en",
    )

    await store.upsert_async("P4.v14", 53)
    value = await resolver.resolve_value("PARAM_14")

    assert value.kind == "direct"
    assert value.address == "P4.v14"
    assert value.value == 5.3
    assert value.unit == "kW"

    await store.upsert_async("P4.v14", "154")
    value_from_text = await resolver.resolve_value("PARAM_14")
    assert value_from_text.value == 15.4
    assert value_from_text.unit == "kW"


@pytest.mark.asyncio
async def test_resolve_value_label_resolves_nested_units_token_reference() -> None:
    """Value label resolves units token references (e.g. units.8.22) to final text."""
    store = ParamStore()

    mapping = ParamMap(
        key="PARAM_66",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 1}]},
        component_type=None,
        units=8,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "group": "P4",
            "use": {
                "v": {"pool": "P4", "chan": "v", "idx": 1},
            },
        },
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                unit_descriptors={
                    "8": {
                        "options": {
                            "22": "units.2200.1",
                        }
                    }
                },
                i18n_by_namespace={
                    "units": {
                        "2200": {
                            "1": "Histereza trybu Eco",
                        },
                    }
                },
            ),
        ),
        lang="en",
    )

    await store.upsert_async("P4.v1", 22)
    value = await resolver.resolve_value("PARAM_66")

    assert value.kind == "direct"
    assert value.address == "P4.v1"
    assert value.value == 22
    assert value.value_label == "Histereza trybu Eco"


@pytest.mark.asyncio
async def test_resolve_value_label_resolves_app_lang_token_reference() -> None:
    """Value label resolves app.lang.* token references from options mapping."""
    store = ParamStore()

    mapping = ParamMap(
        key="PARAM_200",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 200}]},
        component_type=None,
        units=37,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "group": "P4",
            "use": {
                "v": {"pool": "P4", "chan": "v", "idx": 200},
            },
        },
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                unit_descriptors={
                    "37": {
                        "options": {
                            "9": "app.lang.en",
                            "5": "app.lang.ru",
                        }
                    }
                },
                i18n_by_namespace={
                    "app": {
                        "lang": {
                            "en": "English",
                            "ru": "Русский",
                        }
                    }
                },
            ),
        ),
        lang="en",
    )

    await store.upsert_async("P4.v200", 5)
    value = await resolver.resolve_value("PARAM_200")
    assert value.value_label == "Русский"


@pytest.mark.asyncio
async def test_resolve_value_applies_unit_66_time_transform() -> None:
    """Unit 66 function-style transform should produce translated zero label or HH:MM."""
    store = ParamStore()

    mapping = ParamMap(
        key="PARAM_300",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 300}]},
        component_type=None,
        units=66,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "group": "P4",
            "use": {
                "v": {"pool": "P4", "chan": "v", "idx": 300},
            },
        },
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                unit_descriptors={
                    "66": {
                        "text": "units.0",
                        "value": (
                            'e => { if (e === 0) return "units.202.0"; const t = (e - 1) * 10, '
                            "n = Math.floor(t / 60), r = t % 60; "
                            'return `${n.toString().padStart(2, "0")}:${r.toString().padStart(2, "0")}`; }'
                        ),
                    }
                },
                i18n_by_namespace={
                    "units": {
                        "0": "",
                        "202": {
                            "0": "Wyłączony",
                        },
                    }
                },
            ),
        ),
        lang="en",
    )

    await store.upsert_async("P4.v300", 0)
    zero_val = await resolver.resolve_value("PARAM_300")
    assert zero_val.value == "Wyłączony"
    assert zero_val.unit == ""

    await store.upsert_async("P4.v300", 7)
    time_val = await resolver.resolve_value("PARAM_300")
    assert time_val.value == "01:00"


@pytest.mark.asyncio
async def test_resolve_label_uses_mapping_name_parameters_namespace() -> None:
    """Label should resolve from mapping raw `name` token in `parameters.*` namespace."""
    store = ParamStore()

    mapping = ParamMap(
        key="PARAM_150",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 150}]},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "name": "parameters.PARAM_150",
            "group": "P4",
            "use": {
                "v": {"pool": "P4", "chan": "v", "idx": 150},
            },
        },
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                i18n_by_namespace={
                    "parameters": {
                        "PARAM_150": "Status kotła",
                    }
                },
            ),
        ),
        lang="pl",
    )

    label = await resolver.resolve_label("PARAM_150")
    assert label == "Status kotła"


@pytest.mark.asyncio
async def test_resolve_label_uses_mapping_name_app_namespace() -> None:
    """Label should resolve from mapping raw `name` token in nested `app.*` namespace."""
    store = ParamStore()

    mapping = ParamMap(
        key="URUCHOMIENIE_KOTLA",
        group="P4",
        paths={"value": [{"pool": "P4", "chan": "v", "idx": 151}]},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={
            "name": "app.one.parameters.URUCHOMIENIE_KOTLA",
            "group": "P4",
            "use": {
                "v": {"pool": "P4", "chan": "v", "idx": 151},
            },
        },
    )

    resolver = ParamResolver(
        store=store,
        assets=cast(
            AssetsProtocol,
            _StubAssets(
                mapping=mapping,
                i18n_by_namespace={
                    "app": {
                        "one": {
                            "parameters": {
                                "URUCHOMIENIE_KOTLA": "Uruchomienie kotła",
                            }
                        }
                    }
                },
            ),
        ),
        lang="pl",
    )

    label = await resolver.resolve_label("URUCHOMIENIE_KOTLA")
    assert label == "Uruchomienie kotła"
