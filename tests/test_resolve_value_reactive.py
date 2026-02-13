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

    async def get_param_mapping(self, symbols: list[str]) -> dict[str, ParamMap | None]:
        return {s: (self.mapping if s == self.mapping.key else None) for s in symbols}

    async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
        return None

    async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
        return f"ENUM[{lang}]:{value}"

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        return {}


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

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="en")

    await store.upsert_async("P5.s0", 1)
    first = await resolver.resolve_value("STATUS_P5_0")
    assert first.kind == "computed"
    assert first.value == "e.ON"
    assert first.value_label == "ENUM[en]:e.ON"

    await store.upsert_async("P5.s0", 0)
    second = await resolver.resolve_value("STATUS_P5_0")
    assert second.kind == "computed"
    assert second.value == "e.OFF"
    assert second.value_label == "ENUM[en]:e.OFF"


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
