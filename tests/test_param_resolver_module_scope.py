"""Regression: ParamResolver must not mix overlapping registers across modules (#502)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any, cast

import pytest

from pybragerone.models import ParamResolver, ParamStore
from pybragerone.models.catalog import ParamMap
from pybragerone.models.menu import MenuResult
from pybragerone.models.param_resolver import AssetsProtocol, ComputedValueEvaluator


class _ScopeAssets:
    """Minimal assets stub returning one ParamMap per symbol."""

    def __init__(self, mappings: dict[str, ParamMap]) -> None:
        self._mappings = mappings

    async def get_param_mapping(self, tokens: Iterable[str]) -> dict[str, ParamMap]:
        return {token: self._mappings[token] for token in tokens if token in self._mappings}

    async def get_module_menu(
        self,
        device_menu: int,
        permissions: Iterable[str] | None = None,
        *,
        debug_mode: bool = False,
        devices: object | None = None,
    ) -> MenuResult:
        _ = (device_menu, permissions, debug_mode, devices)
        return MenuResult.model_validate({"routes": []})

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


def _direct_map(symbol: str, *, group: str, number: int) -> ParamMap:
    paths = {"value": [{"group": group, "number": number, "use": "v"}]}
    return ParamMap(
        key=symbol,
        group=group,
        paths=paths,
        component_type="u.NUMBER",
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={"paths": paths},
    )


def _status_map(symbol: str, *, group: str, number: int) -> ParamMap:
    """STATUS-like rules that pick labels from a shared address selector list."""
    raw = {
        "any": [
            {
                "if": [
                    {
                        "value": [{"group": group, "number": number, "use": "v"}],
                        "operation": "equalTo",
                        "expected": 1,
                    }
                ],
                "then": "WORK",
            },
            {"else": "STOP"},
        ]
    }
    return ParamMap(
        key=symbol,
        group=group,
        paths={},
        component_type="u.STATUS",
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw=raw,
    )


def _resolver(store: ParamStore, mappings: dict[str, ParamMap]) -> ParamResolver:
    return ParamResolver(store=store, assets=cast(AssetsProtocol, _ScopeAssets(mappings)), lang="en")


async def test_resolve_value_scopes_direct_register_by_devid() -> None:
    """Same address under two modules must resolve independently (#502 minimal example)."""
    store = ParamStore()
    store.upsert("P4.v14", 0, devid="MODULE_A")
    store.upsert("P4.v14", 35, devid="MODULE_B")

    mapping = _direct_map("BURNER_POWER", group="P4", number=14)
    resolver = _resolver(store, {"BURNER_POWER": mapping})

    # Merged flatten still last-write-wins (MODULE_B).
    assert store.flatten()["P4.v14"] == 35

    a = await resolver.resolve_value("BURNER_POWER", devid="MODULE_A")
    b = await resolver.resolve_value("BURNER_POWER", devid="MODULE_B")
    assert a.value == 0
    assert b.value == 35
    assert await resolver.get_value("BURNER_POWER", devid="MODULE_A") == 0
    assert await resolver.get_value("BURNER_POWER", devid="MODULE_B") == 35


async def test_resolve_value_scopes_computed_status_by_devid() -> None:
    """Computed STATUS rules must read the module's own registers."""
    store = ParamStore()
    store.upsert("P5.v0", 0, devid="MODULE_A")
    store.upsert("P5.v0", 1, devid="MODULE_B")

    mapping = _status_map("STATUS_P5_0", group="P5", number=0)
    resolver = _resolver(store, {"STATUS_P5_0": mapping})

    a = await resolver.resolve_value("STATUS_P5_0", devid="MODULE_A")
    b = await resolver.resolve_value("STATUS_P5_0", devid="MODULE_B")
    assert a.kind == "computed"
    assert b.kind == "computed"
    assert a.value == "STOP"
    assert b.value == "WORK"


def test_compose_mapping_register_value_scopes_by_devid() -> None:
    """Multi-word compose must not pull high/low words from another module."""
    store = ParamStore()
    store.upsert("P4.v59", -27473, devid="MODULE_A")
    store.upsert("P4.v60", 0, devid="MODULE_A")
    store.upsert("P4.v59", 1, devid="MODULE_B")
    store.upsert("P4.v60", 1, devid="MODULE_B")

    mapping = ParamMap(
        key="PARAM_54_55",
        group="P4",
        paths={
            "value": [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
                {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
            ]
        },
        component_type="u.NUMBER",
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={},
    )
    assert ParamResolver.compose_mapping_register_value(store, mapping, devid="MODULE_A") == 38063
    assert ParamResolver.compose_mapping_register_value(store, mapping, devid="MODULE_B") == 65537


async def test_describe_symbol_scopes_live_value_by_devid() -> None:
    """describe_symbol live ``value`` must follow devid, not merged LWW."""
    store = ParamStore()
    store.upsert("P4.v14", 0, devid="MODULE_A")
    store.upsert("P4.v14", 35, devid="MODULE_B")
    mapping = _direct_map("BURNER_POWER", group="P4", number=14)
    resolver = _resolver(store, {"BURNER_POWER": mapping})

    desc_a = await resolver.describe_symbol("BURNER_POWER", devid="MODULE_A")
    desc_b = await resolver.describe_symbol("BURNER_POWER", devid="MODULE_B")
    assert desc_a["value"] == 0
    assert desc_b["value"] == 35

    both = await resolver.describe_symbols(["BURNER_POWER"], devid="MODULE_A")
    assert both["BURNER_POWER"]["value"] == 0


async def test_describe_scopes_family_by_devid() -> None:
    """describe(pool, idx) without devid remains LWW; with devid isolates modules."""
    store = ParamStore()
    store.upsert("P4.v14", 0, devid="MODULE_A")
    store.upsert("P4.v14", 35, devid="MODULE_B")
    resolver = _resolver(store, {})

    _label, _unit, value_lww = await resolver.describe("P4", 14)
    assert value_lww == 35
    _label_a, _unit_a, value_a = await resolver.describe("P4", 14, devid="MODULE_A")
    assert value_a == 0


def _any_branch_map(symbol: str) -> ParamMap:
    """``raw.any`` branch selection: guard on P31.s13 bit 2, then P32.v0 else P32.v221."""
    raw = {
        "name": f"parameters.{symbol}",
        "any": [
            {
                "if": [{"expected": 0, "operation": "equalTo", "value": [{"bit": 2, "group": "P31", "number": 13, "use": "s"}]}],
                "then": {"value": [{"group": "P32", "number": 0, "use": "v"}]},
            },
            {"else": {"value": [{"group": "P32", "number": 221, "use": "v"}]}},
        ],
    }
    return ParamMap(
        key=symbol,
        group="P32",
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


def _seed_branch_modules(store: ParamStore) -> None:
    # MODULE_A guard bit 2 clear -> ``then`` (P32.v0); MODULE_B guard bit 2 set -> ``else`` (P32.v221).
    store.upsert("P31.s13", 0, devid="MODULE_A")
    store.upsert("P32.v0", 215, devid="MODULE_A")
    store.upsert("P32.v221", 111, devid="MODULE_A")
    store.upsert("P31.s13", 4, devid="MODULE_B")
    store.upsert("P32.v0", 999, devid="MODULE_B")
    store.upsert("P32.v221", 190, devid="MODULE_B")


async def test_resolve_value_raw_any_branch_selection_scoped_by_devid() -> None:
    """Branch guard + selected register both come from the requested module (flatten_for_devid)."""
    store = ParamStore()
    _seed_branch_modules(store)
    resolver = _resolver(store, {"CARD": _any_branch_map("CARD")})

    a = await resolver.resolve_value("CARD", devid="MODULE_A")
    b = await resolver.resolve_value("CARD", devid="MODULE_B")
    assert (a.address, a.value) == ("P32.v0", 215)
    assert (b.address, b.value) == ("P32.v221", 190)

    # Legacy unscoped read keeps merged last-write-wins semantics (guard from MODULE_B).
    legacy = await resolver.resolve_value("CARD")
    assert legacy.address == "P32.v221"


async def test_resolve_value_concurrent_modules_do_not_share_devid_state() -> None:
    """Interleaved resolves for two modules on one resolver must each see their own registers."""
    store = ParamStore()
    _seed_branch_modules(store)
    store.upsert("P5.v0", 0, devid="MODULE_A")
    store.upsert("P5.v0", 1, devid="MODULE_B")
    resolver = _resolver(
        store,
        {
            "CARD": _any_branch_map("CARD"),
            "STATUS_P5_0": _status_map("STATUS_P5_0", group="P5", number=0),
        },
    )

    results = await asyncio.gather(
        *(
            resolver.resolve_value(sym, devid=dev)
            for _ in range(5)
            for sym in ("CARD", "STATUS_P5_0")
            for dev in ("MODULE_A", "MODULE_B")
        )
    )
    seen = {(r.symbol, r.value) for r in results}
    assert seen == {("CARD", 215), ("CARD", 190), ("STATUS_P5_0", "STOP"), ("STATUS_P5_0", "WORK")}
    # Order per iteration: CARD A/B, STATUS A/B.
    for idx in range(0, len(results), 4):
        assert [r.value for r in results[idx : idx + 4]] == [215, 190, "STOP", "WORK"]


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
async def test_blank_devid_is_unscoped_everywhere(blank: str) -> None:
    """Empty / whitespace devid behaves like ``None`` (merged LWW), not an empty module bucket."""
    store = ParamStore()
    store.upsert("P4.v14", 0, devid="MODULE_A")
    store.upsert("P4.v14", 35, devid="MODULE_B")
    store.upsert("P5.v0", 1, devid="MODULE_B")
    store.upsert("P4.v59", 1, devid="MODULE_B")
    store.upsert("P4.v60", 1, devid="MODULE_B")
    resolver = _resolver(
        store,
        {
            "BURNER_POWER": _direct_map("BURNER_POWER", group="P4", number=14),
            "STATUS_P5_0": _status_map("STATUS_P5_0", group="P5", number=0),
            "CARD": _any_branch_map("CARD"),
        },
    )
    assert (await resolver.resolve_value("BURNER_POWER", devid=blank)).value == 35
    assert (await resolver.resolve_value("STATUS_P5_0", devid=blank)).value == "WORK"
    assert (await resolver.describe_symbol("BURNER_POWER", devid=blank))["value"] == 35
    assert (await resolver.describe("P4", 14, devid=blank))[2] == 35
    # CARD with no P31.s13 anywhere still resolves through the unscoped (merged) path without error.
    _seed_branch_modules(store)
    assert (await resolver.resolve_value("CARD", devid=blank)).address == "P32.v221"

    # Public evaluator / compose entry points normalize blank devid too.
    evaluator = ComputedValueEvaluator(store)
    assert evaluator.evaluate(_status_map("S", group="P5", number=0).raw, devid=blank) == "WORK"
    compose_map = ParamMap(
        key="PARAM_54_55",
        group="P4",
        paths={
            "value": [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
                {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
            ]
        },
        component_type="u.NUMBER",
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={},
    )
    assert ParamResolver.compose_mapping_register_value(store, compose_map, devid=blank) == 65537


async def test_unknown_devid_does_not_fall_back_to_other_module() -> None:
    """A non-empty devid with no bucket must yield no value rather than another module's data."""
    store = ParamStore()
    store.upsert("P4.v14", 35, devid="MODULE_B")
    store.upsert("P5.v0", 1, devid="MODULE_B")
    resolver = _resolver(
        store,
        {
            "BURNER_POWER": _direct_map("BURNER_POWER", group="P4", number=14),
            "STATUS_P5_0": _status_map("STATUS_P5_0", group="P5", number=0),
        },
    )
    assert (await resolver.resolve_value("BURNER_POWER", devid="MISSING")).value is None
    assert (await resolver.resolve_value("STATUS_P5_0", devid="MISSING")).value == "STOP"


async def test_resolve_value_devid_flatten_only_on_raw_any(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scoped direct/computed resolves never snapshot the store; only ``raw.any`` uses flatten_for_devid."""
    store = ParamStore()
    _seed_branch_modules(store)
    store.upsert("P4.v14", 35, devid="MODULE_B")
    resolver = _resolver(
        store,
        {
            "BURNER_POWER": _direct_map("BURNER_POWER", group="P4", number=14),
            "CARD": _any_branch_map("CARD"),
        },
    )
    calls: list[str] = []
    orig_flat, orig_scoped = ParamStore.flatten, ParamStore.flatten_for_devid

    def _flat(self: ParamStore) -> dict[str, Any]:
        calls.append("flatten")
        return orig_flat(self)

    def _scoped(self: ParamStore, devid: str) -> dict[str, Any]:
        calls.append(f"scoped:{devid}")
        return orig_scoped(self, devid)

    monkeypatch.setattr(ParamStore, "flatten", _flat)
    monkeypatch.setattr(ParamStore, "flatten_for_devid", _scoped)

    await resolver.resolve_value("BURNER_POWER", devid="MODULE_B")
    assert calls == []
    await resolver.resolve_value("CARD", devid="MODULE_B")
    assert calls == ["scoped:MODULE_B"]
