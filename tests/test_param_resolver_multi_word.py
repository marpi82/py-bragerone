"""Regression tests for multi-register (multi-word) value composition (#327).

``PARAM_P4_59`` ("Czas pracy podajnika") addresses two consecutive registers as an
address-selector list rather than a single value channel::

    [
        {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
        {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
    ]

Before the fix, ``_mapping_has_computed_rules`` treated this list as STATUS
``if``/``elseif`` rules (any non-empty ``raw["value"]`` list), routed it through
``ComputedValueEvaluator`` (which returns ``None`` for it), and the direct-value
fallback only read the primary register — producing the signed int16 register
word (``-27473``) instead of the web UI's composed unsigned value (``38063``).
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from pybragerone.models import ParamResolver, ParamStore
from pybragerone.models.catalog import ParamMap
from pybragerone.models.param_resolver import AssetsProtocol


def _multi_word_mapping(*, key: str = "PARAM_P4_59", convert: str | None = "_0x35dce1") -> ParamMap:
    low: dict[str, Any] = {"group": "P4", "number": 59, "use": "v"}
    high: dict[str, Any] = {"group": "P4", "number": 60, "use": "v", "times": 65536}
    if convert:
        low["convert"] = convert
        high["convert"] = convert
    value_paths = [low, high]
    return ParamMap(
        key=key,
        group="P4",
        paths={"value": value_paths},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={"name": "parameters.PARAM_P4_59", "value": value_paths},
    )


class _StubAssets:
    def __init__(self, mapping: ParamMap) -> None:
        self.mapping = mapping

    async def get_param_mapping(self, tokens: Any) -> dict[str, ParamMap]:
        # Match AssetsProtocol: omit unresolved tokens rather than mapping them to None.
        return {token: self.mapping for token in tokens if token == self.mapping.key}

    async def get_module_menu(self, device_menu: int, permissions: Any = None, *, debug_mode: bool = False) -> Any:
        raise NotImplementedError

    async def list_symbols_for_permissions(self, device_menu: int, permissions: Any) -> set[str]:
        return set()

    async def get_i18n(self, lang: str, namespace: str) -> dict[str, Any]:
        return {}

    async def get_unit_descriptor(self, unit_code: Any) -> dict[str, Any] | None:
        return None

    async def list_language_config(self) -> Any:
        return None


def _resolver(mapping: ParamMap, store: ParamStore | None = None) -> ParamResolver:
    return ParamResolver(store=store or ParamStore(), assets=cast(AssetsProtocol, _StubAssets(mapping)), lang="en")


def test_is_address_selector_list_rejects_status_rules_and_accepts_selectors() -> None:
    """Address-selector lists and STATUS if/then rule lists must not be confused."""
    status_rules = [
        {
            "if": [{"expected": 1, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
            "then": {"value": "e.ON"},
        },
        {
            "elseif": [{"expected": 0, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
            "then": {"value": "e.OFF"},
        },
    ]
    address_selectors = [
        {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
        {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
    ]

    assert ParamResolver._is_status_rule_list(status_rules) is True
    assert ParamResolver._is_address_selector_list(status_rules) is False

    assert ParamResolver._is_status_rule_list(address_selectors) is False
    assert ParamResolver._is_address_selector_list(address_selectors) is True

    assert ParamResolver._is_address_selector_list([]) is False
    assert ParamResolver._is_address_selector_list("not-a-list") is False


def test_mapping_has_computed_rules_false_for_address_selectors_true_for_status() -> None:
    """#327: address-selector value lists are not STATUS computed rules."""
    multi_word = _multi_word_mapping()
    assert ParamResolver._mapping_has_computed_rules(multi_word) is False

    status_mapping = ParamMap(
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
        raw={
            "any": [
                {
                    "if": [{"expected": 1, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
                    "then": {"value": "e.ON"},
                }
            ]
        },
    )
    assert ParamResolver._mapping_has_computed_rules(status_mapping) is True

    status_paths_mapping = ParamMap(
        key="STATUS_P5_13",
        group=None,
        paths={
            "value": [
                {
                    "if": [{"expected": 1, "operation": "t.equalTo", "value": [{"group": "P5", "number": 13, "use": "s"}]}],
                    "then": "e.ON",
                }
            ]
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
    assert ParamResolver._mapping_has_computed_rules(status_paths_mapping) is True


def test_compose_mapping_register_value_web_ui_regression() -> None:
    """P4.v59=-27473 (int16), P4.v60=0 must compose to the web UI's 38063, not -27473."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)
    store.upsert("P4.v60", 0)

    mapping = _multi_word_mapping()
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == 38063


def test_compose_mapping_register_value_accepts_plain_dict_ha_descriptor_shape() -> None:
    """HA caches mapping details as a plain dict with paths/raw/channels keys."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)
    store.upsert("P4.v60", 0)

    mapping = _multi_word_mapping()
    ha_style_mapping = {
        "paths": mapping.paths,
        "raw": mapping.raw,
        "channels": {"value": [{"address": "P4.v59", "channel": "P4.v59"}]},
    }
    result = ParamResolver.compose_mapping_register_value(store, ha_style_mapping)
    assert result == 38063


def test_compose_mapping_register_value_high_word_nonzero() -> None:
    """High word contributes times=65536 once uint16-coerced via convert."""
    store = ParamStore()
    store.upsert("P4.v59", 1)
    store.upsert("P4.v60", 1)

    mapping = _multi_word_mapping()
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == 65537


def test_compose_mapping_register_value_preserves_sign_without_convert() -> None:
    """Without a convert entry, negative words are not forced into uint16."""
    store = ParamStore()
    store.upsert("P4.v59", -5)
    store.upsert("P4.v60", 0)

    mapping = _multi_word_mapping(convert=None)
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == -5


def test_compose_mapping_register_value_returns_none_for_status_rule_lists() -> None:
    """STATUS if/then rule lists never compose to a register value."""
    store = ParamStore()
    store.upsert("P5.s0", 1)

    raw = {
        "any": [
            {
                "if": [{"expected": 1, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
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
    assert ParamResolver.compose_mapping_register_value(store, mapping) is None


def test_compose_mapping_register_value_returns_none_without_store_values() -> None:
    """No register words present in the store yields None, not zero."""
    store = ParamStore()
    mapping = _multi_word_mapping()
    assert ParamResolver.compose_mapping_register_value(store, mapping) is None


def test_compose_mapping_register_value_returns_none_for_non_selector_mapping() -> None:
    """Unrelated dicts / None mappings return None rather than raising."""
    store = ParamStore()
    assert ParamResolver.compose_mapping_register_value(store, None) is None
    assert ParamResolver.compose_mapping_register_value(store, {"paths": {}, "raw": {}}) is None
    assert ParamResolver.compose_mapping_register_value(store, "not-a-mapping") is None


def test_compose_mapping_register_value_falls_back_to_raw_when_paths_empty() -> None:
    """When ``paths`` carries no selector list, the ``raw["value"]`` selectors are used instead."""
    store = ParamStore()
    store.upsert("P4.v59", 38063)
    store.upsert("P4.v60", 0)

    ha_style_mapping = {
        "paths": {"value": []},
        "raw": {
            "value": [
                {"group": "P4", "number": 59, "use": "v"},
                {"group": "P4", "number": 60, "use": "v", "times": 65536},
            ]
        },
    }
    result = ParamResolver.compose_mapping_register_value(store, ha_style_mapping)
    assert result == 38063


def test_compose_mapping_register_value_falls_back_to_raw_when_paths_not_mapping() -> None:
    """Non-mapping ``paths`` must not block ``raw['value']`` multi-register compose."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)
    store.upsert("P4.v60", 0)

    raw_only = {
        "raw": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
                {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
            ]
        },
    }
    assert ParamResolver.compose_mapping_register_value(store, raw_only) == 38063

    paths_none = {
        "paths": None,
        "raw": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
                {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
            ]
        },
    }
    assert ParamResolver.compose_mapping_register_value(store, paths_none) == 38063


def test_compose_mapping_register_value_skips_plain_single_selector() -> None:
    """Plain single ``{group,number,use}`` paths must not compose (preserves float halves)."""
    store = ParamStore()
    store.upsert("P7.v12", 40.5)

    mapping = {
        "paths": {"value": [{"group": "P7", "number": 12, "use": "v"}]},
        "raw": {},
    }
    assert ParamResolver.compose_mapping_register_value(store, mapping) is None
    assert ParamResolver._address_selectors_need_compose(mapping["paths"]["value"]) is False


def test_address_selectors_need_compose_empty_and_single_convert() -> None:
    """Zero selectors skip compose; a lone convert selector still needs it."""
    assert ParamResolver._address_selectors_need_compose([]) is False
    assert ParamResolver._address_selectors_need_compose([{"not": "a-selector"}]) is False
    assert (
        ParamResolver._address_selectors_need_compose(
            [{"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"}],
        )
        is True
    )


def test_compose_mapping_register_value_single_convert_selector() -> None:
    """Single-selector maps with convert still uint16-coerce the register word."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
            ]
        },
        "raw": {},
    }
    assert ParamResolver.compose_mapping_register_value(store, mapping) == 38063


def test_compose_mapping_register_value_preserves_fractional_word_without_convert() -> None:
    """Without convert, fractional store words stay floats under a times multiplier."""
    store = ParamStore()
    store.upsert("P4.v59", 3.5)

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "times": 2},
            ]
        },
        "raw": {},
    }
    assert ParamResolver.compose_mapping_register_value(store, mapping) == 7.0


def test_compose_mapping_register_value_returns_float_for_fractional_times() -> None:
    """Non-integer ``times`` multipliers must keep a float composed value."""
    store = ParamStore()
    store.upsert("P4.v59", 3)

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "times": 0.5},
            ]
        },
        "raw": {},
    }
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == 1.5


def test_compose_mapping_register_value_ignores_bool_times() -> None:
    """Boolean ``times`` does not trigger compose (``bool`` subclasses ``int``)."""
    store = ParamStore()
    store.upsert("P4.v59", 7)

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "times": True},
            ]
        },
        "raw": {},
    }
    assert ParamResolver.compose_mapping_register_value(store, mapping) is None


def test_compose_mapping_register_value_skips_malformed_selector_entries() -> None:
    """Non-mapping and malformed selector entries are skipped, valid ones still contribute."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)
    store.upsert("P4.v60", 0)

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v", "convert": "_0x35dce1"},
                "not-a-dict",
                {"group": "P4", "use": "v"},  # missing number
                {"group": 4, "number": 60, "use": "v"},  # group not a string
                {"group": "P4", "number": 60, "use": "v", "convert": "_0x35dce1", "times": 65536},
            ]
        },
        "raw": {},
    }
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == 38063


def test_compose_mapping_register_value_skips_missing_family_and_non_numeric_word() -> None:
    """A selector with no live family and one with a non-numeric raw word are both skipped."""
    store = ParamStore()
    store.upsert("P4.v59", 38063)
    store.upsert("P4.v61", "not-a-number")

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v"},
                {"group": "P4", "number": 60, "use": "v"},  # no family at all
                {"group": "P4", "number": 61, "use": "v"},  # family exists, non-numeric word
            ]
        },
        "raw": {},
    }
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == 38063


def test_compose_mapping_register_value_skips_channel_missing_on_existing_family() -> None:
    """A selector whose family exists but the requested channel is unset is skipped, not zeroed."""
    store = ParamStore()
    store.upsert("P4.u59", 1)  # unit channel set, but no "v" channel yet
    store.upsert("P4.v60", 5)

    mapping = {
        "paths": {
            "value": [
                {"group": "P4", "number": 59, "use": "v"},
                {"group": "P4", "number": 60, "use": "v"},
            ]
        },
        "raw": {},
    }
    result = ParamResolver.compose_mapping_register_value(store, mapping)
    assert result == 5


def test_is_address_selector_entry_rejects_non_mapping() -> None:
    """Non-mapping entries (e.g. plain strings) are never address selectors."""
    assert ParamResolver._is_address_selector_entry("not-a-dict") is False
    assert ParamResolver._is_address_selector_entry(None) is False


def test_mapping_has_computed_rules_handles_none_and_raw_value_status_rules() -> None:
    """None mapping is not computed; STATUS rules living directly under raw['value'] still count."""
    assert ParamResolver._mapping_has_computed_rules(None) is False

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
        raw={
            "value": [
                {
                    "if": [{"expected": 1, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
                    "then": {"value": "e.ON"},
                }
            ]
        },
    )
    assert ParamResolver._mapping_has_computed_rules(mapping) is True


@pytest.mark.asyncio
async def test_resolve_value_composes_multi_word_register_value() -> None:
    """End-to-end: resolve_value must return the composed web UI value, not the raw int16 word."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)
    store.upsert("P4.v60", 0)

    resolver = _resolver(_multi_word_mapping(), store)
    resolved = await resolver.resolve_value("PARAM_P4_59")

    assert resolved.kind == "direct"
    assert resolved.value == 38063


@pytest.mark.asyncio
async def test_resolve_value_composes_and_resolves_string_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the numeric transform yields a string, resolve_value must still i18n-resolve it."""
    store = ParamStore()
    store.upsert("P4.v59", -27473)
    store.upsert("P4.v60", 0)

    resolver = _resolver(_multi_word_mapping(), store)

    def _string_display(_self_or_cls: object, raw_value: Any, _raw_expr: Any) -> str:
        assert raw_value == 38063
        return "units.202.0"

    async def _resolve_token(_self: ParamResolver, label: str | None) -> str | None:
        if label == "units.202.0":
            return "Off"
        if isinstance(label, str) and label.strip():
            return label.strip()
        return None

    monkeypatch.setattr(ParamResolver, "_apply_numeric_transform", _string_display)
    monkeypatch.setattr(ParamResolver, "_resolve_units_value_token", _resolve_token)

    resolved = await resolver.resolve_value("PARAM_P4_59")
    assert resolved.kind == "direct"
    assert resolved.value == "Off"


@pytest.mark.asyncio
async def test_resolve_value_compose_miss_falls_through_to_direct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose returning None must fall through to the primary-register direct path."""
    store = ParamStore()
    store.upsert("P4.v59", 11)

    mapping = ParamMap(
        key="PARAM_P4_59",
        group="P4",
        paths={"value": [{"group": "P4", "number": 59, "use": "v"}]},
        component_type=None,
        units=None,
        limits=None,
        status_flags=[],
        status_conditions=None,
        command_rules=[],
        origin="inline:test",
        raw={"name": "parameters.PARAM_P4_59", "value": [{"group": "P4", "number": 59, "use": "v"}]},
    )
    resolver = _resolver(mapping, store)

    def _compose_none(_cls: type[Any], _store: ParamStore, _mapping: Any) -> None:
        return None

    monkeypatch.setattr(ParamResolver, "compose_mapping_register_value", classmethod(_compose_none))

    resolved = await resolver.resolve_value("PARAM_P4_59")
    assert resolved.kind == "direct"
    assert resolved.value == 11


@pytest.mark.asyncio
async def test_resolve_value_without_mapping_skips_compose_block() -> None:
    """Symbols with no ParamMap must skip the multi-word compose branch entirely."""
    store = ParamStore()
    store.upsert("P4.v59", 5)
    # Assets stub only knows PARAM_P4_59; ask for a different symbol so mapping is None.
    resolver = _resolver(_multi_word_mapping(), store)
    resolved = await resolver.resolve_value("PARAM_UNKNOWN")
    assert resolved.kind == "direct"
    assert resolved.value is None


@pytest.mark.asyncio
async def test_resolve_value_string_display_keeps_value_when_token_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If token resolution returns None, the transformed string display is kept as-is."""
    store = ParamStore()
    store.upsert("P4.v59", 1)
    store.upsert("P4.v60", 0)

    resolver = _resolver(_multi_word_mapping(convert=None), store)

    def _string_display(_self_or_cls: object, _raw_value: Any, _raw_expr: Any) -> str:
        return "literal-display"

    async def _resolve_token(_self: ParamResolver, _label: str | None) -> str | None:
        return None

    monkeypatch.setattr(ParamResolver, "_apply_numeric_transform", _string_display)
    monkeypatch.setattr(ParamResolver, "_resolve_units_value_token", _resolve_token)

    resolved = await resolver.resolve_value("PARAM_P4_59")
    assert resolved.kind == "direct"
    assert resolved.value == "literal-display"


@pytest.mark.asyncio
async def test_resolve_value_status_computed_rules_still_work_after_fix() -> None:
    """Regression guard: STATUS computed evaluation must still work alongside the fix."""
    store = ParamStore()
    raw = {
        "name": "app.one.devicePumpStatus",
        "any": [
            {
                "if": [{"expected": 1, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
                "then": {"value": "e.ON"},
            },
            {
                "elseif": [{"expected": 0, "operation": "equalTo", "value": [{"group": "P5", "number": 0, "use": "s"}]}],
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

    resolver = _resolver(mapping, store)
    await store.upsert_async("P5.s0", 1)
    resolved = await resolver.resolve_value("STATUS_P5_0")
    assert resolved.kind == "computed"
    assert resolved.value == "e.ON"

    await store.upsert_async("P5.s0", 0)
    resolved_off = await resolver.resolve_value("STATUS_P5_0")
    assert resolved_off.kind == "computed"
    assert resolved_off.value == "e.OFF"
