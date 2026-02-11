"""Tests for unified value resolution and reactive computed-value caching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from pybragerone.models.catalog import ParamMap
from pybragerone.models.param import ParamStore


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
    """Computed values register dependencies and update reactively on upserts."""
    store = ParamStore()
    store._lang = "en"

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

    store._assets = _StubAssets(mapping=mapping)  # type: ignore[assignment]

    await store.upsert_async("P5.s0", 1)
    first = await store.resolve_value("STATUS_P5_0")
    assert first.kind == "computed"
    assert first.value == "e.ON"
    assert first.value_label == "ENUM[en]:e.ON"

    await store.upsert_async("P5.s0", 0)
    second = await store.resolve_value("STATUS_P5_0")
    assert second.kind == "computed"
    assert second.value == "e.OFF"
    assert second.value_label == "ENUM[en]:e.OFF"


@pytest.mark.asyncio
async def test_resolve_value_computed_reactive_paths_value_rules() -> None:
    """Dependencies are detected in computed rules stored under paths.value."""
    store = ParamStore()
    store._lang = "en"

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

    store._assets = _StubAssets(mapping=mapping)  # type: ignore[assignment]

    await store.upsert_async("P5.s13", 1 << 1)
    first = await store.resolve_value("STATUS_P5_13")
    assert first.kind == "computed"
    assert first.value == "e.ON"

    await store.upsert_async("P5.s13", 0)
    second = await store.resolve_value("STATUS_P5_13")
    assert second.kind == "computed"
    assert second.value == "e.OFF"
