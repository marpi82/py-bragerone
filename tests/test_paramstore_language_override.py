"""Regression tests for resolver language behavior.

These tests ensure that `ParamResolver` resolves `app.one.*` labels via assets
for any language, and never invents labels when assets cannot resolve them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

import pytest

from pybragerone.models import ParamResolver, ParamStore
from pybragerone.models.catalog import ParamMap
from pybragerone.models.param_resolver import AssetsProtocol


@dataclass(slots=True)
class _StubAssets:
    mapping: ParamMap

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        return {}

    async def get_param_mapping(self, symbols: Iterable[str]) -> dict[str, ParamMap | None]:
        return {s: (self.mapping if s == self.mapping.key else None) for s in symbols}

    async def resolve_app_one_field_label(self, *, name_key: str, lang: str) -> str | None:
        return f"FIELD[{lang}]:{name_key}"

    async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
        return f"VALUE[{lang}]:{name_key}={value}"

    async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
        return None


@pytest.mark.asyncio
async def test_status_label_and_value_use_assets_for_non_pl_languages() -> None:
    """Resolve app.one.* labels via assets for non-Polish languages."""
    store = ParamStore()

    raw = {
        "name": "app.one.boilerStatus.name",
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": 0},
            }
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
    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _StubAssets(mapping=mapping)), lang="de")

    # Provide live input value for the rule engine (P5.s0 == 1)
    store.upsert("P5.s0", 1)

    desc = await resolver.describe_symbol("STATUS_P5_0")

    assert desc["label"] == "FIELD[de]:app.one.boilerStatus.name"
    assert desc["computed_value"] == "0"
    assert desc["computed_value_label"] == "VALUE[de]:app.one.boilerStatus.name=0"


@pytest.mark.asyncio
async def test_polish_fallback_only_when_assets_do_not_resolve() -> None:
    """Do not invent Polish labels when assets cannot resolve them."""
    store = ParamStore()

    raw = {
        "name": "app.one.boilerStatus.name",
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": 14},
            }
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

    class _NoopAssets(_StubAssets):
        async def resolve_app_one_field_label(self, *, name_key: str, lang: str) -> str | None:
            return None

        async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
            return None

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _NoopAssets(mapping=mapping)), lang="pl")

    store.upsert("P5.s0", 1)
    desc = await resolver.describe_symbol("STATUS_P5_0")

    # No hardcoded Polish fallbacks: if assets do not resolve, labels remain None.
    assert desc["label"] is None
    assert desc["computed_value"] == "14"
    assert desc["computed_value_label"] is None


@pytest.mark.asyncio
async def test_enum_computed_value_label_uses_app_enum_lookup() -> None:
    """If app.one table lacks a value, fall back to app enum lookup."""
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
            }
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

    class _EnumAssets(_StubAssets):
        async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
            return None

        async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
            return f"ENUM[{lang}]:{value}"

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EnumAssets(mapping=mapping)), lang="en")
    store.upsert("P5.s0", 1)

    desc = await resolver.describe_symbol("STATUS_P5_0")

    assert desc["computed_value"] == "e.ON"
    assert desc["computed_value_label"] == "ENUM[en]:e.ON"


@pytest.mark.asyncio
async def test_enum_computed_value_can_be_evaluated_from_mapping_paths() -> None:
    """Evaluate enum outputs from mapping `paths.value` rules."""
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
                "if": [
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

    class _EnumAssets(_StubAssets):
        async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
            return None

        async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
            return f"ENUM[{lang}]:{value}"

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _EnumAssets(mapping=mapping)), lang="en")
    store.upsert("P5.s13", 1 << 1)

    desc = await resolver.describe_symbol("STATUS_P5_13")
    assert desc["computed_value"] == "e.ON"
    assert desc["computed_value_label"] == "ENUM[en]:e.ON"


@pytest.mark.asyncio
async def test_enum_computed_value_label_uses_component_i18n_table_when_app_has_no_value_table() -> None:
    """Resolve enum labels from component i18n tables when needed."""
    store = ParamStore()

    raw = {
        "name": "app.one.deviceStatus",
        "useComponent": "a.DIODE",
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": "e.OFF_MANUAL"},
            }
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

    class _ComponentAssets(_StubAssets):
        async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
            return None

        async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
            return None

        async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
            # Simulate official component-specific enum tables.
            if namespace.lower() in {"diodestate", "diodeState".lower()}:
                return {"off_manual": "Wyłączony (ręcznie)", "on": "Włączony"}
            return {}

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _ComponentAssets(mapping=mapping)), lang="pl")
    store.upsert("P5.s0", 1)

    desc = await resolver.describe_symbol("STATUS_P5_0")
    assert desc["computed_value"] == "e.OFF_MANUAL"
    assert desc["computed_value_label"] == "Wyłączony (ręcznie)"


@pytest.mark.asyncio
async def test_enum_manual_labels_can_be_resolved_from_app_one_component_state_table() -> None:
    """Resolve manual enum labels from app.one.<component>State tables."""
    store = ParamStore()

    raw = {
        "name": "app.one.deviceStatus",
        "useComponent": "a.DIODE",
        "any": [
            {
                "if": [
                    {
                        "expected": 1,
                        "operation": "equalTo",
                        "value": [{"group": "P5", "number": 0, "use": "s"}],
                    }
                ],
                "then": {"value": "e.ON_MANUAL"},
            }
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

    class _AppTableAssets(_StubAssets):
        async def resolve_app_one_value_label(self, *, name_key: str, value: str, lang: str) -> str | None:
            # The code under test derives `app.one.diodeState` from `useComponent=a.DIODE`.
            if name_key == "app.one.diodeState" and value == "e.ON_MANUAL":
                return "Włączone (ręcznie)"
            return None

        async def resolve_app_enum_value_label(self, *, value: str, lang: str) -> str | None:
            return None

        async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
            return {}

    resolver = ParamResolver(store=store, assets=cast(AssetsProtocol, _AppTableAssets(mapping=mapping)), lang="pl")
    store.upsert("P5.s0", 1)

    desc = await resolver.describe_symbol("STATUS_P5_0")
    assert desc["computed_value"] == "e.ON_MANUAL"
    assert desc["computed_value_label"] == "Włączone (ręcznie)"
